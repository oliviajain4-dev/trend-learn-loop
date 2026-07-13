"""GitHub 자동 발견 — '개발자들이 실제로 많이 쓰는' AI/LLM 저장소를 GitHub Search 로 캐온다.

손목록 없이 GitHub 자체 지표(스타·포크·이슈)로 '중요한 것'을 자동 선정 → 개념 등록 + 채택 신호.
정직한 한계: OSS 개발자도구에 치우침(폐쇄형 API·아이디어형은 repo 가 없어 못 잡음).
스타는 주목 편향이 있어(He 2026 가짜 별) 포크·이슈도 함께 신호로 쓴다. fetcher 주입(오프라인 테스트).
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Callable

from tll.signals.models import Signal
from tll.signals.store import DEFAULT_SIGNALS, log_many

# '중요한 AI/LLM 기술'이 모이는 GitHub 토픽(고정 설정 — 사용자 편집 아님, 자동 발견의 탐색 범위).
DEFAULT_QUERIES = ["topic:llm", "topic:rag", "topic:ai-agents", "topic:llmops", "topic:vector-database"]


def _search_url(query: str, per_page: int, min_stars: int) -> str:
    q = urllib.parse.quote(f"{query} stars:>{min_stars}")
    return f"https://api.github.com/search/repositories?q={q}&sort=stars&order=desc&per_page={per_page}"


def default_search_fetcher(url: str, *, timeout: float = 6.0) -> dict:
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "TLL"})
        with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310
            return json.loads(r.read().decode("utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def _today(now) -> str:
    d = now or datetime.now(timezone.utc)
    return (d.date() if isinstance(d, datetime) else d).isoformat()


def discover_repos(*, fetcher: Callable[[str], dict], queries=DEFAULT_QUERIES,
                   per_query: int = 8, min_stars: int = 500, max_repos: int = 30) -> list[dict]:
    """여러 토픽에서 스타순 상위 저장소를 모아 중복 제거·정렬. 반환: [{name, full_name, stars, forks, issues}]."""
    seen: set[str] = set()
    out: list[dict] = []
    for q in queries:
        data = fetcher(_search_url(q, per_query, min_stars)) or {}
        for it in data.get("items") or []:
            full = it.get("full_name")
            stars = int(it.get("stargazers_count") or 0)
            if not full or full in seen or stars < min_stars:
                continue
            seen.add(full)
            out.append({
                "name": it.get("name") or full.split("/")[-1],
                "full_name": full, "stars": stars,
                "forks": int(it.get("forks_count") or 0), "issues": int(it.get("open_issues_count") or 0),
                "created_at": str(it.get("created_at") or ""),
            })
    out.sort(key=lambda r: r["stars"], reverse=True)
    return out[:max_repos]


def refresh_discovered(registry, *, fetcher: Callable[[str], dict] | None = None, repos=None,
                       queries=DEFAULT_QUERIES, per_query: int = 8, min_stars: int = 500, max_repos: int = 30,
                       signals_path: str = DEFAULT_SIGNALS, now=None, category: str = "발견") -> int:
    """자동 발견 → 개념 등록(추출 grounding용) + 채택 신호(스타·포크·이슈) 로깅. 반환: 로깅된 신호 수."""
    f = fetcher or default_search_fetcher
    repos = repos if repos is not None else discover_repos(
        fetcher=f, queries=queries, per_query=per_query, min_stars=min_stars, max_repos=max_repos)
    ds = _today(now)
    logged = 0
    for rp in repos:
        cid = registry.add(rp["name"], category=category, status="confirmed", now=now, created_at=rp.get("created_at", ""))
        sigs = [Signal(cid=cid, date=ds, source="github", kind=k, value=float(rp[k]), family="stock")
                for k in ("stars", "forks", "issues") if rp.get(k) is not None]
        if sigs:
            log_many(sigs, path=signals_path)
            logged += len(sigs)
    return logged


def resolve_adoption(registry, *, fetcher=None, signals_path: str = DEFAULT_SIGNALS, now=None,
                     limit: int = 5, min_stars: int = 300) -> int:
    """채택 신호가 없는(버즈만 있는) 개념에 이름으로 GitHub 채택을 붙인다 — 'Node.js처럼 언급됐지만 미측정' 구제.

    반환: 채택을 새로 붙인 개념 수. 사이클당 limit 개까지(쿼터). resource(자료)는 건너뜀.
    """
    from tll.concepts.classify import concept_kind
    from tll.signals.github import default_github_fetcher, search_top_repo
    from tll.signals.store import load_signals

    f = fetcher or default_github_fetcher
    have_stock = {s.cid for s in load_signals(signals_path) if s.family == "stock"}
    ds = (now.date() if isinstance(now, datetime) else now).isoformat() if now else datetime.now(timezone.utc).date().isoformat()
    done = 0
    for c in registry.all():
        if done >= limit:
            break
        if c.cid in have_stock:
            continue   # 이미 채택 있음
        if concept_kind(c.canonical, category=getattr(c, "category", "")) == "resource":
            continue   # 자료는 티어 대상 아님
        repo = search_top_repo(c.canonical, f, min_stars=min_stars)
        if not repo:
            continue
        log_many([
            Signal(cid=c.cid, date=ds, source="github", kind="stars", value=float(repo["stars"]), family="stock"),
            Signal(cid=c.cid, date=ds, source="github", kind="forks", value=float(repo["forks"]), family="stock"),
            Signal(cid=c.cid, date=ds, source="github", kind="issues", value=float(repo["issues"]), family="stock"),
        ], path=signals_path)
        if repo.get("created_at"):
            registry.add(c.canonical, now=now, created_at=repo["created_at"])  # 신뢰 나이 보정
        done += 1
    return done
