"""교차검증(다른 모델 독립 채점) — PYTHONPATH=src python tests/test_crosscheck.py"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from tll.factcheck.crosscheck import cross_verify  # noqa: E402

checks = 0


def ok(c, m):
    global checks
    assert c, "FAIL: " + m
    checks += 1


sections = {
    "gist": "Milvus 는 벡터 검색 데이터베이스다. 초당 수십억 벡터를 다룬다.",
    "compare": "판다스처럼 표를 다루는 게 아니라 임베딩을 다룬다.",
}
source = "Milvus is an open-source vector database for embedding similarity search."

# 검증자(다른 모델)가 2번 주장을 원문에 없다고 판정
def verifier(prompt, system):
    assert "원문" in prompt and "주장" in prompt, "원문·주장 프롬프트 구성"
    # '수십억' 과장은 원문에 없음 → 그 문장 번호를 unsupported 로
    return json.dumps({"unsupported": [2], "note": "초당 수십억은 원문에 없음(과장)"})

r = cross_verify("Milvus", source, sections, verifier_call=verifier, model_label="Claude")
ok(r["model"] == "Claude" and r["n"] >= 3, "다른 모델·주장 추출됨")
ok(0 <= r["score"] < 100, "일부 미근거 → 100 미만 점수")
ok(any("수십억" in u for u in r["unsupported"]), "과장 문장을 교차검증이 잡아냄")

# 원문/주장 없으면 건너뜀(안전)
ok(cross_verify("x", "", sections, verifier_call=verifier)["score"] is None, "원문 없으면 None")
ok(cross_verify("x", source, {}, verifier_call=verifier)["n"] == 0, "주장 없으면 0")

# 검증자가 깨진 응답 → score 유지(전부 supported 로 관대하지 않게, 파싱 실패는 미검출로)
ok(cross_verify("x", source, sections, verifier_call=lambda p, s: "그건 좀 애매")["score"] == 100, "파싱 실패 시 미검출(점수 유지)")

print(f"{checks} checks passed")


# --- 재집필: 검증에서 지적된 걸 다른 모델이 고쳐 다시 씀 ---
import json as _json  # noqa: E402
from tll.factcheck.crosscheck import revise_textbook  # noqa: E402


def reviser(prompt, system):
    assert "원문" in prompt and "초안" in prompt, "원문+초안 프롬프트"
    return _json.dumps({"one_liner": "Milvus 는 벡터 검색 DB [S1]",
                        "sections": {"gist": "임베딩 유사도 검색용 오픈소스 DB [S1]", "compare": "임베딩을 다룬다",
                                     "why": "", "watch": "", "try": ""}})


rev = revise_textbook("Milvus", source, sections, {"unsupported": ["초당 수십억 벡터를 다룬다."]}, reviser_call=reviser)
ok(rev is not None and rev["sections"]["gist"].startswith("임베딩"), "재집필본 반환")
ok("수십억" not in rev["sections"]["gist"], "지적된 과장은 재집필에서 빠짐")
ok(revise_textbook("x", "", sections, {}, reviser_call=reviser) is None, "원문 없으면 재집필 안 함(초안 유지)")

print(f"{checks} checks passed (재집필 포함)")
