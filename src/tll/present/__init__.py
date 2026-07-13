"""Present(산출) — 검증된 교과서를 자체 완결 HTML(서버 없이 브라우저로 여는 단일 파일)로 산출.

신선도·충실도%·원문 링크·미확인을 한눈에, 최신순.
(주 화면은 Streamlit 통합 앱 tll.manage.app — 교과서+관리·비용. 이 HTML 은 선택적 자동 export.)
"""

from tll.present.html import render_dashboard, save_dashboard
from tll.present.store import load_records, save_textbook

__all__ = ["render_dashboard", "save_dashboard", "save_textbook", "load_records"]
