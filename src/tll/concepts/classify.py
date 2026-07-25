"""개념 종류 분류 — 도구 / 기법 / 자료. (규칙문서 §5)

- tool(도구): 실행하는 소프트웨어. 저장소 신호(별·포크)로 채택 측정, 동물 계급 부여.
- technique(기법): 특정 제품 아닌 '하는 방식'(RAG·하네스 등). 용어 빈도로 측정(category 로 지정).
- resource(자료): awesome-list·튜토리얼·논문목록 등 '읽을거리 모음'. 티어에서 제외.

전부 결정론(이름·토픽·category 패턴). LLM 안 부른다 → 빠르고 공짜·재현가능.
확실치 않으면 기본값 tool(과잉 제외 방지 — 자료로 잘못 버리지 않음).
"""

from __future__ import annotations

from typing import Iterable

# 자료(읽을거리 모음) 신호 — 이름에 들어가면 자료일 확률 높음
_RESOURCE_HINTS = (
    "awesome", "tutorial", "example", "cookbook", "roadmap", "cheatsheet", "cheat-sheet",
    "handbook", "papers", "paper-list", "reading-list", "readinglist", "curated", "collection",
    "techniques", "prompts", "interview", "list-of", "-list", "500-", "100-days", "bestof", "best-of",
)
_RESOURCE_TOPICS = {"awesome-list", "awesome", "learning-resources", "tutorial", "curated-list", "list", "book"}
_TECHNIQUE_CATS = {"기법", "technique", "concept", "개념", "practice"}


def concept_kind(name: str, *, category: str = "", topics: Iterable[str] = ()) -> str:
    """'tool' | 'technique' | 'resource' 반환. 순수 결정론."""
    cat = (category or "").strip().lower()
    if cat in _TECHNIQUE_CATS:
        return "technique"
    n = (name or "").strip().lower()
    tset = {str(t).strip().lower() for t in (topics or [])}
    if tset & _RESOURCE_TOPICS:
        return "resource"
    if n.startswith("awesome") or any(h in n for h in _RESOURCE_HINTS):
        return "resource"
    return "tool"
