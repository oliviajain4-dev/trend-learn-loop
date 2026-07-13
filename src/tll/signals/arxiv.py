"""arXiv 연구 채택 신호 — repo 없는 '아이디어·기법·API'(RAG·ReAct·하네스 등)의 중요도를 논문으로 잰다.

왜: GitHub 스타는 코드 도구만 잡는다. 연구 개념은 '얼마나 많은 논문이 다루나'가 곧 채택이다.
무엇을: arXiv API(무료·키 불필요)로 개념명 매칭 논문의
  (1) arxiv_total  = 총량(연구 footprint)
  (2) arxiv_recent = 최근 활동(모멘텀)
  (3) 최초 등장일 = 나이(created_at) → 젊은 개념/오래된 개념 구분에도 씀
정직한 한계: 둘 다 arXiv 한 소스라 완전 독립은 아니다(총량 vs 최근으로 성격은 다르게 봄). 연구 하이프도 섞일 수 있음.
fetcher 주입(오프라인 테스트).
"""

from __future__ import annotations

import re
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from typing import Callable

from tll.signals.models import Signal
from tll.signals.store import DEFAULT_SIGNALS, log_many

_API = "http://export.arxiv.org/api/query"
_TOTAL_RE = re.compile(r"<opensearch:totalResults[^>]*>(\d+)</opensearch:totalResults>")
_PUB_RE = re.compile(r"<published>(\d{4}-\d{2}-\d{2})")


def _url(term: str, order: str, n: int) -> str:
    q = urllib.parse.quote(f'all:"{term}"')
    return f"{_API}?search_query={q}&sortBy=submittedDate&sortOrder={order}&max_results={n}"


def default_arxiv_fetcher(url: str, *, timeout: float = 8.0) -> str:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "TLL"})
        with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310
            return r.read().decode("utf-8", "replace")
    except Exception:  # noqa: BLE001
        return ""


def _as_date(x) -> date:
    d = x or datetime.now(timezone.utc)
    return d.date() if isinstance(d, datetime) else d


def arxiv_stats(term: str, *, fetcher: Callable[[str], str], now=None, window_days: int = 180) -> dict:
    """개념명 → {total, recent, earliest}. 논문 총량·최근 활동·최초 등장일."""
    now_d = _as_date(now)
    xml = fetcher(_url(term, "descending", 100)) or ""
    m = _TOTAL_RE.search(xml)
    total = int(m.group(1)) if m else 0
    cutoff = now_d - timedelta(days=window_days)
    recent = 0
    for ds in _PUB_RE.findall(xml):
        try:
            if date.fromisoformat(ds) >= cutoff:
                recent += 1
        except ValueError:
            pass
    xml2 = fetcher(_url(term, "ascending", 1)) or ""
    pubs = _PUB_RE.findall(xml2)
    return {"total": total, "recent": recent, "earliest": pubs[0] if pubs else ""}


def refresh_research(registry, *, concepts=None, fetcher: Callable[[str], str] | None = None,
                     signals_path: str = DEFAULT_SIGNALS, now=None, max_concepts: int = 12, min_total: int = 5) -> int:
    """repo 없는(=category!='발견') 개념들에 arXiv 채택 신호를 붙인다(나이로는 안 씀). 반환: 로깅 신호 수."""
    f = fetcher or default_arxiv_fetcher
    if concepts is None:
        concepts = [c for c in registry.all() if c.category != "발견"][:max_concepts]
    ds = _as_date(now).isoformat()
    logged = 0
    for c in concepts:
        stt = arxiv_stats(c.canonical, fetcher=f, now=now)
        if stt["total"] < min_total:
            continue
        log_many([
            Signal(cid=c.cid, date=ds, source="arxiv", kind="arxiv_total", value=float(stt["total"]), family="stock"),
            Signal(cid=c.cid, date=ds, source="arxiv", kind="arxiv_recent", value=float(stt["recent"]), family="stock"),
        ], path=signals_path)
        logged += 2
        # 최초 논문일은 '기술 나이'로 쓰지 않는다 — 단어가 옛 논문에 우연히 있으면 늙어 보이는 불량 대리지표.
        # (정착=코끼리 판정은 신뢰 가능한 GitHub 저장소 생일 또는 '오래 평탄 관측'으로만.)
    return logged
