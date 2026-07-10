"""HackerNewsProvider — HN Algolia 검색 API 로 topic 관련 story 수집 (무키).

API: https://hn.algolia.com/api/v1/search?query=...&tags=story
반환 hit 필드(실측): title, url(외부, Ask HN 은 없음), author, points,
                    num_comments, created_at(ISO), objectID.

주의(실측으로 발견한 함정): Algolia 는 오타허용 검색이라 "RAG" 가 "Rage" 같은 단어에
  매칭돼 무관한 스토리를 물어온다. → 클라이언트에서 **단어경계 관련성 필터**로 거른다
  (결정론·투명). 다어절 topic 은 모든 토큰이 제목/URL 에 단어로 등장해야 통과.

원칙: 링크·날짜·points 는 API 원본만. points/num_comments 는 '반응 신호'로 text 에 기록.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests

from tll.collector.models import CollectedDoc, grade_from_domain
from tll.collector.providers.base import BaseProvider
from tll.collector.rate_limiter import RateLimiter
from tll.collector.robots_guard import RobotsGuard

logger = logging.getLogger(__name__)

_ALGOLIA = "https://hn.algolia.com/api/v1/search"
_UA = "TLLCollector/0.1"
_TIMEOUT = 15
_HN_ITEM = "https://news.ycombinator.com/item?id={id}"


class HackerNewsProvider(BaseProvider):
    name = "hackernews"
    source_type = "hackernews"

    def search(
        self,
        topic: str,
        limit: int = 10,
        *,
        rate_limiter: RateLimiter | None = None,
        robots_guard: RobotsGuard | None = None,  # HN 은 API → robots 예외
    ) -> list[CollectedDoc]:
        # HN Algolia 는 공개 API → robots 미적용, rate limit 만 예의상.
        if rate_limiter is not None:
            rate_limiter.wait("hn.algolia.com")

        try:
            resp = requests.get(
                _ALGOLIA,
                params={
                    "query": topic,
                    "tags": "story",
                    # 관련성 필터로 줄어드니 넉넉히 받아서 거른다.
                    "hitsPerPage": max(limit * 3, limit),
                },
                headers={"User-Agent": _UA},
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
            hits = resp.json().get("hits", [])
        except Exception as e:  # 한 provider 실패가 전체를 죽이지 않게
            logger.warning("HN 검색 실패(topic=%s): %s", topic, e)
            return []

        collected_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        docs: list[CollectedDoc] = []
        for h in hits:
            title = (h.get("title") or "").strip()
            if not title:
                continue
            url = h.get("url")  # 외부 기사 URL or None(Ask/Show 텍스트글)
            if not self._is_relevant(topic, title, url):
                continue

            points = int(h.get("points") or 0)
            num_comments = int(h.get("num_comments") or 0)

            if url:
                domain = urlparse(url).netloc.lower()
                org = domain[4:] if domain.startswith("www.") else domain
                grade = grade_from_domain(domain)
            else:
                # 외부 url 없는 글은 HN 토론 자체를 가리킨다.
                url = _HN_ITEM.format(id=h.get("objectID"))
                org = "Hacker News"
                grade = 3

            docs.append(
                CollectedDoc(
                    source_type=self.source_type,
                    title=title,
                    org=org,
                    url=url,
                    collected_at=collected_at,
                    grade=grade,
                    # points/댓글은 API 원본 수치 — 반응 신호로 기록(지어내지 않음).
                    text=f"[HN 반응] ▲{points} points · 💬{num_comments} comments",
                    published_at=h.get("created_at"),
                )
            )
            if len(docs) >= limit:
                break
        return docs

    @staticmethod
    def _is_relevant(topic: str, title: str, url: str | None) -> bool:
        """topic 의 모든 토큰이 제목/URL 에 단어경계로 등장하는지(결정론 관련성 필터).

        "RAG" → \\bRAG\\b 는 "Rage" 를 거부한다. 다어절은 AND(모든 토큰 등장).
        (변형/복수형은 놓칠 수 있으나, fuzzy 오탐을 넣느니 보수적으로 거르는 쪽.)
        """
        haystack = f"{title} {url or ''}".lower()
        tokens = [t for t in re.split(r"\s+", topic.strip().lower()) if t]
        if not tokens:
            return True
        return all(re.search(rf"\b{re.escape(tok)}\b", haystack) for tok in tokens)
