"""Tracker(추적) — 에이전트 작동 순서의 3단계.

Triage가 선별한 주제의 **공식 문서 본문을 실제로 가져온다**(그 '검증 반쪽' 구멍 메우기).
등급은 원천 근접도(1차/2차/3차) + 성격 태그(제작사/논문/레포/뉴스/블로그).
"""

from tll.tracker.grading import classify_source
from tll.tracker.models import TrackedDoc, TrackResult
from tll.tracker.tracker import track

__all__ = ["track", "TrackResult", "TrackedDoc", "classify_source"]
