"""GitHub 채택 신호 — repo URL → stars/forks/issues 스냅샷(축적형 Signal).

fetcher 주입(오프라인/테스트 가능). 실제 실행 시 fetcher 가 GitHub API JSON(dict)을 준다.
값은 '누적 스냅샷'으로 기록한다(score_concept 이 그렇게 가정).
"""

from __future__ import annotations

import re
from datetime import date, datetime, timezone
from typing import Callable

from tll.signals.models import Signal

_RESERVED = {"orgs", "sponsors", "features", "about", "topics", "collections", "marketplace", "settings"}
_MAP = {"stargazers_count": "stars", "forks_count": "forks", "open_issues_count": "issues"}


def parse_repo(url: str) -> str | None:
    """github.com/owner/repo → 'owner/repo' (아니면 None)."""
    m = re.search(r"github\.com/([^/\s]+)/([^/\s#?]+)", url or "")
    if not m:
        return None
    owner, repo = m.group(1), re.sub(r"\.git$", "", m.group(2))
    if owner.lower() in _RESERVED:
        return None
    return f"{owner}/{repo}"


def api_url(repo: str) -> str:
    return f"https://api.github.com/repos/{repo}"


def github_signals(url: str, cid: str, *, fetcher: Callable[[str], dict], now=None, source: str = "github") -> list[Signal]:
    """repo URL → [Signal]. fetcher(api_url)->dict. github repo 아니거나 데이터 없으면 []."""
    repo = parse_repo(url)
    if not repo:
        return []
    data = fetcher(api_url(repo)) or {}
    d = now or datetime.now(timezone.utc)
    ds = (d.date() if isinstance(d, datetime) else d if isinstance(d, date) else date.fromisoformat(str(d))).isoformat()
    out: list[Signal] = []
    for key, kind in _MAP.items():
        v = data.get(key)
        if v is not None:
            out.append(Signal(cid=cid, date=ds, source=source, kind=kind, value=float(v), family="stock"))
    return out


def default_github_fetcher(url: str, *, timeout: float = 6.0) -> dict:
    """실행용 기본 fetcher — GitHub API 를 stdlib 로 호출. 실패 시 {} (사이클 안 죽음)."""
    import json
    import urllib.request

    try:
        req = urllib.request.Request(
            url, headers={"Accept": "application/vnd.github+json", "User-Agent": "TLL"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310
            return json.loads(r.read().decode("utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def github_readme(full_name: str, text_fetcher, *, max_chars: int = 2500) -> str:
    """저장소 README 원문(raw)을 가져와 앞부분만. text_fetcher(url)->str. 실패는 ''."""
    if not full_name:
        return ""
    for branch in ("HEAD", "main", "master"):
        url = f"https://raw.githubusercontent.com/{full_name}/{branch}/README.md"
        try:
            t = text_fetcher(url) or ""
        except Exception:  # noqa: BLE001
            t = ""
        if t and t.strip():
            return t.strip()[:max_chars]
    return ""


def search_top_repo(name: str, fetcher, *, min_stars: int = 300) -> dict | None:
    """이름으로 GitHub 저장소 검색 → 이름이 매칭되는 최상위(별순). 없으면 None.

    'Node.js·PgBouncer 처럼 언급만 되고 채택이 0'인 개념에 실제 별·포크를 붙여주기 위함.
    엉뚱한 저장소 방지: 정규화한 개념명이 full_name 에 들어가야 채택.
    """
    import urllib.parse
    q = urllib.parse.quote(f"{name} sort:stars")
    url = f"https://api.github.com/search/repositories?q={q}&sort=stars&order=desc&per_page=5"
    data = fetcher(url) or {}
    norm = re.sub(r"[^a-z0-9]", "", (name or "").lower())
    if not norm:
        return None
    for it in data.get("items") or []:
        full = re.sub(r"[^a-z0-9]", "", (it.get("full_name") or "").lower())
        stars = int(it.get("stargazers_count") or 0)
        if stars >= min_stars and norm in full:
            return {"full_name": it.get("full_name"), "stars": stars,
                    "forks": int(it.get("forks_count") or 0), "issues": int(it.get("open_issues_count") or 0),
                    "created_at": str(it.get("created_at") or "")}
    return None
