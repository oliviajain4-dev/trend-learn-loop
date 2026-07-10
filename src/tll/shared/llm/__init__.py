"""LLM 추상화 패키지.

- base: LLMProvider(추상)·LLMResponse·LLMError.
- gemini/anthropic: 실제 프로바이더(다음 단계에서 추가).
- 레지스트리(get_provider/기본 프로바이더)는 프로바이더 완성 후 이 모듈에 붙인다.
"""

from __future__ import annotations

from tll.shared.llm.base import LLMError, LLMProvider, LLMResponse

__all__ = ["LLMError", "LLMProvider", "LLMResponse"]
