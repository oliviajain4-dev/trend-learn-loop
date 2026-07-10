"""수집 엔진 — 여러 provider 를 돌려 CollectedDoc 를 모으고 정규화한다.

collect(topic, sources=None, max_per_source=10) -> CollectionResult
  - sources 지정(없으면 전체 provider) 를 돌린다.
  - content_hash 로 중복 제거(같은 url+title 한 번만).
  - 소스 round-robin 인터리브로 '다양성 배분'(상위가 한 소스로 도배되지 않게).
  - summary 를 채워 반환한다 — 나중에 ReAct 루프의 '관찰'이 되어 재수집 결정에 쓰인다.

설계(ReAct 호환):
  - 부작용 최소 순수 함수처럼. 전역 가변 상태 없음(rate_limiter/robots_guard 는 호출마다 생성).
  - **가짜 균형을 만들지 않는다**: 한 소스만 결과가 있으면 그걸 버려 균형 맞추지 않고,
    summary(소스별 수)에 그대로 드러낸다 → 모델이 "다른 소스 더 돌릴까"를 스스로 판단.
"""

from __future__ import annotations

import json
import logging
import re
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path

from tll.collector.models import CollectedDoc, CollectionResult
from tll.collector.providers import all_providers, get_provider
from tll.collector.rate_limiter import RateLimiter
from tll.collector.robots_guard import RobotsGuard

logger = logging.getLogger(__name__)

# engine.py: src/tll/collector/engine.py → parents[3] == <repo>
_REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_COLLECTED_DIR = _REPO_ROOT / "data" / "collected"  # 원자료(브리핑 아님) 디버그 저장


def _dedup(docs: list[CollectedDoc]) -> tuple[list[CollectedDoc], int]:
    """content_hash 로 중복 제거(첫 등장 유지). (결과, 제거수)."""
    seen: set[str] = set()
    out: list[CollectedDoc] = []
    removed = 0
    for d in docs:
        if d.content_hash in seen:
            removed += 1
            continue
        seen.add(d.content_hash)
        out.append(d)
    return out, removed


def _interleave(docs: list[CollectedDoc]) -> list[CollectedDoc]:
    """소스별로 나눠 round-robin 으로 다시 합친다(상위 다양성 확보, 소스 내 순서 유지)."""
    buckets: dict[str, deque[CollectedDoc]] = defaultdict(deque)
    order: list[str] = []
    for d in docs:
        if d.source_type not in buckets:
            order.append(d.source_type)
        buckets[d.source_type].append(d)
    out: list[CollectedDoc] = []
    while any(buckets[s] for s in order):
        for s in order:
            if buckets[s]:
                out.append(buckets[s].popleft())
    return out


def _slug(topic: str) -> str:
    s = re.sub(r"[^0-9A-Za-z가-힣]+", "-", topic.strip().lower()).strip("-")
    return s or "topic"


def _save(result: CollectionResult) -> Path:
    DEFAULT_COLLECTED_DIR.mkdir(parents=True, exist_ok=True)
    path = DEFAULT_COLLECTED_DIR / f"{_slug(result.topic)}.json"
    path.write_text(
        json.dumps(result.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return path


def collect(
    topic: str,
    sources: list[str] | None = None,
    max_per_source: int = 10,
    *,
    save: bool = False,
    min_interval: float = 1.5,
    max_total: int | None = None,
) -> CollectionResult:
    """topic 으로 여러 소스를 수집해 정규화된 CollectionResult 반환."""
    # provider 선택
    if sources is None:
        providers = all_providers()
    else:
        providers = []
        for name in sources:
            p = get_provider(name)
            if p is None:
                logger.warning("알 수 없는 provider 무시: %s", name)
            else:
                providers.append(p)

    # 호출마다 독립 인스턴스(전역 상태 없음)
    rate_limiter = RateLimiter(min_interval=min_interval)
    robots_guard = RobotsGuard()

    per_source_raw: dict[str, int] = {}
    errors: dict[str, str] = {}
    all_docs: list[CollectedDoc] = []
    for p in providers:
        try:
            docs = p.search(
                topic, limit=max_per_source, rate_limiter=rate_limiter, robots_guard=robots_guard
            )
        except Exception as e:  # 한 provider 실패가 전체를 죽이지 않게
            logger.warning("provider %s 실패: %s", p.name, e)
            errors[p.name] = str(e)
            docs = []
        per_source_raw[p.name] = len(docs)
        all_docs.extend(docs)

    deduped, removed = _dedup(all_docs)
    documents = _interleave(deduped)
    if max_total is not None:
        documents = documents[:max_total]

    per_source_final: dict[str, int] = defaultdict(int)
    for d in documents:
        per_source_final[d.source_type] += 1

    summary = {
        "topic": topic,
        "providers": [p.name for p in providers],
        "per_source_raw": per_source_raw,  # provider 가 준 원수
        "per_source_final": dict(per_source_final),  # 정규화 후
        "total_raw": len(all_docs),
        "deduped_removed": removed,
        "total": len(documents),
        "collected_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "errors": errors,
    }
    result = CollectionResult(topic=topic, documents=documents, summary=summary)

    if save:
        saved = _save(result)
        logger.info("수집 원자료 저장: %s", saved)

    return result
