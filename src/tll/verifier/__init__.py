"""Verifier — 검증 코어. **의도적으로 비에이전트(결정론)**.

Phase 1 범위 = L1 인용 앵커링(LLM 판단 0):
  - 유령 인용: 본문 [S#] 이 실존하지 않는 출처를 가리키면 위반(폐기 대상).
  - 미인용 사실문: [S#] 없는 사실성 문장은 근거 약함으로 표시.
  - 인용문 앵커링: 문장 속 따옴표 인용이 그 출처 text 에 문자열로 실제 있는지(출처 text 가 있을 때).

**유보(정직 고지)**: L4 NLI·CoVe 는 '출처 원문 전체'가 있어야 검증기 자신이 환각하지 않는다.
현재 Collector 는 본문 전체를 안 가져오므로, 근거 없이 돌리지 않고 '본문 수집' 이후로 유보한다.
이 유보 자체가 "검증기가 환각하면 안 된다"는 설계 철학(기획서 §2.5)의 실천이다.
"""

from tll.verifier.anchoring import (
    SentenceCheck,
    VerificationResult,
    apply_verification,
    verify_brief,
)

__all__ = [
    "SentenceCheck",
    "VerificationResult",
    "apply_verification",
    "verify_brief",
]
