"""Loop 데이터 계약."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class CycleResult:
    published: list[dict]  # {topic, support_rate, status}
    lessons: list[dict]  # {topic, reason} — "더 찾자"로 넘긴 것
    decisions: list[dict]  # {topic, next_action, mode} — 후보별 ReAct 결정
    summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
