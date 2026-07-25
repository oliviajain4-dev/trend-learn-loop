"""Memory 데이터 계약."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ConceptCard:
    """KB에 쌓이는 개념 1건(의미기억). 다음 교과서의 대조·유추 근거."""

    key: str  # slug(topic) — 안정 키(중복/갱신)
    topic: str
    one_liner: str
    category: str = ""
    key_terms: list[str] = field(default_factory=list)  # 회상용 용어(영문 tech 토큰)
    grade: int = 3
    nature: str = ""
    source_url: str = ""
    first_seen: str = ""
    updated_at: str = ""
    times_seen: int = 1

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "ConceptCard":
        return cls(
            key=d["key"],
            topic=d.get("topic", ""),
            one_liner=d.get("one_liner", ""),
            category=d.get("category", ""),
            key_terms=list(d.get("key_terms") or []),
            grade=int(d.get("grade", 3)),
            nature=d.get("nature", ""),
            source_url=d.get("source_url", ""),
            first_seen=d.get("first_seen", ""),
            updated_at=d.get("updated_at", ""),
            times_seen=int(d.get("times_seen", 1)),
        )


@dataclass
class Lesson:
    """실패·교훈 1건(에피소드기억, Reflexion)."""

    topic: str
    kind: str  # insufficient | author_fail | low_faithfulness | ...
    note: str
    ts: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Lesson":
        return cls(
            topic=d.get("topic", ""),
            kind=d.get("kind", ""),
            note=d.get("note", ""),
            ts=d.get("ts", ""),
        )
