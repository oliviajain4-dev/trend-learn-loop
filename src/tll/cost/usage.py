"""사용량 로깅 + 집계 — 호출마다 토큰을 남기고, 일별/월별 요금을 계산한다.

- log_usage: 한 호출(provider·model·in/out 토큰)을 JSONL 한 줄로 append(결정론·추가전용).
- TrackingProvider: 실제 프로바이더를 감싸 generate 마다 자동 로깅(파이프라인 무침투).
- monthly_report: 월 필터 → 일별 표 + 모델별 + 합계(cost_usd 로 정확 계산).
UI 무관. 실제 토큰(공급자 usage) 기반이라 추정이 아니라 실측.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone

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


def monthly_report(*, path: str = DEFAULT_USAGE_PATH, month: str | None = None,
                   paid_provider: str | None = None) -> dict:
    """month='YYYY-MM'(None=전체) → {month, days[], by_model[], total, unpriced[]}.

    cost_usd = 모든 프로바이더의 '정가'(참고용, 무료 티어여도 계산됨).
    paid_provider 를 주면 각 버킷에 paid_cost_usd(그 프로바이더분만 = 실제 청구)도 같이 낸다 —
    무료 프로바이더는 cost_usd > 0 이어도 paid_cost_usd = 0 이라 화면에서 명확히 구분된다."""
    recs = load_usage(path)
    if month:
        recs = [r for r in recs if str(r.get("date", "")).startswith(month)]

    days: dict[str, dict] = {}
    by_model: dict[str, dict] = {}
    unpriced: set[str] = set()
    tot = {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0, "paid_cost_usd": 0.0}

    for r in recs:
        d = r.get("date", "?")
        m = r.get("model", "?")
        prov = r.get("provider", "?")
        it = int(r.get("input_tokens") or 0)
        ot = int(r.get("output_tokens") or 0)
        c = cost_usd(m, it, ot)
        paid_c = c if (paid_provider is not None and prov == paid_provider) else 0.0
        if not price_for(m)["matched"]:
            unpriced.add(m)

        day = days.setdefault(d, {"date": d, "calls": 0, "input_tokens": 0, "output_tokens": 0,
                                  "cost_usd": 0.0, "paid_cost_usd": 0.0})
        bm = by_model.setdefault(m, {"model": m, "provider": prov, "calls": 0, "input_tokens": 0,
                                     "output_tokens": 0, "cost_usd": 0.0, "paid_cost_usd": 0.0})
        for bucket in (day, bm, tot):
            bucket["calls"] += 1
            bucket["input_tokens"] += it
            bucket["output_tokens"] += ot
            bucket["cost_usd"] += c
            bucket["paid_cost_usd"] += paid_c

    for bucket in list(days.values()) + list(by_model.values()) + [tot]:
        bucket["cost_usd"] = round(bucket["cost_usd"], 6)
        bucket["paid_cost_usd"] = round(bucket["paid_cost_usd"], 6)

    return {
        "month": month,
        "paid_provider": paid_provider,
        "days": sorted(days.values(), key=lambda x: x["date"]),
        "by_model": sorted(by_model.values(), key=lambda x: -x["cost_usd"]),
        "total": tot,
        "unpriced": sorted(unpriced),
    }


def available_months(path: str = DEFAULT_USAGE_PATH) -> list[str]:
    return sorted({str(r.get("date", ""))[:7] for r in load_usage(path) if r.get("date")}, reverse=True)


def _stage_breakdown(recs: list[dict]) -> list[dict]:
    by_stage: dict[str, dict] = {}
    for r in recs:
        st = r.get("stage") or "기타(이전 기록)"
        it, ot = int(r.get("input_tokens") or 0), int(r.get("output_tokens") or 0)
        b = by_stage.setdefault(st, {"stage": st, "calls": 0, "cost_usd": 0.0})
        b["calls"] += 1
        b["cost_usd"] += cost_usd(r.get("model", "?"), it, ot)
    for b in by_stage.values():
        b["cost_usd"] = round(b["cost_usd"], 6)
    return sorted(by_stage.values(), key=lambda x: -x["cost_usd"])


def _period(recs: list[dict]) -> dict:
    cost = sum(
        cost_usd(r.get("model", "?"), int(r.get("input_tokens") or 0), int(r.get("output_tokens") or 0))
        for r in recs
    )
    return {
        "calls": len(recs),
        "cost_usd": round(cost, 6),
        "by_stage": _stage_breakdown(recs),
        "models": sorted({r.get("model", "?") for r in recs}),
    }


def paid_summary(path: str = DEFAULT_USAGE_PATH, *, paid_provider: str = "anthropic",
                 now: datetime | None = None) -> dict:
    """실제 '유료' 프로바이더(기본 anthropic)만 걸러 오늘/이번주(월요일부터)/이번달/전체누적 지출 +
    각 구간마다 무엇에 썼는지(stage: 선별·판단/집필/개념·설명서/교차검증) + 실제 쓰인 모델명.
    Gemini 는 무료 티어 사용을 전제로 이 집계에서 제외(관리>비용 화면이 '실제 나가는 돈'에 집중하도록)."""
    today = (now or datetime.now(timezone.utc)).date()
    week_start = (today - timedelta(days=today.weekday())).isoformat()
    month = today.isoformat()[:7]

    recs = [r for r in load_usage(path) if r.get("provider") == paid_provider]
    today_recs = [r for r in recs if r.get("date") == today.isoformat()]
    week_recs = [r for r in recs if str(r.get("date", "")) >= week_start]
    month_recs = [r for r in recs if str(r.get("date", ""))[:7] == month]

    return {
        "provider": paid_provider,
        "today": _period(today_recs),
        "week": _period(week_recs),
        "month": _period(month_recs),
        "all_time": _period(recs),
    }
