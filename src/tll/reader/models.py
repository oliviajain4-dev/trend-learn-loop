"""Reader 데이터 계약.

- ReadVerdict: 본문 1건 독해 판단(충분/부족 + 이해 요지 + 부족한 것 + 다음 행동).
- ReadResult: 전체 판단 + 집필로 넘길 ready + 더 찾을 needs_more + 관찰용 summary.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from tll.tracker.models import TrackedDoc


@dataclass
class ReadVerdict:
    """본문 1건에 대한 독해 판단."""

    cid: str
    topic_title: str
    grade: int
    nature: str
    sufficient: bool  # 이 본문으로 교과서를 쓸 수 있나
    next_action: str  # "proceed" | "collect_more" (모델이 고른 다음 행동 = ReAct)
    understanding: str  # 본문 근거 요지(충분할 때 의미). 지어내지 않음
    missing: str  # 부족하면 뭐가 없는지
    reason: str  # 판단 이유
    mode: str = "llm"  # llm | precheck(결정론) | error

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ReadResult:
    verdicts: list[ReadVerdict]
    ready: list[TrackedDoc]  # sufficient 문서(집필 대상)
    needs_more: list[ReadVerdict]  # 부족 → 재수집 대상("더 찾자")
    summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdicts": [v.to_dict() for v in self.verdicts],
            "ready": [d.to_dict() for d in self.ready],
            "needs_more": [v.to_dict() for v in self.needs_more],
            "summary": self.summary,
        }
