"""Provider 레지스트리 — 이름으로 수집기를 등록/조회한다.

새 소스를 붙일 때: 여기 import 하고 _PROVIDERS 에 인스턴스를 추가하면
engine.collect() 가 자동으로 사용한다.

자리표시(다음에 붙일 것):
  - GeekNewsProvider (news.hada.io RSS) — 3단계에서 추가
  - ArxivProvider (arXiv API) — 로드맵
  - OfficialDocsProvider (tech→공식문서 URL 레지스트리) — 로드맵
"""

from __future__ import annotations

from tll.collector.providers.base import BaseProvider
from tll.collector.providers.hackernews import HackerNewsProvider

_PROVIDERS: dict[str, BaseProvider] = {
    p.name: p
    for p in (
        HackerNewsProvider(),
    )
}


def get_provider(name: str) -> BaseProvider | None:
    return _PROVIDERS.get(name)


def all_providers() -> list[BaseProvider]:
    return list(_PROVIDERS.values())


def provider_names() -> list[str]:
    return list(_PROVIDERS.keys())
