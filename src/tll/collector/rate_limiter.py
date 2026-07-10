"""도메인별 rate limiter (수집 예의).

- 같은 도메인에 대해 최소 간격(기본 1.5초)을 보장한다.
- 인스턴스 상태만 사용(전역 가변 상태 없음) → collect() 호출마다 새로 만들면 독립적.
- 스레드 안전: 다음 호출 가능 시각을 락 안에서 예약하고, 대기는 락 밖에서 sleep.
"""

from __future__ import annotations

import threading
import time
from urllib.parse import urlparse


class RateLimiter:
    def __init__(self, min_interval: float = 1.5) -> None:
        self.min_interval = min_interval
        self._next_allowed: dict[str, float] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _domain(url_or_domain: str) -> str:
        if "://" in url_or_domain:
            return urlparse(url_or_domain).netloc.lower()
        return url_or_domain.lower()

    def wait(self, url_or_domain: str) -> float:
        """해당 도메인 호출 전 필요한 만큼 대기. 실제 대기한 초를 반환(관찰/테스트용)."""
        domain = self._domain(url_or_domain)
        with self._lock:
            now = time.monotonic()
            earliest = self._next_allowed.get(domain, 0.0)
            start = max(now, earliest)
            # 이번 호출 시각(start) 기준으로 다음 허용 시각을 예약
            self._next_allowed[domain] = start + self.min_interval
            wait_for = start - now
        if wait_for > 0:
            time.sleep(wait_for)
        return max(wait_for, 0.0)
