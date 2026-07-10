"""Analyst(집필) — 수집물(CollectionResult)로 §3 양식 브리핑 '초안'을 쓴다.

- 출처 sid(S1..Sn)는 **코드가 결정론적으로 부여**(LLM 아님).
- LLM 은 그 출처만 근거로 각 사실 문장에 [S#] 을 달아 집필한다.
- 산출은 status="draft" 브리핑(아직 미검증). 지표는 0(미측정) → Metrics 단계에서 채운다.
- URL·날짜·수치는 출처 원본에서만(LLM 생성 금지, 프로젝트 DNA).
"""

from tll.analyst.writer import AnalystError, write_brief

__all__ = ["AnalystError", "write_brief"]
