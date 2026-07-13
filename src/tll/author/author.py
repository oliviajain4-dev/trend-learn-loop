"""Author(집필) — 충분 판정된 본문으로 한국어 교과서를 '한 편의 글처럼' 쓴다.

- 오직 원문(body_text)만 근거로 쉬운 한국어로 집필(짧은 문장·술술), 각 사실 문장에 [S1].
- **가장 중요: 기존/유사 기술과의 비교**(닮은 점·다른 점·언제 뭘 쓰나·비유)를 가장 두껍고 구체적으로.
  라벨 채우기("큰 뼈대"…)가 아니라 자연스러운 설명 흐름으로.
- 원문(body_text)을 Source 에 보존 → Fact-Check(결정론 L1)가 그 문자열로 실제 대조.
결과의 사실성은 여기서 보장하지 않는다(status="draft"). 진위는 Fact-Check가 판정.
Memory 회상(contrast_hint)을 받으면 비교 근거로 프롬프트에 주입한다.
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
    "너는 IT/AI 기술을 처음 보는 사람에게 풀어 설명하는 한국어 교과서 작성자다. "
    "오직 '주어진 원문'만 근거로 쓴다. 라벨을 채우듯 쓰지 말고, 한 편의 자연스러운 글처럼 술술 풀어라. "
    "문장은 짧게, 한 문장에 한 생각. 딱딱한 번역투·긴 만연체 금지. "
    "가장 중요한 건 '기존/유사 기술과의 비교'다: 무엇과 닮았는지, 정확히 무엇이 다른지, 그 차이가 왜 생기는지, "
    "언제 이걸 쓰고 언제 기존 걸 쓰는지, 초보가 이해할 비유 하나를 '구체적으로' 써라. 이 부분을 가장 두껍게. "
    "각 사실 문장 끝에 [S1] 을 단다(원문 근거 표시). 원문에 없는 사실·수치·URL 을 지어내지 마라. "
    "원문 밖 비교·상식은 문장 끝에 (일반지식) 이라 표시한다. 확실치 않은 주장은 sections 대신 unverified 에 넣는다. "
    "반드시 유효한 JSON 하나만 출력한다(마크다운/설명 금지)."
)


def _build_prompt(topic: str, src: Source, contrast_hint: str = "") -> str:
    hint = (
        f"참고(이미 아는 관련 개념 — 비교에 활용, 원문 밖 비교는 (일반지식) 표시): {contrast_hint}\n\n"
        if contrast_hint
        else ""
    )
    return (
        f"기술 주제: {topic}\n\n"
        f"{hint}"
        f"[S1] {src.title} ({src.nature}, {src.grade}급) — {src.url}\n"
        f'원문 본문:\n"""\n{src.body_text}\n"""\n\n'
        "위 원문만 근거로, 쉬운 한국어로 '한 편의 글처럼' 써라(짧은 문장·술술). 모든 사실 문장 끝에 [S1].\n"
        "특히 compare 는 다른 섹션보다 2배 이상 길고 구체적으로 — 막연히 '더 좋다'가 아니라 '무엇이 어떻게 다른지'를 원문 근거로.\n"
        "아래 JSON 하나만 출력:\n"
        "{\n"
        '  "one_liner": "이게 뭔지 한 줄 [S1]",\n'
        '  "sections": {\n'
        '    "gist": "한눈에: 이게 뭐고 어떻게 생겼는지 자연스럽게 2~4문장 [S1]",\n'
        '    "compare": "기존/유사 기술과 비교(★ 가장 길게·구체적으로): 무엇과 닮았나 / 정확히 무엇이 다른가 / '
        '그 차이가 왜 생기나 / 언제 이걸 쓰고 언제 기존 걸 쓰나 / 초보용 비유 하나. 원문 근거는 [S1], 원문 밖은 (일반지식)",\n'
        '    "why": "왜 필요한가 · 어떤 문제를 푸나 [S1]",\n'
        '    "watch": "전망·주의: 채택 신호·한계·리스크 [S1]",\n'
        '    "try": "바로 써보기: 어떻게 시작하나 간단히 [S1]"\n'
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
        except Exception as e:  # noqa: BLE001
            logger.warning("Author 집필 실패(%s): %s", d.topic_title, e)
            errors.append({"topic": d.topic_title, "error": str(e)})
    return books, errors



_MANUAL_SYSTEM = (
    "너는 IT/AI 도구·개념을 처음 보는 사람에게 짧게 설명하는 한국어 작성자다. "
    "오직 '주어진 원문(README/초록)'만 근거로, 딱딱한 번역투 없이 3~5문장으로 쓴다. "
    "가장 중요한 건 '뭐랑 비슷하고 뭐가 다른지'(유사·대조)를 한 줄이라도 넣는 것. "
    "각 사실 문장 끝에 [S1]. 원문에 없는 걸 지어내지 마라. 유효한 JSON 하나만 출력."
)


def _manual_prompt(name: str, src: Source) -> str:
    return (
        f"대상: {name}\n"
        f"[S1] {src.title} ({src.nature}, {src.grade}급) — {src.url}\n"
        f'원문:\n"""\n{src.body_text}\n"""\n\n'
        "위 원문만 근거로 짧은 '설명서'를 써라. 아래 JSON 하나만:\n"
        "{\n"
        '  "one_liner": "이게 뭔지 한 줄 [S1]",\n'
        '  "gist": "한눈에: 무엇이고 어떻게 생겼는지 2~3문장 [S1]",\n'
        '  "compare": "무엇과 비슷하고 정확히 무엇이 다른지 1~2문장 [S1] (원문 밖은 (일반지식))"\n'
        "}\n"
    )


def write_manual(
    name: str,
    body_text: str,
    *,
    url: str = "",
    nature: str = "저장소",
    grade: str = "2",
    llm_call: Callable[[str, str], str],
) -> Textbook:
    """README/초록 같은 짧은 원문으로 가벼운 '설명서'(depth 표시는 저장 시)를 집필. 발견형 개념 전부가 최소 설명을 갖게 한다."""
    body = (body_text or "").strip()
    if not body:
        raise AuthorError(f"설명 원문이 비어 집필 불가(name={name!r})")
    src = Source(sid="S1", title=name, url=url, grade=grade, nature=nature, body_text=body[:2500],
                 published_at="", collected_at="")
    raw = llm_call(_manual_prompt(name, src), _MANUAL_SYSTEM)
    if not raw.strip():
        raise AuthorError("LLM 이 빈 응답을 반환")
    parsed = _extract_json_object(raw)
    gist = str(parsed.get("gist") or "").strip()
    compare = str(parsed.get("compare") or "").strip()
    sections = {k: "" for k in SECTION_KEYS}
    sections["gist"] = gist or "(설명 생성 실패 — 미확인)"
    sections["compare"] = compare
    one_liner = str(parsed.get("one_liner") or "").strip() or f"{name} — (설명서 초안)"
    return Textbook(
        topic=name, one_liner=one_liner, sections=sections,
        judgment=_norm_judgment(None), sources=[src], unverified=[],
        status="draft", age_label="", collected_at="",
    )


if __name__ == "__main__":
    print("author 모듈 — write_textbook(doc) 로 사용")