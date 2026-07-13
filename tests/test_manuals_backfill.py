"""설명서 백필 + README fetch — PYTHONPATH=src python tests/test_manuals_backfill.py"""

from __future__ import annotations

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from tll.author.manuals import backfill_manuals  # noqa: E402
from tll.concepts import ConceptRegistry  # noqa: E402
from tll.present.store import load_records, save_textbook  # noqa: E402
from tll.signals.github import github_readme  # noqa: E402

checks = 0


def ok(c, m):
    global checks
    assert c, "FAIL: " + m
    checks += 1


# README fetch: HEAD 실패 → main 폴백
def text_fetcher(url):
    return "# Milvus\nVector database for embeddings." if "/main/" in url else ""


ok(github_readme("milvus-io/milvus", text_fetcher).startswith("# Milvus"), "README main 폴백 성공")
ok(github_readme("", text_fetcher) == "", "빈 full_name → ''")


def llm(prompt, system):
    return json.dumps({"one_liner": "요약 [S1]", "gist": "설명 [S1]", "compare": "비교 [S1]"})


with tempfile.TemporaryDirectory() as d:
    reg = ConceptRegistry()
    reg.add("milvus", category="발견")
    reg.add("qdrant", category="발견")
    reg.add("langchain", category="발견")
    # langchain 은 이미 교과서 있음 → 스킵돼야
    save_textbook_stub = None
    from types import SimpleNamespace
    tb = SimpleNamespace(topic="langchain", to_dict=lambda: {"topic": "langchain", "one_liner": "", "sections": {},
                         "judgment": {}, "sources": [], "unverified": [], "status": "draft", "age_label": "", "collected_at": ""})
    save_textbook(tb, out_dir=d, concept_cid=reg.resolve("langchain").cid, concept_name="langchain", depth="교과서")

    sources = {"milvus": ("Milvus vector DB", "https://x/milvus"), "qdrant": ("Qdrant vector DB", "https://x/qdrant")}
    def source_for(c):
        return sources.get(c.canonical, ("", ""))

    made = backfill_manuals(reg, records_dir=d, source_for=source_for, llm_call=llm, limit=8)
    ok(set(made) == {"milvus", "qdrant"}, "설명 없던 2개만 설명서 생성(langchain 스킵)")
    recs = {r["concept_name"]: r for r in load_records(d)}
    ok(recs["milvus"]["depth"] == "설명서", "milvus depth=설명서")
    ok(recs["langchain"]["depth"] == "교과서", "langchain 교과서 유지")
    # 재실행 → 이미 있으니 아무것도 새로 안 함
    ok(backfill_manuals(reg, records_dir=d, source_for=source_for, llm_call=llm) == [], "재실행 시 중복 생성 없음")

print(f"{checks} checks passed")
