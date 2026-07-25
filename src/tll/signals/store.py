"""신호 로그 — data/memory/signals.jsonl 에 append-only 로 시간열을 쌓는다.

랭킹·재라벨의 '재료'. 결정론이며, 손상된 줄은 건너뛴다(부분 쓰기 견딤).
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from tll.signals.models import Signal, family_of

DEFAULT_SIGNALS = "data/memory/signals.jsonl"


def log_signal(cid, source, kind, value, *, date=None, family=None, path=DEFAULT_SIGNALS, now=None) -> Signal:
    """신호 한 점을 append. date 미지정 시 오늘(UTC), family 미지정 시 kind 로 추론."""
    d = date or (now or datetime.now(timezone.utc)).date().isoformat()
    rec = Signal(cid=cid, date=d, source=source, kind=kind, value=float(value), family=family or family_of(kind))
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec.to_dict(), ensure_ascii=False) + "\n")
    return rec


def log_many(signals, *, path=DEFAULT_SIGNALS) -> int:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    n = 0
    with open(path, "a", encoding="utf-8") as f:
        for s in signals:
            f.write(json.dumps(s.to_dict(), ensure_ascii=False) + "\n")
            n += 1
    return n


def load_signals(path=DEFAULT_SIGNALS) -> list[Signal]:
    if not os.path.exists(path):
        return []
    out: list[Signal] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(Signal.from_dict(json.loads(line)))
            except (json.JSONDecodeError, ValueError, TypeError):
                continue  # 손상된 줄은 조용히 스킵
    return out


def signals_for(cid, path=DEFAULT_SIGNALS) -> list[Signal]:
    return [s for s in load_signals(path) if s.cid == cid]
