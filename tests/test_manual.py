"""가벼운 설명서 집필 + depth 저장 — PYTHONPATH=src python tests/test_manual.py"""

from __future__ import annotations

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from tll.author.author import AuthorError, write_manual  # noqa: E402
from tll.present.store import load_records, save_textbook  # noqa: E402

checks = 0


def ok(c, m):
    global checks
    assert c, "FAIL: " + m
    checks += 1


def fake_llm(prompt, system):
    # 원문(README)만 근거로 쓴다는 계약 확인 + JSON 반환
    assert "milvus" in prompt.lower(), "이름이 프롬프트에 들어감"
    return json.dumps({
        "one_liner": "Milvus 는 벡터 검색 데이터베이스다 [S1]",
        "gist": "대규모 임베딩을 저장하고 유사도로 빠르게 찾는다 [S1]",
        "compare": "판다스 DataFrame 이 표를 다루듯, 벡터를 다루는 DB다 (일반지식)",
    })


tb = write_manual("milvus", "Milvus is an open-source vector database for embeddings.",
                  url="https://github.com/milvus-io/milvus", nature="저장소", grade="2", llm_call=fake_llm)
ok(tb.sections["gist"] and tb.sections["compare"], "gist·compare 채워짐")
ok(tb.sections["why"] == "" and tb.sections["try"] == "", "설명서는 나머지 섹션 비움(짧게)")
ok(tb.status == "draft", "초안 상태(팩트체크 대상)")
ok(tb.sources[0].body_text.startswith("Milvus"), "원문 보존(팩트체크용)")

# 빈 원문 → 실패 격리
try:
    write_manual("x", "   ", llm_call=fake_llm)
    ok(False, "빈 원문은 예외")
except AuthorError:
    ok(True, "빈 원문 → AuthorError")

# depth 태그 저장/로드
with tempfile.TemporaryDirectory() as d:
    save_textbook(tb, metrics={"support_rate": 0.8}, provider="gemini", out_dir=d,
                  concept_cid="c-milvus", concept_name="milvus", depth="설명서")
    rec = load_records(d)[0]
    ok(rec["depth"] == "설명서", "depth=설명서 저장됨")
    ok(rec["concept_cid"] == "c-milvus", "concept 꼬리표 유지")

print(f"{checks} checks passed")
