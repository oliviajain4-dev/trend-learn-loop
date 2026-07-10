"""자체 완결 HTML 대시보드 — 서버 없이 브라우저로 여는 단일 파일. 의존성 0.

검증 교과서 레코드(dict) 리스트 → 최신순 카드. 신선도·충실도%(색 배지)·status·원문 링크·6섹션·미확인.
순수 함수(같은 입력 → 같은 HTML). 모든 사용자 콘텐츠는 HTML escape.
"""

from __future__ import annotations

import html as _html
import os

from tll.author.models import SECTION_KEYS

_LABELS = {
    "skeleton": "큰 뼈대",
    "background": "왜 나왔나",
    "contrast_analogy": "대조·유추",
    "why_needed": "왜 필요한가",
    "outlook": "전망",
    "quickstart": "바로 따라하기",
}

_CSS = """
*{box-sizing:border-box}
body{font-family:'Apple SD Gothic Neo','Malgun Gothic',system-ui,sans-serif;max-width:860px;margin:0 auto;
padding:24px 16px;background:#faf9f7;color:#1f2023;line-height:1.6}
h1{font-size:22px;margin:0 0 2px}
.sub{color:#86858b;font-size:13px;margin:0 0 20px}
.card{background:#fff;border:1px solid #e7e5e2;border-radius:14px;padding:16px 18px;margin:0 0 14px}
.head{display:flex;justify-content:space-between;align-items:flex-start;gap:10px;flex-wrap:wrap}
.head h2{font-size:17px;margin:0}
.badges{display:flex;gap:6px;flex-wrap:wrap}
.badge{font-size:11px;font-weight:600;color:#fff;border-radius:999px;padding:2px 9px;white-space:nowrap}
.badge.age{background:#6b7280}.badge.ok{background:#059669}.badge.draft{background:#9ca3af}
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
        badges.append(
            f"<span class='badge' style='background:{_fid_color(pct)}'>충실도 {pct}%</span>"
        )
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
            f"<li>{_esc(u.get('claim'))[:120]} <em>({_esc(u.get('reason'))})</em></li>"
            for u in unv[:8]
        )
        unv_html = f"<details class='unv'><summary>⚠️ 미확인 {len(unv)}건</summary><ul>{items}</ul></details>"

    return (
        f"<article class='card'><div class='head'><h2>{topic}</h2>"
        f"<div class='badges'>{''.join(badges)}</div></div>"
        f"<p class='one'>{one}</p><div class='srcline'>{srcline}</div>"
        f"<details><summary>교과서 펼치기</summary>{secs}{unv_html}</details></article>"
    )


def render_dashboard(records: list[dict], *, title: str = "TLL — 최신 기술 한국어 교과서") -> str:
    recs = sorted(records, key=_sort_key, reverse=True)
    body = (
        "".join(_card(r) for r in recs)
        or "<p class='empty'>아직 생성된 교과서가 없어요. 에이전트를 돌려보세요.</p>"
    )
    return (
        "<!doctype html><html lang='ko'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{_esc(title)}</title><style>{_CSS}</style></head><body>"
        f"<h1>{_esc(title)}</h1>"
        "<p class='sub'>에이전트가 스스로 찾아 만든 · 최신순 · 충실도(원문근거)·원문 링크</p>"
        f"{body}</body></html>"
    )


def save_dashboard(records: list[dict], out_path: str = "data/dashboard.html", **kw) -> str:
    html = render_dashboard(records, **kw)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    return out_path


def _run_cli() -> None:  # 사용자 머신 데모: python -m tll.present.html
    from tll.author.author import author_all
    from tll.factcheck.factcheck import apply, check_textbook
    from tll.memory.memory import remember_textbook
    from tll.present.store import load_records, save_textbook
    from tll.reader.reader import read
    from tll.scout.scout import scout
    from tll.tracker.tracker import track
    from tll.triage.triage import triage

    res = scout()
    tr = triage(res.candidates, top_n=5)
    if tr.summary.get("mode") == "error":
        print("[Triage] 실패:", tr.summary.get("error"))
        return
    tk = track(tr.selected)
    rd = read(tk.docs)
    if not rd.ready:
        print("충분한 본문 없음(전부 '더 찾자').")
    books, _ = author_all(rd.ready[:3]) if rd.ready else ([], [])
    for tb in books:
        rep = check_textbook(tb)
        verified = apply(tb, rep)
        remember_textbook(verified)
        save_textbook(verified, metrics=rep.metrics)
    recs = load_records()
    out = save_dashboard(recs)
    print(f"교과서 {len(recs)}건 → {out}\n브라우저로 여세요: file:///{os.path.abspath(out)}")


if __name__ == "__main__":
    _run_cli()
