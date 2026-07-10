"""AnthropicProvider — Claude(anthropic SDK) 구현. 교차모델 검증용.

API(claude-api 레퍼런스): client.messages.create(model, max_tokens, system?, messages)
  응답 content 는 블록 리스트 → type=="text" 블록의 text 를 이어붙인다.
  usage 에 input/output tokens.

주의(중요): **Claude Opus 4.8 은 temperature/top_p 를 주면 400** 이다.
  그래서 base 인터페이스의 temperature 를 받아도 Anthropic 에는 전달하지 않는다.
"""

from __future__ import annotations

import logging

import anthropic

from tll.shared.config import get_key
from tll.shared.llm.base import LLMError, LLMProvider, LLMResponse

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "claude-opus-4-8"


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self, *, api_key: str | None = None, model: str | None = None) -> None:
        self.default_model = model or _DEFAULT_MODEL
        key = api_key or get_key("ANTHROPIC_API_KEY")
        # HTTP 헤더는 ASCII 여야 한다. 자리표시(예: 한글 "여기에…")면 httpx 가
        # 깊은 곳에서 UnicodeEncodeError 로 죽으므로, 여기서 미리 명확히 막는다.
        if not key.isascii():
            raise LLMError(
                "ANTHROPIC_API_KEY 가 유효한 키가 아닙니다(비-ASCII 자리표시로 보임). "
                ".env 에 실제 Claude 키(sk-ant-…)를 넣으세요. 아직 미발급이면 Gemini 로 진행."
            )
        self._client = anthropic.Anthropic(api_key=key)

    def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        max_tokens: int = 2048,
        temperature: float | None = None,  # 의도적으로 미전달(Opus 4.8 은 400)
        model: str | None = None,
    ) -> LLMResponse:
        used = model or self.default_model
        kwargs: dict = {
            "model": used,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system
        try:
            resp = self._client.messages.create(**kwargs)
        except anthropic.APIError as e:
            raise LLMError(f"Claude 호출 실패({used}): {e}") from e

        text = "".join(
            b.text for b in resp.content if getattr(b, "type", None) == "text"
        )
        usage = {
            "input_tokens": resp.usage.input_tokens,
            "output_tokens": resp.usage.output_tokens,
        }
        return LLMResponse(text=text, provider=self.name, model=used, usage=usage)
