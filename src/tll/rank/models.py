"""랭킹 모델 — 개념 하나의 '측정된' 점수. 감이 아니라 신호에서 계산된다."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ConceptScore:
    cid: str
    attention: float        # 주목(버즈형 신호의 감쇠 합, 소스 가중) — 빨리 식음
    adoption: float         # 채택 수준 0-100 (참여 중심 크기를 포화정규화) — 별은 강등
    adoption_growth: float  # 최근 창(window)의 절대 성장(>0 = 상승 중)
    accelerating: bool      # 최근 성장 > 직전 창 성장 (모멘텀 ↑)
    rising_kinds: int       # 상승 중인 '독립' 채택 신호 수 (다중신호 합의)
    stock_kinds: int        # 관측된 채택 신호 종류 수(전체)
    recurrence: int         # 등장한 서로 다른 날짜 수 (지속성)
    fake_flag: bool         # 스타↑인데 '있는' 참여(이슈·PR·포크)가 정체 (가짜 의심)
    n_signals: int
    growth_measured: bool = False  # 베이스라인이 있어 '성장/평탄'을 실제로 잰 적 있나
    corrob_kinds: int = 0          # 독립 채택 지표 수(arxiv_recent 제외 — 동일소스 중복 안 셈)
    adoption_mag: float = 0.0      # 정규화 전 원자료 크기(참여 중심)
    buzz_sources: int = 0          # 화제를 낸 '서로 다른 소스' 수 (여러 곳서 떠야 진짜 화제)
