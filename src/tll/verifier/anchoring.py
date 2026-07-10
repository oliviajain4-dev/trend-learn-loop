"""L1 인용 앵커링 — 결정론 검증(LLM 판단 0). 같은 입력 → 같은 판정.

동작:
  1) one_liner + 본문 6섹션을 문장으로 분할.
  2) 각 문장의 [S#] 인용 추출.
  3) 판정:
     - phantom_citation: 실존하지 않는 sid 인용 → 위반(폐기 대상).
     - quote_mismatch : 문장 속 따옴표 인용이 '인용된 출처 text' 에 없음(출처 text 존재 시) → 위반.
     - uncited        : 사실성으로 보이는 문장에 [S#] 이 없음 → 근거 약함(경고).
     - ok             : 위 어디에도 안 걸림.
  4) apply_verification: 위반(phantom/quote) 문장을 섹션에서 제거하고 unverified 로 이동(CoVe 삭제/수정의 결정론판).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from tll.schema import SECTION_ORDER, Brief, Source, parse_brief

# 문장 분할: 종결부호(.,!,?,。) 뒤 공백 또는 줄바꿈.
_SENT_SPLIT = re.compile(r"(?<=[.!?。])\s+|\n+")
_CITE = re.compile(r"\[(S\d+)\]")
# 따옴표 인용(4자 이상): "..." 또는 「...」 또는 '...'
_QUOTE = re.compile(r"[\"“”「](.{4,}?)[\"“”」]")
# 사실성 문장 최소 길이(휴리스틱): 이보다 짧으면 미인용이어도 경고 안 함.
_MIN_FACTUAL_LEN = 20

# 섹션 필드명 → 사람이 읽을 라벨
_SECTION_LABEL = {"one_liner": "0. 한 줄 정체", **{k: f"{n}. {label}" for k, n, label in SECTION_ORDER}}


@dataclass
class SentenceCheck:
    section: str  # "one_liner" 또는 섹션 키
    text: str
    cited_sids: list[str]
    status: str  # ok | phantom_citation | quote_mismatch | uncited
    detail: str = ""

    @property
    def is_violation(self) -> bool:
        return self.status in ("phantom_citation", "quote_mismatch")


@dataclass
class VerificationResult:
    checks: list[SentenceCheck] = field(default_factory=list)

    @property
    def violations(self) -> list[SentenceCheck]:
        return [c for c in self.checks if c.is_violation]

    @property
    def uncited(self) -> list[SentenceCheck]:
        return [c for c in self.checks if c.status == "uncited"]

    @property
    def passed(self) -> bool:
        return not self.violations

    @property
    def summary(self) -> dict[str, Any]:
        by_status: dict[str, int] = {}
        for c in self.checks:
            by_status[c.status] = by_status.get(c.status, 0) + 1
        return {
            "total_sentences": len(self.checks),
            "by_status": by_status,
            "violations": len(self.violations),
            "uncited": len(self.uncited),
            "passed": self.passed,
        }


def _sentences(text: str) -> list[str]:
    return [p.strip() for p in _SENT_SPLIT.split(text or "") if p.strip()]


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def _iter_sections(brief: Brief):
    yield "one_liner", brief.one_liner
    for key, _n, _label in SECTION_ORDER:
        yield key, getattr(brief.sections, key)


def _check_sentence(
    section: str, sent: str, valid_sids: set[str], source_text: dict[str, str]
) -> SentenceCheck:
    cited = _CITE.findall(sent)

    # 1) 유령 인용 — 결정론 L1 핵심
    phantom = [sid for sid in cited if sid not in valid_sids]
    if phantom:
        return SentenceCheck(
            section, sent, cited, "phantom_citation", f"실존하지 않는 출처 인용: {phantom}"
        )

    # 2) 인용문 앵커링 — 따옴표 인용이 인용된 출처 text 에 실제 있는지(text 존재 시)
    for q in _QUOTE.findall(sent):
        qn = _norm(q)
        # 인용된 출처들 중 text 가 있는 것만 대상
        checkable = [sid for sid in cited if source_text.get(sid)]
        if checkable and not any(qn in _norm(source_text[sid]) for sid in checkable):
            return SentenceCheck(
                section, sent, cited, "quote_mismatch", f'인용문 "{q[:30]}…" 이 출처 원문에 없음'
            )

    # 3) 미인용 사실문(휴리스틱 경고)
    if not cited and len(sent) >= _MIN_FACTUAL_LEN:
        return SentenceCheck(section, sent, cited, "uncited", "사실성 문장인데 [S#] 인용 없음")

    return SentenceCheck(section, sent, cited, "ok")


def verify_brief(brief: Brief) -> VerificationResult:
    """L1 결정론 검증. LLM 을 쓰지 않는다(같은 입력 → 같은 판정)."""
    valid_sids = {s.sid for s in brief.sources}
    source_text: dict[str, str] = {}
    for s in brief.sources:
        t = _source_text(s)
        if t:
            source_text[s.sid] = t

    checks: list[SentenceCheck] = []
    for section, text in _iter_sections(brief):
        for sent in _sentences(text):
            checks.append(_check_sentence(section, sent, valid_sids, source_text))
    return VerificationResult(checks=checks)


def _source_text(source: Source) -> str:
    """Source 에서 앵커링에 쓸 원문 텍스트. 지금 스키마엔 별도 text 필드가 없어
    title 을 근사 원문으로 쓴다(제목은 원본 유래라 앵커로 유효)."""
    return source.title or ""


def apply_verification(brief: Brief, result: VerificationResult) -> Brief:
    """위반(phantom/quote) 문장을 섹션에서 제거하고 unverified 로 이동한 새 Brief 반환.

    CoVe '불일치 문장 삭제/수정'의 결정론 버전. 계약(parse_brief)으로 결과 무결성 보증.
    """
    bad_by_section: dict[str, list[SentenceCheck]] = {}
    for c in result.violations:
        bad_by_section.setdefault(c.section, []).append(c)

    data = brief.to_dict()

    # one_liner 위반이면 표식만(섹션과 달리 비우면 계약 위반이라 문구로 대체)
    for c in bad_by_section.get("one_liner", []):
        data["one_liner"] = f"(검증에서 근거 미달로 보류) {brief.tech_name}"
        data.setdefault("unverified", []).append(
            {"claim": c.text, "reason": f"L1: {c.detail}", "conflicting_sids": []}
        )

    for key, _n, _label in SECTION_ORDER:
        bad = bad_by_section.get(key, [])
        if not bad:
            continue
        bad_texts = {b.text for b in bad}
        kept = [s for s in _sentences(data["sections"][key]) if s not in bad_texts]
        data["sections"][key] = " ".join(kept) or "(검증에서 근거 미달 문장 제거됨 — 미확인)"
        for b in bad:
            data.setdefault("unverified", []).append(
                {"claim": b.text, "reason": f"L1: {b.detail}", "conflicting_sids": []}
            )

    return parse_brief(data, strict=True)
