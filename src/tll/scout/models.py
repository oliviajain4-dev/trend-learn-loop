"""Scout 데이터 계약.

- TrendCandidate: 실시간 소스에서 발견한 트렌드 후보 1건. 링크·수치·발행일은 원본만.
- ScoutResult: 한 번의 정찰 결과 + 관찰용 summary(ReAct 루프의 observation).

주의: 이건 '교과서'도 '수집 원자료'도 아니다. **무엇을 파고들지 후보 목록**이다.
등급/신선도/안정 id 만 붙이고, 가치 판단(교과서 감이냐)은 Triage(에이전트)가 한다.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class TrendCandidate:
    """트렌드 후보 1건. 모든 값은 소스 원본 유래(코드가 지어내지 않는다)."""

    cid: str  # 안정 id = content_hash(url+title). 신규성/중복 판단 키
    source: str  # "hackernews" | "geeknews" | ...
    title: str
    url: str
    domain: str
    grade: int  # 1~3 (grade_from_domain)
    score: int = 0  # 인기 신호(HN points). 없으면 0
    comments: int = 0  # 댓글 수(있으면)
    published_at: str | None = None  # 발행일 ISO8601 (원본이 주면)
    first_seen: str = ""  # Scout 가 처음 본 시각 ISO8601 (Memory 가 고정)
    age_label: str = ""  # "3시간 전" 신선도 표시(결정론 파생)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ScoutResult:
    """한 번의 정찰 결과.

    - candidates: 이번에 폴링한 전체 후보(순위 정렬)
    - new_candidates: 그중 '지난 확인 이후 새로 뜬' 것만 (Triage 로 넘길 대상)
    - summary: ReAct 관찰용 구조화 요약 {polled, new, per_source, ...}
    """

    collected_at: str
    candidates: list[TrendCandidate]
    new_candidates: list[TrendCandidate]
    summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
