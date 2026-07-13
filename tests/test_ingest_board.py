"""기록기 + 티어 보드 테스트 — PYTHONPATH=src python tests/test_ingest_board.py"""

from __future__ import annotations

import os
import sys
import tempfile
from datetime import date
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from tll.concepts import ConceptRegistry  # noqa: E402
from tll.rank import build_board  # noqa: E402
from tll.signals import signals_for  # noqa: E402
from tll.signals.ingest import ingest_candidate  # noqa: E402

NOW = date(2026, 7, 15)
checks = 0


def ok(cond, msg):
    global checks
    assert cond, "FAIL: " + msg
    checks += 1


def gh(u):
    return {"stargazers_count": 50000, "forks_count": 8000, "open_issues_count": 300}


with tempfile.TemporaryDirectory() as d:
    sig = os.path.join(d, "signals.jsonl")
    reg = ConceptRegistry()

    # 후보: HN 점수+댓글 + github URL → 버즈 + 채택 신호 다 로깅
    cand = SimpleNamespace(title="Show HN: LangGraph", url="https://github.com/langchain-ai/langgraph",
                           source="hackernews", score=180, comments=42)
    cid = ingest_candidate(cand, registry=reg, github_fetcher=gh,
                           llm_call=lambda p, s: "LangGraph", signals_path=sig, now=NOW)
    ok(reg.get(cid).canonical == "LangGraph", "개념 resolve")
    kinds = {s.kind for s in signals_for(cid, sig)}
    ok(kinds == {"hn_points", "hn_comments", "stars", "forks", "issues"}, "버즈+채택 5신호 로깅")

    # 같은 개념 다시 (다른 표기) → 같은 cid, 신호 누적
    cand2 = SimpleNamespace(title="langgraph is great", url="", source="reddit", score=90, comments=0)
    cid2 = ingest_candidate(cand2, registry=reg, llm_call=lambda p, s: "langgraph", signals_path=sig, now=NOW)
    ok(cid2 == cid, "표기 달라도 같은 개념")
    ok(len(reg) == 1, "중복 개념 안 생김")

    # 두 번째 개념: 버즈만
    cand3 = SimpleNamespace(title="반짝툴", url="https://blog.x/p", source="hackernews", score=400, comments=5)
    ingest_candidate(cand3, registry=reg, llm_call=lambda p, s: "반짝툴", signals_path=sig, now=NOW)
    ok(len(reg) == 2, "새 개념 추가")

    # 보드: LangGraph(채택 상승+버즈) = 호랑이가 반짝툴(버즈만) 위
    board = build_board(registry=reg, signals_path=sig, now=NOW)
    ok(board[0].name == "LangGraph" and board[0].tier.tier == "tiger", "보드 1위=호랑이")
    ok(board[1].tier.tier in ("cheetah", "mayfly"), "버즈만=치타/하루살이")
    ok([r.cid for r in board].count(cid) == 1, "개념당 한 줄")

print(f"{checks} checks passed")
