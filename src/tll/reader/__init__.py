"""Reader(독해) — 에이전트 작동 순서의 4단계, **ReAct 결정점**.

Tracker가 가져온 본문을 읽고 "이걸로 이 기술이 뭔지 교과서를 쓸 수 있나"를 판단한다.
- 충분 → proceed(집필로).
- 부족 → collect_more("더 찾자") → 루프가 Tracker/Scout로 되돌림.
여기서 **모델이 다음 행동(진행 vs 더 수집)을 스스로 고른다** = 진짜 에이전트 제어.
"""

from tll.reader.models import ReadResult, ReadVerdict
from tll.reader.reader import read

__all__ = ["read", "ReadResult", "ReadVerdict"]
