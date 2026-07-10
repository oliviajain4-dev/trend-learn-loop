"""Provider 베이스 — 소스별 수집기의 공통 인터페이스.

각 provider 는 topic 을 받아 CollectedDoc 리스트를 돌려주는 순수 수집기다.
LLM 을 쓰지 않으며, URL·날짜·수치는 소스 원본에서만 채운다.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from tll.collector.models import CollectedDoc
from tll.collector.rate_limiter import RateLimiter
from tll.collector.robots_guard import RobotsGuard


class BaseProvider(ABC):
    name: str = ""  # 레지스트리 키 (예: "hackernews")
    source_type: str = ""  # CollectedDoc.source_type 값

    @abstractmethod
    def search(
        self,
        topic: str,
        limit: int = 10,
        *,
        rate_limiter: RateLimiter | None = None,
        robots_guard: RobotsGuard | None = None,
    ) -> list[CollectedDoc]:
        """topic 관련 문서를 최대 limit 건 수집. 실패해도 예외를 던지지 말고 빈 리스트."""
        raise NotImplementedError
