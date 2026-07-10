"""Metrics + Eval-Harness — "신뢰도를 감이 아니라 숫자로", 그리고 그 숫자를 실측 검증.

- compute: 브리핑의 충실도 지표(결정론 프록시) 산출 + 브리핑에 반영.
- harness: 환각을 일부러 주입해 Verifier 검출률(recall)·오탐을 실측.

정직 고지: 진짜 FActScore(atomic-fact)·RAGAS·ALCE-NLI 는 '출처 원문 전체'가 있어야 한다.
현재는 본문 미수집 → **결정론 프록시**(인용 커버리지·유효율·신뢰출처 지지율)로 계산하고,
지표 이름 옆에 프록시임을 명시한다. 본문 수집 후 진짜 지표로 승격(로드맵).
"""

from tll.metrics.compute import apply_metrics, compute_metrics
from tll.metrics.harness import HarnessReport, inject, run_harness

__all__ = [
    "apply_metrics",
    "compute_metrics",
    "HarnessReport",
    "inject",
    "run_harness",
]
