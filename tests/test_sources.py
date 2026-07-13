"""소스 다양화 — Reddit 소스 · 버즈 소스수/허세 할인 · 다중소스 화제 확정.
PYTHONPATH=src python tests/test_sources.py"""

from __future__ import annotations

import os
import sys
import tempfile
from datetime import date, datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from tll.rank import ConceptScore, assign_tier, score_concept  # noqa: E402
from tll.scout.models import TrendCandidate  # noqa: E402
from tll.scout.scout import _reddit_candidates, scout  # noqa: E402
from tll.signals.models import Signal  # noqa: E402

checks = 0


def ok(c, m):
    global checks
    assert c, "FAIL: " + m
    checks += 1


NOW = datetime(2026, 7, 12, tzinfo=timezone.utc)

# 1) Reddit 파싱
stub = lambda: {"data": {"children": [  # noqa: E731
    {"data": {"title": "Harness engineering thread", "url": "https://x/a", "score": 420, "num_comments": 88, "created_utc": 1752300000}},
    {"data": {"title": "", "url": "https://y", "score": 1}},
]}}
rc = _reddit_candidates(10, NOW, stub)
ok(len(rc) == 1 and rc[0].source == "reddit", "reddit 후보 1개(빈 제목 스킵)")
ok(rc[0].score == 420 and rc[0].comments == 88, "점수·댓글 파싱")

# 2) scout 다중소스(hn + reddit) 합침 + per_source
def C(src, title, score):
    return TrendCandidate(cid=f"{src}:{title}", source=src, title=title, url=f"https://{src}/{title}",
                          domain=f"{src}.com", grade=2, score=score)

with tempfile.TemporaryDirectory() as d:
    store = os.path.join(d, "seen.json")
    res = scout(sources=["hackernews", "reddit"], store_path=store, now=NOW,
                hn_fetch=lambda: [C("hackernews", "A", 100)],
                reddit_fetch=lambda: [C("reddit", "B", 200)])
    srcs = {c.source for c in res.candidates}
    ok(srcs == {"hackernews", "reddit"}, "두 소스 후보 합쳐짐")
    ok(res.summary["per_source"].get("reddit") == 1, "per_source에 reddit 집계")

# 3) 버즈 소스수 + 허세(공식) 할인
def B(cid, src, v):
    return Signal(cid=cid, date="2026-07-12", source=src, kind="score", value=float(v), family="buzz")

multi = score_concept([B("m", "hackernews", 100), B("m", "reddit", 100), B("m", "geeknews", 100)], now=date(2026, 7, 12))
single = score_concept([B("s", "hackernews", 300)], now=date(2026, 7, 12))
official = score_concept([B("o", "official", 300)], now=date(2026, 7, 12))
ok(multi.buzz_sources == 3 and single.buzz_sources == 1, "버즈 소스수 집계")
ok(abs(official.attention - 150.0) < 0.01, "공식=발표원천이나 자기홍보라 0.5 가중(300→150)")
ok(official.buzz_sources == 0, "공식은 독립 화제 근거 아님(허세 방지 — 남이 받아줘야 자랑)")
ok(abs(single.attention - 300.0) < 0.01, "커뮤니티는 온전")

# 4) 다중소스 화제 = 확정 치타 / 단일소스 = 잠정
def CS(**kw):
    base = dict(cid="c", attention=300.0, adoption=0.0, adoption_growth=0.0, accelerating=False,
               rising_kinds=0, stock_kinds=0, recurrence=6, fake_flag=False, n_signals=1,
               growth_measured=False, corrob_kinds=0, adoption_mag=0.0, buzz_sources=1)
    base.update(kw)
    return ConceptScore(**base)

ok(assign_tier(CS(buzz_sources=1, recurrence=1)).tier == "cheetah", "단일소스 화제 첫 관측 = 치타")
ok(assign_tier(CS(buzz_sources=1, recurrence=2)).tier == "mayfly", "단일소스 화제 반복 = 하루살이(빨리 강등)")
ok(assign_tier(CS(buzz_sources=3, recurrence=3)).tier == "cheetah", "3소스 화제는 오래 치타 유지")
ok(assign_tier(CS(buzz_sources=3, recurrence=5)).tier == "mayfly", "3소스도 오래 미전환이면 하루살이")

print(f"{checks} checks passed")
