"""TLL 대시보드 진입점 (Streamlit).

실행:
    streamlit run src/tll/dashboard/app.py
    → http://localhost:8501 (내 PC 전용 로컬)

역할:
    - data/briefs/*.json 을 데이터 계약(tll.schema)으로 로드.
    - 선택된 브리핑이 없으면 목록 화면, 있으면 상세 화면으로 라우팅.
    - 계약 위반 파일이 있으면 화면에 정직하게 오류를 노출(숨기지 않는다).
"""

from __future__ import annotations

import sys
from pathlib import Path

# `streamlit run` 은 이 파일을 스크립트로 실행하므로 패키지 임포트 경로(src)를 직접 추가.
# app.py: src/tll/dashboard/app.py → parents[2] == <repo>/src
_SRC = Path(__file__).resolve().parents[2]
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import streamlit as st  # noqa: E402

from tll.dashboard import render  # noqa: E402
from tll.schema import Brief, SchemaError  # noqa: E402


@st.cache_data(show_spinner=False)
def _load_briefs() -> tuple[list[Brief], list[str]]:
    """브리핑을 로드. (유효 목록, 오류메시지 목록) 반환.

    한 파일이 계약을 어겨도 나머지는 보여주되, 어긴 파일은 오류로 모아 노출한다.
    캐시하되 data/briefs 변경 시 사이드바 '새로고침'으로 무효화.
    """
    from tll.schema import DEFAULT_BRIEFS_DIR, load_brief

    briefs: list[Brief] = []
    errors: list[str] = []
    for p in sorted(DEFAULT_BRIEFS_DIR.glob("*.json")):
        try:
            briefs.append(load_brief(p, strict=True))
        except SchemaError as e:
            errors.append(str(e))
    return briefs, errors


def main() -> None:
    st.set_page_config(page_title="TLL — 정체 브리핑", page_icon="🧭", layout="wide")

    with st.sidebar:
        st.markdown("### 🧭 TLL")
        st.caption("Trend · Learn · Loop")
        if st.button("🔄 데이터 새로고침", use_container_width=True):
            _load_briefs.clear()
            st.rerun()

    briefs, errors = _load_briefs()

    # 계약 위반 파일은 숨기지 않고 노출 (정직 원칙)
    if errors:
        with st.expander(f"⚠️ 로드 실패 {len(errors)}건 (계약 위반)", expanded=False):
            for msg in errors:
                st.code(msg, language="text")

    selected_id = st.session_state.get("selected_brief_id")
    if selected_id:
        brief = next((b for b in briefs if b.id == selected_id), None)
        if brief is None:
            # 선택했던 브리핑이 사라짐(파일 삭제 등) → 목록으로 안전 복귀
            st.session_state.pop("selected_brief_id", None)
            st.rerun()
        else:
            render.render_detail(brief)
    else:
        render.render_list(briefs)


if __name__ == "__main__":
    main()
