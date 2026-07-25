"""기능 카테고리 + 범위 게이트 테스트 — PYTHONPATH=src python tests/test_categorize.py"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from tll.concepts.categorize import (  # noqa: E402
    CATEGORIES,
    OUT_OF_SCOPE,
    categorize,
    recategorize,
)
from tll.concepts.registry import ConceptRegistry  # noqa: E402

checks = 0


def eq(a, b, msg):
    global checks
    assert a == b, f"FAIL {msg}: {a!r} != {b!r}"
    checks += 1


def ok(cond, msg):
    global checks
    assert cond, "FAIL: " + msg
    checks += 1


# ── 기능 카테고리(AI) 정확 분류 ──
eq(categorize("LangChain"), "개발도구·프레임워크", "langchain=도구")
eq(categorize("LangGraph"), "개발도구·프레임워크", "langgraph=도구")
eq(categorize("llama-index"), "개발도구·프레임워크", "llama-index=도구(모델 llama 보다 먼저)")
eq(categorize("Ollama"), "개발도구·프레임워크", "ollama=도구")
eq(categorize("RAG"), "RAG·검색", "rag=검색")
eq(categorize("retrieval augmented generation"), "RAG·검색", "retrieval=검색")
eq(categorize("Qdrant vector database"), "RAG·검색", "vector db=검색")
eq(categorize("AutoGPT"), "에이전트·자동화", "autogpt=에이전트")
eq(categorize("Model Context Protocol"), "에이전트·자동화", "mcp=에이전트")
eq(categorize("GPT-5.6"), "AI 모델", "gpt=모델")
eq(categorize("Claude Opus"), "AI 모델", "claude=모델")
eq(categorize("prompt engineering"), "기법·최적화", "prompt=기법")
eq(categorize("LoRA fine-tuning"), "기법·최적화", "finetune=기법")
eq(categorize("하네스 엔지니어링"), "기법·최적화", "하네스=기법(한글)")

# ── 범위 밖(비-AI) 박제 ──
eq(categorize("Node.js"), OUT_OF_SCOPE, "node.js=범위밖")
eq(categorize("PgBouncer"), OUT_OF_SCOPE, "pgbouncer=범위밖")
eq(categorize("Turing Machine"), OUT_OF_SCOPE, "turing=범위밖")
eq(categorize("Ghost Font"), OUT_OF_SCOPE, "font=범위밖")
eq(categorize("dotenv-diff"), OUT_OF_SCOPE, "dotenv=범위밖")
eq(categorize("PostgreSQL"), OUT_OF_SCOPE, "postgres=범위밖")

# ── AI 근거는 있으나 세분류 안 됨 → 기타(과잉 제외 방지) ──
eq(categorize("fenic"), "기타", "이름만·근거없음 → 기본 기타(진짜 AI 안 버림)")
eq(categorize("SomethingNew", hint="발견"), "기타", "발견 힌트=AI 출처 → 기타")
eq(categorize("MyThing", hint="AI모델"), "AI 모델", "힌트 'AI모델'(붙여쓰기) → 모델 매칭")
eq(categorize("MyThing", hint="AI 모델"), "AI 모델", "힌트 'AI 모델'(띄어쓰기) → 동일")

# ── 경계 매칭: 'rag' 가 'storage' 를 오탐하지 않음(RAG·검색 아님) ──
ok(categorize("cloud storage service") != "RAG·검색", "storage 는 rag 오탐 안 함(경계)")

# ── 모든 반환값은 고정 목록 안 ──
allowed = set(CATEGORIES) | {OUT_OF_SCOPE}
for s in ["x", "GPT", "Node.js", "vLLM serving on GPU", "random noise 123"]:
    ok(categorize(s) in allowed, f"'{s}' 반환이 고정목록 안")

# ── recategorize: 자유형·발견·빈칸을 통일 + 범위밖 박제 ──
reg = ConceptRegistry()
reg.add("langchain", category="발견")          # 출처 → 도구로 통일
reg.add("Node.js", category="런타임/도구")       # 비-AI → 범위밖
reg.add("JEPA", category="AI모델")              # 붙여쓰기 → 모델
reg.add("fenic", category="")                  # 빈칸 → 기타
counts = recategorize(reg)
eq(reg.resolve("langchain").cid and next(c.category for c in reg.all() if c.canonical == "langchain"),
   "개발도구·프레임워크", "발견 → 도구")
eq(next(c.category for c in reg.all() if c.canonical == "Node.js"), OUT_OF_SCOPE, "Node.js → 범위밖")
eq(next(c.category for c in reg.all() if c.canonical == "JEPA"), "AI 모델", "AI모델 → 모델(통일)")
eq(next(c.category for c in reg.all() if c.canonical == "fenic"), "기타", "빈칸 → 기타")
ok(counts.get(OUT_OF_SCOPE, 0) == 1, "범위밖 1개 집계")

print(f"OK - {checks} checks passed")
