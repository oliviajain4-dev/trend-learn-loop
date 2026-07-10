"""Author 데이터 계약.

- Source: 교과서가 근거로 삼은 출처 1건. **원문 body_text 를 보존**(Fact-Check 대조·'원문 보기'용).
- Textbook: 한국어 교과서 초안(정체 브리핑). status="draft" → Fact-Check가 검증.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

SECTION_KEYS = (
    "skeleton",  # 큰 뼈대(구조/틀)
    "background",  # 왜 나왔나(배경·계보)
    "contrast_analogy",  # 대조·유추(뭐가 비슷/다른가) — 핵심
    "why_needed",  # 왜 필요한가/어떤 문제를 푸나
    "outlook",  # 전망(채택신호·한계·리스크)
    "quickstart",  # 바로 따라하기 개요
)


@dataclass
class Source:
    sid: str  # "S1"
    title: str
    url: str
    grade: int  # 1~3 (원천 근접도)
    nature: str  # 제작사/논문/레포/뉴스/블로그
    body_text: str  # 원문 보존 (Fact-Check 문자열 대조 + '원문 보기')
    published_at: str | None = None
    collected_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Textbook:
    topic: str
    one_liner: str
    sections: dict[str, str]  # SECTION_KEYS
    judgment: dict[str, Any]
    sources: list[Source]
    unverified: list[dict[str, Any]] = field(default_factory=list)
    status: str = "draft"  # draft → (Fact-Check) → verified
    age_label: str = ""  # 신선도("3시간 전")
    collected_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["sources"] = [s.to_dict() for s in self.sources]
        return d
