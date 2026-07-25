"""교과서 저장/로드 (JSON). 대시보드가 읽을 레코드.

레코드 = Textbook.to_dict() + {metrics(충실도), provider(사용 모델), saved_at, concept_cid, concept_name}.
저장은 원자적(tmp→replace), 로드는 손상 파일 스킵.
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
    tb,
    *,
    metrics: dict | None = None,
    provider: str = "",
    out_dir: str = DEFAULT_DIR,
    now: datetime | None = None,
    concept_cid: str = "",
    concept_name: str = "",
    depth: str = "교과서",
) -> str:
    """검증된 Textbook + 지표 + 사용 모델을 레코드로 저장(같은 주제 덮어씀=최신).

    concept_cid/concept_name: 이 교과서가 '어떤 기술 개념'을 설명하는지 꼬리표(화면이 기술 중심으로 묶는 키).
    """
    now_iso = (now or datetime.now(timezone.utc)).isoformat(timespec="seconds")
    rec: dict[str, Any] = tb.to_dict()
    rec["metrics"] = metrics or {}
    rec["provider"] = provider
    rec["saved_at"] = now_iso
    rec["concept_cid"] = concept_cid
    rec["concept_name"] = concept_name
    rec["depth"] = depth
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
