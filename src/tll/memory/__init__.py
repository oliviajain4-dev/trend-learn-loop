"""Memory(기억) — 에이전트 작동 순서의 7단계. **대조·유추의 엔진**.

- 개념 KB(의미기억): 검증된 교과서를 '개념 카드'로 축적 → 다음 교과서가 "기존과 뭐가 다른지"를
  쓸 때 관련 개념을 회상해 근거로 준다. (CoALA 의미기억)
- lessons(에피소드기억, Reflexion): 실패·교훈을 기록해 다음 시도가 회피.
저장은 결정론(JSON), 회상은 용어 overlap(임베딩 아님 — 정직). 이게 '스스로 학습'의 실체.
"""

from tll.memory.memory import (
    ConceptKB,
    LessonLog,
    contrast_context,
    recall_related,
    record_lesson,
    recent_lessons,
    remember_textbook,
)
from tll.memory.models import ConceptCard, Lesson

__all__ = [
    "remember_textbook",
    "recall_related",
    "contrast_context",
    "record_lesson",
    "recent_lessons",
    "ConceptKB",
    "LessonLog",
    "ConceptCard",
    "Lesson",
]
