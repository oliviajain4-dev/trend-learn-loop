"""Triage(선별) — 에이전트 작동 순서의 2단계 (첫 '에이전트' 조각).

Scout가 찾은 트렌드 후보 중, LLM이 **'배울 가치 있는 IT/AI 기술이냐(교과서 감)'**를
판단해 상위 N개를 골라낸다. 여기부터 모델이 제어(무엇을 파고들지 선택) = 진짜 에이전트.
단, 최종 선별(top-N 정렬)은 결정론이고, LLM은 판단 근거만 제공한다.
"""

from tll.triage.models import TriageDecision, TriageResult
from tll.triage.triage import triage

__all__ = ["triage", "TriageResult", "TriageDecision"]
