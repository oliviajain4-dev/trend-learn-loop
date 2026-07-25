"""개념 추출 — 후보(글) → 기술 개념 이름 하나. (오추출 방지 우선)

우선순위:
 1) '이미 아는 개념'(레지스트리=시드+누적)이 글에 '단어'로 나오면 그 표준명 → 결정론, 확실.
 2) 아니면 LLM 이 표준명 추출 — 단 특정 기술·제품이 아니면 'UNCLEAR' 로 기권(엉뚱한 이름 방지).
 3) 그래도 없으면 github repo명, 그것도 없으면 "" (개념 안 만듦 = 소음 안 남김).
레지스트리가 결정론 중복해소 → LLM 실수 영향 최소화.
"""

from __future__ import annotations

import re
from typing import Callable

_RESERVED = {"orgs", "sponsors", "features", "about", "topics", "collections", "marketplace", "settings"}

_SYSTEM = (
    "너는 IT/AI 글에서 '핵심 기술 또는 제품 하나'의 표준 이름만 뽑는다. "
    "설명 없이 이름만 한 줄로. 여러 개면 가장 대표적인 하나. "
    "특정 기술·제품·라이브러리·모델이 아니면(일반 토론·의견·역사·잡담 등) 'UNCLEAR' 라고만 답한다. "
    "예: 'LangChain', 'PostgreSQL', 'Model Context Protocol', 'UNCLEAR'."
)


def repo_name_from_url(url: str) -> str:
    m = re.search(r"github\.com/([^/\s]+)/([^/\s#?]+)", url or "")
    if not m:
        return ""
    owner, repo = m.group(1), re.sub(r"\.git$", "", m.group(2))
    return "" if owner.lower() in _RESERVED else repo


def find_known(text: str, registry) -> str:
    """레지스트리의 표준명/별칭이 text 에 '단어'로 등장하면 그 표준명(가장 긴 매칭) 반환."""
    t = text or ""
    best, best_len = "", 0
    for c in registry.all():
        for surface in [c.canonical, *c.aliases]:
            s = (surface or "").strip()
            if len(s) >= 2 and re.search(r"(?<![A-Za-z0-9])" + re.escape(s) + r"(?![A-Za-z0-9])", t, re.I) and len(s) > best_len:
                best, best_len = c.canonical, len(s)
    return best


def _parse_name(raw: str) -> str:
    if not raw or not raw.strip():
        return ""
    line = raw.strip().splitlines()[0].strip().strip("\"'` ").strip()
    return "" if line.upper() in ("UNCLEAR", "N/A", "NONE", "") else line[:60]


def extract_concept_name(title: str, *, url: str = "", summary: str = "",
                         llm_call: Callable[[str, str], str] | None = None, registry=None) -> str:
    """핵심 기술 개념 이름. 아는 개념 우선 → LLM(기권 가능) → repo명 → ""."""
    if registry is not None:
        known = find_known(f"{title} {summary}", registry)
        if known:
            return known
    if llm_call:
        try:
            raw = llm_call(
                f"제목: {title}\n요약: {summary}\nURL: {url}\n\n핵심 기술/제품 표준 이름 하나만(특정 기술 아니면 UNCLEAR):",
                _SYSTEM,
            )
            name = _parse_name(raw)
            if name:
                return name
        except Exception:  # noqa: BLE001
            pass
    return repo_name_from_url(url)  # 제목은 '개념'이 아니라 글제목 → 안 씀. 없으면 ""
