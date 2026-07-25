"""Tracker(추적) — 선별 주제의 공식 문서 '본문'을 실제로 가져온다. (에이전트 순서 3단계)

- 후보의 링크를 따라가 본문 수집(그 '검증 반쪽' 구멍 메우기).
- 등급: 원천 근접도(1차/2차/3차) + 성격 태그(grading.classify_source).
- robots·rate limit 준수. 실패·비HTML·공식링크없음·본문빈약은 지어내지 않고 status/note 로 정직 노출.

경계: '어느 소스를 볼지'는 Triage(에이전트)가 이미 골랐다. 여기 fetch·추출·등급은 결정론.
테스트/재현: fetcher·robots·rate_limiter·now 주입 → 오프라인 검증(네트워크 0).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Callable

import requests

from tll.collector.rate_limiter import RateLimiter
from tll.collector.robots_guard import RobotsGuard
from tll.scout.models import TrendCandidate
from tll.tracker.extract import extract_text
from tll.tracker.grading import classify_source, domain_of
from tll.tracker.models import TrackedDoc, TrackResult

logger = logging.getLogger(__name__)

_UA = "TLLCollector/0.1"
_TIMEOUT = 15
_HN = "news.ycombinator.com"
_THIN = 200  # 본문이 이보다 짧으면 'JS 렌더 가능' 경고

# fetcher: url -> (status_code, content_type, text)
Fetcher = Callable[[str], "tuple[int, str, str]"]


def _default_fetcher(url: str) -> tuple[int, str, str]:
    r = requests.get(url, headers={"User-Agent": _UA}, timeout=_TIMEOUT)
    return r.status_code, r.headers.get("Content-Type", ""), r.text


def track(
    candidates: list[TrendCandidate],
    *,
    max_docs: int = 5,
    rate_limiter: RateLimiter | None = None,
    robots_guard: RobotsGuard | None = None,
    fetcher: Fetcher | None = None,
    max_chars: int = 8000,
    now: datetime | None = None,
) -> TrackResult:
    rl = rate_limiter or RateLimiter()
    rg = robots_guard or RobotsGuard()
    fetch = fetcher or _default_fetcher
    now = now or datetime.now(timezone.utc)
    now_iso = now.isoformat(timespec="seconds")

    docs: list[TrackedDoc] = []
    for c in candidates[:max_docs]:
        grade, nature, tier = classify_source(c.url)
        dom = domain_of(c.url) or c.domain
        doc = TrackedDoc(
            cid=c.cid,
            topic_title=c.title,
            url=c.url,
            domain=dom,
            grade=grade,
            nature=nature,
            tier_label=tier,
            status="ok",
            published_at=c.published_at,
            collected_at=now_iso,
        )
        if nature == "레포":
            doc.note = "레포 출처 — 이 기술의 '공식' 레포인지(3자 여부)는 미확인."

        # 공식 링크 없음(HN 토론만) → 지어내지 않고 표기
        if dom == _HN:
            doc.status = "no_official"
            doc.note = "HN 토론만 있고 외부 공식 링크 없음 → 공식 자료 부족."
            docs.append(doc)
            continue

        if not rg.allowed(c.url):
            doc.status = "blocked_robots"
            doc.note = "robots.txt Disallow → 수집 안 함."
            docs.append(doc)
            continue

        rl.wait(dom)
        try:
            code, ctype, text = fetch(c.url)
        except Exception as e:  # 네트워크 실패가 전체를 죽이지 않게
            doc.status = "fetch_error"
            doc.error = str(e)
            docs.append(doc)
            continue

        if code >= 400:
            doc.status = "fetch_error"
            doc.error = f"HTTP {code}"
            docs.append(doc)
            continue

        is_html = "html" in ctype.lower() or "<html" in text[:500].lower()
        if not is_html:
            if "text/plain" in ctype.lower():
                doc.body_text = text[:max_chars]  # 평문(예: IERS 게시)은 그대로
            else:
                doc.status = "non_html"
                doc.note = f"본문 추출 불가(Content-Type: {ctype or '미상'})."
            docs.append(doc)
            continue

        title, body = extract_text(text, max_chars=max_chars)
        doc.title = title
        doc.body_text = body
        if not body:
            doc.status = "non_html"
            doc.note = "본문 텍스트를 추출하지 못함."
        elif len(body) < _THIN:
            doc.note = (doc.note + " " if doc.note else "") + "본문 빈약 — JS 렌더링 페이지일 수 있음."
        docs.append(doc)

    by_grade: dict[int, int] = {}
    by_status: dict[str, int] = {}
    for d in docs:
        by_grade[d.grade] = by_grade.get(d.grade, 0) + 1
        by_status[d.status] = by_status.get(d.status, 0) + 1
    summary = {
        "tracked": len(docs),
        "ok": by_status.get("ok", 0),
        "by_grade": by_grade,
        "by_status": by_status,
        "collected_at": now_iso,
    }
    return TrackResult(docs=docs, summary=summary)


def _run_cli() -> None:  # 사용자 머신 데모: python -m tll.tracker.tracker
    from tll.scout.scout import scout
    from tll.triage.triage import triage

    res = scout()
    print(f"[Scout] 폴링 {res.summary['polled']} · 신규 {res.summary['new']}")
    tr = triage(res.candidates, top_n=5)
    if tr.summary.get("mode") == "error":
        print("[Triage] 실패:", tr.summary.get("error"))
        return
    print(f"[Triage] 교과서 감 {tr.summary['kept']} → 선별 {len(tr.selected)}")
    tk = track(tr.selected)
    s = tk.summary
    print(
        f"[Tracker] 추적 {s['tracked']} · 본문확보 {s['ok']} · 등급 {s['by_grade']} · 상태 {s['by_status']}\n"
    )
    for d in tk.docs:
        print(f"[{d.tier_label}·{d.domain}] {d.topic_title}")
        line = f"    상태={d.status} · 본문 {len(d.body_text)}자"
        if d.note:
            line += f" · ⚠️{d.note}"
        print(line)
        print(f"    {d.url}")
        if d.body_text:
            print(f"    발췌: {d.body_text[:140]}…")


if __name__ == "__main__":
    _run_cli()
