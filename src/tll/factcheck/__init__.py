"""Fact-Check(검증) — 에이전트 작동 순서의 6단계. **결정론 코어(LLM=0)**.

Author 교과서의 [S1] 인용을 **원문(body_text)과 실제로 대조**한다. 이제 Tracker→Author가
원문을 보존하므로, Phase 1의 '반쪽'(title 근사)이 아니라 진짜 본문 대조가 된다.
- 유령 인용 검출 / 인용문 원문 존재 / 수치 앵커링(원문에 없는 숫자) / 미인용 / 일반지식 표시
- 진짜 충실도%(원문 근거) 산출. 같은 입력 → 같은 판정(재현성). 검증기 자신은 환각 안 함.
"""

from tll.factcheck.factcheck import apply, check_textbook
from tll.factcheck.models import FactCheckReport, SentenceVerdict

__all__ = ["check_textbook", "apply", "FactCheckReport", "SentenceVerdict"]
