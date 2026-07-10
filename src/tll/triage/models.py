"""Triage 데이터 계약.

- TriageDecision: 후보 1건에 대한 LLM 판단(교과서 감이냐 + 분류·가치·이유).
- TriageResult: 전체 판단 + 선별된(채택) 후보 + 관찰용 summary(ReAct observation).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from tll.scout.models import TrendCandidate


@dataclass
class TriageDecision:
    """후보 1건에 대한 판단. keep=교과서 감 여부, worth=교과서 가치(0~100)."""

    cid: str
    title: str
    source: str
    keep: bool
    category: str  # 짧은 분류 (예: AI모델/프레임워크/DB/언어/도구/뉴스/기타)
    worth: int  # 0~100 (LLM이 매긴 교과서 가치)
    reason: str  # 한국어 한 문장 근거

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TriageResult:
    """한 번의 선별 결과.

    - decisions: 판단한 모든 후보(keep/drop 포함)
    - selected: 교과서 감으로 채택된 상위 N건(다음 단계 Tracker 로 넘어감)
    - summary: ReAct 관찰용 {judged, kept, selected, categories, mode, ...}
    """

    decisions: list[TriageDecision]
    selected: list[TrendCandidate]
    summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "decisions": [d.to_dict() for d in self.decisions],
            "selected": [c.to_dict() for c in self.selected],
            "summary": self.summary,
        }
