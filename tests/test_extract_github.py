"""개념 추출(grounding·기권) + GitHub 신호 — PYTHONPATH=src python tests/test_extract_github.py"""

from __future__ import annotations

import os
import sys
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from tll.concepts import ConceptRegistry  # noqa: E402
from tll.concepts.extract import extract_concept_name, find_known  # noqa: E402
from tll.signals.github import github_signals, parse_repo  # noqa: E402

checks = 0


def ok(c, m):
    global checks
    assert c, "FAIL: " + m
    checks += 1


def throw(p, s):
    raise RuntimeError("llm 없음")


# --- 추출 ---
ok(extract_concept_name("Postgres를 Rust로 재작성", llm_call=lambda p, s: '"PostgreSQL"\n(설명)') == "PostgreSQL", "LLM 추출")
ok(extract_concept_name("Show HN: cool tool", url="https://github.com/foo/langgraph") == "langgraph", "fallback=repo명")
ok(extract_concept_name("Vector DB explained", url="https://blog.x/p") == "", "제목은 개념 아님 → 빈값(소음 안 남김)")
ok(extract_concept_name("T", url="https://github.com/a/b", llm_call=throw) == "b", "LLM 예외 → repo fallback")
ok(extract_concept_name("무슨 잡담", llm_call=lambda p, s: "UNCLEAR") == "", "특정 기술 아님 → 기권(UNCLEAR)")

# --- 아는 개념(시드+누적) 우선 매칭 = 오추출 방지 ---
reg = ConceptRegistry()
reg.add("LangChain")
reg.add("RAG")
reg.add("Model Context Protocol", aliases=["MCP"])
ok(extract_concept_name("Show HN: LangChain 실전 팁", registry=reg) == "LangChain", "아는 개념 매칭(무LLM)")
ok(extract_concept_name("MCP servers 가이드", registry=reg) == "Model Context Protocol", "별칭 매칭→표준명")
ok(extract_concept_name("How storage works", registry=reg) == "", "단어경계: storage 가 RAG 로 오매칭 안 됨")
ok(find_known("using RAG for search", reg) == "RAG", "find_known 단어 매칭")
ok(find_known("전혀 관련 없음", reg) == "", "find_known 없음")

# --- GitHub 신호 ---
ok(parse_repo("https://github.com/langchain-ai/langchain") == "langchain-ai/langchain", "parse_repo")
ok(parse_repo("https://example.com/a/b") is None, "비-github None")


def gh(u):
    return {"stargazers_count": 1200, "forks_count": 150, "open_issues_count": 40}


sigs = github_signals("https://github.com/x/y", "yid", fetcher=gh, now=date(2026, 7, 15))
ok(len(sigs) == 3 and {s.kind for s in sigs} == {"stars", "forks", "issues"}, "3종 스냅샷")
ok(github_signals("https://blog.x/p", "id", fetcher=gh) == [], "비-github → []")

print(f"{checks} checks passed")
