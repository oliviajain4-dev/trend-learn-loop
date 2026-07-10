"""robots.txt 가드 (수집 윤리).

- RSS·스크래핑 대상 URL 이 robots.txt 에서 Disallow 면 건너뛴다.
- 파싱 실패/robots 없음/네트워크 오류 → **보수적으로 허용**(False negative 방지).
- 도메인별 robots 를 캐시(호출마다 재요청 안 함).
- 인스턴스 상태만 사용(전역 가변 상태 없음).
- API(HN Algolia 등)는 이 가드를 적용하지 않는다(엔진/프로바이더가 판단). 예의상
  rate limit 은 별도로 적용.
"""

from __future__ import annotations

import logging
import urllib.robotparser
from urllib.parse import urljoin, urlparse

import requests

logger = logging.getLogger(__name__)

USER_AGENT = "TLLCollector/0.1"


class RobotsGuard:
    def __init__(self, user_agent: str = USER_AGENT, timeout: int = 8) -> None:
        self.user_agent = user_agent
        self.timeout = timeout
        # base("scheme://netloc") → RobotFileParser | None(허용)
        self._cache: dict[str, urllib.robotparser.RobotFileParser | None] = {}

    def allowed(self, url: str) -> bool:
        """이 URL 을 우리 UA 로 가져와도 되는지. 확신 없으면 허용(보수적)."""
        try:
            parsed = urlparse(url)
            if not parsed.scheme.startswith("http") or not parsed.netloc:
                return True
            base = f"{parsed.scheme}://{parsed.netloc}"
            rp = self._get_parser(base)
            if rp is None:
                return True  # robots 없음/파싱 실패 → 허용
            return rp.can_fetch(self.user_agent, url)
        except Exception as e:  # 어떤 예외든 수집을 막지 않음(로그만)
            logger.warning("robots 확인 실패(%s) → 허용: %s", url, e)
            return True

    def _get_parser(self, base: str) -> urllib.robotparser.RobotFileParser | None:
        if base in self._cache:
            return self._cache[base]
        rp: urllib.robotparser.RobotFileParser | None = None
        try:
            robots_url = urljoin(base, "/robots.txt")
            resp = requests.get(
                robots_url, timeout=self.timeout, headers={"User-Agent": self.user_agent}
            )
            if resp.status_code < 400 and resp.text.strip():
                rp = urllib.robotparser.RobotFileParser()
                rp.parse(resp.text.splitlines())
            # 4xx/5xx/빈 응답 → rp=None(허용)
        except Exception as e:
            logger.warning("robots.txt 가져오기 실패(%s) → 허용: %s", base, e)
            rp = None
        self._cache[base] = rp
        return rp
