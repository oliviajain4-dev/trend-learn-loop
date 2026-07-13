"""신호(Signal) 모델 — 개념마다 시간에 걸쳐 쌓는 관측치 한 점."""

from __future__ import annotations

from dataclasses import dataclass

# 신호 종류 → 계열(family). 버즈형=빨리 식는 '주목', 축적형=천천히 쌓이는 '채택'.
KIND_FAMILY = {
    # 주목(버즈형)
    "mention": "buzz", "hn_points": "buzz", "hn_comments": "buzz",
    "reddit_score": "buzz", "news_mention": "buzz", "youtube_views": "buzz",
    # 채택(축적형)
    "stars": "stock", "forks": "stock", "issues": "stock", "prs": "stock",
    "dependents": "stock", "downloads": "stock", "citations": "stock",
    "arxiv_total": "stock", "arxiv_recent": "stock",  # 연구 채택(논문)
}


def family_of(kind: str) -> str:
    """알려진 종류면 매핑, 모르면 'buzz'(주목)로 보수적 처리."""
    return KIND_FAMILY.get(kind, "buzz")


@dataclass
class Signal:
    cid: str        # 개념 id
    date: str       # ISO 날짜 (YYYY-MM-DD)
    source: str     # 소스 (hn, github, arxiv, reddit, youtube ...)
    kind: str       # 신호 종류 (stars, hn_points ...)
    value: float    # 관측값
    family: str     # buzz | stock

    def to_dict(self) -> dict:
        return {"cid": self.cid, "date": self.date, "source": self.source,
                "kind": self.kind, "value": self.value, "family": self.family}

    @classmethod
    def from_dict(cls, d: dict) -> "Signal":
        kind = str(d.get("kind", ""))
        return cls(
            cid=str(d.get("cid", "")), date=str(d.get("date", "")),
            source=str(d.get("source", "")), kind=kind, value=float(d.get("value", 0.0) or 0.0),
            family=str(d.get("family") or family_of(kind)),
        )
