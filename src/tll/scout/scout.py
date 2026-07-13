"""Scout(정찰) — 실시간 소스를 훑어 '새로 뜬' 트렌드 후보를 뽑는다.

에이전트 작동 순서의 1단계. 순수 결정론(LLM 0):
  1) 실시간 소스 폴링 — HN 프론트페이지(topstories) + GeekNews 최근 피드
  2) TrendCandidate 로 정규화 — 등급(grade_from_domain)·신선도(age_label)·안정 id(content_hash)
  3) 최소 Memory(seen 로그)로 '지난 확인 이후 새 것'만 골라냄

'교과서 감이냐'는 가치 판단은 다음 단계 Triage(에이전트)가 한다 — 여기선 안 섞는다.
출력(ScoutResult.summary)은 ReAct 루프의 '관찰(observation)'로 그대로 쓰인다.

테스트/재현성: 네트워크(폴링 함수)와 '지금(now)'을 주입받아 오프라인 검증이 가능하다.
소스 하나가 실패해도 전체를 죽이지 않는다(빈 결과 + summary.errors 에 정직 노출).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Callable
from urllib.parse import urlparse

from tll.collector.models import compute_content_hash, grade_from_domain
from tll.collector.providers.geeknews import GeekNewsProvider
from tll.collector.rate_limiter import RateLimiter
from tll.collector.robots_guard import RobotsGuard
from tll.collector.trends import fetch_top_stories
from tll.scout.freshness import age_label, unix_to_iso
from tll.scout.models import ScoutResult, TrendCandidate
from tll.scout.seen_store import SeenStore

logger = logging.getLogger(__name__)

DEFAULT_STORE = "data/memory/seen.json"
DEFAULT_SOURCES = ("hackernews", "geeknews", "reddit", "official")
DEFAULT_OFFICIAL_FEEDS = (
    "https://huggingface.co/blog/feed.xml",
    "https://blog.google/technology/ai/rss/",
    "https://openai.com/blog/rss.xml",
    "https://www.anthropic.com/rss.xml",
)


def _hn_candidates(limit: int, now: datetime) -> list[TrendCandidate]:
    feed = fetch_top_stories(limit=limit)
    out: list[TrendCandidate] = []
    for s in feed.stories:
        pub = unix_to_iso(s.time)
        out.append(
            TrendCandidate(
                cid=compute_content_hash(s.link, s.title),
                source="hackernews",
                title=s.title,
                url=s.link,
                domain=s.domain,
                grade=grade_from_domain(s.domain),
                score=s.score,
                comments=s.descendants,
                published_at=pub,
                age_label=age_label(pub, now),
            )
        )
    return out


def _gn_candidates(
    limit: int, now: datetime, rl: RateLimiter, rg: RobotsGuard
) -> list[TrendCandidate]:
    # topic="" → topic_matches 가 True(토큰 없음) → 최근 피드 전체를 후보로.
    docs = GeekNewsProvider().search("", limit=limit, rate_limiter=rl, robots_guard=rg)
    out: list[TrendCandidate] = []
    for d in docs:
        net = urlparse(d.url).netloc
        domain = (net[4:] if net.startswith("www.") else net) or "news.hada.io"
        out.append(
            TrendCandidate(
                cid=compute_content_hash(d.url, d.title),
                source="geeknews",
                title=d.title,
                url=d.url,
                domain=domain,
                grade=d.grade,  # 2 (국내 IT 기관)
                published_at=d.published_at,
                age_label=age_label(d.published_at, now),
            )
        )
    return out


def _reddit_candidates(limit: int, now: datetime, fetcher) -> list[TrendCandidate]:
    """Reddit(r/LocalLLaMA·MachineLearning 등) 상위글 → 후보. fetcher()->JSON(주입가능)."""
    data = fetcher() or {}
    out: list[TrendCandidate] = []
    for ch in (data.get("data", {}).get("children") or [])[:limit]:
        d = ch.get("data", {}) if isinstance(ch, dict) else {}
        title = (d.get("title") or "").strip()
        if not title:
            continue
        url = d.get("url_overridden_by_dest") or d.get("url") or f"https://www.reddit.com{d.get('permalink', '')}"
        cu = d.get("created_utc")
        pub = unix_to_iso(int(cu)) if cu else None
        net = urlparse(url).netloc
        domain = (net[4:] if net.startswith("www.") else net) or "reddit.com"
        out.append(
            TrendCandidate(
                cid=compute_content_hash(url, title),
                source="reddit",
                title=title,
                url=url,
                domain=domain,
                grade=grade_from_domain(domain),
                score=int(d.get("score") or 0),
                comments=int(d.get("num_comments") or 0),
                published_at=pub,
                age_label=age_label(pub, now),
            )
        )
    return out


def default_reddit_fetcher(subreddits=("LocalLLaMA", "MachineLearning"), limit: int = 25) -> dict:
    """라이브 Reddit 공개 top.json 수집(무인증, UA 필요). 실패 소스는 건너뜀."""
    import json
    import urllib.request

    children: list = []
    for sub in subreddits:
        url = f"https://www.reddit.com/r/{sub}/top.json?t=week&limit={limit}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "TLL/0.1 (trend-learn-loop)"})
            with urllib.request.urlopen(req, timeout=10) as r:  # noqa: S310
                data = json.loads(r.read().decode("utf-8", "replace"))
            children += data.get("data", {}).get("children") or []
        except Exception:  # noqa: BLE001
            continue
    return {"data": {"children": children}}


def _official_candidates(limit: int, now: datetime, fetcher) -> list[TrendCandidate]:
    """공식/벤더 발표(RSS) → 후보. '기술이 최초 발표되는 원천'(발견용). fetcher()->[{title,url,published}]."""
    items = fetcher() or []
    out: list[TrendCandidate] = []
    for it in items[:limit]:
        title = (it.get("title") or "").strip()
        if not title:
            continue
        url = it.get("url") or ""
        net = urlparse(url).netloc
        domain = (net[4:] if net.startswith("www.") else net) or "official"
        pub = it.get("published") or None
        out.append(
            TrendCandidate(
                cid=compute_content_hash(url, title),
                source="official",   # 역할=발표원천(자기홍보라 '중요도 독립투표'엔 안 낌)
                title=title,
                url=url,
                domain=domain,
                grade=1,             # 1급(1차 출처)
                score=0,             # 버즈 점수 없음 — 발견 신호(존재)로만
                published_at=pub,
                age_label=age_label(pub, now),
            )
        )
    return out


def default_official_fetcher(feeds=DEFAULT_OFFICIAL_FEEDS, per_feed: int = 8) -> list[dict]:
    """벤더 블로그/뉴스 RSS·Atom 파싱(무인증). 실패 피드는 건너뜀."""
    import re
    import urllib.request

    def _txt(x: str) -> str:
        x = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", x or "", flags=re.S)
        return re.sub(r"<[^>]+>", "", x).strip()

    items: list[dict] = []
    for feed in feeds:
        try:
            req = urllib.request.Request(feed, headers={"User-Agent": "TLL/0.1 (trend-learn-loop)"})
            with urllib.request.urlopen(req, timeout=10) as r:  # noqa: S310
                xml = r.read().decode("utf-8", "replace")
        except Exception:  # noqa: BLE001
            continue
        for b in re.findall(r"<(?:item|entry)\b.*?</(?:item|entry)>", xml, re.S)[:per_feed]:
            mt = re.search(r"<title[^>]*>(.*?)</title>", b, re.S)
            ml = re.search(r'<link[^>]*href="([^"]+)"', b) or re.search(r"<link[^>]*>(.*?)</link>", b, re.S)
            mp = re.search(r"<(?:pubDate|published|updated)[^>]*>(.*?)</", b, re.S)
            if mt:
                items.append({"title": _txt(mt.group(1)), "url": _txt(ml.group(1)) if ml else "",
                              "published": mp.group(1).strip() if mp else None})
    return items


def scout(
    sources: list[str] | None = None,
    *,
    limit_per_source: int = 30,
    store_path: str = DEFAULT_STORE,
    now: datetime | None = None,
    hn_fetch: Callable[[], list[TrendCandidate]] | None = None,
    gn_fetch: Callable[[], list[TrendCandidate]] | None = None,
    reddit_fetch: Callable[[], list[TrendCandidate]] | None = None,
    official_fetch: Callable[[], list[TrendCandidate]] | None = None,
) -> ScoutResult:
    now = now or datetime.now(timezone.utc)
    now_iso = now.isoformat(timespec="seconds")
    sources = sources or list(DEFAULT_SOURCES)
    rl, rg = RateLimiter(), RobotsGuard()

    errors: dict[str, str] = {}
    cands: list[TrendCandidate] = []

    if "hackernews" in sources:
        try:
            cands += (hn_fetch or (lambda: _hn_candidates(limit_per_source, now)))()
        except Exception as e:  # 한 소스 실패가 전체를 죽이지 않게
            logger.warning("Scout HN 실패: %s", e)
            errors["hackernews"] = str(e)
    if "geeknews" in sources:
        try:
            cands += (gn_fetch or (lambda: _gn_candidates(limit_per_source, now, rl, rg)))()
        except Exception as e:
            logger.warning("Scout GeekNews 실패: %s", e)
            errors["geeknews"] = str(e)
    if "reddit" in sources:
        try:
            cands += (reddit_fetch or (lambda: _reddit_candidates(limit_per_source, now, default_reddit_fetcher)))()
        except Exception as e:
            logger.warning("Scout Reddit 실패: %s", e)
            errors["reddit"] = str(e)
    if "official" in sources:
        try:
            cands += (official_fetch or (lambda: _official_candidates(limit_per_source, now, default_official_fetcher)))()
        except Exception as e:
            logger.warning("Scout Official 실패: %s", e)
            errors["official"] = str(e)

    # 중복 제거(소스 간 동일 링크) → 순위: 인기(score)↓, 동점이면 최신↓
    seen_cid: set[str] = set()
    deduped: list[TrendCandidate] = []
    for c in cands:
        if c.cid in seen_cid:
            continue
        seen_cid.add(c.cid)
        deduped.append(c)
    deduped.sort(key=lambda c: (c.score, c.published_at or ""), reverse=True)

    # 신규성 판단 + first_seen 박제 (최소 Memory)
    store = SeenStore(store_path)
    prev_last_check = store.last_check
    new_list: list[TrendCandidate] = []
    for c in deduped:
        was_new = store.is_new(c.cid)
        c.first_seen = store.first_seen_of(c.cid) or now_iso
        store.mark_seen(c.cid, first_seen=c.first_seen, title=c.title, source=c.source)
        if was_new:
            new_list.append(c)
    store.commit(now=now_iso)

    per_source: dict[str, int] = {}
    for c in deduped:
        per_source[c.source] = per_source.get(c.source, 0) + 1

    summary = {
        "collected_at": now_iso,
        "prev_last_check": prev_last_check,
        "polled": len(deduped),
        "new": len(new_list),
        "per_source": per_source,
        "errors": errors,
    }
    return ScoutResult(
        collected_at=now_iso,
        candidates=deduped,
        new_candidates=new_list,
        summary=summary,
    )


def _fmt(c: TrendCandidate) -> str:
    age = f" · {c.age_label}" if c.age_label else ""
    sc = f" · ▲{c.score}" if c.score else ""
    return f"[{c.source} · {c.grade}급{sc}{age}] {c.title}\n    {c.url}"


if __name__ == "__main__":  # 사용자 머신에서 실제 폴링 확인용: python -m tll.scout.scout
    res = scout()
    s = res.summary
    print(
        f"폴링 {s['polled']}건 · 신규 {s['new']}건 · 소스 {s['per_source']} · 이전확인 {s['prev_last_check']}"
    )
    if s.get("errors"):
        print("에러:", s["errors"])
    print("\n=== 새로 뜬 것 (최대 15) ===")
    for c in res.new_candidates[:15]:
        print(_fmt(c))
