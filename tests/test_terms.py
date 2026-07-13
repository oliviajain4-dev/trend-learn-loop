"""기법 발견기 — PYTHONPATH=src python tests/test_terms.py"""

from __future__ import annotations

import os
import sys
import tempfile
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from tll.concepts import ConceptRegistry  # noqa: E402
from tll.signals import signals_for  # noqa: E402
from tll.signals.terms import discover_terms, extract_terms, refresh_terms  # noqa: E402

checks = 0


def ok(c, m):
    global checks
    assert c, "FAIL: " + m
    checks += 1


# 추출: 약어 + 헤드명사 구 (repo 아닌 기법)
t = extract_terms("Harness engineering for LLM agents with RAG")
ok("harness engineering" in t, "‘harness engineering’ 추출(헤드명사)")
ok("RAG" in t and "LLM" in t, "약어 RAG·LLM 추출")
ok("llm agents" in t, "‘llm agents’ 구 추출")
ok(extract_terms("The new model is great") == set() or "new model" not in extract_terms("The new model is great"), "불용어 앞단어 제외")

# 빈도 발견
titles = [
    "Harness engineering for agentic LLMs",
    "A survey of harness engineering",
    "Context engineering beats prompt engineering",
    "Context engineering in production",
    "RAG systems at scale",
    "Improving RAG with rerankers",
    "RAG evaluation benchmarks",
]
found = dict(discover_terms(titles, min_count=2))
ok("harness engineering" in found and found["harness engineering"] == 2, "하네스 엔지니어링 2회 발견")
ok("context engineering" in found, "컨텍스트 엔지니어링 발견")
ok(found.get("RAG", 0) == 3, "RAG 3회")
ok("rerankers" not in found, "1회짜리는 미달(임계)")

# 등록 + 신호
with tempfile.TemporaryDirectory() as d:
    sig = os.path.join(d, "s.jsonl")
    reg = ConceptRegistry()
    n = refresh_terms(reg, titles=titles, signals_path=sig, now=date(2026, 7, 12), min_count=2)
    ok(n >= 3, "여러 기법 자동 등록")
    r = reg.resolve("harness engineering")
    ok(r.matched and reg.get(r.cid).category == "기법", "하네스=기법 개념으로 등록(내가 언급 안 해도)")
    ok(len(signals_for(r.cid, sig)) == 1, "community 빈도 신호 1개")

print(f"{checks} checks passed")
