"""비용 사용량 로깅·집계 테스트 — PYTHONPATH=src python tests/test_usage.py"""

from __future__ import annotations

import os
import sys
import tempfile
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from tll.cost.usage import (  # noqa: E402
    log_usage,
    monthly_report,
    paid_summary,
)

NOW = datetime(2026, 7, 16, tzinfo=timezone.utc)   # 목요일(같은 주: 월 7/13 ~ 일 7/19)
checks = 0


def ok(cond, msg):
    global checks
    assert cond, "FAIL: " + msg
    checks += 1


with tempfile.TemporaryDirectory() as d:
    path = os.path.join(d, "usage.jsonl")

    # ── log_usage 왕복 ──
    log_usage("gemini", "gemini-flash-lite-latest", 1000, 200, stage="집필",
              path=path, now=datetime(2026, 7, 16, 9, 0, tzinfo=timezone.utc))          # 오늘, gemini(무료)
    log_usage("anthropic", "claude-sonnet-5", 2000, 500, stage="교차검증",
              path=path, now=datetime(2026, 7, 16, 10, 0, tzinfo=timezone.utc))         # 오늘, anthropic
    log_usage("anthropic", "claude-sonnet-5", 3000, 800, stage="교차검증",
              path=path, now=datetime(2026, 7, 15, 9, 0, tzinfo=timezone.utc))          # 어제(같은 주 — 수요일)
    log_usage("anthropic", "claude-sonnet-5", 1500, 300, stage="",
              path=path, now=datetime(2026, 6, 20, 9, 0, tzinfo=timezone.utc))          # 저번달(주·달 밖)

    # ── monthly_report 기존 동작 유지 ──
    rep = monthly_report(path=path, month="2026-07")
    ok(rep["total"]["calls"] == 3, "7월 전체 호출수(2제공자 합, 저번달 제외)")
    ok(rep["total"]["paid_cost_usd"] == 0.0, "paid_provider 안 주면 실제청구 0(무료/유료 구분 안 함)")

    # ── monthly_report(paid_provider=...) — 무료 모델은 정가는 잡히되 실제청구는 0 ──
    rep2 = monthly_report(path=path, month="2026-07", paid_provider="anthropic")
    gemini_row = next(r for r in rep2["by_model"] if r["model"] == "gemini-flash-lite-latest")
    claude_row = next(r for r in rep2["by_model"] if r["model"] == "claude-sonnet-5")
    ok(gemini_row["provider"] == "gemini", "모델별 행에 provider 노출")
    ok(gemini_row["cost_usd"] > 0, "gemini 도 정가(참고용)는 계산됨")
    ok(gemini_row["paid_cost_usd"] == 0.0, "gemini(무료)는 실제청구 0")
    ok(claude_row["paid_cost_usd"] == claude_row["cost_usd"], "anthropic(유료)는 실제청구=정가")
    ok(rep2["total"]["paid_cost_usd"] < rep2["total"]["cost_usd"],
       "전체 실제청구 < 전체 정가합계(무료분 만큼 차이나야 정상)")

    # ── paid_summary: anthropic 만, 오늘/이번주/이번달 ──
    s = paid_summary(path, paid_provider="anthropic", now=NOW)
    ok(s["provider"] == "anthropic", "유료 프로바이더 표시")
    ok(s["today"]["calls"] == 1, "오늘(7/16) anthropic 호출 1건(gemini 는 제외)")
    ok(s["week"]["calls"] == 2, "이번주(월 7/13~) anthropic 호출 2건(오늘+어제 수요일)")
    ok(s["month"]["calls"] == 2, "이번달(7월) anthropic 호출 2건(6월 것 제외)")
    ok(s["today"]["cost_usd"] > 0, "오늘 비용 > 0")
    ok(s["week"]["cost_usd"] >= s["today"]["cost_usd"], "이번주 비용 >= 오늘 비용(누적)")
    ok(s["month"]["cost_usd"] >= s["week"]["cost_usd"], "이번달 비용 >= 이번주 비용(누적)")

    # ── stage 별 집계는 구간마다 따로(오늘/주/월 탭 각각 자기 것만 보여줘야 하므로) ──
    by_stage_today = {b["stage"]: b for b in s["today"]["by_stage"]}
    by_stage_month = {b["stage"]: b for b in s["month"]["by_stage"]}
    ok("교차검증" in by_stage_today, "오늘 탭에도 교차검증 stage 집계됨")
    ok(by_stage_today["교차검증"]["calls"] == 1, "오늘 탭은 오늘 것만(1건)")
    ok(by_stage_month["교차검증"]["calls"] == 2, "이번달 탭은 오늘+어제(2건)")

    # ── 실제 쓰인 모델명(정확히 뭘 썼는지) ──
    ok(s["month"]["models"] == ["claude-sonnet-5"], "이번달 실제 사용 모델명 노출")

    # ── 전체 누적(all_time) — 6월 것까지 포함해서 더 커야 함 ──
    ok(s["all_time"]["calls"] == 3, "전체 누적은 6월 것까지 포함(3건)")
    ok(s["all_time"]["cost_usd"] >= s["month"]["cost_usd"], "누적 비용 >= 이번달 비용")

    # ── gemini 는 유료(anthropic) 집계에 절대 안 섞임 ──
    ok(all(r["calls"] > 0 for r in (s["today"], s["week"], s["month"])), "anthropic 기록만 정확히 집계")

    # ── stage 없는(과거) 기록은 '기타(이전 기록)' 로 정직하게 표시 ──
    s2 = paid_summary(path, paid_provider="anthropic", now=datetime(2026, 6, 25, tzinfo=timezone.utc))
    by_stage2 = {b["stage"] for b in s2["month"]["by_stage"]}
    ok("기타(이전 기록)" in by_stage2, "stage 미기록 과거 데이터는 '기타(이전 기록)'")

    # ── 빈 로그 ──
    empty_path = os.path.join(d, "empty.jsonl")
    s3 = paid_summary(empty_path, now=NOW)
    ok(s3["today"]["calls"] == 0 and s3["today"]["cost_usd"] == 0.0, "기록 없으면 전부 0(에러 아님)")
    ok(s3["all_time"]["models"] == [], "빈 로그는 모델 목록도 빈 리스트")

print(f"OK - {checks} checks passed")
