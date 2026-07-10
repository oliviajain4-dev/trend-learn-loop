"""Fact-Check 데이터 계약."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class SentenceVerdict:
    """문장 1건에 대한 결정론 판정."""

    section: str  # one_liner 또는 섹션 키
    text: str
    cited_sids: list[str]
    verdict: str  # ok | phantom_citation | quote_mismatch | unsupported_number | uncited | general_knowledge
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class FactCheckReport:
    verdicts: list[SentenceVerdict]
    metrics: dict[str, Any] = field(default_factory=dict)  # support_rate·factual·각 카운트
    status: str = "draft"  # verified(위반 0) | draft

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdicts": [v.to_dict() for v in self.verdicts],
            "metrics": self.metrics,
            "status": self.status,
        }
