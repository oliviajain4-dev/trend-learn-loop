"""사용량 로깅 + 집계 — 호출마다 토큰을 남기고, 일별/월별 요금을 계산한다.

- log_usage: 한 호출(provider·model·in/out 토큰)을 JSONL 한 줄로 append(결정론·추가전용).
- TrackingProvider: 실제 프로바이더를 감싸 generate 마다 자동 로깅(파이프라인 무침투).
- monthly_report: 월 필터 → 일별 표 + 모델별 + 합계(cost_usd 로 정확 계산).
UI 무관. 실제 토큰(공급자 usage) 기반이라 추정이 아니라 실측.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from tll.cost.pricing import cost_usd, price_for
from tll.shared.llm.base import LLMProvider, LLMResponse

DEFAULT_USAGE_PATH = "data/cost/usage.jsonl"


def log_usage(
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    *,
    stage: str = "",
    path: str = DEFAULT_USAGE_PATH,
    now: datetime | None = None,
) -> None:
    dt = now or datetime.now(timezone.utc)
    rec = {
        "ts": dt.isoformat(timespec="seconds"),
        "date": dt.date().isoformat(),
        "provider": provider,
        "model": model,
        "input_tokens": int(input_tokens or 0),
        "output_tokens": int(output_tokens or 0),
        "stage": stage,
    }
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def load_usage(path: str = DEFAULT_USAGE_PATH) -> list[dict]:
    if not os.path.exists(path):
        return []
    out: list[dict] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue  # 손상 줄은 건너뜀
    return out


class TrackingProvider(LLMProvider):
    """실제 프로바이더를 감싸 generate 마다 토큰을 로깅한다. 인터페이스는 동일(무침투)."""

    def __init__(self, inner: LLMProvider, *, provider_name: str, path: str = DEFAULT_USAGE_PATH, stage: str = "") -> None:
        self._inner = inner
        self.provider_name = provider_name
        self.path = path
        self.stage = stage
        self.name = getattr(inner, "name", provider_name)
        self.default_model = getattr(inner, "default_model", "")

    def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        max_tokens: int = 2048,
        temperature: float | None = None,
        model: str | None = None,
    ) -> LLMResponse:
        resp = self._inner.generate(
            prompt, system=system, max_tokens=max_tokens, temperature=temperature, model=model
        )
        u = resp.usage or {}
        log_usage(
            self.provider_name,
            resp.model,
            u.get("input_tokens"),
            u.get("output_tokens"),
            stage=self.stage,
            path=self.path,
        )
        return resp


def monthly_report(*, path: str = DEFAULT_USAGE_PATH, month: str | None = None) -> dict:
    """month='YYYY-MM'(None=전체) → {month, days[], by_model[], total, unpriced[]}."""
    recs = load_usage(path)
    if month:
        recs = [r for r in recs if str(r.get("date", "")).startswith(month)]

    days: dict[str, dict] = {}
    by_model: dict[str, dict] = {}
    unpriced: set[str] = set()
    tot = {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}

    for r in recs:
        d = r.get("date", "?")
        m = r.get("model", "?")
        it = int(r.get("input_tokens") or 0)
        ot = int(r.get("output_tokens") or 0)
        c = cost_usd(m, it, ot)
        if not price_for(m)["matched"]:
            unpriced.add(m)

        day = days.setdefault(d, {"date": d, "calls": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0})
        bm = by_model.setdefault(m, {"model": m, "calls": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0})
        for bucket in (day, bm, tot):
            bucket["calls"] += 1
            bucket["input_tokens"] += it
            bucket["output_tokens"] += ot
            bucket["cost_usd"] += c

    for bucket in list(days.values()) + list(by_model.values()):
        bucket["cost_usd"] = round(bucket["cost_usd"], 6)
    tot["cost_usd"] = round(tot["cost_usd"], 6)

    return {
        "month": month,
        "days": sorted(days.values(), key=lambda x: x["date"]),
        "by_model": sorted(by_model.values(), key=lambda x: -x["cost_usd"]),
        "total": tot,
        "unpriced": sorted(unpriced),
    }


def available_months(path: str = DEFAULT_USAGE_PATH) -> list[str]:
    return sorted({str(r.get("date", ""))[:7] for r in load_usage(path) if r.get("date")}, reverse=True)
