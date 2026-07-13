"""신호 로그 테스트 — PYTHONPATH=src python tests/test_signals.py"""

from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from tll.signals import Signal, family_of, load_signals, log_signal, signals_for  # noqa: E402

checks = 0


def ok(cond, msg):
    global checks
    assert cond, "FAIL: " + msg
    checks += 1


# 1) family_of 매핑
ok(family_of("stars") == "stock", "stars=stock")
ok(family_of("hn_points") == "buzz", "hn_points=buzz")
ok(family_of("무슨신호") == "buzz", "미지 기본=buzz")

with tempfile.TemporaryDirectory() as d:
    p = os.path.join(d, "signals.jsonl")
    # 2) log → load 왕복
    log_signal("langchain", "github", "stars", 120, date="2026-07-10", path=p)
    log_signal("langchain", "hn", "hn_points", 240, date="2026-07-10", path=p)
    log_signal("mcp", "github", "forks", 33, date="2026-07-11", path=p)
    rows = load_signals(p)
    ok(len(rows) == 3, "3개 적재")
    s0 = rows[0]
    ok(s0.cid == "langchain" and s0.kind == "stars" and s0.value == 120.0 and s0.family == "stock", "레코드 정확")
    # 3) family 자동 태깅
    ok(rows[1].family == "buzz", "hn_points 자동 buzz")
    # 4) cid 필터
    ok(len(signals_for("langchain", p)) == 2 and len(signals_for("mcp", p)) == 1, "cid 필터")
    # 5) append 누적
    log_signal("mcp", "github", "stars", 500, date="2026-07-11", path=p)
    ok(len(load_signals(p)) == 4, "append 누적")
    # 6) 손상된 줄 스킵
    with open(p, "a", encoding="utf-8") as f:
        f.write("이건 JSON 아님\n")
    ok(len(load_signals(p)) == 4, "손상 줄 스킵")

# 7) 없는 파일 → []
ok(load_signals("/tmp/nope_tll_signals.jsonl") == [], "없는 파일 → []")
# 8) date 미지정 시 now 날짜
r = Signal.from_dict({"cid": "x", "date": "2026-01-01", "source": "s", "kind": "stars", "value": 1})
ok(r.family == "stock", "from_dict family 추론")

print(f"{checks} checks passed")
