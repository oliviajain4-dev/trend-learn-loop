"""교과서 저장/로드 (JSON). 대시보드가 읽을 레코드.

레코드 = Textbook.to_dict() + {metrics(충실도 등), saved_at}. 결정론 저장(정렬·원자적).
로드는 dict 그대로 반환(렌더는 dict 로 처리 — 재구성 불필요).
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from typing import Any

DEFAULT_DIR = "data/textbooks"


def _slug(topic: str) -> str:
    s = re.sub(r"[^0-9A-Za-z가-힣]+", "-", (topic or "").strip().lower()).strip("-")
    return s or "topic"


def save_textbook(
    tb, *, metrics: dict | None = None, out_dir: str = DEFAULT_DIR, now: datetime | None = None
) -> str:
    """검증된 Textbook + 지표를 레코드로 저장. 파일명=slug(topic).json (같은 주제는 덮어씀=최신 유지)."""
    now_iso = (now or datetime.now(timezone.utc)).isoformat(timespec="seconds")
    rec: dict[str, Any] = tb.to_dict()
    rec["metrics"] = metrics or {}
    rec["saved_at"] = now_iso
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{_slug(tb.topic)}.json")
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=2, sort_keys=True)
    os.replace(tmp, path)
    return path


def load_records(out_dir: str = DEFAULT_DIR) -> list[dict]:
    """저장된 교과서 레코드 전부. 손상 파일은 건너뜀."""
    if not os.path.isdir(out_dir):
        return []
    recs: list[dict] = []
    for fn in sorted(os.listdir(out_dir)):
        if not fn.endswith(".json"):
            continue
        try:
            with open(os.path.join(out_dir, fn), encoding="utf-8") as f:
                recs.append(json.load(f))
        except (json.JSONDecodeError, OSError):
            continue
    return recs
