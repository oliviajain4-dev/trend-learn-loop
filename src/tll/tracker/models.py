"""Tracker 데이터 계약.

- TrackedDoc: 선별 주제 1건의 공식 문서 추적 결과(등급·성격·본문·상태·정직 caveat).
- TrackResult: 추적 전체 + 관찰용 summary.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class TrackedDoc:
    """공식 문서 추적 1건. 본문·등급·성격 + 실패/미확인은 status/note 로 정직 노출."""

    cid: str
    topic_title: str  # 트렌드 제목(교과서 주제)
    url: str
    domain: str
    grade: int  # 1~3 (원천 근접도)
    nature: str  # 제작사/논문/레포/뉴스/블로그/커뮤니티
    tier_label: str  # "1차·제작사" 등
    status: str  # ok | no_official | blocked_robots | non_html | fetch_error
    title: str = ""  # 가져온 페이지 title
    body_text: str = ""  # 추출 본문(잘림)
    published_at: str | None = None
    collected_at: str = ""
    note: str = ""  # 정직 caveat (레포 3자여부·등급 미확인·본문 빈약 등)
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TrackResult:
    docs: list[TrackedDoc]
    summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"docs": [d.to_dict() for d in self.docs], "summary": self.summary}
