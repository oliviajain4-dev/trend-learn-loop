"""Scout(정찰) — 에이전트 작동 순서의 1단계.

실시간 소스를 훑어 '새로 뜬' 트렌드 후보를 뽑는다(순수 결정론, LLM 0).
'교과서 감이냐'는 판단은 다음 단계 Triage(에이전트)가 한다 — 여기선 발견·신규성만.
"""

from tll.scout.models import ScoutResult, TrendCandidate
from tll.scout.scout import scout
from tll.scout.seen_store import SeenStore

__all__ = ["scout", "ScoutResult", "TrendCandidate", "SeenStore"]
