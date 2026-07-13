"""Author 데이터 계약.

- Source: 교과서가 근거로 삼은 출처 1건. **원문 body_text 를 보존**(Fact-Check 대조·'원문 보기'용).
- Textbook: 한국어 교과서 초안(정체 브리핑). status="draft" → Fact-Check가 검증.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

SECTION_KEYS = (
    "gist",     # 한눈에 — 뭐고 어떻게 생겼나 (자연스럽게 풀어)
    "compare",  # 기존/유사 기술과 비교 ★ 가장 두껍게 (같은 점·다른 점·언제 뭘·비유)
    "why",      # 왜 필요한가 / 어떤 문제를 푸나
    "watch",    # 전망·주의 (채택신호·한계·리스크)
    "try",      # 바로 써보기
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
