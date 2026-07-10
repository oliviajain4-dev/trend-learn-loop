"""Reader(독해) — 본문을 읽고 '이걸로 교과서를 쓸 수 있나'를 판단. **ReAct 결정점**.

각 본문에 대해 LLM이:
  - 이 본문만으로 "이게 뭔지"를 설명할 수 있는지(sufficient) 판단
  - 본문 근거로 이해 요지(understanding)를 뽑음 (지어내지 않음)
  - 부족하면 뭐가 없는지(missing)
그 결과로 **다음 행동을 고른다**: 충분→proceed(집필) / 부족→collect_more("더 찾자").

경계: 판단은 LLM(에이전트). 단, status!=ok·본문 빈약은 LLM 쓰기 전에 결정론 precheck로 '부족' 처리
(뻔한 실패에 토큰 낭비 안 함). 실패·JSON 파싱오류는 지어내지 않고 부족+error로 정직 처리.
테스트/재현: llm_call 주입 → 오프라인 검증.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Callable

from tll.reader.models import ReadResult, ReadVerdict
from tll.shared.llm import get_provider
from tll.shared.llm.base import LLMProvider
from tll.tracker.models import TrackedDoc

logger = logging.getLogger(__name__)

_SYSTEM = (
    "너는 기술 문서 독해 담당이다. 주어진 '본문'만 근거로, 이 본문으로 이 기술이 뭔지 "
    "교과서를 쓸 수 있는지 판단한다. 본문에 없는 내용을 지어내지 않는다. "
    "반드시 유효한 JSON 하나만 출력한다(마크다운/설명 금지)."
)


def _build_prompt(topic: str, body: str) -> str:
    return (
        f"기술 주제: {topic}\n\n"
        f'가져온 본문(발췌):\n"""\n{body}\n"""\n\n'
        "이 본문만으로 판단해 아래 JSON 으로 답하라:\n"
        "{\n"
        '  "sufficient": true 또는 false,\n'
        '  "understanding": "본문 근거로 이 기술이 뭔지 2~3문장(한국어). 본문에 없으면 쓰지 마라",\n'
        '  "missing": "부족하면 뭐가 없는지 한 문장, 충분하면 빈 문자열",\n'
        '  "reason": "판단 이유 한 문장(한국어)"\n'
        "}\n"
        "본문이 로그인/에러/목차/광고뿐이거나 주제와 무관하면 sufficient=false."
    )


def _extract_json_object(text: str) -> dict:
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z]*\n?", "", t)
        t = re.sub(r"\n?```$", "", t).strip()
    start, end = t.find("{"), t.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("JSON 객체를 찾지 못함")
    return json.loads(t[start : end + 1])


def _make_default_call(
    provider: LLMProvider | None, model: str | None, max_tokens: int
) -> Callable[[str, str], str]:
    def _call(prompt: str, system: str) -> str:
        llm = provider or get_provider()
        return llm.generate(prompt, system=system, max_tokens=max_tokens, model=model).text

    return _call


def _precheck_verdict(d: TrackedDoc, body_len: int) -> ReadVerdict:
    return ReadVerdict(
        cid=d.cid,
        topic_title=d.topic_title,
        grade=d.grade,
        nature=d.nature,
        sufficient=False,
        next_action="collect_more",
        understanding="",
        missing=d.note or f"본문 상태 {d.status}",
        reason=f"본문 부족(status={d.status}, {body_len}자) → LLM 없이 '더 찾자'",
        mode="precheck",
    )


def read(
    docs: list[TrackedDoc],
    *,
    provider: LLMProvider | None = None,
    model: str | None = None,
    max_tokens: int = 1024,
    min_body: int = 80,
    body_chars: int = 4000,
    llm_call: Callable[[str, str], str] | None = None,
) -> ReadResult:
    call = llm_call or _make_default_call(provider, model, max_tokens)
    verdicts: list[ReadVerdict] = []
    ready: list[TrackedDoc] = []
    needs_more: list[ReadVerdict] = []

    for d in docs:
        body = (d.body_text or "").strip()
        # 결정론 pre-check: 뻔한 실패는 LLM 없이 '부족'
        if d.status != "ok" or len(body) < min_body:
            v = _precheck_verdict(d, len(body))
            verdicts.append(v)
            needs_more.append(v)
            continue

        try:
            raw = call(_build_prompt(d.topic_title, body[:body_chars]), _SYSTEM)
            p = _extract_json_object(raw)
        except Exception as e:  # 파싱·LLM 실패 → 지어내지 않고 '부족+error'
            logger.warning("Reader 독해 실패(%s): %s", d.topic_title, e)
            v = ReadVerdict(
                cid=d.cid,
                topic_title=d.topic_title,
                grade=d.grade,
                nature=d.nature,
                sufficient=False,
                next_action="collect_more",
                understanding="",
                missing="독해 실패",
                reason=str(e),
                mode="error",
            )
            verdicts.append(v)
            needs_more.append(v)
            continue

        suff = bool(p.get("sufficient"))
        v = ReadVerdict(
            cid=d.cid,
            topic_title=d.topic_title,
            grade=d.grade,
            nature=d.nature,
            sufficient=suff,
            next_action="proceed" if suff else "collect_more",
            understanding=str(p.get("understanding") or "").strip(),
            missing=str(p.get("missing") or "").strip(),
            reason=str(p.get("reason") or "").strip(),
            mode="llm",
        )
        verdicts.append(v)
        if suff:
            ready.append(d)
        else:
            needs_more.append(v)

    summary = {
        "read": len(docs),
        "sufficient": len(ready),
        "needs_more": len(needs_more),
        "actions": {"proceed": len(ready), "collect_more": len(needs_more)},
    }
    return ReadResult(verdicts=verdicts, ready=ready, needs_more=needs_more, summary=summary)


def _run_cli() -> None:  # 사용자 머신 데모: python -m tll.reader.reader
    from tll.scout.scout import scout
    from tll.tracker.tracker import track
    from tll.triage.triage import triage

    res = scout()
    print(f"[Scout] 폴링 {res.summary['polled']} · 신규 {res.summary['new']}")
    tr = triage(res.candidates, top_n=5)
    if tr.summary.get("mode") == "error":
        print("[Triage] 실패:", tr.summary.get("error"))
        return
    print(f"[Triage] 교과서 감 {tr.summary['kept']} → 선별 {len(tr.selected)}")
    tk = track(tr.selected)
    print(f"[Tracker] 본문확보 {tk.summary['ok']}/{tk.summary['tracked']}")
    rd = read(tk.docs)
    s = rd.summary
    print(f"[Reader] 읽음 {s['read']} · ✅충분 {s['sufficient']}(집필 가능) · 🔁더 찾자 {s['needs_more']}\n")
    for v in rd.verdicts:
        mark = "✅충분" if v.sufficient else "🔁더 찾자"
        print(f"[{mark} · {v.tier_label if hasattr(v, 'tier_label') else v.nature}] {v.topic_title}")
        print(f"    판단: {v.reason}")
        if v.sufficient and v.understanding:
            print(f"    이해: {v.understanding}")
        if not v.sufficient and v.missing:
            print(f"    부족: {v.missing}")


if __name__ == "__main__":
    _run_cli()
