"""환율 자동 갱신 테스트 — PYTHONPATH=src python tests/test_fx.py"""

from __future__ import annotations

import os
import sys
import tempfile
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from tll.cost import fx  # noqa: E402

NOW = datetime(2026, 7, 11, tzinfo=timezone.utc)
checks = 0


def ok(cond, msg):
    global checks
    assert cond, "FAIL: " + msg
    checks += 1


def boom(url):
    raise RuntimeError("네트워크 없음")


def good(url):
    return {"rates": {"KRW": 1520.0}}


os.environ.pop("TLL_USD_KRW", None)

with tempfile.TemporaryDirectory() as d:
    cp = os.path.join(d, "fx.json")

    # 1) env 최우선
    os.environ["TLL_USD_KRW"] = "1400"
    r, src, _ = fx.get_usd_krw(cache_path=cp, now=NOW, fetcher=boom)
    ok(r == 1400.0 and "env" in src, "env 최우선(네트워크 안 씀)")
    del os.environ["TLL_USD_KRW"]

    # 2) 캐시 없음 + 실시간 성공 → 갱신 + 캐시 기록
    r, src, at = fx.get_usd_krw(cache_path=cp, now=NOW, fetcher=good)
    ok(r == 1520.0 and src == "자동 갱신", "실시간 갱신")
    ok(os.path.exists(cp), "캐시 파일 생성")

    # 3) 신선한 캐시 → 네트워크 안 씀(fetcher 폭발해도 OK)
    r, src, _ = fx.get_usd_krw(cache_path=cp, now=NOW, fetcher=boom)
    ok(r == 1520.0 and src == "자동(캐시)", "신선 캐시 재사용")

    # 4) 캐시 오래됨 + 실시간 실패 → 오래된 캐시로 폴백
    later = datetime(2026, 7, 12, 12, tzinfo=timezone.utc)  # 12h+ 경과
    r, src, _ = fx.get_usd_krw(cache_path=cp, now=later, fetcher=boom)
    ok(r == 1520.0 and "오래됨" in src, "실패 시 오래된 캐시")

    # 5) 상식 밖 값은 거부 → (캐시 없을 때) 기본값
    cp2 = os.path.join(d, "fx2.json")
    r, src, _ = fx.get_usd_krw(cache_path=cp2, now=NOW, fetcher=lambda u: {"rates": {"KRW": 3.0}})
    ok(src == "기본값" and r == fx._FALLBACK, "이상치 거부→기본값")

    # 6) 네트워크 차단(allow_network=False) + 캐시 없음 → 기본값(행 안 걸림)
    cp3 = os.path.join(d, "fx3.json")
    r, src, _ = fx.get_usd_krw(cache_path=cp3, now=NOW, allow_network=False)
    ok(src == "기본값", "오프라인·무캐시→기본값")

print(f"{checks} checks passed")
