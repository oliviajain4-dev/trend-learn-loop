"""티어 보드 — 레지스트리 + 신호로그 → 개념별 점수·나이·티어, 티어순 정렬. 대시보드가 이걸 그린다."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime

from tll.concepts.categorize import OUT_OF_SCOPE
from tll.concepts.classify import concept_kind
from tll.concepts.registry import DEFAULT_REGISTRY, ConceptRegistry
from tll.rank.models import ConceptScore
from tll.rank.score import score_concept
from tll.rank.tier import Thresholds, TierResult, assign_tier
from tll.signals.store import DEFAULT_SIGNALS, load_signals

_TIER_RANK = {"tiger": 0, "cheetah": 1, "sprout": 2, "dinosaur": 3, "hyena": 4, "elephant": 5, "turtle": 6, "mayfly": 7}


@dataclass
class BoardRow:
    cid: str
    name: str
    category: str
    score: ConceptScore
    tier: TierResult
    age_days: int | None
    kind: str = "tool"
    first_seen: str = ""


def _as_date(x) -> date:
    if isinstance(x, datetime):
        return x.date()
    if isinstance(x, date):
        return x
    return date.fromisoformat(str(x)[:10])


def _age_days(concept, now_d: date) -> int | None:
    raw = concept.created_at or ""   # 진짜 생성일만. first_seen(우리가 처음 본 날)은 나이가 아님
    if not raw:
        return None
    try:
        return max(0, (now_d - date.fromisoformat(raw[:10])).days)
    except ValueError:
        return None


def build_board(*, registry: ConceptRegistry | None = None, registry_path: str = DEFAULT_REGISTRY,
                signals=None, signals_path: str = DEFAULT_SIGNALS, now,
                cfg: Thresholds | None = None, half_life_days: float = 3.0, window_days: int = 14,
                include_out_of_scope: bool = False) -> list[BoardRow]:
    reg = registry or ConceptRegistry.load(registry_path)
    rows_sigs = signals if signals is not None else load_signals(signals_path)
    now_d = _as_date(now)
    by_cid: dict[str, list] = defaultdict(list)
    for s in rows_sigs:
        by_cid[s.cid].append(s)

    board: list[BoardRow] = []
    for c in reg.all():
        sc = score_concept(by_cid.get(c.cid, []), now=now, half_life_days=half_life_days, window_days=window_days)
        age = _age_days(c, now_d)
        tr = assign_tier(sc, age_days=age, cfg=cfg)
        kind = concept_kind(c.canonical, category=c.category, topics=getattr(c, "topics", ()))
        board.append(BoardRow(cid=c.cid, name=c.canonical, category=c.category, score=sc, tier=tr, age_days=age, kind=kind, first_seen=getattr(c, "first_seen", "") or ""))
    if not include_out_of_scope:
        board = [r for r in board if r.category != OUT_OF_SCOPE]   # 범위 밖(비-IT/AI) 개념은 화면에서 제외
    board.sort(key=lambda r: (_TIER_RANK.get(r.tier.tier, 9), -r.score.adoption, -r.score.attention))
    return board
