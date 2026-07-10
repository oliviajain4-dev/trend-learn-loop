"""브리핑을 Streamlit 화면에 그리는 함수들.

- 목록 화면(render_list): 카드 그리드. 각 카드에 상태 배지·충실도·출처수·최초확인.
- 상세 화면(render_detail): [4단계]에서 본문/게이지/출처표/미확인을 채운다.
- 공통 헬퍼: 상태 배지·충실도 색상 — 목록과 상세가 같은 규칙을 공유한다.

원칙: 샘플 데이터의 숫자가 진짜처럼 보이지 않게 status 배지로 구분한다.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from tll.schema import (
    SECTION_ORDER,
    Brief,
    Judgment,
    Media,
    Metrics,
    Reaction,
    Source,
    Unverified,
)

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

        if st.button("자세히 보기 →", key=f"view_{brief.id}", width="stretch"):
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
# 상세 화면 — §3 순서대로: 헤더 지표 → 0~9 섹션 → 출처표 → 미확인
# ─────────────────────────────────────────────────────────────────────────────

# 여론 감성 표기 (이모지, 라벨, 색)
_SENTIMENT_STYLE = {
    "positive": ("😊", "긍정", "#16a34a"),
    "negative": ("😟", "부정", "#dc2626"),
    "mixed": ("😐", "엇갈림", "#d97706"),
    "neutral": ("😶", "중립", "#6b7280"),
}

# 판단 도우미 수준 표기
_LEVEL_STYLE = {
    "high": ("🟢", "높음"),
    "medium": ("🟡", "중간"),
    "low": ("🔴", "낮음"),
}

# 출처 등급 라벨
_GRADE_LABEL = {1: "1급 (최상)", 2: "2급 (보통)", 3: "3급 (약함)"}


def _metric_gauge(value: float, title: str) -> go.Figure:
    """0~1 지표를 반원 게이지로. 색은 목록과 같은 fidelity_color 규칙."""
    color = fidelity_color(value)
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=value * 100,
            number={"suffix": "%", "font": {"size": 24}},
            title={"text": title, "font": {"size": 13}},
            gauge={
                "axis": {"range": [0, 100], "tickwidth": 1, "tickvals": [0, 50, 100]},
                "bar": {"color": color},
                "steps": [
                    {"range": [0, 75], "color": "#fee2e2"},
                    {"range": [75, 90], "color": "#fef3c7"},
                    {"range": [90, 100], "color": "#dcfce7"},
                ],
            },
        )
    )
    fig.update_layout(
        height=190,
        margin={"l": 15, "r": 15, "t": 45, "b": 10},
        paper_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def _render_metrics_header(brief: Brief) -> None:
    """상단 측정 지표: 4개 게이지 + 출처수·최초확인."""
    m: Metrics = brief.metrics
    st.subheader("측정된 신뢰도")
    if brief.is_sample:
        st.caption("아래 수치는 **샘플** 입니다 — 실제 측정값이 아닙니다.")

    gauges = [
        (m.atomic_support_rate, "충실도 (atomic-fact 지지율)"),
        (m.ragas_faithfulness, "RAGAS faithfulness"),
        (m.citation_precision, "인용 정밀도"),
        (m.citation_recall, "인용 재현율"),
    ]
    for col, (value, title) in zip(st.columns(4), gauges):
        with col:
            st.plotly_chart(_metric_gauge(value, title), width="stretch")

    c1, c2 = st.columns(2)
    c1.metric("출처 개수", f"{m.source_count}개")
    c2.metric("최초확인", brief.first_seen)


def _render_media(media: Media) -> None:
    st.subheader("7. 미디어 (유튜브)")
    total = len(media.youtube_global) + len(media.youtube_kr)
    if total == 0:
        st.caption(
            "링크·조회수는 **YouTube API 실데이터로만** 채웁니다(LLM 생성 금지). "
            "현재 샘플이라 비어 있습니다."
        )
        return
    for label, items in (("글로벌", media.youtube_global), ("한국어", media.youtube_kr)):
        if items:
            st.markdown(f"**{label}**")
            for it in items:
                views = f" · 조회수 {it.view_count:,}" if it.view_count is not None else ""
                st.markdown(f"- [{it.title}]({it.url}) — {it.channel}{views}")


def _render_reactions(reactions: list[Reaction]) -> None:
    st.subheader("8. 사람들의 반응 (여론)")
    st.caption("⚠️ 여론은 **사실이 아니라 감성**입니다. 참고용.")
    if not reactions:
        st.caption("수집된 반응이 없습니다.")
        return
    for r in reactions:
        emoji, label, color = _SENTIMENT_STYLE.get(r.sentiment, ("•", r.sentiment, "#6b7280"))
        with st.container(border=True):
            st.markdown(
                f"<span style='color:{color};font-weight:700;'>{emoji} {label}</span> "
                f"· {r.source}",
                unsafe_allow_html=True,
            )
            st.write(r.summary)
            st.markdown(f"[원문 링크]({r.url}) · 수집 {r.collected_at}")


def _render_judgment(judgment: Judgment) -> None:
    st.subheader("9. 판단 도우미")
    items = [
        ("배울 가치", judgment.worth_learning),
        ("성숙도", judgment.maturity),
        ("나와의 관련성", judgment.relevance),
    ]
    for col, (name, item) in zip(st.columns(3), items):
        emoji, label = _LEVEL_STYLE.get(item.level, ("•", item.level))
        with col:
            st.markdown(f"**{name}**")
            st.markdown(f"### {emoji} {label}")
            st.caption(item.note)


def _render_sources(sources: list[Source]) -> None:
    st.subheader("출처 (provenance)")
    if not sources:
        st.caption("출처가 없습니다.")
        return
    df = pd.DataFrame(
        [
            {
                "[S#]": s.sid,
                "제목": s.title,
                "기관": s.org,
                "발행일": s.date,
                "등급": _GRADE_LABEL.get(s.grade, str(s.grade)),
                "URL": s.url,
                "수집시각": s.collected_at,
            }
            for s in sources
        ]
    )
    st.dataframe(
        df,
        width="stretch",
        hide_index=True,
        column_config={"URL": st.column_config.LinkColumn("URL", display_text="열기")},
    )


def _render_unverified(unverified: list[Unverified]) -> None:
    st.subheader("⚠️ 미확인 · 출처 충돌")
    if not unverified:
        st.success("미확인/충돌로 표시된 주장이 없습니다.")
        return
    st.caption("근거가 약하거나 출처가 충돌하는 주장을 숨기지 않고 드러냅니다(정직 원칙).")
    for u in unverified:
        conflict = (
            f"  \n충돌 출처: {', '.join(u.conflicting_sids)}" if u.conflicting_sids else ""
        )
        st.warning(f"**{u.claim}**  \n사유: {u.reason}{conflict}")


def render_detail(brief: Brief) -> None:
    """브리핑 1건 상세 — §3 표준 양식 순서 그대로."""
    if st.button("← 목록으로"):
        st.session_state.pop("selected_brief_id", None)
        st.rerun()

    st.markdown(status_badge_html(brief), unsafe_allow_html=True)
    st.title(brief.tech_name)

    # 샘플이면 크게 경고 (측정값 오인 방지)
    if brief.is_sample:
        st.error(
            "🧪 **샘플 데이터 — 실제 측정값이 아닙니다.** "
            "이 화면의 지표·수치는 형식 확인용 자리표시입니다.",
            icon="🧪",
        )

    # 0. 한 줄 정체
    st.markdown(f"> **0. 한 줄 정체** — {brief.one_liner}")

    # 헤더: 측정 지표
    _render_metrics_header(brief)
    st.divider()

    # 1~6 본문 섹션 (§3 순서)
    for key, num, label in SECTION_ORDER:
        st.subheader(f"{num}. {label}")
        st.markdown(getattr(brief.sections, key))

    st.divider()
    _render_media(brief.media)
    _render_reactions(brief.reactions)
    _render_judgment(brief.judgment)
    st.divider()
    _render_sources(brief.sources)
    _render_unverified(brief.unverified)
