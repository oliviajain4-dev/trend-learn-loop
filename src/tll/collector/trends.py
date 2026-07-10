"""대시보드 트렌드 피드 — Hacker News 상위 스토리(주제 무관).

API: https://github.com/HackerNews/API  (인증 불필요)
  - topstories.json  → 상위 스토리 id 목록
  - item/{id}.json   → 스토리 1건(title/url/score/by/time/descendants ...)

파이프라인의 '주제 수집기'(providers/*, engine)와는 목적이 다르다:
  여긴 topic 없이 지금 뜨는 것을 순위대로 보여주는 용도.

원칙:
  - 점수(score)·댓글수(descendants)·URL 은 **API 원본 그대로**. LLM 생성 금지.
  - 제목도 원문(대개 영어) 그대로 노출한다. 번역해 지어내지 않는다(충실도).
  - 수집시각을 박제(provenance)해 함께 반환한다.
"""

from __future__ import annotations

import concurrent.futures
from dataclasses import dataclass, field
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests

HN_API = "https://hacker-news.firebaseio.com/v0"
HN_ITEM_WEB = "https://news.ycombinator.com/item?id={id}"
_TIMEOUT = 10  # 초
_MAX_WORKERS = 8  # 동시 요청 상한(예의상 과하지 않게)


@dataclass
class HNStory:
    """HN 스토리 1건. 모든 수치는 API 원본."""

    id: int
    title: str
    score: int  # ▲ 포인트
    by: str  # 작성자
    time: int  # 게시 시각(unix seconds)
    descendants: int  # 댓글 수
    type: str  # story/job/poll ...
    url: str | None = None  # 외부 기사 URL. Ask/Show 텍스트글은 None.

    @property
    def hn_url(self) -> str:
        """HN 토론 페이지 URL."""
        return HN_ITEM_WEB.format(id=self.id)

    @property
    def link(self) -> str:
        """제목이 가리킬 링크: 외부 url 있으면 그것, 없으면 HN 토론."""
        return self.url or self.hn_url

    @property
    def domain(self) -> str:
        """표시용 도메인. url 없으면 HN 자체."""
        if not self.url:
            return "news.ycombinator.com"
        net = urlparse(self.url).netloc
        return net[4:] if net.startswith("www.") else net


@dataclass
class HNFeed:
    """수집 결과 + provenance(출처·수집시각)."""

    stories: list[HNStory]
    collected_at: str  # ISO8601
    source: str = "Hacker News API (hacker-news.firebaseio.com)"
    fetched: int = 0  # 요청한 개수
    dropped: int = field(default=0)  # 널/삭제로 제외된 개수


def _get_json(path: str):
    r = requests.get(f"{HN_API}/{path}", timeout=_TIMEOUT)
    r.raise_for_status()
    return r.json()


def _to_story(item: dict) -> HNStory:
    return HNStory(
        id=item["id"],
        title=item.get("title", "(제목 없음)"),
        score=int(item.get("score", 0)),
        by=item.get("by", "unknown"),
        time=int(item.get("time", 0)),
        descendants=int(item.get("descendants", 0)),
        type=item.get("type", "story"),
        url=item.get("url"),
    )


def fetch_top_stories(limit: int = 30) -> HNFeed:
    """상위 `limit`건을 병렬로 가져와 순위 순서를 보존해 반환.

    널(삭제된) 항목은 건너뛰되 몇 건이 빠졌는지 provenance 에 남긴다.
    """
    ids: list[int] = _get_json("topstories.json")[:limit]

    # 순위(입력 순서) 보존을 위해 map 사용
    with concurrent.futures.ThreadPoolExecutor(max_workers=_MAX_WORKERS) as ex:
        items = list(ex.map(lambda i: _get_json(f"item/{i}.json"), ids))

    stories: list[HNStory] = []
    dropped = 0
    for it in items:
        if not it:  # null(삭제/비공개)
            dropped += 1
            continue
        stories.append(_to_story(it))

    return HNFeed(
        stories=stories,
        collected_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        fetched=len(ids),
        dropped=dropped,
    )
