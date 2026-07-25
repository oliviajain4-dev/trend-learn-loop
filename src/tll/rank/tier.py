"""동물 티어 — 얇은 표시층. ConceptScore + (신뢰가능) 나이 → 배지. (점검 F1~F5 + RAG 재점검 반영)

정착(코끼리) = 거대 + **내구성** + 안 뜸 + 안 하락.
  내구성 = (신뢰가능 나이 ≥ 4년)  또는  (측정된 평탄 + 재등장 ≥3).
  · 나이는 **GitHub 저장소 생일만** 신뢰(arxiv 최초논문일은 안 씀 — 불량 대리).
  · 그래서 RAG(arxiv 단일소스, 신뢰나이 없음)·젊은 저장소(랭그래프 등)는 코끼리 못 됨.
합의는 독립 지표 수(arxiv_recent 제외). 단일소스인데 큰 것 = 거북이 '잠정'.
"""

from __future__ import annotations

from dataclasses import dataclass

from tll.rank.models import ConceptScore

TIERS = {
    "tiger":    ("🐯", "호랑이", "지금 배워라"),
    "elephant": ("🐘", "코끼리", "필수·기반"),
    "turtle":   ("🐢", "거북이", "참고·필요시"),
    "cheetah":  ("🐆", "치타", "지켜봐(잠정)"),
    "sprout":   ("🌱", "새싹", "관측 시작"),
    "dinosaur": ("🦕", "공룡", "참고만·이관"),
    "mayfly":   ("🦟", "하루살이", "무시"),
    "hyena":    ("🐺", "하이에나", "걸러(가짜·파생)"),
}


@dataclass
class Thresholds:
    attention_high: float = 50.0
    adoption_giant: float = 78.0
    adoption_high: float = 60.0
    adoption_mid: float = 38.0
    min_consensus: int = 2
    settle_recur: int = 3          # 재등장 ≥3 + 측정된 평탄 → '오래 평탄 관측'(내구성)
    mature_days: int = 1460        # 신뢰가능 나이 ≥4년 → 내구성(코끼리). GitHub 생일만.
    demote_after: int = 4


@dataclass
class TierResult:
    tier: str
    emoji: str
    label: str
    action: str
    provisional: bool


def assign_tier(score: ConceptScore, *, age_days: int | None = None, cfg: Thresholds | None = None) -> TierResult:
    cfg = cfg or Thresholds()
    s = score
    att_high = s.attention >= cfg.attention_high
    corroborated = s.corrob_kinds >= cfg.min_consensus
    giant = s.adoption >= cfg.adoption_giant
    high = s.adoption >= cfg.adoption_high
    mid = s.adoption >= cfg.adoption_mid
    rising = s.rising_kinds >= cfg.min_consensus and s.adoption_growth > 0
    declining = s.growth_measured and s.adoption_growth < 0
    flat_confirmed = s.growth_measured and not rising and not declining
    settled = flat_confirmed and s.recurrence >= cfg.settle_recur          # 오래 평탄 관측
    reliable_old = age_days is not None and age_days >= cfg.mature_days     # GitHub 생일만(arxiv 나이 X)
    durable = reliable_old or settled                                      # 내구성 = 둘 중 하나
    hot = rising or att_high

    if s.fake_flag:
        tier = "hyena"
    elif corroborated and giant and durable and not hot and not declining:
        tier = "elephant"        # 거대 + 내구성 + 안 뜸 = 정착·기반
    elif corroborated and high and declining:
        tier = "dinosaur"
    elif corroborated and high and hot:
        tier = "tiger"
    elif corroborated and mid:
        tier = "turtle"
    elif high:
        tier = "turtle"          # 단일소스인데 큼 = 주목할 만하나 미확인
    elif att_high and s.buzz_sources >= 1:
        demote = cfg.demote_after if s.buzz_sources >= 2 else 2   # 단일소스 화제는 빨리 하루살이(노이즈↑)
        tier = "cheetah" if s.recurrence < demote else "mayfly"
    elif att_high:
        tier = "sprout" if s.recurrence <= 1 else "mayfly"        # 주목 크나 독립 0 = 공식 자기홍보(허세 후보)
    elif rising:
        tier = "cheetah"
    elif s.recurrence <= 1:
        tier = "sprout"
    else:
        tier = "mayfly"

    emoji, label, action = TIERS[tier]
    if tier in ("tiger", "cheetah", "sprout"):
        prov = s.recurrence < cfg.demote_after
    elif tier == "turtle":
        prov = not durable        # 내구성(신뢰나이/오래평탄) 없으면 잠정
    else:
        prov = False
    return TierResult(tier=tier, emoji=emoji, label=label, action=action, provisional=prov)
