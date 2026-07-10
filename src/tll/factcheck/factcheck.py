"""Fact-Check — Textbook 을 원문(body_text)과 대조하는 결정론 검증. LLM=0.

문장별 판정:
  - phantom_citation : 실존하지 않는 sid 인용 → 위반(제거).
  - quote_mismatch   : 따옴표 인용이 원문 body_text 에 없음 → 위반(제거).
  - unsupported_number: [S1] 인용인데 문장의 유효 숫자가 원문에 없음 → 미확인(플래그).
  - uncited          : 사실성 문장인데 [S#] 없음 → 미확인(플래그).
  - general_knowledge: 원문 밖 '(일반지식)' 표시 문장 → 미확인(정직 노출).
  - ok               : 인용 유효 + 인용문 원문 존재 + 숫자 원문 근거.
충실도%(support_rate) = ok(사실문) / 전체 사실문. 같은 입력 → 같은 판정(재현성).

정직한 한계: 이건 '인용·수치·따옴표'의 원문 앵커링이지 완전한 의미 함의(NLI)는 아니다.
문장이 인용·숫자는 맞아도 의미가 미묘하게 틀릴 수 있다(그건 LLM 판정 영역 → 검증 코어에서 제외).
"""

from __future__ import annotations

import re

from tll.author.models import SECTION_KEYS, Textbook
from tll.factcheck.models import FactCheckReport, SentenceVerdict

_SENT_SPLIT = re.compile(r"(?<=[.!?。])\s+|\n+")
_CITE = re.compile(r"\[(S\d+)\]")
_QUOTE = re.compile(r"[\"“”「](.{4,}?)[\"”」]")
_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")
_MIN_FACTUAL_LEN = 20


def _sentences(text: str) -> list[str]:
    return [p.strip() for p in _SENT_SPLIT.split(text or "") if p.strip()]


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip().lower()


def _numbers(text: str) -> set[str]:
    return {m.replace(",", "") for m in _NUM.findall(text or "")}


def _significant(n: str) -> bool:
    return len(n) >= 2 or "." in n  # 한 자리(1개·2개 등)는 잡음 → 제외


def _check_sentence(
    section: str, sent: str, valid: set[str], body_norm: str, body_nums: set[str]
) -> SentenceVerdict:
    cited = _CITE.findall(sent)

    phantom = [c for c in cited if c not in valid]
    if phantom:
        return SentenceVerdict(section, sent, cited, "phantom_citation", f"실존X 인용 {phantom}")

    for q in _QUOTE.findall(sent):
        if _norm(q) not in body_norm:
            return SentenceVerdict(
                section, sent, cited, "quote_mismatch", f'인용문 "{q[:24]}…" 원문에 없음'
            )

    if cited:
        bad = [n for n in _numbers(sent) if _significant(n) and n not in body_nums]
        if bad:
            return SentenceVerdict(section, sent, cited, "unsupported_number", f"원문에 없는 수치 {bad}")
        return SentenceVerdict(section, sent, cited, "ok")

    # 미인용
    if "(일반지식)" in sent:
        return SentenceVerdict(section, sent, cited, "general_knowledge", "원문 밖 일반지식 기반")
    if len(sent) >= _MIN_FACTUAL_LEN:
        return SentenceVerdict(section, sent, cited, "uncited", "사실성 문장인데 [S#] 없음")
    return SentenceVerdict(section, sent, cited, "ok")  # 짧은 비사실문


def check_textbook(tb: Textbook) -> FactCheckReport:
    """결정론 L1 검증(LLM=0). 같은 입력 → 같은 판정."""
    valid = {s.sid for s in tb.sources}
    body = " ".join(s.body_text for s in tb.sources)
    body_norm = _norm(body)
    body_nums = _numbers(body)

    verdicts: list[SentenceVerdict] = []
    for sent in _sentences(tb.one_liner):
        verdicts.append(_check_sentence("one_liner", sent, valid, body_norm, body_nums))
    for k in SECTION_KEYS:
        for sent in _sentences(tb.sections.get(k, "")):
            verdicts.append(_check_sentence(k, sent, valid, body_norm, body_nums))

    counts: dict[str, int] = {}
    for v in verdicts:
        counts[v.verdict] = counts.get(v.verdict, 0) + 1

    factual = [v for v in verdicts if len(v.text) >= _MIN_FACTUAL_LEN or v.cited_sids]
    ok = [v for v in factual if v.verdict == "ok"]
    violations = counts.get("phantom_citation", 0) + counts.get("quote_mismatch", 0)
    support = round(len(ok) / len(factual), 3) if factual else 0.0

    metrics = {
        "factual": len(factual),
        "ok": len(ok),
        "support_rate": support,
        "violations": violations,
        **{
            k: counts.get(k, 0)
            for k in (
                "phantom_citation",
                "quote_mismatch",
                "unsupported_number",
                "uncited",
                "general_knowledge",
            )
        },
    }
    status = "verified" if violations == 0 else "draft"
    return FactCheckReport(verdicts=verdicts, metrics=metrics, status=status)


def apply(tb: Textbook, report: FactCheckReport) -> Textbook:
    """위반(phantom/quote) 문장을 섹션에서 제거, 모든 비-ok 를 unverified 로 이동한 새 Textbook."""
    remove: dict[str, set[str]] = {}
    for v in report.verdicts:
        if v.verdict in ("phantom_citation", "quote_mismatch"):
            remove.setdefault(v.section, set()).add(v.text)

    one_liner = tb.one_liner
    if "one_liner" in remove:
        one_liner = f"(검증 보류 — 근거 미달) {tb.topic}"

    sections = dict(tb.sections)
    for k in SECTION_KEYS:
        bad = remove.get(k)
        if not bad:
            continue
        kept = [s for s in _sentences(sections.get(k, "")) if s not in bad]
        sections[k] = " ".join(kept) or "(검증에서 근거 미달 문장 제거됨 — 미확인)"

    unverified = list(tb.unverified)
    for v in report.verdicts:
        if v.verdict != "ok":
            unverified.append(
                {"claim": v.text, "reason": f"L1:{v.verdict} {v.note}".strip(), "conflicting_sids": []}
            )

    return Textbook(
        topic=tb.topic,
        one_liner=one_liner,
        sections=sections,
        judgment=tb.judgment,
        sources=tb.sources,
        unverified=unverified,
        status=report.status,
        age_label=tb.age_label,
        collected_at=tb.collected_at,
    )


def _run_cli() -> None:  # 사용자 머신 데모: python -m tll.factcheck.factcheck
    from tll.author.author import author_all
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
        return
    books, _ = author_all(rd.ready[:2])
    for tb in books:
        rep = check_textbook(tb)
        verified = apply(tb, rep)
        m = rep.metrics
        print("=" * 64)
        print(
            f"# {tb.topic} · 충실도(원문근거) {int(m['support_rate'] * 100)}% · status={verified.status}"
        )
        print(
            f"  ok {m['ok']}/{m['factual']} · 유령인용 {m['phantom_citation']} · 인용불일치 {m['quote_mismatch']}"
            f" · 수치미확인 {m['unsupported_number']} · 미인용 {m['uncited']} · 일반지식 {m['general_knowledge']}"
        )
        print(f"  한 줄: {verified.one_liner}")
        if verified.unverified:
            print("  ⚠️ 미확인:")
            for u in verified.unverified[:5]:
                print(f"    - {u['claim'][:56]} … ({u['reason']})")
        print()


if __name__ == "__main__":
    _run_cli()
