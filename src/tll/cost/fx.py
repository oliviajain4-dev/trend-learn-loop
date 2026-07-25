"""USD→KRW 환율 자동 갱신.

- 무료 공개 API에서 실시간 환율을 가져와 캐시(TTL 12h). 캐시가 신선하면 네트워크 안 씀.
- 실패하면 캐시(오래돼도) → 상수(pricing.USD_KRW) 순으로 폴백 → 화면이 절대 안 멈춘다.
- TLL_USD_KRW 환경변수가 있으면 그걸 최우선(수동 고정).
결정론 아님(외부 환율)이지만, 실패에 안전하고 캐시로 재현·저비용.
"""

from __future__ import annotations

import json
import os
import urllib.request
from datetime import datetime, timezone

from tll.cost.pricing import USD_KRW as _FALLBACK
from tll.cost.pricing import USD_KRW_ASOF as _FALLBACK_ASOF

DEFAULT_FX_CACHE = "data/cost/fx_cache.json"
TTL_SECONDS = 12 * 3600  # 12시간마다 갱신

# 무료·키 불필요 엔드포인트 (순서대로 시도). 값 경로는 d["rates"]["KRW"].
_ENDPOINTS = [
    "https://open.er-api.com/v6/latest/USD",
    "https://api.frankfurter.app/latest?from=USD&to=KRW",
]


def _http_json(url: str, *, timeout: float = 4.0) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "TLL"})
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310
        return json.loads(r.read().decode("utf-8"))


def _fetch_live(fetcher) -> float | None:
    for url in _ENDPOINTS:
        try:
            rate = float((fetcher(url) or {}).get("rates", {}).get("KRW"))
            if 500.0 < rate < 5000.0:  # 원/달러 상식 범위 가드(엉뚱한 값 차단)
                return rate
        except Exception:  # noqa: BLE001 — 어떤 실패든 다음 엔드포인트로
            continue
    return None


def _read_cache(path: str):
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        if isinstance(d, dict) and "rate" in d:
            return d
    except (OSError, json.JSONDecodeError, ValueError):
        pass
    return None


def _write_cache(path: str, data: dict) -> None:
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        tmp = f"{path}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        os.replace(tmp, path)  # 원자적
    except OSError:
        pass


def get_usd_krw(*, cache_path: str = DEFAULT_FX_CACHE, ttl: int = TTL_SECONDS,
                now=None, fetcher=None, allow_network: bool = True):
    """(환율, 출처라벨, 기준시각) 반환. 우선순위: env > 신선한 캐시 > 실시간 > 오래된 캐시 > 상수."""
    env = os.environ.get("TLL_USD_KRW")
    if env:
        try:
            return float(env), "수동 고정(env)", "-"
        except ValueError:
            pass

    now_dt = now or datetime.now(timezone.utc)
    now_ts = now_dt.timestamp()
    cache = _read_cache(cache_path)
    if cache and (now_ts - float(cache.get("fetched_ts", 0))) < ttl:
        return float(cache["rate"]), "자동(캐시)", cache.get("fetched_at", "")

    if allow_network:
        rate = _fetch_live(fetcher or _http_json)
        if rate:
            at = now_dt.isoformat(timespec="seconds")
            _write_cache(cache_path, {"rate": rate, "fetched_ts": now_ts, "fetched_at": at})
            return rate, "자동 갱신", at

    if cache:
        return float(cache["rate"]), "자동(캐시·오래됨)", cache.get("fetched_at", "")
    return float(_FALLBACK), "기본값", _FALLBACK_ASOF
