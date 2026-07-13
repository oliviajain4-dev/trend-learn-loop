"""주목·채택 2시계열 계산 테스트 — PYTHONPATH=src python tests/test_score.py"""

from __future__ import annotations

import os
import sys
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from tll.rank import score_concept  # noqa: E402
from tll.signals import Signal, family_of  # noqa: E402

NOW = date(2026, 7, 15)
checks = 0


def ok(cond, msg):
    global checks
    assert cond, "FAIL: " + msg
    checks += 1


def near(a, b, msg, tol=0.01):
    ok(abs(a - b) < tol, f"{msg} ({a} vs {b})")


def mk(cid, d, kind, value):
    return Signal(cid=cid, date=d, source="t", kind=kind, value=float(value), family=family_of(kind))


# 주목 감쇠: 오늘 100 + 6일전 100(hl3 → 0.25*100) = 125
dec = score_concept([mk("a", "2026-07-15", "mention", 100), mk("a", "2026-07-09", "mention", 100)], now=NOW)
near(dec.attention, 125.0, "주목 감쇠합")
ok(dec.adoption == 0.0 and dec.rising_kinds == 0 and dec.stock_kinds == 0, "버즈만 → 채택 0")
ok(dec.recurrence == 2, "recurrence=distinct 날짜")

# A) 호랑이 재료: 버즈 + 스타·포크·이슈 상승(참여 동반)
A = score_concept([
    mk("lc", "2026-07-15", "mention", 200),
    mk("lc", "2026-06-16", "stars", 100), mk("lc", "2026-07-02", "stars", 140), mk("lc", "2026-07-14", "stars", 200),
    mk("lc", "2026-07-10", "forks", 20), mk("lc", "2026-07-12", "issues", 5),
], now=NOW)
near(A.attention, 200.0, "A 주목")
near(A.adoption, 0.5284, "A 채택=참여중심 포화정규화(별 200·포크20·이슈5)")
ok(A.growth_measured and A.corrob_kinds == 3 and abs(A.adoption_mag - 42.5) < 0.01, "A 성장측정됨·독립3·크기42.5(별 강등)")
near(A.adoption_growth, 100.0, "A 성장(베이스라인 있는 stars 만)")
ok(A.rising_kinds == 1 and A.stock_kinds == 3, "A: 성장 측정된 신호만 rising(첫관측 규칙)")
ok(A.fake_flag is False, "A 가짜 아님(참여 동반 상승)")

# B) 버즈 스파이크만
B = score_concept([mk("fly", "2026-07-15", "mention", 300)], now=NOW)
ok(B.adoption == 0.0 and B.rising_kinds == 0 and B.stock_kinds == 0, "B 채택 전무")

# C) 채택 높고 최근 평탄
C = score_concept([mk("sql", "2026-05-01", "stars", 5000), mk("sql", "2026-06-01", "stars", 5000)], now=NOW)
near(C.adoption, 5.882, "C 채택=별만 5000(별 0.1 강등 → 낮음)")
ok(C.corrob_kinds == 1 and C.growth_measured, "C 단일지표·성장측정됨")
ok(C.adoption_growth == 0.0 and C.stock_kinds == 1, "C 평탄·단일지표")

# D) 가짜: 스타↑인데 '있는' 참여(포크·이슈) 정체 → fake True
D = score_concept([
    mk("x", "2026-06-16", "stars", 100), mk("x", "2026-07-14", "stars", 300),
    mk("x", "2026-06-16", "forks", 10), mk("x", "2026-07-14", "forks", 10),
    mk("x", "2026-06-16", "issues", 3), mk("x", "2026-07-14", "issues", 3),
], now=NOW)
ok(D.fake_flag is True, "D 가짜(참여 정체)")
ok(D.rising_kinds == 1 and D.stock_kinds == 3, "D 스타만 상승")

# D2) 스타만 있고 참여 데이터 없음 → 가짜 아님(없음≠정체)
D2 = score_concept([mk("y", "2026-06-16", "stars", 100), mk("y", "2026-07-14", "stars", 300)], now=NOW)
ok(D2.fake_flag is False, "D2 참여 부재 시 가짜 판단 보류")
ok(D2.stock_kinds == 1, "D2 단일지표")

# E) 빈 입력
E = score_concept([], now=NOW)
ok(E.n_signals == 0 and E.adoption == 0.0 and E.stock_kinds == 0, "E 빈 입력 안전")

print(f"{checks} checks passed")
