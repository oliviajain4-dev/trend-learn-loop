"""GeekNewsProvider — news.hada.io 피드에서 topic 관련 국내 IT 뉴스 수집 (무키).

피드: https://news.hada.io/rss/news
형식(실측): RSS 2.0 이 아니라 **Atom**(<feed>/<entry>, <link href=...>, <published>).
  그래서 stdlib xml.etree 로 Atom 을 파싱한다(feedparser 같은 새 의존성 불필요).

성격: HN Algolia 처럼 topic 검색이 아니라 **최근 피드**다. 그래서 topic 관련 항목이
  최근 피드에 없으면 0건이 정상(RSS 는 검색이 아니다 — 정직하게 빈 결과).

윤리: RSS 는 API 예외가 아니므로 robots_guard 를 적용한다(Disallow 면 스킵). rate limit 도.
원칙: title·link·published 는 피드 원본만. grade=2(국내 IT 뉴스 기관).
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import requests

from tll.collector.models import CollectedDoc
from tll.collector.providers.base import BaseProvider, topic_matches
from tll.collector.rate_limiter import RateLimiter
from tll.collector.robots_guard import RobotsGuard

logger = logging.getLogger(__name__)

_RSS_URL = "https://news.hada.io/rss/news"
_UA = "TLLCollector/0.1"
_TIMEOUT = 15
_ATOM = "{http://www.w3.org/2005/Atom}"  # Atom 네임스페이스


class GeekNewsProvider(BaseProvider):
    name = "geeknews"
    source_type = "geeknews"

    def search(
        self,
        topic: str,
        limit: int = 10,
        *,
        rate_limiter: RateLimiter | None = None,
        robots_guard: RobotsGuard | None = None,
    ) -> list[CollectedDoc]:
        # RSS 는 API 예외가 아님 → robots 확인 후 스킵 가능.
        if robots_guard is not None and not robots_guard.allowed(_RSS_URL):
            logger.warning("GeekNews RSS robots Disallow → 스킵")
            return []
        if rate_limiter is not None:
            rate_limiter.wait("news.hada.io")

        try:
            resp = requests.get(_RSS_URL, headers={"User-Agent": _UA}, timeout=_TIMEOUT)
            resp.raise_for_status()
            root = ET.fromstring(resp.content)
        except Exception as e:  # 실패해도 전체를 죽이지 않음
            logger.warning("GeekNews RSS 실패(topic=%s): %s", topic, e)
            return []

        collected_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        docs: list[CollectedDoc] = []
        for entry in root.findall(f"{_ATOM}entry"):
            title = self._text(entry.find(f"{_ATOM}title"))
            if not title:
                continue
            link = self._alternate_link(entry)
            content = self._text(entry.find(f"{_ATOM}content"))
            # 제목+본문에 topic 이 등장하는 항목만(최근 피드라 없으면 0건이 정상).
            if not topic_matches(topic, title, content or ""):
                continue
            published = self._text(entry.find(f"{_ATOM}published")) or self._text(
                entry.find(f"{_ATOM}updated")
            )
            docs.append(
                CollectedDoc(
                    source_type=self.source_type,
                    title=title,
                    org="GeekNews",
                    url=link or _RSS_URL,
                    collected_at=collected_at,
                    grade=2,  # 국내 IT 뉴스 기관
                    published_at=published,
                )
            )
            if len(docs) >= limit:
                break
        return docs

    @staticmethod
    def _text(el: ET.Element | None) -> str:
        return (el.text or "").strip() if el is not None else ""

    @staticmethod
    def _alternate_link(entry: ET.Element) -> str:
        """<link rel='alternate' href='...'/> 의 href. 없으면 첫 link href."""
        first = ""
        for link in entry.findall(f"{_ATOM}link"):
            href = link.get("href", "")
            if link.get("rel", "alternate") == "alternate" and href:
                return href
            first = first or href
        return first
