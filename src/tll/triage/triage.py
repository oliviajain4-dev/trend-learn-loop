"""Triage(선별) — Scout 후보 중 '교과서 감'을 LLM이 판단해 상위 N 선별.

에이전트 작동 순서 2단계. **여기부터 모델이 제어**(무엇을 파고들지 선택) = 진짜 에이전트.
경계: 판단(교과서 감이냐)은 LLM. 최종 선별(top-N 정렬)·집계는 결정론 코드.
DNA 준수: LLM은 후보 '제목·소스·등급·신호'만 보고 분류/가치판단만 한다. 원문 fetch·수치 생성 없음.

재현성/테스트: LLM 호출(llm_call)을 주입받아 오프라인 검증 가능. 실패(네트워크·JSON)해도
전체를 죽이지 않고 summary.mode="error"로 정직 노출(지어내지 않음).
"""

from __future__ import annotations

import json
import logging
import re
from collections import deque
from typing import Callable

from tll.scout.models import TrendCandidate
from tll.shared.llm import get_provider
from tll.shared.llm.base import LLMProvider
from tll.triage.models import TriageDecision, TriageResult

logger = logging.getLogger(__name__)


class TriageError(RuntimeError):
    """선별 실패(LLM 응답 파싱 등)."""


_SYSTEM = (
    "너는 '한국어 IT/AI 기술 교과서'를 만드는 시스템의 선별 담당이다. "
    "지금 뜨는 트렌드 후보 중 '배울 가치가 있는 기술'만 골라낸다. "
    "반드시 유효한 JSON 배열 하나만 출력한다(마크다운/설명 금지)."
)


def _build_prompt(cands: list[TrendCandidate]) -> str:
    lines = []
    for i, c in enumerate(cands, 1):
        sig = f"·▲{c.score}" if c.score else ""
        lines.append(f"{i}. [{c.source}·{c.grade}급{sig}·{c.domain}] {c.title}")
    listing = "\n".join(lines)
    return (
        "아래 후보 각각이 **배울 가치 있는 IT/AI 기술·도구·프레임워크·모델·라이브러리·기법·개념**인지 판단하라.\n\n"
        "교과서 감(keep=true): 새 AI 모델, 프레임워크/라이브러리, 개발도구, DB/인프라, "
        "알고리즘·자료구조·기법, 프로그래밍 언어·이론 등 '이게 뭔지 배울 수 있는 기술'.\n"
        "소음(keep=false): 일반 뉴스·정치·정책·규제, 오피니언/칼럼, 게임·엔터·잡담, "
        "사건사고, 채용, 비(非)기술 주제.\n\n"
        "각 후보에 대해 아래 형식의 JSON 객체를 만들어라:\n"
        '{"i": 번호, "keep": true|false, "category": "짧은 분류(예: AI모델/프레임워크/DB/언어/도구/뉴스/기타)", '
        '"worth": 0-100(교과서 가치), "reason": "한국어 한 문장"}\n\n'
        "출력은 **JSON 배열 하나만**. 예: [{\"i\":1,\"keep\":true,\"category\":\"AI모델\",\"worth\":90,\"reason\":\"...\"}]\n\n"
        f"후보:\n{listing}\n"
    )


def _extract_json_array(text: str) -> list:
    t = text.strip()
    if t.startswith("```"):  # ```json ... ``` 펜스 제거
        t = re.sub(r"^```[a-zA-Z]*\n?", "", t)
        t = re.sub(r"\n?```$", "", t).strip()
    start, end = t.find("["), t.rfind("]")
    if start == -1 or end == -1 or end <= start:
        raise TriageError("응답에서 JSON 배열을 찾지 못함")
    try:
        data = json.loads(t[start : end + 1])
    except json.JSONDecodeError as e:
        raise TriageError(f"JSON 파싱 실패: {e}") from e
    if not isinstance(data, list):
        raise TriageError("JSON 최상위가 배열이 아님")
    return data


def _interleave(cands: list[TrendCandidate]) -> list[TrendCandidate]:
    """소스별 라운드로빈 — max_judge 로 자를 때 한 소스만 남지 않게(한국어 소스 보호)."""
    buckets: dict[str, deque] = {}
    for c in cands:
        buckets.setdefault(c.source, deque()).append(c)
    queues = list(buckets.values())
    out: list[TrendCandidate] = []
    while any(queues):
        for q in queues:
            if q:
                out.append(q.popleft())
    return out


def _make_default_call(
    provider: LLMProvider | None, model: str | None, max_tokens: int
) -> Callable[[str, str], str]:
    def _call(prompt: str, system: str) -> str:
        llm = provider or get_provider()  # 기본 Gemini (키 없으면 여기서 예외)
        return llm.generate(prompt, system=system, max_tokens=max_tokens, model=model).text

    return _call


def triage(
    candidates: list[TrendCandidate],
    *,
    top_n: int = 5,
    max_judge: int = 40,
    provider: LLMProvider | None = None,
    model: str | None = None,
    max_tokens: int = 4096,
    llm_call: Callable[[str, str], str] | None = None,
) -> TriageResult:
    if not candidates:
        return TriageResult(
            [], [], {"mode": "empty", "judged": 0, "kept": 0, "selected": 0, "categories": {}}
        )

    judged = _interleave(candidates)[:max_judge]
    idx = {i + 1: c for i, c in enumerate(judged)}  # 1-based (프롬프트 번호와 일치)

    call = llm_call or _make_default_call(provider, model, max_tokens)
    try:
        raw = call(_build_prompt(judged), _SYSTEM)
        items = _extract_json_array(raw)
    except Exception as e:  # LLM 실패·키 없음·JSON 파싱 실패 → 지어내지 않고 정직 노출
        logger.warning("Triage 실패: %s", e)
        return TriageResult(
            [],
            [],
            {"mode": "error", "error": str(e), "judged": len(judged), "kept": 0, "selected": 0},
        )

    decisions: list[TriageDecision] = []
    seen_i: set[int] = set()
    for it in items:
        if not isinstance(it, dict):
            continue
        try:
            i = int(it.get("i"))
        except (TypeError, ValueError):
            continue
        c = idx.get(i)
        if c is None or i in seen_i:  # 범위 밖/중복 무시
            continue
        seen_i.add(i)
        try:
            worth = max(0, min(100, int(it.get("worth", 0))))
        except (TypeError, ValueError):
            worth = 0
        decisions.append(
            TriageDecision(
                cid=c.cid,
                title=c.title,
                source=c.source,
                keep=bool(it.get("keep")),
                category=(str(it.get("category") or "기타").strip() or "기타")[:40],
                worth=worth,
                reason=str(it.get("reason") or "").strip(),
            )
        )
    # LLM이 언급 안 한 후보 → 보수적으로 keep=False(미판단). 누락을 숨기지 않음.
    for i, c in idx.items():
        if i not in seen_i:
            decisions.append(
                TriageDecision(c.cid, c.title, c.source, False, "미판단", 0, "LLM이 판단하지 않음")
            )

    cand_by_cid = {c.cid: c for c in judged}
    kept = [d for d in decisions if d.keep]
    # 선별은 결정론: 교과서 가치(worth)↓, 동점이면 신호(score)↓
    kept.sort(key=lambda d: (d.worth, cand_by_cid[d.cid].score), reverse=True)
    selected = [cand_by_cid[d.cid] for d in kept[:top_n]]

    categories: dict[str, int] = {}
    for d in decisions:
        categories[d.category] = categories.get(d.category, 0) + 1

    summary = {
        "mode": "llm",
        "judged": len(judged),
        "kept": len(kept),
        "selected": len(selected),
        "categories": categories,
    }
    return TriageResult(decisions=decisions, selected=selected, summary=summary)


def _run_cli() -> None:  # 사용자 머신 데모: python -m tll.triage.triage
    from tll.scout.scout import scout

    res = scout()
    print(f"[Scout] 폴링 {res.summary['polled']} · 신규 {res.summary['new']}")
    tr = triage(res.candidates, top_n=5)
    s = tr.summary
    if s.get("mode") == "error":
        print("[Triage] 실패:", s.get("error"))
        print("  → .env 의 GEMINI_API_KEY 확인이 필요할 수 있어요.")
        return
    print(f"[Triage] 판단 {s['judged']} → 교과서 감 {s['kept']} · 선별 {s['selected']} · 분류 {s['categories']}")
    dec = {d.cid: d for d in tr.decisions}
    print("\n=== 교과서 감 (에이전트 선별) ===")
    for c in tr.selected:
        d = dec[c.cid]
        print(f"[{d.category}·worth{d.worth}] {c.title}\n    → {d.reason}\n    {c.url}")
    dropped = [d for d in tr.decisions if not d.keep][:6]
    print("\n=== 소음으로 거른 것 (예시) ===")
    for d in dropped:
        print(f"[{d.category}] {d.title} — {d.reason}")


if __name__ == "__main__":
    _run_cli()
