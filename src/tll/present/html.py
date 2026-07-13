"""자체 완결 HTML 대시보드 — 서버 없이 브라우저로 여는 단일 파일. 의존성 0.

검증 교과서 레코드(dict) 리스트 → 최신순 카드. 신선도·충실도%·status·사용 모델·원문 링크·6섹션·미확인.
헤더에 '현재 사용 모델'을, 카드마다 그 교과서를 만든 모델을 표시(Gemini/Claude 비교용).
순수 함수. 모든 사용자 콘텐츠 HTML escape.
"""

from __future__ import annotations

import html as _html
import os

from tll.author.models import SECTION_KEYS
from tll.shared.llm.select import provider_label

_LABELS = {
    "gist": "한눈에",
    "compare": "기존 기술과 비교",
    "why": "왜 필요한가",
    "watch": "전망 · 주의",
    "try": "바로 써보기",
}

_CSS = """
*{box-sizing:border-box}
body{font-family:'Apple SD Gothic Neo','Malgun Gothic',system-ui,sans-serif;max-width:860px;margin:0 auto;
padding:24px 16px;background:#faf9f7;color:#1f2023;line-height:1.6}
h1{font-size:22px;margin:0 0 2px}
.sub{color:#86858b;font-size:13px;margin:0 0 4px}
.provider{font-size:13px;margin:0 0 18px;color:#4b5563}
.provider code{background:#eef;border-radius:4px;padding:1px 5px;font-size:12px}
.card{background:#fff;border:1px solid #e7e5e2;border-radius:14px;padding:16px 18px;margin:0 0 14px}
.head{display:flex;justify-content:space-between;align-items:flex-start;gap:10px;flex-wrap:wrap}
.head h2{font-size:17px;margin:0}
.badges{display:flex;gap:6px;flex-wrap:wrap}
.badge{font-size:11px;font-weight:600;color:#fff;border-radius:999px;padding:2px 9px;white-space:nowrap}
.badge.age{background:#6b7280}.badge.ok{background:#059669}.badge.draft{background:#9ca3af}
.badge.model{background:#7c3aed}
.one{font-size:14px;margin:8px 0 6px}
.srcline{font-size:12px;margin:2px 0 6px}
.srcline a{color:#2563eb;text-decoration:none;font-weight:600}
.srcline .src{color:#86858b;margin-left:6px}
details{margin-top:6px}summary{cursor:pointer;font-size:13px;color:#57565c;font-weight:600}
details h4{font-size:13px;margin:10px 0 2px;color:#374151}
details p{font-size:13.5px;margin:0 0 4px;white-space:pre-wrap}
.unv summary{color:#b45309}.unv li{font-size:12.5px;color:#57565c}
.empty{color:#86858b;text-align:center;padding:40px 0}
"""


def _esc(s) -> str:
    return _html.escape(str(s if s is not None else ""))


def _fid_color(pct: int) -> str:
    return "#059669" if pct >= 80 else ("#d97706" if pct >= 50 else "#dc2626")


def _sort_key(rec: dict) -> str:
    src = (rec.get("sources") or [{}])[0]
    return src.get("published_at") or rec.get("saved_at") or ""


def _card(rec: dict) -> str:
    topic = _esc(rec.get("topic"))
    one = _esc(rec.get("one_liner"))
    age = _esc(rec.get("age_label"))
    status = rec.get("status", "draft")
    metrics = rec.get("metrics") or {}
    sr = metrics.get("support_rate")
    badges = []
    if age:
        badges.append(f"<span class='badge age'>{age}</span>")
    if isinstance(sr, (int, float)):
        pct = int(round(sr * 100))
        badges.append(f"<span class='badge' style='background:{_fid_color(pct)}'>충실도 {pct}%</span>")
    prov = rec.get("provider")
    if prov:
        badges.append(f"<span class='badge model'>{_esc(provider_label(prov))}</span>")
    badges.append(
        f"<span class='badge {'ok' if status == 'verified' else 'draft'}'>"
        f"{'검증됨' if status == 'verified' else '초안'}</span>"
    )

    src = (rec.get("sources") or [{}])[0]
    srcline = ""
    if src.get("url"):
        srcline = (
            f"<a href='{_esc(src.get('url'))}' target='_blank' rel='noopener'>원문 보기 ↗</a>"
            f"<span class='src'>{_esc(src.get('nature'))}·{_esc(src.get('grade'))}급</span>"
        )

    sections = rec.get("sections") or {}
    secs = "".join(
        f"<h4>{_LABELS.get(k, k)}</h4><p>{_esc(sections.get(k))}</p>"
        for k in SECTION_KEYS
        if (sections.get(k) or "").strip()
    )

    unv = rec.get("unverified") or []
    unv_html = ""
    if unv:
        items = "".join(
            f"<li>{_esc(u.get('claim'))[:120]} <em>({_esc(u.get('reason'))})</em></li>" for u in unv[:8]
        )
        unv_html = f"<details class='unv'><summary>⚠️ 미확인 {len(unv)}건</summary><ul>{items}</ul></details>"

    return (
        f"<article class='card'><div class='head'><h2>{topic}</h2>"
        f"<div class='badges'>{''.join(badges)}</div></div>"
        f"<p class='one'>{one}</p><div class='srcline'>{srcline}</div>"
        f"<details><summary>교과서 펼치기</summary>{secs}{unv_html}</details></article>"
    )


def render_dashboard(records: list[dict], *, title: str = "TLL — 최신 기술 한국어 교과서", current_provider: str = "") -> str:
    recs = sorted(records, key=_sort_key, reverse=True)
    body = "".join(_card(r) for r in recs) or "<p class='empty'>아직 생성된 교과서가 없어요. 에이전트를 돌려보세요.</p>"
    prov_line = ""
    if current_provider:
        prov_line = (
            f"<p class='provider'>🤖 현재 사용 모델: <b>{_esc(provider_label(current_provider))}</b> "
            "· 전환: <code>--provider gemini|anthropic</code> 또는 <code>TLL_PROVIDER</code></p>"
        )
    return (
        "<!doctype html><html lang='ko'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{_esc(title)}</title><style>{_CSS}</style></head><body>"
        f"<h1>{_esc(title)}</h1>"
        "<p class='sub'>에이전트가 스스로 찾아 만든 · 최신순 · 충실도(원문근거)·원문 링크</p>"
        f"{prov_line}{body}</body></html>"
    )


def save_dashboard(records: list[dict], out_path: str = "data/dashboard.html", *, current_provider: str = "", **kw) -> str:
    html = render_dashboard(records, current_provider=current_provider, **kw)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    return out_path
