"""후보 → 개념 resolve + 신호 로깅. (아는 개념 우선 매칭으로 오추출 방지)

버즈(주목): HN 점수·댓글. 채택: 후보 글이 GitHub repo 면 스타·포크·이슈.
개념 자동 발견은 tll.signals.discover.refresh_discovered 가 담당(손목록 없음).
"""

from __future__ import annotations

from datetime import datetime, timezone

from tll.concepts.extract import extract_concept_name
from tll.signals.github import github_signals
from tll.signals.models import Signal
from tll.signals.store import DEFAULT_SIGNALS, log_many


def _today(now) -> str:
    d = now or datetime.now(timezone.utc)
    return (d.date() if isinstance(d, datetime) else d).isoformat()


def ingest_candidate(cand, *, registry, doc_url: str = "", category: str = "",
                     llm_call=None, github_fetcher=None, signals_path: str = DEFAULT_SIGNALS, now=None) -> str:
    """후보→개념 cid + 신호 로깅. 개념을 못 정하면 "" 반환(소음 안 남김)."""
    title = getattr(cand, "title", "") or ""
    url = doc_url or getattr(cand, "url", "") or ""
    summary = getattr(cand, "summary", "") or ""
    name = extract_concept_name(title, url=url, summary=summary, llm_call=llm_call, registry=registry)
    if not name:
        return ""
    cid = registry.resolve_or_add(name, category=category, now=now).cid

    ds = _today(now)
    src = getattr(cand, "source", "") or "web"
    sigs: list[Signal] = []
    score = getattr(cand, "score", 0) or 0
    comments = getattr(cand, "comments", 0) or 0
    if score:
        sigs.append(Signal(cid=cid, date=ds, source=src, kind="hn_points", value=float(score), family="buzz"))
    if comments:
        sigs.append(Signal(cid=cid, date=ds, source=src, kind="hn_comments", value=float(comments), family="buzz"))
    if github_fetcher:
        sigs.extend(github_signals(url, cid, fetcher=github_fetcher, now=now))
    if sigs:
        log_many(sigs, path=signals_path)
    return cid
