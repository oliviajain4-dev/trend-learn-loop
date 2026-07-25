"""arXiv 연구 채택 신호 — PYTHONPATH=src python tests/test_arxiv.py"""

from __future__ import annotations

import os
import sys
import tempfile
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from tll.concepts import ConceptRegistry  # noqa: E402
from tll.rank import build_board  # noqa: E402
from tll.signals import signals_for  # noqa: E402
from tll.signals.arxiv import arxiv_stats, refresh_research  # noqa: E402

NOW = date(2026, 7, 15)
checks = 0


def ok(c, m):
    global checks
    assert c, "FAIL: " + m
    checks += 1


DESC = ('<feed xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/">'
        '<opensearch:totalResults>4200</opensearch:totalResults>'
        '<entry><published>2026-06-01T00:00:00Z</published></entry>'
        '<entry><published>2026-05-15T00:00:00Z</published></entry>'
        '<entry><published>2023-02-02T00:00:00Z</published></entry></feed>')
ASC = ('<feed><opensearch:totalResults>4200</opensearch:totalResults>'
       '<entry><published>2020-05-22T00:00:00Z</published></entry></feed>')


def mock(url):
    return ASC if "ascending" in url else DESC


# arxiv_stats 파싱
st = arxiv_stats("RAG", fetcher=mock, now=NOW)
ok(st["total"] == 4200, "총량 파싱")
ok(st["recent"] == 2, "최근 180일 논문 2건")
ok(st["earliest"] == "2020-05-22", "최초 등장(나이) 파싱")

with tempfile.TemporaryDirectory() as d:
    sig = os.path.join(d, "s.jsonl")
    reg = ConceptRegistry()
    reg.add("RAG", category="기법")          # repo 없는 개념
    reg.add("langchain", category="발견")     # github-발견 → arXiv 스킵돼야
    n = refresh_research(reg, fetcher=mock, signals_path=sig, now=NOW)
    ok(n == 2, "RAG만 arXiv 2신호(발견 개념은 스킵)")
    rag = reg.resolve("RAG").cid
    ok(len(signals_for(rag, sig)) == 2, "RAG arxiv 신호 2개")
    ok(reg.get(rag).created_at == "", "arXiv 최초논문일은 나이로 안 씀(불량 대리지표 제거)")
    ok(len(signals_for(reg.resolve("langchain").cid, sig)) == 0, "발견(github) 개념은 arXiv 스킵")

    # repo 없어도 랭킹에 '신뢰' 티어로 등장
    board = build_board(registry=reg, signals_path=sig, now=NOW)
    row = next(r for r in board if r.name == "RAG")
    ok(row.score.stock_kinds == 2 and row.score.adoption > 5, "RAG 연구 채택 실제로 잡힘")
    ok(row.tier.tier not in ("mayfly", "hyena"), "채널이 실제 티어 산출(하루살이·가짜 아님)")

    # 총량 미달 → 스킵
    sig2 = os.path.join(d, "s2.jsonl")
    reg2 = ConceptRegistry()
    reg2.add("무명개념", category="기법")
    ok(refresh_research(reg2, fetcher=lambda u: "<feed><opensearch:totalResults>1</opensearch:totalResults></feed>",
                        signals_path=sig2, now=NOW) == 0, "논문 미달 → 스킵")

print(f"{checks} checks passed")
