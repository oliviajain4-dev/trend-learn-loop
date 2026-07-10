"""Analyst 집필기 — CollectionResult → status="draft" Brief.

절차:
  1) 수집물 상위 N건에 코드가 sid(S1..Sn) 부여 → schema.Source 형식으로.
  2) 그 출처 목록을 프롬프트에 넣고 LLM 에 §3 섹션·판단을 JSON 으로 집필 요청.
  3) LLM JSON 을 파싱·정규화해 유효한 Brief(status="draft", 지표 0)로 조립.
결과의 사실성은 여기서 보장하지 않는다 — Verifier(결정론 L1 등)가 판정한다.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import date

from tll.collector.models import CollectionResult, to_source
from tll.schema import Brief, parse_brief
from tll.shared.llm import get_provider
from tll.shared.llm.base import LLMProvider

logger = logging.getLogger(__name__)

_SECTION_KEYS = (
    "skeleton",
    "background",
    "contrast_analogy",
    "why_needed",
    "outlook",
    "quickstart",
)
_LEVELS = ("high", "medium", "low")


class AnalystError(RuntimeError):
    """집필 실패(수집물 없음·LLM 응답 파싱 실패 등)."""


def _slug(topic: str) -> str:
    s = re.sub(r"[^0-9A-Za-z가-힣]+", "-", topic.strip().lower()).strip("-")
    return s or "topic"


def _render_sources(sources: list[dict]) -> str:
    lines = []
    for s in sources:
        head = f"[{s['sid']}] {s['title']} ({s['org']}, {s.get('date') or '발행일 미상'}) — {s['url']}"
        lines.append(head)
    return "\n".join(lines)


_SYSTEM = (
    "너는 IT/AI 기술 브리핑 작성자다. 오직 '주어진 출처'만 근거로 한국어로 집필한다. "
    "각 사실 문장 끝에 근거 출처를 [S1] 형식으로 단다(여러 개면 [S1][S2]). "
    "출처에 없는 사실·URL·수치를 지어내지 마라. 확실치 않은 주장은 sections 에 넣지 말고 "
    "unverified 에 사유와 함께 넣어라. 반드시 유효한 JSON 하나만 출력한다(마크다운/설명 금지)."
)


def _build_prompt(topic: str, sources: list[dict]) -> str:
    return (
        f"기술 주제: {topic}\n\n"
        f"사용 가능한 출처(이 sid 만 인용 가능):\n{_render_sources(sources)}\n\n"
        "아래 JSON 스키마로만 답하라. 모든 사실 문장에 [S#] 인용을 달 것:\n"
        "{\n"
        '  "one_liner": "한 줄 정체 [S#]",\n'
        '  "sections": {\n'
        '    "skeleton": "큰 뼈대(구조/틀) [S#]",\n'
        '    "background": "왜 나왔나(배경·계보) [S#]",\n'
        '    "contrast_analogy": "대조·유추: 뭐가 비슷/다른가 [S#]",\n'
        '    "why_needed": "왜 필요한가/어떤 문제를 푸나 [S#]",\n'
        '    "outlook": "전망: 채택신호·한계·리스크 균형 [S#]",\n'
        '    "quickstart": "바로 따라하기 개요 [S#]"\n'
        "  },\n"
        '  "judgment": {\n'
        '    "worth_learning": {"level": "high|medium|low", "note": "..."},\n'
        '    "maturity": {"level": "high|medium|low", "note": "..."},\n'
        '    "relevance": {"level": "high|medium|low", "note": "..."}\n'
        "  },\n"
        '  "unverified": [{"claim": "...", "reason": "...", "conflicting_sids": []}]\n'
        "}\n"
    )


def _extract_json(text: str) -> dict:
    t = text.strip()
    if t.startswith("```"):  # ```json ... ``` 펜스 제거
        t = re.sub(r"^```[a-zA-Z]*\n?", "", t)
        t = re.sub(r"\n?```$", "", t).strip()
    start, end = t.find("{"), t.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise AnalystError("LLM 응답에서 JSON 객체를 찾지 못함")
    try:
        return json.loads(t[start : end + 1])
    except json.JSONDecodeError as e:
        raise AnalystError(f"LLM JSON 파싱 실패: {e}") from e


def _norm_level(value) -> str:
    v = str(value or "").strip().lower()
    return v if v in _LEVELS else "medium"


def _norm_judgment_item(d) -> dict:
    d = d if isinstance(d, dict) else {}
    return {"level": _norm_level(d.get("level")), "note": str(d.get("note") or "").strip()}


def write_brief(
    topic: str,
    collection: CollectionResult,
    *,
    provider: LLMProvider | None = None,
    model: str | None = None,
    max_sources: int = 8,
    max_tokens: int = 4096,
) -> Brief:
    """수집물로 status="draft" 브리핑을 집필해 반환."""
    docs = collection.documents[:max_sources]
    if not docs:
        raise AnalystError(f"수집물이 비어 있어 집필 불가(topic={topic!r})")

    # 1) 코드가 sid 부여 (결정론)
    sources: list[dict] = []
    for i, d in enumerate(docs, 1):
        s = to_source(d)
        s["sid"] = f"S{i}"
        sources.append(s)
    valid_sids = {s["sid"] for s in sources}

    # 2) LLM 집필
    llm = provider or get_provider()
    resp = llm.generate(
        _build_prompt(topic, sources), system=_SYSTEM, max_tokens=max_tokens, model=model
    )
    if not resp.text.strip():
        raise AnalystError("LLM 이 빈 응답을 반환")
    parsed = _extract_json(resp.text)

    # 3) 정규화 → 유효 Brief 조립
    raw_sections = parsed.get("sections") if isinstance(parsed.get("sections"), dict) else {}
    sections = {}
    for k in _SECTION_KEYS:
        text = str(raw_sections.get(k) or "").strip()
        sections[k] = text or "(초안 생성 실패 — 미확인)"

    raw_j = parsed.get("judgment") if isinstance(parsed.get("judgment"), dict) else {}
    judgment = {
        "worth_learning": _norm_judgment_item(raw_j.get("worth_learning")),
        "maturity": _norm_judgment_item(raw_j.get("maturity")),
        "relevance": _norm_judgment_item(raw_j.get("relevance")),
    }

    unverified = []
    for u in parsed.get("unverified") or []:
        if not isinstance(u, dict):
            continue
        claim = str(u.get("claim") or "").strip()
        if not claim:
            continue
        sids = [s for s in (u.get("conflicting_sids") or []) if s in valid_sids]
        unverified.append(
            {"claim": claim, "reason": str(u.get("reason") or "").strip(), "conflicting_sids": sids}
        )

    one_liner = str(parsed.get("one_liner") or "").strip() or f"{topic} — (초안, 미확인)"

    brief_dict = {
        "schema_version": "1.0",
        "id": _slug(topic),
        "tech_name": topic,
        "first_seen": date.today().isoformat(),
        "status": "draft",  # 아직 미검증
        "one_liner": one_liner,
        "metrics": {  # 미측정 → Metrics 단계에서 채움
            "atomic_support_rate": 0.0,
            "citation_precision": 0.0,
            "citation_recall": 0.0,
            "ragas_faithfulness": 0.0,
            "source_count": len(sources),
        },
        "sections": sections,
        "media": {"youtube_global": [], "youtube_kr": []},
        "reactions": [],
        "judgment": judgment,
        "sources": sources,
        "unverified": unverified,
    }
    # 계약 위반이면 여기서 SchemaError → 초안이 계약을 지키는지 자동 보증
    return parse_brief(brief_dict, strict=True)
