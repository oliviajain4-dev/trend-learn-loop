"""Loop — ReAct 루프 + 30분 스케줄러. 전체 조각을 감싸 자율 사이클로 돌린다.

run_cycle: 한 사이클(관찰→판단→행동). 후보별로 Track→Read 하고 Reader의 결정에 따라
  - 충분(proceed) → Author(+Memory 대조)→Fact-Check→Memory 기억→저장.
  - 부족(collect_more, "더 찾자") → lesson 기록하고 다음 후보로(bounded 재수집).
안전장치: target(사이클당 발행 상한=예산)·max_attempts(시도 상한=비용캡)·무진전 가드.
run_forever: interval_minutes(기본 30)마다 run_cycle. only_new=True 로 '새 것만'.

테스트/재현: candidates·llm_call·fetcher·rate_limiter·robots_guard·paths 주입 → 완전 오프라인.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime

from tll.author.author import write_textbook
from tll.factcheck.factcheck import apply, check_textbook
from tll.loop.models import CycleResult
from tll.memory.memory import (
    DEFAULT_KB,
    DEFAULT_LESSONS,
    contrast_context,
    record_lesson,
    remember_textbook,
)
from tll.present.html import save_dashboard
from tll.present.store import DEFAULT_DIR, load_records, save_textbook
from tll.reader.reader import read
from tll.scout.scout import DEFAULT_STORE, scout
from tll.tracker.tracker import track
from tll.triage.triage import triage

logger = logging.getLogger(__name__)


def run_cycle(
    *,
    target: int = 3,
    max_attempts: int = 6,
    top_n: int = 5,
    only_new: bool = False,
    scout_sources=None,
    seen_path: str | None = None,
    kb_path: str | None = None,
    lessons_path: str | None = None,
    textbook_dir: str | None = None,
    dashboard_path: str = "data/dashboard.html",
    llm_call=None,
    fetcher=None,
    rate_limiter=None,
    robots_guard=None,
    candidates=None,
    now: datetime | None = None,
) -> CycleResult:
    """한 사이클 실행. 관찰→판단→행동, 안전장치 안에서."""
    kb_path = kb_path or DEFAULT_KB
    lessons_path = lessons_path or DEFAULT_LESSONS
    textbook_dir = textbook_dir or DEFAULT_DIR
    seen_path = seen_path or DEFAULT_STORE

    # 1) 후보 (Scout — 새 것만/전체)
    if candidates is None:
        res = scout(sources=scout_sources, store_path=seen_path, now=now)
        cands = res.new_candidates if only_new else res.candidates
        cand_total = res.summary["polled"]
    else:
        cands = list(candidates)
        cand_total = len(cands)

    # 2) Triage (에이전트: 교과서 감 선별)
    tr = triage(cands, top_n=top_n, llm_call=llm_call)
    selected = tr.selected
    cat_by_cid = {d.cid: d.category for d in tr.decisions}

    published: list[dict] = []
    lessons_out: list[dict] = []
    decisions: list[dict] = []
    attempts = 0

    for cand in selected:
        if attempts >= max_attempts or len(published) >= target:  # 예산·상한
            break
        attempts += 1

        # 3) Track → Read (ReAct 관찰·판단)
        tk = track([cand], fetcher=fetcher, rate_limiter=rate_limiter, robots_guard=robots_guard, now=now)
        doc = tk.docs[0]
        verdict = read([doc], llm_call=llm_call).verdicts[0]
        decisions.append({"topic": cand.title, "next_action": verdict.next_action, "mode": verdict.mode})

        if verdict.sufficient and doc.status == "ok":
            # 4) 집필(+Memory 대조) → 검증 → 기억 → 저장
            hint = contrast_context(cand.title, kb_path=kb_path)
            book = write_textbook(doc, contrast_hint=hint, llm_call=llm_call)
            report = check_textbook(book)
            verified = apply(book, report)
            remember_textbook(verified, category=cat_by_cid.get(cand.cid, ""), kb_path=kb_path, now=now)
            save_textbook(verified, metrics=report.metrics, out_dir=textbook_dir, now=now)
            published.append(
                {
                    "topic": cand.title,
                    "support_rate": report.metrics.get("support_rate", 0.0),
                    "status": verified.status,
                }
            )
        else:
            # "더 찾자" — 이번엔 다음 후보로 넘기고 교훈 기록(Reflexion)
            reason = verdict.missing or verdict.reason or doc.status
            record_lesson(cand.title, "insufficient", reason, log_path=lessons_path, now=now)
            lessons_out.append({"topic": cand.title, "reason": reason})

    # 5) Dashboard 산출(누적 교과서 전체)
    save_dashboard(load_records(textbook_dir), dashboard_path)

    summary = {
        "candidates": cand_total,
        "selected": len(selected),
        "attempts": attempts,
        "published": len(published),
        "lessons": len(lessons_out),
        "target_reached": len(published) >= target,
        "no_progress": attempts > 0 and len(published) == 0,
    }
    return CycleResult(published=published, lessons=lessons_out, decisions=decisions, summary=summary)


def run_forever(*, interval_minutes: int = 30, max_cycles: int | None = None, **cycle_kwargs) -> None:
    """interval_minutes 마다 run_cycle. only_new=True(새 것만). Ctrl-C 로 중단."""
    n = 0
    while True:
        try:
            res = run_cycle(only_new=True, **cycle_kwargs)
            s = res.summary
            print(
                f"[cycle {n + 1}] 후보 {s['candidates']} · 선별 {s['selected']} · "
                f"발행 {s['published']} · 더찾자 {s['lessons']}"
            )
        except Exception as e:  # 한 사이클 실패가 스케줄러를 죽이지 않게
            logger.warning("cycle 실패: %s", e)
            print(f"[cycle {n + 1}] 실패: {e}")
        n += 1
        if max_cycles is not None and n >= max_cycles:
            break
        time.sleep(interval_minutes * 60)


def _run_cli() -> None:  # 사용자 머신: python -m tll.loop.loop [--watch]
    import os
    import sys

    if "--watch" in sys.argv:
        print("30분마다 자동 반복 시작 (Ctrl-C 로 중단)")
        run_forever(interval_minutes=30, target=3)
        return

    res = run_cycle(only_new=False, target=3)
    s = res.summary
    print(
        f"[1 사이클] 후보 {s['candidates']} · 선별 {s['selected']} · 시도 {s['attempts']} · "
        f"발행 {s['published']} · 더찾자 {s['lessons']}\n"
    )
    for p in res.published:
        print(f"  ✅ {p['topic']} — 충실도 {int(p['support_rate'] * 100)}% ({p['status']})")
    for les in res.lessons:
        print(f"  🔁 {les['topic']} — 더 찾자 ({les['reason'][:40]})")
    if s["no_progress"]:
        print("  (무진전 가드: 이번엔 발행 0 — lessons 기록됨)")
    print(f"\n대시보드: {os.path.abspath('data/dashboard.html')}")
    print("자동 30분 반복: python -m tll.loop.loop --watch")


if __name__ == "__main__":
    _run_cli()
