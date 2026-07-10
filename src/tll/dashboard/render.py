"""브리핑을 Streamlit 화면에 그리는 함수들.

- 목록 화면(render_list): 카드 그리드. 각 카드에 상태 배지·충실도·출처수·최초확인.
- 상세 화면(render_detail): [4단계]에서 본문/게이지/출처표/미확인을 채운다.
- 공통 헬퍼: 상태 배지·충실도 색상 — 목록과 상세가 같은 규칙을 공유한다.

원칙: 샘플 데이터의 숫자가 진짜처럼 보이지 않게 status 배지로 구분한다.
"""

from __future__ import annotations

import streamlit as st

from tll.schema import Brief

# ─────────────────────────────────────────────────────────────────────────────
# 공통 색상 규칙 (목록·상세가 공유하는 단일 근거)
# ─────────────────────────────────────────────────────────────────────────────

# 상태별 배지 색 (배경, 글자)
_STATUS_STYLE = {
    "sample": ("#f59e0b", "#1f2937"),   # 앰버 — 샘플/자리표시(측정값 아님)
    "draft": ("#3b82f6", "#ffffff"),    # 파랑 — 초안(미검증)
    "verified": ("#16a34a", "#ffffff"),  # 초록 — 검증됨
}


def fidelity_color(rate: float) -> str:
    """충실도(0~1)를 색으로. 높음=초록 / 중간=앰버 / 낮음=빨강."""
    if rate >= 0.9:
        return "#16a34a"
    if rate >= 0.75:
        return "#d97706"
    return "#dc2626"


def status_badge_html(brief: Brief) -> str:
    """상태 배지 HTML. is_sample 이면 '측정값 아님'을 덧붙여 정직하게."""
    bg, fg = _STATUS_STYLE.get(brief.status, ("#6b7280", "#ffffff"))
    extra = " · 측정값 아님" if brief.is_sample else ""
    return (
        f"<span style='background:{bg};color:{fg};padding:2px 10px;"
        f"border-radius:999px;font-size:0.78rem;font-weight:700;white-space:nowrap;'>"
        f"{brief.status_label}{extra}</span>"
    )


def _pct(x: float) -> str:
    return f"{x * 100:.0f}%"


# ─────────────────────────────────────────────────────────────────────────────
# 목록 화면
# ─────────────────────────────────────────────────────────────────────────────


def _render_card(brief: Brief) -> None:
    """브리핑 1건을 카드로. '자세히 보기' 클릭 시 상세로 라우팅."""
    with st.container(border=True):
        st.markdown(status_badge_html(brief), unsafe_allow_html=True)
        st.markdown(f"### {brief.tech_name}")
        st.caption(brief.one_liner)

        # 충실도 강조 (색 입힌 퍼센트 + 진행 막대)
        rate = brief.metrics.atomic_support_rate
        color = fidelity_color(rate)
        st.markdown(
            f"<div style='font-size:0.8rem;color:#6b7280;margin-bottom:-6px;'>충실도 "
            f"(atomic-fact 지지율)</div>"
            f"<div style='font-size:1.9rem;font-weight:800;color:{color};line-height:1.1;'>"
            f"{_pct(rate)}</div>",
            unsafe_allow_html=True,
        )
        st.progress(rate)

        st.caption(f"📄 출처 {brief.metrics.source_count}개 · 🗓 최초확인 {brief.first_seen}")

        if st.button("자세히 보기 →", key=f"view_{brief.id}", use_container_width=True):
            st.session_state["selected_brief_id"] = brief.id
            st.rerun()


def render_list(briefs: list[Brief], *, columns: int = 3) -> None:
    """브리핑 카드 그리드. 파일명순(load_all_briefs)이라 순서가 결정론적."""
    st.title("🧭 TLL — 정체 브리핑")
    st.caption(
        "빠르게 변하는 IT/AI 기술의 '신뢰할 수 있는 이해'를 빠르게 형성하기 위한 대시보드. "
        "각 카드의 충실도는 측정된 값이며, 샘플은 배지로 구분된다."
    )

    if not briefs:
        st.info("표시할 브리핑이 없습니다. `data/briefs/`에 브리핑 JSON을 추가하세요.")
        return

    # 지금은 전부 샘플 → 상단에 한 번 정직하게 고지
    if all(b.is_sample for b in briefs):
        st.warning(
            "⚠️ 현재 표시되는 브리핑은 **샘플 데이터**입니다. "
            "수치는 형식 확인용이며 **실제 측정값이 아닙니다.**",
            icon="⚠️",
        )

    st.markdown(f"**{len(briefs)}건**의 브리핑")

    # n개씩 끊어 행으로 배치
    for i in range(0, len(briefs), columns):
        row = briefs[i : i + columns]
        cols = st.columns(columns)
        for col, brief in zip(cols, row):
            with col:
                _render_card(brief)


# ─────────────────────────────────────────────────────────────────────────────
# 상세 화면 (자리표시 — [4단계]에서 본문/게이지/출처표/미확인을 채운다)
# ─────────────────────────────────────────────────────────────────────────────


def render_detail(brief: Brief) -> None:
    if st.button("← 목록으로"):
        st.session_state.pop("selected_brief_id", None)
        st.rerun()

    st.markdown(status_badge_html(brief), unsafe_allow_html=True)
    st.title(f"{brief.tech_name}")
    st.info("상세 화면(측정 지표 게이지·본문 섹션·출처표·미확인)은 [4단계]에서 구현됩니다.")
