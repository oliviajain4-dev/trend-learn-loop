"""YouTube 신호 — '대두' 측정. 뜨는 기술일수록 튜토리얼·해설 영상이 쏟아진다.

개념 이름으로 최근(기본 90일) 영상 수를 세어 **주목(buzz, source=youtube)** 신호로 남긴다.
역할: 실무·교육 관심(독립 소스, 가중 0.8). arXiv(후행·연구)·커뮤니티와 합쳐 '여러 곳서 뜨면 진짜' 판정.
YouTube Data API 키(YT_API_KEY)가 있으면 라이브, 없으면 조용히 건너뜀(그래도 파이프라인 안 죽음).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Callable

from tll.signals.models import Signal
from tll.signals.store import DEFAULT_SIGNALS, log_many


def _as_date(x) -> date:
    if isinstance(x, datetime):
        return x.date()
    if isinstance(x, date):
        return x
    return date.fromisoformat(str(x)[:10]) if x else date.today()


def youtube_stats(term: str, fetcher: Callable[[str], dict], *, window_days: int = 90) -> dict:
    """개념명 → {recent}. 최근 영상 수(대두 강도)."""
    data = fetcher(term) or {}
    items = data.get("items") or []
    return {"recent": len(items)}


def default_youtube_fetcher(term: str, *, window_days: int = 90, max_results: int = 50) -> dict:
    """YouTube Data API 검색(키 없으면 빈 dict)."""
    import json
    import urllib.parse
    import urllib.request

    from tll.shared.config import get_key

    key = get_key("YOUTUBE_API_KEY", required=False) or get_key("YT_API_KEY", required=False)
    if not key:
        return {}   # 키 없으면 조용히 건너뜀(파이프라인 안 죽음)
    after = (datetime.now(timezone.utc) - timedelta(days=window_days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    q = urllib.parse.quote(term)
    url = (
        "https://www.googleapis.com/youtube/v3/search?part=snippet&type=video&order=date"
        f"&maxResults={max_results}&publishedAfter={after}&q={q}&key={key}"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "TLL/0.1"})
        with urllib.request.urlopen(req, timeout=10) as r:  # noqa: S310
            return json.loads(r.read().decode("utf-8", "replace"))
    except Exception:  # noqa: BLE001
        return {}


def refresh_youtube(registry, *, concepts=None, fetcher: Callable[[str], dict] | None = None,
                    signals_path: str = DEFAULT_SIGNALS, now=None, max_concepts: int = 10, min_videos: int = 3) -> int:
    """상위 개념들에 YouTube 최근 영상 수를 주목 신호로. 반환: 로깅 수. (쿼터 아껴 max_concepts 제한)"""
    f = fetcher or default_youtube_fetcher
    if concepts is None:
        concepts = list(registry.all())[:max_concepts]
    ds = _as_date(now).isoformat()
    logged = 0
    for c in concepts:
        stt = youtube_stats(c.canonical, f)
        if stt["recent"] < min_videos:
            continue
        log_many([Signal(cid=c.cid, date=ds, source="youtube", kind="youtube_videos",
                         value=float(stt["recent"]), family="buzz")], path=signals_path)
        logged += 1
    return logged
