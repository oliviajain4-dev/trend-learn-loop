"""파이프라인 실행 — 한 topic 을 end-to-end 로 브리핑까지.

순서(결정론 워크플로우):
  1) collect(topic)            — 무키 소스에서 수집(provenance)
  2) write_brief(...)          — LLM 초안(status="draft", 문장별 [S#])
  3) verify_brief → apply_verification — L1 위반 문장 제거·미확인 이동(결정론)
  4) apply_metrics             — 충실도 지표 반영 + 위반0이면 status="verified"
  5) save                      — data/briefs/<slug>.json (대시보드가 렌더)

LLM 은 (2)에서만 쓰이고, 진위 판정은 (3) 결정론 코어가 한다(프로젝트 DNA).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from tll.analyst import write_brief
from tll.collector.engine import collect
from tll.metrics import apply_metrics
from tll.schema import Brief, DEFAULT_BRIEFS_DIR
from tll.shared.llm.base import LLMProvider
from tll.verifier import VerificationResult, apply_verification, verify_brief

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    brief: Brief
    collection_summary: dict
    verification: VerificationResult  # 정리 후 재검증 결과
    removed_violations: int  # apply_verification 이 제거한 위반 수
    saved_path: str | None


def run_pipeline(
    topic: str,
    sources: list[str] | None = None,
    *,
    provider: LLMProvider | None = None,
    model: str | None = None,
    max_per_source: int = 8,
    save: bool = True,
    briefs_dir: str | Path | None = None,
) -> PipelineResult:
    """topic 하나를 수집→집필→검증→지표→저장까지 실행."""
    # 1) 수집
    collection = collect(topic, sources=sources, max_per_source=max_per_source)
    if not collection.documents:
        raise RuntimeError(f"수집 결과가 비어 파이프라인 중단(topic={topic!r})")

    # 2) 집필(초안)
    draft = write_brief(topic, collection, provider=provider, model=model)

    # 3) 검증 → 위반 문장 정리(결정론)
    pre = verify_brief(draft)
    cleaned = apply_verification(draft, pre)
    post = verify_brief(cleaned)  # 정리 후 재검증(위반 0 기대)

    # 4) 지표 반영(+ 위반0이면 status="verified")
    final = apply_metrics(cleaned, result=post)

    # 5) 저장
    saved_path: str | None = None
    if save:
        d = Path(briefs_dir) if briefs_dir is not None else DEFAULT_BRIEFS_DIR
        d.mkdir(parents=True, exist_ok=True)
        path = d / f"{final.id}.json"
        path.write_text(
            json.dumps(final.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        saved_path = str(path)
        logger.info("브리핑 저장: %s", saved_path)

    return PipelineResult(
        brief=final,
        collection_summary=collection.summary,
        verification=post,
        removed_violations=len(pre.violations),
        saved_path=saved_path,
    )


def main() -> None:
    """CLI: python -m tll.pipeline.run "<topic>" [source ...]"""
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if len(sys.argv) < 2:
        print('사용법: python -m tll.pipeline.run "<topic>" [hackernews geeknews]')
        raise SystemExit(2)
    topic = sys.argv[1]
    srcs = sys.argv[2:] or None
    res = run_pipeline(topic, sources=srcs)
    b = res.brief
    print(f"\n[완료] {b.tech_name} → status={b.status}")
    print(f"  지표: 지지율 {b.metrics.atomic_support_rate:.0%} · 인용정밀도 {b.metrics.citation_precision:.2f} "
          f"· 커버리지 {b.metrics.citation_recall:.0%} · 출처 {b.metrics.source_count}")
    print(f"  정리된 위반: {res.removed_violations} · 미확인: {len(b.unverified)}")
    print(f"  저장: {res.saved_path}")


if __name__ == "__main__":
    main()
