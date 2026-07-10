"""Loop — 에이전트 작동 순서의 마지막(9). 전부를 감싸는 ReAct 루프 + 스케줄러.

한 사이클: Scout → Triage → (후보별) Track → Read → [충분? 집필 : "더 찾자"→다음/lesson]
→ Author(+Memory 대조) → Fact-Check → Memory 기억 → 저장 → Dashboard.
안전장치: 예산(target)·시도 상한(max_attempts)·무진전 가드. run_forever 로 30분마다 자동.
"""

from tll.loop.loop import run_cycle, run_forever
from tll.loop.models import CycleResult

__all__ = ["run_cycle", "run_forever", "CycleResult"]
