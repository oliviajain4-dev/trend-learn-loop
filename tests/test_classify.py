"""개념 종류 분류(결정론) — PYTHONPATH=src python tests/test_classify.py"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from tll.concepts.classify import concept_kind  # noqa: E402

checks = 0


def ok(c, m):
    global checks
    assert c, "FAIL: " + m
    checks += 1


# 자료(읽을거리) — 사용자가 든 예시들
ok(concept_kind("awesome-llm-apps") == "resource", "awesome- = 자료")
ok(concept_kind("RAG_Techniques") == "resource", "techniques = 자료")
ok(concept_kind("prompts.chat") == "resource", "prompts = 자료")
ok(concept_kind("developer-roadmap") == "resource", "roadmap = 자료")
ok(concept_kind("free-programming-books", topics=["book", "list"]) == "resource", "토픽 list = 자료")
ok(concept_kind("system-design-primer", topics=["awesome-list"]) == "resource", "토픽 awesome-list = 자료")
# 도구 — 실행 소프트웨어(기본값 tool)
ok(concept_kind("langchain") == "tool", "langchain = 도구")
ok(concept_kind("ollama") == "tool", "ollama = 도구")
ok(concept_kind("milvus") == "tool", "milvus = 도구")
ok(concept_kind("mystery-xyz") == "tool", "신호 없으면 기본 도구(자료로 오분류 안 함)")
# 기법 — category 로 지정
ok(concept_kind("하네스 엔지니어링", category="기법") == "technique", "category 기법 = technique")
ok(concept_kind("RAG", category="개념") == "technique", "category 개념 = technique")

print(f"{checks} checks passed")
