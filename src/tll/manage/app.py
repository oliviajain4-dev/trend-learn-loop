"""TLL 통합 콘솔 (Streamlit) — 한 앱. 실행: streamlit run src/tll/manage/app.py

- 📚 기술: 에이전트가 스스로 찾은 '기술'을 주목×채택 티어순으로. 기술명이 제목, 펼치면 한국어 설명·원문.
- ⚙️ 관리 > 개요: 현재 모델·교과서 수.
- ⚙️ 관리 > 비용: 월 선택 → 일별/모델별 사용량·요금·월 합계 + 차트 + 단가표.
데이터는 공용 엔진(tll.rank / tll.present.store / tll.cost)에서 읽는다.
"""

from __future__ import annotations

import os
import sys

# streamlit run 으로 직접 실행해도 tll 이 임포트되게 src 를 경로에 추가.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import re  # noqa: E402
from datetime import datetime, timezone  # noqa: E402
from html import escape as _esc  # noqa: E402

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from tll.author.models import SECTION_KEYS  # noqa: E402
from tll.concepts.registry import DEFAULT_REGISTRY  # noqa: E402
from tll.cost.fx import get_usd_krw  # noqa: E402
from tll.cost.pricing import PRICES, PRICING_ASOF, PRICING_SOURCES  # noqa: E402
from tll.cost.usage import DEFAULT_USAGE_PATH, available_months, monthly_report  # noqa: E402
from tll.present.store import DEFAULT_DIR, load_records  # noqa: E402
from tll.rank import build_board  # noqa: E402
from tll.shared.llm.select import provider_label, resolve_provider_name  # noqa: E402
from tll.signals.store import DEFAULT_SIGNALS, load_signals  # noqa: E402

USAGE_PATH = os.environ.get("TLL_USAGE_PATH", DEFAULT_USAGE_PATH)
TEXTBOOK_DIR = os.environ.get("TLL_TEXTBOOK_DIR", DEFAULT_DIR)
REGISTRY_PATH = os.environ.get("TLL_REGISTRY_PATH", DEFAULT_REGISTRY)
SIGNALS_PATH = os.environ.get("TLL_SIGNALS_PATH", DEFAULT_SIGNALS)
_SEC_LABELS = {
    "gist": "한눈에",
    "compare": "기존 기술과 비교",
    "why": "왜 필요한가",
    "watch": "전망 · 주의",
    "try": "바로 써보기",
}

# 가독성 스타일 — 제목 크고 진하게, 본문 키우고 줄간격 넓게.
_STYLE = """
<style>
.tb-title{font-size:23px;font-weight:800;color:#0f172a;line-height:1.4;margin:2px 0 6px}
.tb-meta{font-size:13px;color:#64748b;margin:0 0 10px}
.tb-one{font-size:17px;color:#1f2937;line-height:1.8;margin:0 0 8px}
.tb-sec-h{font-size:15px;font-weight:700;color:#111827;margin:12px 0 2px}
.tb-sec-b{font-size:15.5px;color:#1f2937;line-height:1.85;margin:0 0 6px}
</style>
"""

_CITE_RE = re.compile(r"\s*\[S\d+\]")


def _clean(text: str) -> str:
    """화면용: [S#] 검증표시 숨김(원문 대조는 저장본에서 그대로)."""
    return _CITE_RE.sub("", text or "").strip()


def _age_str(days) -> str:
    """나이(일수)를 사람이 읽기 쉽게. 912일 → '2년 6개월'."""
    if days is None:
        return ""
    if days < 30:
        return f"{days}일"
    months = days // 30
    if months < 12:
        return f"{months}개월"
    y, m = divmod(months, 12)
    return f"{y}년 {m}개월" if m else f"{y}년"


def _latest_by_concept(records: list[dict]) -> dict:
    """concept_cid → 가장 최근 교과서 레코드(꼬리표 있는 것만)."""
    m: dict[str, dict] = {}
    for r in records:
        cid = r.get("concept_cid")
        if not cid:
            continue
        if cid not in m or (r.get("saved_at", "") > m[cid].get("saved_at", "")):
            m[cid] = r
    return m


@st.cache_resource
def _start_agent(interval_minutes: int = 30):
    """대시보드가 켜져 있는 동안 백그라운드로 자동 수집(한 번만 시작). Streamlit 재실행에도 1개만."""
    import threading

    from tll.loop.loop import run_forever

    t = threading.Thread(
        target=run_forever, kwargs={"interval_minutes": interval_minutes}, daemon=True
    )
    t.start()
    return t


def _card(r, rec) -> None:
    """기술 하나를 큰 카드로(제목·지표·교과서/설명서)."""
    with st.container(border=True):
        prov = " · 잠정" if r.tier.provisional else ""
        st.markdown(
            f"<div class='tb-title'>{r.tier.emoji} {_esc(r.name)} "
            f"<span style='font-size:15px;color:#64748b'>· {r.tier.label}{prov}</span></div>",
            unsafe_allow_html=True,
        )
        _meta(r, rec)
        _body(r, rec)


def _meta(r, rec) -> None:
    sc = r.score
    bits = [f"주목 {sc.attention:.0f}" + (f"·{sc.buzz_sources}곳" if getattr(sc, "buzz_sources", 0) else ""), f"채택 {sc.adoption:.1f}", f"재등장 {sc.recurrence}"]
    if r.age_days is not None:
        bits.append(f"🗓 만든 지 {_age_str(r.age_days)}")
    if rec:
        srr = (rec.get("metrics") or {}).get("support_rate")
        if isinstance(srr, (int, float)):
            bits.append(f"✅ 충실도 {int(round(srr * 100))}%")
        cc = (rec.get("metrics") or {}).get("cross_check")
        if isinstance(cc, dict) and cc.get("score") is not None:
            bits.append(f"🔀 {cc.get('model', '')} 교차 {cc['score']}%")
        depth = rec.get("depth") or "교과서"
        bits.append("📖 교과서" if depth == "교과서" else "📝 설명서")
        if rec.get("age_label"):
            bits.append(f"🕒 {rec['age_label']}")
    if sc.fake_flag:
        bits.append("⚠️가짜의심")
    bits.append(f"→ {r.tier.action}")
    st.markdown(f"<div class='tb-meta'>{' · '.join(_esc(b) for b in bits)}</div>", unsafe_allow_html=True)


def _body(r, rec) -> None:
    if not rec:
        st.caption("아직 설명 없음 · 관측 중 (신호만 쌓는 중)")
        return
    st.markdown(f"<div class='tb-one'>{_esc(_clean(rec.get('one_liner', '')))}</div>", unsafe_allow_html=True)
    src = (rec.get("sources") or [{}])[0]
    if src.get("url"):
        st.markdown(f"[원문 보기 ↗]({src['url']}) · {src.get('nature', '')}·{src.get('grade', '')}급")
    label = "교과서" if (rec.get("depth") or "교과서") == "교과서" else "설명서"
    with st.expander(f"📖 {_esc(r.name)} {label} 전체 보기"):
        sections = rec.get("sections") or {}
        for k in SECTION_KEYS:
            txt = (sections.get(k) or "").strip()
            if txt:
                st.markdown(f"<div class='tb-sec-h'>{_SEC_LABELS.get(k, k)}</div>", unsafe_allow_html=True)
                st.markdown(f"<div class='tb-sec-b'>{_esc(_clean(txt))}</div>", unsafe_allow_html=True)
        unv = rec.get("unverified") or []
        if unv:
            st.warning("⚠️ 미확인 " + str(len(unv)) + "건: " + " / ".join(u.get("claim", "")[:60] for u in unv[:5]))


_TIER_ORDER = [("tiger", "🐯"), ("cheetah", "🐆"), ("sprout", "🌱"), ("turtle", "🐢"),
               ("elephant", "🐘"), ("dinosaur", "🦕"), ("mayfly", "🦟"), ("hyena", "🐺")]


def _summary(board):
    """계급별 개수 + 오늘/이번주/이번달 신규(first_seen 기준)."""
    from collections import Counter
    from datetime import date, timedelta
    cnt = Counter(r.tier.tier for r in board if r.kind != "resource")
    res = sum(1 for r in board if r.kind == "resource")
    today = date.today()
    tod, wk, mo = today.isoformat(), (today - timedelta(days=7)).isoformat(), (today - timedelta(days=30)).isoformat()
    fs = [(r.first_seen or "")[:10] for r in board]
    return cnt, res, (sum(x == tod for x in fs), sum(x >= wk for x in fs), sum(x >= mo for x in fs))


def page_tech() -> None:
    st.markdown(_STYLE, unsafe_allow_html=True)
    st.header("📚 최신 기술 — 중요한 것부터")
    st.caption("지금 뜨는(🐯 호랑이)·화제(🐆 치타)·갓 등장(🌱 새싹)·배운 기술을 위에. 안정 도구(🐘🐢)와 학습자료는 아래 접어둠.")
    cta, cts = st.columns([1, 3])
    cta.button("🔄 지금 새로고침")
    try:
        _last = max((s.date for s in load_signals(SIGNALS_PATH)), default="")
    except Exception:  # noqa: BLE001
        _last = ""
    cts.caption(
        f"화면 읽은 시각 {datetime.now().strftime('%H:%M:%S')}"
        + (f" · 마지막 신호 수집일 {_last}" if _last else " · 아직 수집 기록 없음(에이전트 첫 사이클 대기)")
    )
    board = build_board(registry_path=REGISTRY_PATH, signals_path=SIGNALS_PATH, now=datetime.now(timezone.utc))
    by_cid = _latest_by_concept(load_records(TEXTBOOK_DIR))
    if not board:
        st.info("아직 기술이 없어요. 에이전트가 한 사이클 돌면 쌓여요.")
        return

    cnt, res, (nt, nw, nm) = _summary(board)
    chips = " · ".join(f"{emoji} {cnt.get(t, 0)}" for t, emoji in _TIER_ORDER if cnt.get(t, 0))
    total = sum(cnt.values())
    st.markdown(
        f"<div class='tb-meta'>계급({total}): {chips} · 📚자료 {res}"
        f" &nbsp;|&nbsp; 신규: 오늘 <b>+{nt}</b> · 이번주 <b>+{nw}</b> · 이번달 <b>+{nm}</b></div>",
        unsafe_allow_html=True,
    )

    focus, tools, resources = [], [], []
    for r in board:
        rec = by_cid.get(r.cid)
        if r.kind == "resource":
            resources.append(r)
            continue
        if rec is None and r.tier.tier == "mayfly":
            continue
        deep = rec is not None and (rec.get("depth") or "교과서") == "교과서"
        if r.tier.tier in ("tiger", "cheetah", "sprout", "dinosaur", "hyena") or deep:
            focus.append((r, rec))
        else:
            tools.append((r, rec))  # 🐘 코끼리 · 🐢 거북이 = 안정 도구 지도

    if focus:
        st.markdown("#### 🔥 지금 볼 것 — 뜨는 · 새싹 · 배운 기술")
        for r, rec in focus:
            _card(r, rec)
    else:
        st.info("아직 '뜨는 중'으로 잡힌 기술이 없어요. 며칠 더 모으면 성장·화제가 갈려 호랑이가 올라와요.")

    if tools:
        with st.expander(f"🗺 널리 쓰이는 도구 지도 {len(tools)}개 (🐘 코끼리 · 🐢 거북이)"):
            st.caption("채택은 탄탄하지만 지금 급히 뜨진 않는 도구들. 각 이름을 펼치면 설명서.")
            for r, rec in tools:
                age = f" · 🗓 {_age_str(r.age_days)}" if r.age_days is not None else ""
                head = f"{r.tier.emoji} {r.name} · {r.tier.label} · 채택 {r.score.adoption:.1f}{age}"
                if rec:
                    with st.expander(head):
                        _body(r, rec)
                else:
                    st.markdown(
                        f"<div style='padding:5px 0;border-bottom:1px solid #f1f5f9'>{_esc(head)} "
                        f"<span style='color:#94a3b8;font-size:12px'>· 설명서 생성 대기</span></div>",
                        unsafe_allow_html=True,
                    )

    if resources:
        with st.expander(f"📚 학습자료 {len(resources)}개 (기술 아님 · awesome-list·튜토리얼 등)"):
            st.caption("배우는 '기술'이 아니라 읽을거리 모음이라 티어에서 제외.")
            for r in resources:
                st.markdown(f"<div style='padding:3px 0;color:#475569'>📄 {_esc(r.name)}</div>", unsafe_allow_html=True)


def page_overview() -> None:
    st.header("⚙️ 관리 · 개요")
    c1, c2 = st.columns(2)
    c1.metric("현재 선택 모델", provider_label(resolve_provider_name()))
    c2.metric("생성된 교과서", len(load_records(TEXTBOOK_DIR)))
    st.caption("모델 전환: 에이전트 실행 시 `--provider gemini|anthropic` 또는 `.env` 의 `TLL_PROVIDER`.")


def page_cost() -> None:
    st.header("⚙️ 관리 · 💰 비용")
    months = available_months(USAGE_PATH)
    if not months:
        st.info("아직 사용 기록이 없어요. 에이전트를 돌리면(`python -m tll.loop.loop`) 호출마다 토큰이 쌓여요.")
    else:
        month = st.selectbox("월", months)
        rep = monthly_report(path=USAGE_PATH, month=month)
        t = rep["total"]
        rate, fx_src, fx_at = get_usd_krw()
        c1, c2, c3 = st.columns(3)
        c1.metric(f"{month} 합계", f"${t['cost_usd']:.4f}")
        c1.caption(f"≈ ₩{t['cost_usd'] * rate:,.0f}")
        c2.metric("호출 수", f"{t['calls']:,}")
        c3.metric("토큰 in/out", f"{t['input_tokens']:,} / {t['output_tokens']:,}")
        st.caption(
            f"요금 기준일 {PRICING_ASOF} · 환율 ₩{rate:,.0f}/$1 ({fx_src} {fx_at}) · "
            "정가 기준(캐싱/배치 할인 미반영) · Gemini 무료 티어면 쿼터 내 실제 청구 $0."
        )
        if rep["unpriced"]:
            st.warning("단가 미등록 모델(계산 $0): " + ", ".join(rep["unpriced"]))
        st.subheader("일별 사용·요금")
        days_df = pd.DataFrame(rep["days"])
        if not days_df.empty:
            if "cost_usd" in days_df:
                days_df["원화(₩)"] = (days_df["cost_usd"] * rate).round().astype(int)
            st.dataframe(days_df, width="stretch")
            st.bar_chart(days_df.set_index("date")["cost_usd"])
        else:
            st.write("이 달 기록 없음.")
        st.subheader("모델별")
        by_model_df = pd.DataFrame(rep["by_model"])
        if "cost_usd" in by_model_df:
            by_model_df["원화(₩)"] = (by_model_df["cost_usd"] * rate).round().astype(int)
        st.dataframe(by_model_df, width="stretch")
    with st.expander("적용 단가표 (per 1M tokens, USD)"):
        st.dataframe(pd.DataFrame(PRICES), width="stretch")
        st.caption("출처: " + " · ".join(f"[{k}]({v})" for k, v in PRICING_SOURCES.items()))


st.set_page_config(page_title="TLL", page_icon="📚", layout="wide")
st.sidebar.title("TLL")
section = st.sidebar.radio("메뉴", ["📚 기술", "⚙️ 관리"])
st.sidebar.caption(f"현재 모델: {provider_label(resolve_provider_name())}")

# 자동 수집: 대시보드가 켜져 있는 동안 에이전트가 스스로 30분마다 돈다.
if st.sidebar.checkbox("🤖 자동 수집 (30분마다)", value=os.environ.get("TLL_AUTORUN", "1") == "1"):
    _start_agent(30)
    st.sidebar.caption("백그라운드 수집 중 · 비용은 ⚙️ 관리 > 비용")
else:
    st.sidebar.caption("자동 수집 꺼짐 (수동: python -m tll.loop.loop --watch)")

if section == "📚 기술":
    page_tech()
else:
    sub = st.sidebar.radio("관리", ["개요", "비용"])
    (page_overview if sub == "개요" else page_cost)()
