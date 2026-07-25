"""Author(집필) — 에이전트 작동 순서의 5단계.

Reader가 '충분'으로 판정한 공식 문서 본문으로 **한국어 교과서(정체 브리핑)**를 쓴다.
- 문장별 [S1] 인용, 원문(body_text) 보존 → 이후 Fact-Check가 실제 대조.
- 특히 **대조·유추**(기존/유사 기술과 뭐가 같고 다른지)를 충실히.
결과의 사실성은 여기서 보장하지 않는다 — Fact-Check(결정론 L1)가 원문으로 판정한다.
"""

from tll.author.author import author_all, write_textbook
from tll.author.models import Source, Textbook

__all__ = ["write_textbook", "author_all", "Textbook", "Source"]
