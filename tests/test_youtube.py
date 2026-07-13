"""YouTube 대두 신호 — PYTHONPATH=src python tests/test_youtube.py"""

from __future__ import annotations

import os
import sys
import tempfile
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from tll.concepts import ConceptRegistry  # noqa: E402
from tll.rank import score_concept  # noqa: E402
from tll.signals import signals_for  # noqa: E402
from tll.signals.youtube import refresh_youtube, youtube_stats  # noqa: E402

checks = 0


def ok(c, m):
    global checks
    assert c, "FAIL: " + m
    checks += 1


def fake(term):
    n = {"RAG": 20, "harness engineering": 5, "obscure": 1}.get(term, 0)
    return {"items": [{"id": i} for i in range(n)]}


ok(youtube_stats("RAG", fake)["recent"] == 20, "최근 영상 수 집계")
ok(youtube_stats("nokey", lambda t: {})["recent"] == 0, "키 없음/빈 응답 → 0 (안 죽음)")

with tempfile.TemporaryDirectory() as d:
    sig = os.path.join(d, "s.jsonl")
    reg = ConceptRegistry()
    reg.add("RAG", category="기법")
    reg.add("harness engineering", category="기법")
    reg.add("obscure", category="기법")
    n = refresh_youtube(reg, fetcher=fake, signals_path=sig, now=date(2026, 7, 12), min_videos=3)
    ok(n == 2, "영상 3+ 개념만 신호(obscure 제외)")
    rag = reg.resolve("RAG").cid
    sigs = signals_for(rag, sig)
    ok(len(sigs) == 1 and sigs[0].source == "youtube" and sigs[0].family == "buzz", "youtube 주목 신호(독립 소스)")

# 유튜브가 붙으면 독립 버즈 소스가 되어 '화제' 근거가 됨
from tll.signals.models import Signal  # noqa: E402
def S(src, v, fam="buzz"):
    return Signal(cid="x", date="2026-07-12", source=src, kind="k", value=float(v), family=fam)
sc = score_concept([S("hackernews", 100), S("youtube", 30)], now=date(2026, 7, 12))
ok(sc.buzz_sources == 2, "HN+YouTube = 독립 2소스(확정 화제 근거)")
ok(abs(sc.attention - (100 + 30 * 0.8)) < 0.01, "유튜브 0.8 가중 반영")

print(f"{checks} checks passed")
