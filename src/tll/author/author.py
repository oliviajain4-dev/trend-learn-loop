"""Author(집필) — 충분 판정된 본문으로 한국어 교과서(정체 브리핑)를 쓴다.

- 오직 원문(body_text)만 근거로 한국어 집필, 각 사실 문장에 [S1].
- **대조·유추** 강조(기존/유사 기술과 뭐가 같고 다른가). 원문 밖 비교는 (일반지식) 표시 → 이후 미확인.
- 원문(body_text)을 Source 에 보존 → Fact-Check(결정론 L1)가 그 문자열로 실제 대조.
결과의 사실성은 여기서 보장하지 않는다(status="draft"). 진위는 Fact-Check가 판정.
Memory 회상(contrast_hint)을 받으면 대조·유추 근거로 프롬프트에 주입한다.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Callable

from tll.author.models import SECTION_KEYS, Source, Textbook
from tll.scout.freshness import age_label
from tll.shared.llm import get_provider
from tll.shared.llm.base import LLMProvider
from tll.tracker.models import TrackedDoc

logger = logging.getLogger(__name__)
_LEVELS = ("high", "medium", "low")


class AuthorError(RuntimeError):
    """집필 실패(본문 없음·LLM 응답 파싱 실패 등)."""


_SYSTEM = (
    "너는 IT/AI 기술을 설명하는 한국어 교과서 작성자다. 오직 '주어진 원문'만 근거로 한국어로 집필한다. "
    "각 사실 문장 끝에 [S1] 을 단다. 원문에 없는 사실·수치·URL을 지어내지 마라. "
    "특히 '대조·유추'(기존/유사 기술과 뭐가 같고 다른지)를 충실히 쓰되, 원문 밖 비교는 문장 끝에 (일반지식)"
    "이라고 표시한다. 확실치 않은 주장은 sections 대신 unverified 에 넣는다. "
    "반드시 유효한 JSON 하나만 출력한다(마크다운/설명 금지)."
)


def _build_prompt(topic: str, src: Source, contrast_hint: str = "") -> str:
    hint = (
        f"참고(이미 아는 관련 개념 — 대조·유추에 활용, 원문 밖 비교는 (일반지식) 표시): {contrast_hint}\n\n"
        if contrast_hint
        else ""
    )
    return (
        f"기술 주제: {topic}\n\n"
        f"{hint}"
        f"[S1] {src.title} ({src.nature}, {src.grade}급) — {src.url}\n"
        f'원문 본문:\n"""\n{src.body_text}\n"""\n\n'
        "위 원문만 근거로 한국어 교과서를 아래 JSON 으로 써라. 모든 사실 문장 끝에 [S1] 을 달 것:\n"
        "{\n"
        '  "one_liner": "한 줄 정체 [S1]",\n'
        '  "sections": {\n'
        '    "skeleton": "큰 뼈대(구조/틀) [S1]",\n'
        '    "background": "왜 나왔나(배경·계보) [S1]",\n'
        '    "contrast_analogy": "대조·유추: 기존/유사 기술과 뭐가 같고 다른가. 원문 근거는 [S1], 일반지식 비교는 (일반지식)",\n'
        '    "why_needed": "왜 필요한가/어떤 문제를 푸나 [S1]",\n'
        '    "outlook": "전망: 채택신호·한계·리스크 [S1]",\n'
        '    "quickstart": "바로 따라하기 개요 [S1]"\n'
        "  },\n"
        '  "judgment": {"worth_learning":{"level":"high|medium|low","note":"..."},'
        '"maturity":{"level":"high|medium|low","note":"..."},'
        '"relevance":{"level":"high|medium|low","note":"..."}},\n'
        '  "unverified": [{"claim":"근거 약한 주장","reason":"왜 미확인","conflicting_sids":[]}]\n'
        "}\n"
    )


def _extract_json_object(text: str) -> dict:
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z]*\n?", "", t)
        t = re.sub(r"\n?```$", "", t).strip()
    start, end = t.find("{"), t.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise AuthorError("LLM 응답에서 JSON 객체를 찾지 못함")
    try:
        return json.loads(t[start : end + 1])
    except json.JSONDecodeError as e:
        raise AuthorError(f"LLM JSON 파싱 실패: {e}") from e


def _norm_level(v) -> str:
    v = str(v or "").strip().lower()
    return v if v in _LEVELS else "medium"


def _norm_item(d) -> dict:
    d = d if isinstance(d, dict) else {}
    return {"level": _norm_level(d.get("level")), "note": str(d.get("note") or "").strip()}


def _norm_judgment(j) -> dict:
    j = j if isinstance(j, dict) else {}
    return {
        "worth_learning": _norm_item(j.get("worth_learning")),
        "maturity": _norm_item(j.get("maturity")),
        "relevance": _norm_item(j.get("relevance")),
    }


def _norm_unverified(items, valid: set[str]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for x in items or []:
        if not isinstance(x, dict):
            continue
        claim = str(x.get("claim") or "").strip()
        if not claim:
            continue
        sids = [s for s in (x.get("conflicting_sids") or []) if s in valid]
        out.append(
            {"claim": claim, "reason": str(x.get("reason") or "").strip(), "conflicting_sids": sids}
        )
    return out


def _make_default_call(
    provider: LLMProvider | None, model: str | None, max_tokens: int
) -> Callable[[str, str], str]:
    def _call(prompt: str, system: str) -> str:
        llm = provider or get_provider()
        return llm.generate(prompt, system=system, max_tokens=max_tokens, model=model).text

    return _call


def write_textbook(
    doc: TrackedDoc,
    *,
    provider: LLMProvider | None = None,
    model: str | None = None,
    max_tokens: int = 4096,
    body_chars: int = 6000,
    contrast_hint: str = "",
    llm_call: Callable[[str, str], str] | None = None,
) -> Textbook:
    """충분 판정된 TrackedDoc 로 status="draft" 한국어 교과서를 집필."""
    body = (doc.body_text or "").strip()
    if not body:
        raise AuthorError(f"본문이 비어 집필 불가(topic={doc.topic_title!r})")

    src = Source(
        sid="S1",
        title=doc.title or doc.topic_title,
        url=doc.url,
        grade=doc.grade,
        nature=doc.nature,
        body_text=body[:body_chars],
        published_at=doc.published_at,
        collected_at=doc.collected_at,
    )

    call = llm_call or _make_default_call(provider, model, max_tokens)
    raw = call(_build_prompt(doc.topic_title, src, contrast_hint), _SYSTEM)
    if not raw.strip():
        raise AuthorError("LLM 이 빈 응답을 반환")
    parsed = _extract_json_object(raw)

    raw_sec = parsed.get("sections") if isinstance(parsed.get("sections"), dict) else {}
    sections = {k: (str(raw_sec.get(k) or "").strip() or "(초안 생성 실패 — 미확인)") for k in SECTION_KEYS}
    one_liner = str(parsed.get("one_liner") or "").strip() or f"{doc.topic_title} — (초안, 미확인)"

    return Textbook(
        topic=doc.topic_title,
        one_liner=one_liner,
        sections=sections,
        judgment=_norm_judgment(parsed.get("judgment")),
        sources=[src],
        unverified=_norm_unverified(parsed.get("unverified"), {"S1"}),
        status="draft",
        age_label=age_label(doc.published_at),
        collected_at=doc.collected_at,
    )


def author_all(docs: list[TrackedDoc], **kw) -> tuple[list[Textbook], list[dict]]:
    """여러 문서를 집필. 한 건 실패가 전체를 죽이지 않게 개별 격리."""
    books: list[Textbook] = []
    errors: list[dict] = []
    for d in docs:
        try:
            books.append(write_textbook(d, **kw))
        except Exception as e:
            logger.warning("Author 집필 실패(%s): %s", d.topic_title, e)
            errors.append({"topic": d.topic_title, "error": str(e)})
    return books, errors


def _run_cli() -> None:
    from tll.reader.reader import read
    from tll.scout.scout import scout
    from tll.tracker.tracker import track
    from tll.triage.triage import triage

    res = scout()
    tr = triage(res.candidates, top_n=5)
    if tr.summary.get("mode") == "error":
        print("[Triage] 실패:", tr.summary.get("error"))
        return
    tk = track(tr.selected)
    rd = read(tk.docs)
    print(f"[Scout to Read] 충분 {rd.summary['sufficient']}건 → 집필\n")
    if not rd.ready:
        print("집필할 충분한 본문이 없음(전부 '더 찾자'). 잠시 후 다시.")
        return
    books, errors = author_all(rd.ready[:2])
    for tb in books:
        print("=" * 64)
        print(f"# {tb.topic} — 정체 브리핑  ({tb.age_label}) · status={tb.status}")
        print(f"한 줄: {tb.one_liner}")
        for k in SECTION_KEYS:
            print(f"\n[{k}]\n{tb.sections[k]}")
        s = tb.sources[0]
        print(f"\n출처 [S1] {s.nature}·{s.grade}급 · {s.url} · 원문 {len(s.body_text)}자")
        if tb.unverified:
            print("⚠️ 미확인:", [u["claim"] for u in tb.unverified])
        print()
    if errors:
        print("집필 실패:", errors)


if __name__ == "__main__":
    _run_cli()
