"""개념(Concept) 모델 — v4 concept-centric 단위. '글'이 아니라 '기술 개념' 하나가 단위다."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Concept:
    cid: str                                          # 안정 id (canonical 슬러그)
    canonical: str                                    # 표시 이름 (예: "LangChain")
    aliases: list[str] = field(default_factory=list)  # 별칭/이표기 (예: ["LC"])
    category: str = ""                                # 기능 분류 (선택)
    first_seen: str = ""                              # 우리가 처음 본 날
    created_at: str = ""                              # 원본 생성일(GitHub repo created_at) = 나이 재료
    status: str = "confirmed"                         # confirmed | provisional(신규·저신뢰)

    def to_dict(self) -> dict:
        return {
            "cid": self.cid, "canonical": self.canonical, "aliases": list(self.aliases),
            "category": self.category, "first_seen": self.first_seen,
            "created_at": self.created_at, "status": self.status,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Concept":
        return cls(
            cid=str(d.get("cid", "")), canonical=str(d.get("canonical", "")),
            aliases=list(d.get("aliases") or []), category=str(d.get("category", "")),
            first_seen=str(d.get("first_seen", "")), created_at=str(d.get("created_at", "")),
            status=str(d.get("status", "confirmed")),
        )
