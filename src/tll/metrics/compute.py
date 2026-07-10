"""충실도 지표 산출 — 결정론 프록시(LLM 없이 Verifier 결과로 계산).

지표(schema.metrics 필드에 매핑):
  - atomic_support_rate : 사실문 중 '신뢰(1·2급) 출처'에 인용된 비율(FActScore 결정론 프록시).
  - citation_precision  : 인용이 실존 출처를 가리키는 비율 = 1 - 유령인용율(ALCE 정밀도 프록시).
  - citation_recall     : 사실문 중 [S#] 인용이 달린 비율(커버리지, ALCE 재현율 프록시).
  - ragas_faithfulness  : 커버리지 기반 결정론 프록시(진짜 RAGAS NLI 아님 — 본문 필요).
  - source_count        : 출처 수(계약상 실제 출처수와 일치).

한계: 진짜 지지 여부(인용 passage 가 문장을 함의하는가)는 본문 원문 NLI 가 필요.
여기 수치는 '인용 구조의 건전성'을 재는 프록시다(과장 금지).
"""

from __future__ import annotations

from typing import Any

from tll.schema import Brief, parse_brief
from tll.verifier import VerificationResult, verify_brief

_MIN_FACTUAL_LEN = 20  # Verifier 와 동일 기준


def _round(x: float) -> float:
    return round(float(x), 3)


def compute_metrics(brief: Brief, result: VerificationResult | None = None) -> dict[str, Any]:
    """브리핑의 충실도 지표(결정론 프록시)를 계산해 schema.metrics 형식 dict 로 반환."""
    result = result or verify_brief(brief)
    sid_grade = {s.sid: s.grade for s in brief.sources}

    # 정밀도(유효율)는 '인용이 달린 모든 문장' 기준 — 유령인용은 길이와 무관하게 잡는다.
    cited_all = [c for c in result.checks if c.cited_sids]
    phantom = [c for c in cited_all if c.status == "phantom_citation"]
    validity = (1 - len(phantom) / len(cited_all)) if cited_all else 1.0

    # 커버리지·지지율은 '사실성 문장'(≥20자) 기준.
    factual = [c for c in result.checks if len(c.text) >= _MIN_FACTUAL_LEN]
    n = len(factual)
    valid_cited = [c for c in factual if c.cited_sids and c.status != "phantom_citation"]
    trusted = [
        c for c in valid_cited if any(sid_grade.get(sid, 3) <= 2 for sid in c.cited_sids)
    ]

    coverage = (len(valid_cited) / n) if n else 0.0
    support = (len(trusted) / n) if n else 0.0

    return {
        "atomic_support_rate": _round(support),
        "citation_precision": _round(validity),
        "citation_recall": _round(coverage),
        "ragas_faithfulness": _round(coverage),
        "source_count": len(brief.sources),
    }


def apply_metrics(
    brief: Brief,
    *,
    result: VerificationResult | None = None,
    metrics: dict[str, Any] | None = None,
) -> Brief:
    """지표를 브리핑에 반영. L1 검증 통과(위반0)면 status="verified", 아니면 draft 유지.

    반환 전 parse_brief(strict) 로 계약(지표 0~1, source_count 일치 등) 자동 보증.
    """
    result = result or verify_brief(brief)
    metrics = metrics or compute_metrics(brief, result)

    data = brief.to_dict()
    data["metrics"] = metrics
    data["status"] = "verified" if result.passed else "draft"
    return parse_brief(data, strict=True)
