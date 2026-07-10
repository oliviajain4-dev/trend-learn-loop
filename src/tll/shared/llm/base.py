"""LLM 프로바이더 추상 인터페이스.

목적: 집필(Analyst)·검증(Verifier)이 특정 벤더에 묶이지 않게 한다.
  - Gemini: 요약·집필 주력.
  - Claude(Anthropic): 교차모델 검증(모델A↔모델B, 기획서 §4-2 L3).

주의: 결과의 사실성은 이 계층이 보장하지 않는다. LLM 은 초안을 쓸 뿐이고,
  진위는 검증 코어(결정론 L1 앵커링 등)가 코드/원본으로 판정한다(프로젝트 DNA).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


class LLMError(RuntimeError):
    """LLM 호출 실패(네트워크·인증·응답형식 등)."""


@dataclass
class LLMResponse:
    """LLM 응답 1건. text 가 본문, 나머지는 관찰/로깅용."""

    text: str
    provider: str  # "gemini" | "anthropic"
    model: str
    usage: dict[str, Any] = field(default_factory=dict)  # 토큰 등(있으면)

    def __bool__(self) -> bool:
        return bool(self.text.strip())


class LLMProvider(ABC):
    """모든 프로바이더가 지키는 최소 계약: 프롬프트→텍스트.

    temperature 는 선택. 일부 모델(예: Claude Opus 4.8)은 temperature 를 받으면
    거부하므로, 각 프로바이더가 자신에게 맞게 처리한다(안 쓰면 무시).
    """

    name: str = ""  # 레지스트리 키
    default_model: str = ""

    @abstractmethod
    def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        max_tokens: int = 2048,
        temperature: float | None = None,
        model: str | None = None,
    ) -> LLMResponse:
        """prompt(+선택 system)로 텍스트를 생성. 실패 시 LLMError."""
        raise NotImplementedError
