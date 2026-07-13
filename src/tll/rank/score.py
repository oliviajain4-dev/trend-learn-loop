"""주목·채택 2시계열 계산 — 개념의 신호들에서 결정론으로 점수를 뽑는다. (규칙문서/점검보고서 반영)

- 주목(버즈형)은 빨리 식는다 → 지수감쇠(반감기).
- 채택 '크기'는 별이 아니라 **참여(포크·이슈·PR)** 중심으로 잰다 — 별은 0.1로 강등(가짜·인기 왜곡 방지, 자체 연구근거).
- 채택 '수준'은 채널별 스케일이 달라 손앵커 대신 **포화함수 100·m/(m+K)** 로 0-100 정규화(채널 간 max).
- 성장은 '이전 스냅샷(베이스라인)'이 있을 때만 잰다 → 첫 관측을 '0에서 폭증/정착'으로 오인하지 않음. growth_measured 로 표시.
- 합의(corroboration)는 독립 지표 수. **arxiv_recent 는 arxiv_total 과 같은 소스라 세지 않는다**(동일소스 중복 방지).
둘을 절대 한 점수로 합치지 않는다 — attention 과 adoption 은 별개 축.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta

from tll.rank.models import ConceptScore

BUZZ, STOCK = "buzz", "stock"
ENGAGEMENT_KINDS = ("issues", "prs", "forks")   # 진짜 사용의 흔적

_KIND_CHANNEL = {
    "stars": "github", "forks": "github", "issues": "github", "prs": "github",
    "arxiv_total": "arxiv", "arxiv_recent": "arxiv",
    "term_freq": "community",
}
# 채택 '크기' 가중치 — 별은 강등(0.1), 참여(포크·PR)는 1.0, 이슈 0.5.
_ENGAGE_WEIGHT = {"forks": 1.0, "prs": 1.0, "issues": 0.5, "stars": 0.1, "term_freq": 1.0}
# 포화 상수 K(채널별): m=K 에서 지수 50. 참여 규모에 맞춰 보정 가능.
_SAT_K = {"github": 8000.0, "arxiv": 1500.0, "community": 30.0}
_NON_CORROB = {"arxiv_recent"}   # 합의 계산에서 제외(동일소스 파생지표)
# 소스 '역할' = (주목 가중, 독립 여부). 공식/벤더 = 발표(존재·최신) 원천이지만 자기홍보라
# '중요도 독립 투표'로는 안 침(독립 False) — 남이 독립적으로 받아줘야 자랑, 공식만이면 허세.
# 주목엔 약하게(0.5)만 반영. 커뮤니티=1.0(유기적), 유튜브=0.8(실무·교육 관심).
_SOURCE_ROLE = {
    "official": (0.5, False), "vendor": (0.5, False), "press": (0.5, False),
    "hackernews": (1.0, True), "reddit": (1.0, True), "geeknews": (1.0, True),
    "youtube": (0.8, True),
}


def _role(src: str) -> tuple[float, bool]:
    return _SOURCE_ROLE.get((src or "").strip().lower(), (1.0, True))


def channel_mags(latest_by_kind: dict[str, float]) -> dict[str, float]:
    """채널별 채택 '크기'(참여 중심). github=Σ가중, arxiv=총논문수(최근은 크기에 안 씀)."""
    mags: dict[str, float] = {}
    for kind, val in latest_by_kind.items():
        v = max(float(val), 0.0)
        ch = _KIND_CHANNEL.get(kind, "github")
        if ch == "arxiv":
            if kind == "arxiv_total":
                mags["arxiv"] = max(mags.get("arxiv", 0.0), v)
        else:
            mags[ch] = mags.get(ch, 0.0) + _ENGAGE_WEIGHT.get(kind, 0.3) * v
    return mags


def adoption_from_mags(mags: dict[str, float]) -> tuple[float, float]:
    """채널별 크기 → 포화정규화 0-100, 채널 간 max. 반환 (지수, 대표크기)."""
    best = 0.0
    mag = 0.0
    for ch, m in mags.items():
        k = _SAT_K.get(ch, 8000.0)
        best = max(best, 100.0 * m / (m + k))
        mag = max(mag, m)
    return best, mag


def _as_date(x) -> date:
    if isinstance(x, datetime):
        return x.date()
    if isinstance(x, date):
        return x
    return date.fromisoformat(str(x))


def _val_at_or_before(series, cutoff: date):
    """series: [(date,value)] 오름차순. cutoff 이하 마지막 값. 없으면 None(=베이스라인 없음, 성장 못 잼)."""
    v = None
    for d, val in series:
        if d <= cutoff:
            v = val
        else:
            break
    return v


def score_concept(signals, *, now, half_life_days: float = 3.0, window_days: int = 14) -> ConceptScore:
    """한 개념의 신호 리스트 → ConceptScore. now 기준으로 감쇠·성장 계산."""
    now_d = _as_date(now)
    cid = signals[0].cid if signals else ""

    attention = 0.0
    buzz_srcs: set[str] = set()
    stock: dict[str, list[tuple[date, float]]] = defaultdict(list)
    dates: set[date] = set()
    for s in signals:
        d = _as_date(s.date)
        dates.add(d)
        if s.family == BUZZ:
            age = max(0, (now_d - d).days)
            w, indep = _role(s.source)
            attention += s.value * (0.5 ** (age / half_life_days)) * w
            if s.value > 0 and indep:           # 독립 소스만 '진짜 화제' 근거로 셈(공식 자기홍보 제외)
                buzz_srcs.add((s.source or "").lower())
        else:
            stock[s.kind].append((d, s.value))

    cut1 = now_d - timedelta(days=window_days)
    cut2 = now_d - timedelta(days=2 * window_days)
    recent_sum = prev_sum = 0.0
    rising = 0
    delta_by_kind: dict[str, float] = {}
    measured: dict[str, bool] = {}
    latest_by_kind: dict[str, float] = {}
    for k, ser in stock.items():
        ser.sort(key=lambda t: t[0])
        latest = ser[-1][1]
        p1 = _val_at_or_before(ser, cut1)
        p2 = _val_at_or_before(ser, cut2)
        has_base = p1 is not None
        d1 = (latest - p1) if has_base else 0.0
        d0 = (p1 - p2) if (has_base and p2 is not None) else 0.0
        delta_by_kind[k] = d1
        measured[k] = has_base
        latest_by_kind[k] = latest
        recent_sum += d1
        prev_sum += d0
        if d1 > 0:
            rising += 1

    mags = channel_mags(latest_by_kind)
    adoption, adoption_mag = adoption_from_mags(mags)
    accelerating = recent_sum > prev_sum
    growth_measured = any(measured.values())
    corrob_kinds = sum(1 for k in stock if k not in _NON_CORROB)

    # 가짜: 스타가 '측정된' 성장으로 오르는데, '측정된' 참여가 정체일 때만(첫 관측엔 판단 보류).
    fake = False
    if measured.get("stars") and delta_by_kind.get("stars", 0.0) > 0:
        eng = [delta_by_kind[k] for k in ENGAGEMENT_KINDS if measured.get(k)]
        if eng and sum(eng) <= 0:
            fake = True

    return ConceptScore(
        cid=cid, attention=attention, adoption=adoption, adoption_growth=recent_sum,
        accelerating=accelerating, rising_kinds=rising, stock_kinds=len(stock),
        recurrence=len(dates), fake_flag=fake, n_signals=len(signals),
        growth_measured=growth_measured, corrob_kinds=corrob_kinds, adoption_mag=adoption_mag,
        buzz_sources=len(buzz_srcs),
    )
