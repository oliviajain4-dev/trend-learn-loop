"""파이프라인 — Collector→Analyst→Verifier→Metrics 를 하나로 엮어 브리핑을 생성한다.

기획서 §2.5 기준 '워크플로우 구역'(순서를 코드가 정함). 에이전트 자율성 없음.
산출: data/briefs/<slug>.json 에 브리핑 저장 → 대시보드가 자동 렌더.
"""

from tll.pipeline.run import PipelineResult, run_pipeline

__all__ = ["PipelineResult", "run_pipeline"]
