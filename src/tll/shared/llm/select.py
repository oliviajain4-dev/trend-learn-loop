"""LLM 프로바이더 선택 — Gemini vs Claude(Anthropic) 중 무엇을 쓸지 정하고 표시 라벨을 준다.

우선순위: 명시 인자 > 환경변수/`.env` 의 TLL_PROVIDER > 기본값(gemini).
모델도 TLL_MODEL 로 덮어쓸 수 있다(없으면 각 프로바이더 기본 모델).
전환이 쉽도록 문자열 이름만 다룬다(실제 생성은 get_provider 가). 잘못된 이름은 기본값으로.
"""

from __future__ import annotations

from tll.shared.config import get_key

KNOWN_PROVIDERS = ("gemini", "anthropic")
DEFAULT_PROVIDER = "gemini"
_LABELS = {"gemini": "Gemini", "anthropic": "Claude (Anthropic)"}


def resolve_provider_name(explicit: str | None = None) -> str:
    """쓸 프로바이더 이름. explicit > TLL_PROVIDER(.env/환경) > gemini. 미지값은 gemini."""
    val = explicit or get_key("TLL_PROVIDER", required=False) or DEFAULT_PROVIDER
    name = str(val).strip().lower()
    return name if name in KNOWN_PROVIDERS else DEFAULT_PROVIDER


def resolve_model_name(explicit: str | None = None) -> str | None:
    """모델 덮어쓰기(TLL_MODEL). 없으면 None → 프로바이더 기본 모델."""
    val = explicit or get_key("TLL_MODEL", required=False)
    v = str(val).strip() if val else ""
    return v or None


def provider_label(name: str) -> str:
    return _LABELS.get((name or "").strip().lower(), name or "?")
