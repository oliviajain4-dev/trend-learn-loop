"""API 요금표 — 실제 공식 단가(per 1M tokens, USD). 정확 계산의 근거.

정직 고지:
  - 기준일 PRICING_ASOF. 가격은 바뀔 수 있으니 실제 청구는 콘솔에서 재확인 권장.
  - 모델명은 substring 매칭(구체 → 일반 순서). 별칭('...-latest')은 추정치 + 비고 표기.
  - Gemini Flash-Lite 는 무료 티어(쿼터 내)면 실제 청구 $0. 아래는 '유료 단가 환산'.
  - 캐싱·배치 할인은 미반영(정가 기준).
출처(2026-07-10 확인): Gemini https://ai.google.dev/gemini-api/docs/pricing ·
  Anthropic https://platform.claude.com/docs/en/about-claude/pricing
"""

from __future__ import annotations

PRICING_ASOF = "2026-07-10"
PRICING_SOURCES = {
    "gemini": "https://ai.google.dev/gemini-api/docs/pricing",
    "anthropic": "https://platform.claude.com/docs/en/about-claude/pricing",
}

# (매칭 substring(소문자), input_per_1M, output_per_1M, 표시명, 비고). **구체적인 것 먼저.**
_TABLE: list[tuple[str, float, float, str, str]] = [
    ("claude-opus-4-8", 5.00, 25.00, "Claude Opus 4.8", ""),
    ("claude-opus-4.8", 5.00, 25.00, "Claude Opus 4.8", ""),
    ("claude-opus-4-6", 5.00, 25.00, "Claude Opus 4.6", ""),
    ("claude-opus-4", 15.00, 75.00, "Claude Opus 4 (구세대)", "legacy"),
    ("claude-haiku-4-5", 1.00, 5.00, "Claude Haiku 4.5", ""),
    ("claude-sonnet-5", 3.00, 15.00, "Claude Sonnet 5", "인트로 $2/$10 (~2026-08-31)"),
    ("gemini-3.1-flash-lite", 0.25, 1.50, "Gemini 3.1 Flash-Lite", ""),
    ("gemini-2.5-flash-lite", 0.10, 0.40, "Gemini 2.5 Flash-Lite", ""),
    ("flash-lite", 0.10, 0.40, "Gemini Flash-Lite (별칭)", "2.5 기준 추정 · 무료 티어면 쿼터 내 $0"),
]

# UI 표시용 단가표(공용)
PRICES = [
    {"model": label, "input_per_1m": ip, "output_per_1m": op, "note": note}
    for _sub, ip, op, label, note in _TABLE
]


def price_for(model: str) -> dict:
    """모델명 → {input, output(per 1M), label, note, matched}. 미등록이면 matched=False."""
    m = (model or "").lower()
    for sub, ip, op, label, note in _TABLE:
        if sub in m:
            return {"input": ip, "output": op, "label": label, "note": note, "matched": True}
    return {"input": 0.0, "output": 0.0, "label": model or "?", "note": "미등록 모델 — 콘솔에서 단가 확인", "matched": False}


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    """실제 토큰 수 × 단가 = USD. 미등록 모델은 0.0(집계에서 '미등록'으로 표시)."""
    p = price_for(model)
    it = int(input_tokens or 0)
    ot = int(output_tokens or 0)
    return (it / 1_000_000) * p["input"] + (ot / 1_000_000) * p["output"]


# 원화 환산 (표시용). 환율은 수시 변동 → 기준일 명시 + 환경변수 TLL_USD_KRW 로 덮어쓸 수 있다.
USD_KRW = 1510.0
USD_KRW_ASOF = "2026-07-11"
