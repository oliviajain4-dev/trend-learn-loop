"""설정·비밀키 로딩 — .env 에서만 읽는다. 코드에 키 하드코딩 금지(프로젝트 DNA).

키 이름(표준):
  - GEMINI_API_KEY     : Gemini(요약·집필 주력)
  - ANTHROPIC_API_KEY  : Claude(교차모델 검증용)
  - YOUTUBE_API_KEY    : YouTube Data API(미디어 실데이터)
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# config.py: src/tll/shared/config.py → parents[3] == <repo>
_REPO_ROOT = Path(__file__).resolve().parents[3]
_ENV_PATH = _REPO_ROOT / ".env"
_loaded = False


class ConfigError(RuntimeError):
    """필수 설정/키가 없을 때."""


def _ensure_loaded() -> None:
    global _loaded
    if not _loaded:
        # override=False: 이미 export 된 환경변수를 .env 가 덮어쓰지 않게.
        load_dotenv(_ENV_PATH, override=False)
        _loaded = True


def get_key(name: str, *, required: bool = True) -> str | None:
    """환경변수(.env)에서 키를 읽는다. required 인데 없으면 ConfigError."""
    _ensure_loaded()
    value = (os.environ.get(name) or "").strip()
    if not value:
        if required:
            raise ConfigError(
                f"환경변수 {name} 가 비어 있습니다. .env 를 확인하세요(코드에 키 하드코딩 금지)."
            )
        return None
    return value


def has_key(name: str) -> bool:
    """키 존재 여부만 확인(값 노출 없이)."""
    return get_key(name, required=False) is not None
