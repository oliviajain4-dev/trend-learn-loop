"""개념 레지스트리 테스트 — 독립 실행: PYTHONPATH=src python tests/test_concepts.py"""

from __future__ import annotations

import os
import sys
import tempfile
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from tll.concepts import ConceptRegistry, normalize, slugify  # noqa: E402

NOW = datetime(2026, 7, 11, tzinfo=timezone.utc)
checks = 0


def ok(cond, msg):
    global checks
    assert cond, "FAIL: " + msg
    checks += 1


# 1) normalize: 공백/기호 무시로 같은 키
ok(normalize("LangChain") == normalize("lang chain") == normalize("Lang-Chain") == "langchain", "normalize 통일")
# 2) normalize: +,# 보존해 언어 구분
ok(normalize("C++") == "c++" and normalize("C#") == "c#" and normalize("C++") != normalize("C#"), "C++/C# 구분")
# 3) normalize: Node.js 계열 통일
ok(normalize("Node.js") == normalize("node js") == normalize("NodeJS") == "nodejs", "Node.js 통일")
# 4) slugify
ok(slugify("Model Context Protocol") == "model-context-protocol", "slugify")

reg = ConceptRegistry()
# 5) add + 정확 매칭
lc = reg.add("LangChain", now=NOW)
r = reg.resolve("LangChain")
ok(r.matched and r.cid == lc == "langchain", "정확 매칭")
# 6) 별칭 매칭
mcp = reg.add("Model Context Protocol", aliases=["MCP"], now=NOW)
ok(reg.resolve("mcp").matched and reg.resolve("mcp").cid == mcp, "별칭 매칭")
# 7) 미매칭
ok(reg.resolve("전혀없는것").matched is False, "미매칭 None")
# 8) 표기만 다른 변형은 같은 개념으로(중복 방지), resolve 동작
before = len(reg)
same = reg.add("lang chain", now=NOW)
ok(same == lc and len(reg) == before, "표기 달라도 병합")
ok(reg.resolve("Lang-Chain").matched and reg.resolve("Lang-Chain").cid == lc, "변형 표기 resolve")
# 8b) 병합 시 '구별되는' 새 별칭은 축적
reg.add("LangChain", aliases=["LC"], now=NOW)
ok(reg.resolve("LC").matched and reg.resolve("LC").cid == lc and "LC" in reg.get(lc).aliases, "새 별칭 축적")
ok(len(reg) == before, "별칭 추가는 개수 불변")
# 9) resolve_or_add → provisional 신규, 재호출 시 기존
r1 = reg.resolve_or_add("Harness Engineering", now=NOW)
ok(r1.matched is False and reg.get(r1.cid).status == "provisional", "신규는 provisional")
r2 = reg.resolve_or_add("harness engineering", now=NOW)
ok(r2.matched is True and r2.cid == r1.cid, "재등장 시 기존 매칭")
# 10) 승격
reg.set_status(r1.cid, "confirmed")
ok(reg.get(r1.cid).status == "confirmed", "provisional→confirmed 승격")

# 11) 영속 왕복 + 리로드 후 별칭 매칭
with tempfile.TemporaryDirectory() as d:
    p = os.path.join(d, "reg.json")
    reg.save(p)
    reg2 = ConceptRegistry.load(p)
    ok(len(reg2) == len(reg), "리로드 개수 동일")
    ok(reg2.resolve("MCP").matched and reg2.resolve("MCP").cid == mcp, "리로드 후 별칭 매칭")

# 12) 없는 파일 load → 빈 레지스트리
ok(len(ConceptRegistry.load("/tmp/nope_tll_reg.json")) == 0, "없는 파일 → 빈")

# 13) 손상된 파일 → 빈 레지스트리(크래시 안 함)
with tempfile.TemporaryDirectory() as _d:
    _bad = os.path.join(_d, "bad.json")
    with open(_bad, "w", encoding="utf-8") as _f:
        _f.write('{"x": {"canonical": "X"},')  # 잘린 JSON
    ok(len(ConceptRegistry.load(_bad)) == 0, "손상 파일 → 빈(크래시 없음)")

# 14) created_at 저장 + 병합 시 가장 이른 생성일 유지(나이 정확도)
reg3 = ConceptRegistry()
reg3.add("Foo", created_at="2022-01-01")
ok(reg3.get(reg3.resolve("Foo").cid).created_at == "2022-01-01", "created_at 저장")
reg3.add("foo", created_at="2020-05-05")
ok(reg3.get(reg3.resolve("Foo").cid).created_at == "2020-05-05", "병합 시 더 이른 생성일 유지")

# 15) 한글 개념 중복해소(정규화가 한글 유지)
regk = ConceptRegistry()
c1 = regk.add("하네스 엔지니어링")
c2 = regk.add("하네스 엔지니어링", created_at="2024-06-01")
ok(c1 == c2 and len(regk) == 1, "한글 개념 중복 안 생김")
ok(regk.resolve("하네스엔지니어링").matched, "한글 띄어쓰기 무시 매칭")
ok(normalize("하네스 엔지니어링") == "하네스엔지니어링", "한글 정규화 유지")

print(f"{checks} checks passed")
