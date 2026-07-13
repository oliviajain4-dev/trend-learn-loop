"""레지스트리 동시 저장 안전성 테스트 — PYTHONPATH=src python tests/test_registry_concurrency.py

배경(실제 버그): Streamlit 백그라운드 자동수집 스레드와 사용자가 따로 돌린
`python -m tll.loop.loop`(별도 프로세스)가 같은 concepts_registry.json 을 동시에 저장하면서
공유 임시파일명(`{path}.tmp`)이 서로 덮어써 JSON 이 두 번 깨졌다(개념 90개 유실).
고침: 저장마다 프로세스별 고유 임시파일명(pid+uuid) 사용 → os.replace() 의 원자성이
실제로 보장되어, 동시에 저장해도 파일은 항상 '둘 중 하나의 완전한 내용'이지 섞여서 깨지지 않는다.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from tll.concepts.registry import ConceptRegistry  # noqa: E402

checks = 0


def ok(cond, msg):
    global checks
    assert cond, "FAIL: " + msg
    checks += 1


def _mk_registry(prefix: str, n: int) -> ConceptRegistry:
    reg = ConceptRegistry()
    for i in range(n):
        reg.add(f"{prefix}-concept-{i}", category="기타")
    return reg


with tempfile.TemporaryDirectory() as d:
    path = os.path.join(d, "concepts_registry.json")

    # ── 기본 저장·로드 왕복 ──
    reg = _mk_registry("solo", 20)
    reg.save(path)
    ok(os.path.exists(path), "저장 파일 생성됨")
    loaded = ConceptRegistry.load(path)
    ok(len(loaded) == 20, "저장→로드 개수 일치")

    # ── 동시 저장 레이스 재현: 두 스레드(프로세스 대리)가 같은 파일에 동시에 save() ──
    # 실제 버그의 핵심은 '공유 임시파일명'이었다. 지금은 프로세스별 고유 임시파일이라
    # 아무리 겹쳐 써도 os.replace() 는 항상 '완전한 하나'만 최종 반영해야 한다.
    reg_a = _mk_registry("A", 500)   # 파일 쓰기에 실제 시간이 걸리도록 넉넉히
    reg_b = _mk_registry("B", 500)
    def _save(reg, barrier, errors):
        try:
            barrier.wait(timeout=5)   # 두 스레드가 최대한 동시에 쓰기 시작하게 강제
            reg.save(path)
        except Exception as e:  # noqa: BLE001
            errors.append(e)

    for trial in range(20):   # 반복해서 레이스 창을 여러 번 노출
        barrier = threading.Barrier(2)
        errors: list[Exception] = []
        t1 = threading.Thread(target=_save, args=(reg_a, barrier, errors))
        t2 = threading.Thread(target=_save, args=(reg_b, barrier, errors))
        t1.start(); t2.start()   # noqa: E702
        t1.join(); t2.join()     # noqa: E702
        ok(not errors, f"trial {trial}: 저장 중 예외 없음({errors[0] if errors else ''})")
        with open(path, encoding="utf-8") as f:
            raw = f.read()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            raise AssertionError(f"trial {trial}: 파일이 깨짐(레이스 재발) — {e}\n{raw[:200]}") from e
        checks += 1
        # 항상 '둘 중 하나'의 완전한 내용이어야 한다(500개 전부, 섞이면 안 됨)
        ok(len(data) == 500, f"trial {trial}: 완전한 하나의 저장본(500개), 섞이지 않음(실제 {len(data)})")
        names = {v["canonical"] for v in data.values()}
        is_a = all(n.startswith("A-concept-") for n in names)
        is_b = all(n.startswith("B-concept-") for n in names)
        ok(is_a or is_b, f"trial {trial}: A 또는 B 중 하나로만 구성(섞임 없음)")

    # ── 임시파일이 프로세스마다 고유한지(핵심 수정 사항) 직접 확인 ──
    tmp_names = set()
    orig_replace = os.replace

    def _capture_replace(src, dst):
        tmp_names.add(src)
        return orig_replace(src, dst)

    import tll.concepts.registry as registry_mod
    registry_mod.os.replace = _capture_replace
    try:
        _mk_registry("x", 3).save(path)
        _mk_registry("y", 3).save(path)
    finally:
        registry_mod.os.replace = orig_replace
    ok(len(tmp_names) == 2, "저장 2회 → 임시파일명 2개(고유, 재사용 없음)")

print(f"OK - {checks} checks passed")
