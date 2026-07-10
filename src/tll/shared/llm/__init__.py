"""LLM 추상화 패키지 + 프로바이더 레지스트리.

- base: LLMProvider(추상)·LLMResponse·LLMError.
- gemini/anthropic: 실제 프로바이더.
- get_provider(name=None): 이름으로 프로바이더 획득(없으면 기본=Gemini). 지연 생성·캐시.
- available_providers(): 실제로 생성 가능한(=유효 키 있는) 프로바이더만.

기본이 Gemini 인 이유: 집필 주력이고 키가 발급돼 있음. Anthropic 은 교차모델 검증용이며
실제 키가 .env 에 있어야 등록된다(현재는 자리표시라 미등록 → available 에서 빠짐).
"""

from __future__ import annotations

from tll.shared.llm.base import LLMError, LLMProvider, LLMResponse

__all__ = [
    "LLMError",
    "LLMProvider",
    "LLMResponse",
    "get_provider",
    "available_providers",
    "default_provider_name",
]

_DEFAULT_PROVIDER = "gemini"
_KNOWN = ("gemini", "anthropic")
_cache: dict[str, LLMProvider] = {}


def default_provider_name() -> str:
    return _DEFAULT_PROVIDER


def _construct(name: str) -> LLMProvider:
    if name == "gemini":
        from tll.shared.llm.gemini import GeminiProvider

        return GeminiProvider()
    if name == "anthropic":
        from tll.shared.llm.anthropic import AnthropicProvider

        return AnthropicProvider()
    raise LLMError(f"알 수 없는 LLM provider: {name} (가능: {_KNOWN})")


def get_provider(name: str | None = None) -> LLMProvider:
    """프로바이더 획득. 키 없음/자리표시면 생성 시 LLMError/ConfigError 가 난다."""
    key = name or _DEFAULT_PROVIDER
    if key not in _cache:
        _cache[key] = _construct(key)  # 실패 시 캐시하지 않음
    return _cache[key]


def available_providers() -> list[str]:
    """유효 키가 있어 실제 생성 가능한 프로바이더 이름 목록."""
    out: list[str] = []
    for name in _KNOWN:
        try:
            _construct(name)
        except Exception:  # 키 없음/자리표시 등 → 미가용으로 간주
            continue
        out.append(name)
    return out
