"""Eval-Harness — 환각을 일부러 주입해 Verifier 검출률(recall)·오탐을 실측한다.

이게 과제의 중심: "내가 설계한 검증기가 실제로 거짓을 잡는지 실측"(기획서 §6).

주입 유형 3가지:
  1) phantom_citation     : 실존하지 않는 출처 인용([S99]) → L1 이 **잡아야** 함(violation).
  2) uncited_fabrication  : 인용 없는 조작 문장 → L1 이 '근거 약함'으로 **표시해야** 함(uncited).
  3) plausible_fabrication: 유효 인용([S1])인데 내용이 거짓 → L1 은 **구조적으로 못 잡음**(정직 고지).
     (이건 본문 원문 NLI/CoVe 가 있어야 잡힌다 → 로드맵. 못 잡음을 숨기지 않고 리포트.)

산출물은 "AI가 틀리는 순간과 그걸 잡는 법"의 실측 증거로 그대로 쓴다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from tll.schema import Brief, load_all_briefs, parse_brief
from tll.verifier import verify_brief

# (kind, expected_catch, 문장) — 명백히 조작된 문장(골드셋에 없는 거짓).
_INJECTIONS: tuple[tuple[str, bool, str], ...] = (
    (
        "phantom_citation",
        True,
        "이 기술은 국제 표준으로 공식 채택되어 전 세계 모든 기업이 의무 도입했다 [S99].",
    ),
    (
        "uncited_fabrication",
        True,
        "이 기술의 창시자는 그 공로로 2018년 노벨물리학상을 단독 수상했다고 전해진다.",
    ),
    (
        "plausible_fabrication",
        False,  # 유효 인용 + 거짓 내용 → L1 은 못 잡음(본문 NLI 필요)
        "이 기술은 어떤 입력에도 100% 정확한 답을 보장하는 것으로 확인되었다 [S1].",
    ),
)


@dataclass
class Injection:
    kind: str
    expected_catch: bool
    text: str
    detected_as: str | None = None  # "violation" | "uncited" | None

    @property
    def correct(self) -> bool:
        # phantom/uncited 는 잡혀야 정답, plausible 은 안 잡혀야(구조적 한계) 정답.
        return self.expected_catch == (self.detected_as is not None)


@dataclass
class HarnessCase:
    brief_id: str
    injections: list[Injection] = field(default_factory=list)
    false_positives: int = 0  # 주입 아닌 깨끗한 문장을 위반으로 오탐한 수


@dataclass
class HarnessReport:
    cases: list[HarnessCase] = field(default_factory=list)

    def _inj(self) -> list[Injection]:
        return [i for c in self.cases for i in c.injections]

    def summary(self) -> dict[str, Any]:
        inj = self._inj()
        expected = [i for i in inj if i.expected_catch]
        caught = [i for i in expected if i.detected_as is not None]
        by_kind: dict[str, dict[str, int]] = {}
        for i in inj:
            d = by_kind.setdefault(i.kind, {"injected": 0, "detected": 0, "expected_catch": int(i.expected_catch)})
            d["injected"] += 1
            d["detected"] += int(i.detected_as is not None)
        return {
            "briefs_tested": len(self.cases),
            "injected_total": len(inj),
            # 검출률(recall): '잡아야 하는' 주입 중 실제로 잡힌 비율
            "detection_recall": round(len(caught) / len(expected), 3) if expected else None,
            "by_kind": by_kind,
            "false_positives": sum(c.false_positives for c in self.cases),
        }


def inject(brief: Brief) -> tuple[Brief, list[Injection]]:
    """브리핑 skeleton 에 조작 문장들을 추가한 새 브리핑 + 주입 기록 반환(결정론)."""
    data = brief.to_dict()
    injections = [Injection(kind=k, expected_catch=e, text=t) for k, e, t in _INJECTIONS]
    data["sections"]["skeleton"] = (
        data["sections"]["skeleton"].rstrip() + " " + " ".join(i.text for i in injections)
    )
    return parse_brief(data, strict=True), injections


def run_case(brief: Brief) -> HarnessCase:
    """브리핑 1건: 주입 → 검증 → 각 주입이 잡혔는지 + 오탐 집계."""
    baseline = {v.text for v in verify_brief(brief).violations}  # 원래 위반(있으면)
    injected, injections = inject(brief)
    result = verify_brief(injected)

    v_texts = {v.text for v in result.violations}
    u_texts = {c.text for c in result.uncited}
    injected_texts = {i.text for i in injections}

    for i in injections:
        if i.text in v_texts:
            i.detected_as = "violation"
        elif i.text in u_texts:
            i.detected_as = "uncited"
        else:
            i.detected_as = None

    # 오탐: 위반인데 (주입도 아니고 원래 위반도 아닌) 깨끗한 문장
    false_positives = sum(
        1 for v in result.violations if v.text not in injected_texts and v.text not in baseline
    )
    return HarnessCase(brief_id=brief.id, injections=injections, false_positives=false_positives)


def run_harness(briefs: list[Brief] | None = None) -> HarnessReport:
    """골드셋(기본: data/briefs 의 브리핑들)에 환각 주입 → 검출률 실측."""
    briefs = briefs if briefs is not None else load_all_briefs()
    return HarnessReport(cases=[run_case(b) for b in briefs])
