"""교차검증(Cross-check) — 집필과 다른 모델이 독립적으로 충실도를 재채점.

신뢰 설계의 핵심: 집필(Gemini)과 검증(Claude)을 **다른 모델**로 분리한다.
결정론 팩트체크(원문 문자열·숫자 대조)에 더해, **다른 모델이 '의미적으로' 원문 근거 여부를 독립 판정** →
한 모델의 환각을 교차로 잡는다. (자기 글을 자기가 검토하는 확인편향을 피함.)
verifier_call 주입 → 테스트는 완전 오프라인. 키/모델 없으면 호출부에서 건너뜀.
"""

from __future__ import annotations

import json
import re
from typing import Callable

_SYSTEM = (
    "너는 엄격한 사실 검증자다. 오직 주어진 '원문'만 근거로, 각 '주장'이 원문으로 뒷받침되는지 판정한다. "
    "원문에 없거나·과장·왜곡된 주장은 unsupported. 관대하게 봐주지 마라. 유효한 JSON 하나만 출력."
)


def _claims(sections: dict) -> list[str]:
    out: list[str] = []
    for v in (sections or {}).values():
        for s in re.split(r"(?<=[.!?다])\s+", (v or "").strip()):
            s = re.sub(r"\s*\[S\d+\]", "", s).strip()
            if len(s) > 8:
                out.append(s)
    return out[:14]


def _parse_unsupported(raw: str, n: int) -> list[int]:
    m = re.search(r"\{.*\}", (raw or "").strip(), re.S)
    if not m:
        return []
    try:
        d = json.loads(m.group(0))
    except (json.JSONDecodeError, ValueError):
        return []
    out = []
    for x in d.get("unsupported") or []:
        try:
            i = int(x) - 1
        except (TypeError, ValueError):
            continue
        if 0 <= i < n:
            out.append(i)
    return sorted(set(out))


def cross_verify(topic: str, source_text: str, sections: dict, *,
                 verifier_call: Callable[[str, str], str], model_label: str = "claude") -> dict:
    """다른 모델로 교과서 주장들의 원문 근거 여부를 독립 판정. 반환 {score, unsupported, model, n}."""
    claims = _claims(sections)
    if not claims or not (source_text or "").strip():
        return {"score": None, "unsupported": [], "model": model_label, "n": 0}
    numbered = "\n".join(f"{i + 1}. {c}" for i, c in enumerate(claims))
    prompt = (
        f"기술: {topic}\n\n원문(근거):\n\"\"\"\n{source_text[:3500]}\n\"\"\"\n\n"
        f"주장들:\n{numbered}\n\n"
        "각 주장이 원문으로 뒷받침되면 넘어가고, 아니면(원문에 없음·과장·왜곡) 그 번호를 unsupported 에 넣어라. "
        '유효한 JSON 하나만: {"unsupported":[번호,...], "note":"간단 사유"}'
    )
    raw = verifier_call(prompt, _SYSTEM)
    unsup = _parse_unsupported(raw, len(claims))
    n = len(claims)
    return {
        "score": round(100 * (n - len(unsup)) / n) if n else None,
        "unsupported": [claims[i] for i in unsup],
        "model": model_label,
        "n": n,
    }


_REVISE_SYSTEM = (
    "너는 원문만 근거로 쓰는 한국어 기술 교과서 편집자다. 다른 모델의 초안을 받아, "
    "검증에서 '원문 근거 없음'으로 지적된 문장을 빼거나 원문 사실로 교체해 다시 쓴다. "
    "원문에 없는 사실·수치를 새로 지어내지 마라. 유효한 JSON 하나만 출력."
)


def _extract_json(raw: str) -> dict:
    t = (raw or "").strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z]*\n?", "", t)
        t = re.sub(r"\n?```$", "", t).strip()
    a, b = t.find("{"), t.rfind("}")
    if a == -1 or b <= a:
        return {}
    try:
        return json.loads(t[a:b + 1])
    except (json.JSONDecodeError, ValueError):
        return {}


def revise_textbook(topic: str, source_text: str, sections: dict, cross: dict, *,
                    reviser_call: Callable[[str, str], str], section_keys=("gist", "compare", "why", "watch", "try")) -> dict | None:
    """검증 결과를 바탕으로 다른 모델이 교과서를 '재집필'(원문 근거만). 반환 {one_liner, sections} 또는 None(실패 시 초안 유지)."""
    if not (source_text or "").strip() or not sections:
        return None
    unsup = (cross or {}).get("unsupported") or []
    flagged = "\n".join(f"- {u}" for u in unsup) if unsup else "(치명적 미근거 없음 — 그래도 원문 근거로 더 정확히 다듬어라)"
    draft = "\n\n".join(f"[{k}]\n{v}" for k, v in sections.items() if v)
    prompt = (
        f"기술: {topic}\n\n원문(유일한 근거):\n\"\"\"\n{source_text[:3500]}\n\"\"\"\n\n"
        f"초안(다른 모델이 씀):\n{draft}\n\n"
        f"검증에서 '원문 근거 없음/과장'으로 지적된 문장:\n{flagged}\n\n"
        "원문만 근거로 초안을 다시 써라. 지적된 문장은 빼거나 원문 사실로 교체. 쉬운 한국어, 짧은 문장. "
        '유효한 JSON 하나만: {"one_liner":"한 줄","sections":{"gist":"...","compare":"...","why":"...","watch":"...","try":"..."}}'
    )
    parsed = _extract_json(reviser_call(prompt, _REVISE_SYSTEM))
    raw_sec = parsed.get("sections") if isinstance(parsed.get("sections"), dict) else {}
    new_sec = {k: str(raw_sec.get(k) or sections.get(k) or "").strip() for k in section_keys}
    if not any(new_sec.values()):
        return None
    return {"one_liner": str(parsed.get("one_liner") or "").strip(), "sections": new_sec}
