"""GeminiProvider — Google Gemini(google-genai SDK) 구현.

API(실측 확정): client.models.generate_content(model, contents, config)
  - config=types.GenerateContentConfig(system_instruction, max_output_tokens, temperature)
  - 응답: r.text(본문), r.usage_metadata(prompt/candidates token count)
Gemini 은 temperature 를 받는다(Claude Opus 4.8 과 달리).
"""

from __future__ import annotations

import logging

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from tll.shared.config import get_key
from tll.shared.llm.base import LLMError, LLMProvider, LLMResponse

logger = logging.getLogger(__name__)

# 기본 모델: **실측으로 결정**. 이 키(무료 티어)에서 gemini-2.5-flash 계열은 404,
# 다른 flash 는 429(쿼터), gemini-flash-lite-latest 만 그린패스로 확인됨.
# LLM 초안은 어차피 비결정론이고 하류 검증으로 판정하므로 "latest" 별칭 허용.
# 쿼터/티어가 열리면 generate(model=...) 로 상위 모델로 오버라이드.
_DEFAULT_MODEL = "gemini-flash-lite-latest"


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(self, *, api_key: str | None = None, model: str | None = None) -> None:
        self.default_model = model or _DEFAULT_MODEL
        # 키는 .env 에서만(하드코딩 금지). 명시 api_key 는 테스트 편의용.
        self._client = genai.Client(api_key=api_key or get_key("GEMINI_API_KEY"))

    def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        max_tokens: int = 2048,
        temperature: float | None = None,
        model: str | None = None,
    ) -> LLMResponse:
        used = model or self.default_model
        config = types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=max_tokens,
            temperature=temperature,
        )
        try:
            resp = self._client.models.generate_content(
                model=used, contents=prompt, config=config
            )
        except genai_errors.APIError as e:
            # 쿼터(429)·인증·모델없음(404) 등 → 상위로 LLMError 로 통일.
            raise LLMError(f"Gemini 호출 실패({used}): {e}") from e

        try:
            text = resp.text or ""
        except Exception:  # 후보 없음/차단 등으로 text 접근이 실패할 수 있음
            text = ""

        usage: dict = {}
        um = getattr(resp, "usage_metadata", None)
        if um is not None:
            usage = {
                "input_tokens": getattr(um, "prompt_token_count", None),
                "output_tokens": getattr(um, "candidates_token_count", None),
            }
        return LLMResponse(text=text, provider=self.name, model=used, usage=usage)
