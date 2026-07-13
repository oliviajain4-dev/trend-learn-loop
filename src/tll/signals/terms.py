"""기법 발견기 — repo 없는 개념(하네스 엔지니어링·RAG 등)을 제목에서 자동 발견. (규칙문서 §6)

특정 소프트웨어가 아닌 '하는 방식'은 GitHub 검색으로 안 잡힌다. 대신 **말의 빈도**로 잡는다:
arXiv·HN 제목에서 (1) 약어(RAG·MCP) + (2) 헤드명사 n-gram("X engineering/learning/generation…")을
뽑아 빈도 임계를 넘으면 🧠기법 개념으로 자동 등록하고 community 빈도 신호를 남긴다.
→ 내가(사용자) 언급 안 해도 뜨는 기법이 스스로 들어온다. arXiv 신호(refresh_research)와 합쳐 2소스 합의.
"""

from __future__ import annotations

import re
from collections import Counter
from datetime import date, datetime

from tll.signals.models import Signal
from tll.signals.store import DEFAULT_SIGNALS, log_many

# 기법 이름이 흔히 끝나는 '헤드' 명사 — 앞 1~2 단어를 붙여 구(句)를 만든다.
_HEADS = {
    "engineering", "learning", "generation", "tuning", "finetuning", "prompting", "distillation",
    "alignment", "reasoning", "agents", "agent", "retrieval", "embeddings", "embedding",
    "quantization", "inference", "orchestration", "grounding", "chaining", "search",
    "augmentation", "compression", "routing", "decoding", "pretraining",
}
_STOP_PREV = {
    "the", "a", "an", "of", "for", "and", "to", "in", "on", "with", "our", "new", "this",
    "that", "using", "via", "based", "toward", "towards", "is", "are", "from", "by", "as",
    "we", "their", "its", "your", "more", "how", "why", "what", "can", "will", "at", "into",
}
_ACRONYM = re.compile(r"\b([A-Z][A-Z0-9]{2,5})\b")
_ACRONYM_STOP = {"PDF", "FAQ", "CEO", "USA", "NEW", "HOW", "WHY", "YOU", "THE", "AND", "ARXIV", "GITHUB", "HTTP", "HTML"}
_WORD = re.compile(r"[A-Za-z][A-Za-z0-9\-]+")


def extract_terms(text: str) -> set[str]:
    """한 제목에서 기법 후보 용어 집합. 약어(대문자 유지) + 헤드명사 구(소문자)."""
    terms: set[str] = set()
    for m in _ACRONYM.findall(text or ""):
        if m not in _ACRONYM_STOP:
            terms.add(m)
    words = _WORD.findall((text or "").lower())
    for i, w in enumerate(words):
        if w in _HEADS and i >= 1:
            p1 = words[i - 1]
            if p1 in _STOP_PREV or len(p1) <= 2 or p1 in _HEADS:
                continue
            term = f"{p1} {w}"
            if i >= 2 and words[i - 2] not in _STOP_PREV and len(words[i - 2]) > 2 and words[i - 2] not in _HEADS:
                term = f"{words[i - 2]} {term}"
            terms.add(term)
    return terms


def count_terms(titles) -> Counter:
    c: Counter = Counter()
    for t in titles:
        for term in extract_terms(t):
            c[term] += 1
    return c


def discover_terms(titles, *, min_count: int = 3, top: int = 15) -> list[tuple[str, int]]:
    """제목 뭉치에서 자주 나오는 기법 용어(빈도 ≥ min_count) 상위 top."""
    return [(t, n) for t, n in count_terms(titles).most_common() if n >= min_count][:top]


def _as_date(x) -> date:
    if isinstance(x, datetime):
        return x.date()
    if isinstance(x, date):
        return x
    return date.fromisoformat(str(x)[:10]) if x else date.today()


def refresh_terms(registry, *, titles, signals_path: str = DEFAULT_SIGNALS, now=None,
                  min_count: int = 3, top: int = 15) -> int:
    """뜨는 기법 용어를 개념으로 등록 + community 빈도 신호. 반환: 등록/로깅한 개념 수."""
    ds = _as_date(now).isoformat()
    made = 0
    for term, n in discover_terms(titles, min_count=min_count, top=top):
        cid = registry.add(term, category="기법", now=now)
        log_many([Signal(cid=cid, date=ds, source="community", kind="term_freq", value=float(n), family="stock")],
                 path=signals_path)
        made += 1
    return made
