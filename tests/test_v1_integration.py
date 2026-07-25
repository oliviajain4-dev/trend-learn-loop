"""v1 통합 — 레지스트리 → 신호로그 → 점수 → 티어 end-to-end. PYTHONPATH=src python tests/test_v1_integration.py"""

from __future__ import annotations

import os
import sys
import tempfile
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from tll.concepts import ConceptRegistry  # noqa: E402
from tll.rank import assign_tier, score_concept  # noqa: E402
from tll.signals import log_signal, signals_for  # noqa: E402

NOW = date(2026, 7, 15)
checks = 0


def ok(cond, msg):
    global checks
    assert cond, "FAIL: " + msg
    checks += 1


with tempfile.TemporaryDirectory() as d:
    sig = os.path.join(d, "signals.jsonl")
    reg = ConceptRegistry()

    # 1) 개념 등록 (신규 → provisional)
    r = reg.resolve_or_add("LangGraph", now=NOW)
    cid = r.cid
    ok(r.matched is False and reg.get(cid).status == "provisional", "신규 개념 provisional")

    # 2) 신호 축적: 주목(HN) + 채택(스타·포크·이슈 상승)
    log_signal(cid, "hn", "hn_points", 200, date="2026-07-15", path=sig)
    log_signal(cid, "github", "stars", 40000, date="2026-06-16", path=sig)
    log_signal(cid, "github", "stars", 60000, date="2026-07-14", path=sig)
    log_signal(cid, "github", "forks", 8000, date="2026-07-10", path=sig)
    log_signal(cid, "github", "issues", 300, date="2026-07-12", path=sig)

    # 3) 점수 → 티어
    sc = score_concept(signals_for(cid, sig), now=NOW)
    tr = assign_tier(sc)
    ok(sc.stock_kinds == 3 and sc.adoption_growth == 20000.0, "채택 3종 관측 · 성장은 베이스라인 있는 stars")
    ok(tr.tier == "tiger", "조립 결과 = 호랑이(높은 채택+상승+화제)")
    ok(tr.provisional is False, "재등장 충분 → 확정")

    # 4) 두 번째 개념: 버즈만 → 호랑이 아님
    r2 = reg.resolve_or_add("반짝툴", now=NOW)
    log_signal(r2.cid, "hn", "hn_points", 300, date="2026-07-15", path=sig)
    tr2 = assign_tier(score_concept(signals_for(r2.cid, sig), now=NOW))
    ok(tr2.tier in ("cheetah", "mayfly") and tr2.tier != "tiger", "버즈만 → 치타/하루살이")

    # 5) 레지스트리·신호 영속 왕복
    reg.save(os.path.join(d, "reg.json"))
    ok(len(ConceptRegistry.load(os.path.join(d, "reg.json"))) == 2, "레지스트리 영속")

print(f"{checks} checks passed")
