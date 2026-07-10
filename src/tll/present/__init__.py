"""Present(산출) — 에이전트 작동 순서의 8단계, 한국어 대시보드.

검증된 교과서를 **자체 완결 HTML**(서버 없이 브라우저로 여는 단일 파일)로 산출한다.
신선도("3시간 전")·충실도%(원문근거)·원문 링크·미확인을 한눈에, 최신순.
(기존 Streamlit 대시보드 `tll.dashboard` 는 그대로 — 이건 자율 교과서용 새 Presenter.)
"""

from tll.present.html import render_dashboard, save_dashboard
from tll.present.store import load_records, save_textbook

__all__ = ["render_dashboard", "save_dashboard", "save_textbook", "load_records"]
