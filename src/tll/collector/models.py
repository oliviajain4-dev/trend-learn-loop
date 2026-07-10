"""수집 결과의 데이터 계약 (Collector 전용).

- CollectedDoc: 소스에서 가져온 원자료 1건. 링크·날짜·수치는 원본에서만 채운다.
- CollectionResult: 한 topic 수집의 결과 + 관찰용 summary(ReAct 호환).
- to_source(): CollectedDoc → schema.Source(provenance) 형식 dict 로 자연 변환.

주의: 이건 '최종 브리핑'이 아니라 그 재료(원자료)다. 최종 브리핑의 출처(schema.Source)로
승격될 때 sid 가 부여된다(여기선 sid 를 만들지 않는다).
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from typing import Any

# 출처 등급 휴리스틱에 쓰는 도메인 힌트 (대략적 — provider 가 필요시 재정의 가능)
_GRADE1_SUFFIXES = ("arxiv.org",)  # 1차 논문/프리프린트
_GRADE2_HINTS = (
    "openai.com",
    "anthropic.com",
    "deepmind",
    "google",
    "microsoft",
    "meta.com",
    "github.com",
    "nature.com",
    "nytimes.com",
    "bbc.",
    "arstechnica.com",
    "theverge.com",
    ".gov",
    ".edu",
)


def compute_content_hash(url: str, title: str) -> str:
    """url+title 기반 안정 해시(중복 제거용). 같은 입력 → 같은 값(결정론)."""
    key = f"{(url or '').strip().lower()}|{(title or '').strip().lower()}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


def grade_from_domain(domain: str) -> int:
    """도메인으로 대략적 신뢰 등급 추정. 1=1차/공식, 2=공식뉴스/기관, 3=블로그/여론.

    휴리스틱(불완전)이며, 확실치 않으면 보수적으로 3(약함)을 준다.
    """
    d = (domain or "").lower()
    if any(d.endswith(sfx) or f".{sfx}" in d for sfx in _GRADE1_SUFFIXES):
        return 1
    if any(h in d for h in _GRADE2_HINTS):
        return 2
    return 3


@dataclass
class CollectedDoc:
    """소스에서 가져온 원자료 1건. 모든 값은 원본 유래 (코드가 지어내지 않는다)."""

    source_type: str  # "hackernews" | "geeknews" | ...
    title: str
    org: str  # 발행처/기관 (도메인 또는 소스명)
    url: str
    collected_at: str  # ISO8601 (수집시각)
    grade: int  # 1~3
    text: str = ""  # 원문/요약 발췌 (없으면 빈 문자열)
    published_at: str | None = None  # 발행일 (원본이 주면 채움)
    content_hash: str = ""  # 비우면 __post_init__ 이 url+title 로 채움

    def __post_init__(self) -> None:
        if not self.content_hash:
            self.content_hash = compute_content_hash(self.url, self.title)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CollectionResult:
    """한 topic 수집 결과 + 관찰용 summary.

    summary 는 나중에 ReAct 루프의 '관찰(observation)'로 쓰인다:
      {topic, per_source, total, deduped, collected_at} 등.
    """

    topic: str
    documents: list[CollectedDoc]
    summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "topic": self.topic,
            "documents": [d.to_dict() for d in self.documents],
            "summary": self.summary,
        }


def to_source(doc: CollectedDoc) -> dict[str, Any]:
    """CollectedDoc → schema.Source 형식 dict.

    필드 대응: title/org/date(=published_at)/grade/url/collected_at.
    sid 는 여기서 만들지 않는다 — 브리핑에 편입될 때 부여한다.
    """
    return {
        "title": doc.title,
        "org": doc.org,
        "date": doc.published_at or "",
        "grade": doc.grade,
        "url": doc.url,
        "collected_at": doc.collected_at,
    }
