"""GitHub 자동 발견 — PYTHONPATH=src python tests/test_discover.py"""

from __future__ import annotations

import os
import sys
import tempfile
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from tll.concepts import ConceptRegistry  # noqa: E402
from tll.rank import build_board  # noqa: E402
from tll.signals import signals_for  # noqa: E402
from tll.signals.discover import discover_repos, refresh_discovered  # noqa: E402

NOW = date(2026, 7, 15)
checks = 0


def ok(c, m):
    global checks
    assert c, "FAIL: " + m
    checks += 1


def fetch(url):
    return {"items": [
        {"full_name": "langchain-ai/langchain", "name": "langchain",
         "stargazers_count": 90000, "forks_count": 14000, "open_issues_count": 300},
        {"full_name": "vllm-project/vllm", "name": "vllm",
         "stargazers_count": 50000, "forks_count": 7000, "open_issues_count": 200},
        {"full_name": "small/thing", "name": "thing",
         "stargazers_count": 100, "forks_count": 1, "open_issues_count": 0},  # min_stars 미달
    ]}


# 발견: 정렬 + min_stars 필터
repos = discover_repos(fetcher=fetch, queries=["topic:llm"], per_query=5, min_stars=500)
ok(len(repos) == 2 and repos[0]["name"] == "langchain", "스타순 정렬 + 저스타 제외")
# 여러 토픽 중복 제거
ok(len(discover_repos(fetcher=fetch, queries=["topic:llm", "topic:rag"], min_stars=500)) == 2, "중복 제거")
# 빈 응답 안전
ok(discover_repos(fetcher=lambda u: {}, min_stars=500) == [], "빈 응답 → []")

with tempfile.TemporaryDirectory() as d:
    sig = os.path.join(d, "s.jsonl")
    reg = ConceptRegistry()
    n = refresh_discovered(reg, fetcher=fetch, queries=["topic:llm"], signals_path=sig, now=NOW)
    ok(len(reg) == 2 and n == 6, "2개 등록 · 6신호(각 스타·포크·이슈)")
    ok(reg.resolve("langchain").matched and reg.resolve("vllm").matched, "발견 개념 등록됨(추출 grounding용)")
    lc = reg.resolve("langchain").cid
    ok(len(signals_for(lc, sig)) == 3, "langchain 채택 신호 3종")

    # 트렌드 없이도 랭킹에 등장
    board = build_board(registry=reg, signals_path=sig, now=NOW)
    row = next(r for r in board if r.name == "langchain")
    ok(row.score.stock_kinds >= 2 and row.score.adoption > 5, "채택 점수 실제로 잡힘")
    ok(row.tier.tier in ("elephant", "tiger", "dinosaur", "turtle"), "채택 근거 티어(반짝 아님)")

    # 재실행 idempotent
    refresh_discovered(reg, fetcher=fetch, queries=["topic:llm"], signals_path=sig, now=NOW)
    ok(len(reg) == 2, "재실행해도 개념 중복 안 생김")

# F1·F2: 첫 관측이면 나이 무관 둘 다 거북이(잠정) — 정착은 시간에 걸친 평탄 관측이라야
def fetch2(url):
    return {"items": [
        {"full_name": "a/langchain", "name": "langchain", "stargazers_count": 90000,
         "forks_count": 40000, "open_issues_count": 300, "created_at": "2023-01-01T00:00:00Z"},
        {"full_name": "b/postgres", "name": "postgres", "stargazers_count": 90000,
         "forks_count": 40000, "open_issues_count": 300, "created_at": "2016-01-01T00:00:00Z"}]}


with tempfile.TemporaryDirectory() as d2:
    sig2 = os.path.join(d2, "s.jsonl")
    reg2 = ConceptRegistry()
    refresh_discovered(reg2, fetcher=fetch2, queries=["topic:x"], signals_path=sig2, now=NOW)
    ok(reg2.get(reg2.resolve("langchain").cid).created_at.startswith("2023"), "created_at 저장됨")
    tiers = {r.name: r.tier.tier for r in build_board(registry=reg2, signals_path=sig2, now=NOW)}
    ok(tiers["langchain"] == "turtle", "거대+젊음(신뢰나이 3년) = 거북이(코끼리 아님)")
    ok(tiers["postgres"] == "elephant", "거대+신뢰나이(10년) = 코끼리(첫 관측이라도)")

print(f"{checks} checks passed")
