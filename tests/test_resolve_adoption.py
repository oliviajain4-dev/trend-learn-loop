"""미측정 개념 채택 구제(이름으로 GitHub 조회) — PYTHONPATH=src python tests/test_resolve_adoption.py"""

from __future__ import annotations

import os
import sys
import tempfile
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from tll.concepts import ConceptRegistry  # noqa: E402
from tll.rank import score_concept  # noqa: E402
from tll.signals import log_signal, signals_for  # noqa: E402
from tll.signals.discover import resolve_adoption  # noqa: E402
from tll.signals.github import search_top_repo  # noqa: E402

checks = 0


def ok(c, m):
    global checks
    assert c, "FAIL: " + m
    checks += 1


def fetch(url):
    if "Node.js" in url or "node" in url.lower():
        return {"items": [
            {"full_name": "nodejs/node", "stargazers_count": 108000, "forks_count": 30000, "open_issues_count": 1800,
             "created_at": "2014-11-26T00:00:00Z"},
        ]}
    if "randomthing" in url.lower():
        return {"items": [{"full_name": "someone/unrelated", "stargazers_count": 50000}]}  # 이름 불일치
    return {"items": []}


# 이름 매칭 + 최소별
ok(search_top_repo("Node.js", fetch)["full_name"] == "nodejs/node", "이름 매칭 저장소 찾음")
ok(search_top_repo("randomthing", fetch) is None, "이름 불일치는 안 붙임(엉뚱 저장소 방지)")

with tempfile.TemporaryDirectory() as d:
    sig = os.path.join(d, "s.jsonl")
    reg = ConceptRegistry()
    cid = reg.add("Node.js", category="")
    log_signal(cid, "hackernews", "hn_points", 6, date="2026-07-12", path=sig)  # 버즈만
    before = score_concept(signals_for(cid, sig), now=date(2026, 7, 12))
    ok(before.adoption == 0.0, "구제 전: 채택 0(그래서 새싹이었음)")

    n = resolve_adoption(reg, fetcher=fetch, signals_path=sig, now=date(2026, 7, 12))
    ok(n == 1, "채택 없는 개념 1개 구제")
    after = score_concept(signals_for(cid, sig), now=date(2026, 7, 12))
    ok(after.adoption > 60 and after.corrob_kinds >= 2, "구제 후: 채택 실측(높음)·독립 지표 2+")
    ok(reg.get(cid).created_at.startswith("2014"), "신뢰 나이(저장소 생일)도 보정")

    # 재실행: 이미 채택 있으니 다시 안 붙임
    ok(resolve_adoption(reg, fetcher=fetch, signals_path=sig, now=date(2026, 7, 12)) == 0, "이미 채택 있으면 스킵")

print(f"{checks} checks passed")
