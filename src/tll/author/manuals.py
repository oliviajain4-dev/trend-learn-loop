"""설명서 백필 — 레지스트리의 '아직 설명 없는' 개념 전부에 최소 설명서를 붙인다. (규칙문서 §7)

교과서(깊음)는 트렌드 기사 경로에서만 나온다. 발견형 개념(GitHub·arXiv)은 여기서 README/초록으로
짧은 설명서를 받는다 → '코끼리인데 설명 없음'이 사라진다. 새 개념만(캐시), 한 번에 limit 개까지.
"""

from __future__ import annotations

import logging
from typing import Callable

from tll.author.author import write_manual
from tll.present.store import load_records, save_textbook

logger = logging.getLogger(__name__)


def backfill_manuals(
    registry,
    *,
    records_dir: str,
    source_for: Callable[[object], tuple[str, str]],
    llm_call: Callable[[str, str], str],
    provider: str = "",
    limit: int = 8,
) -> list[str]:
    """설명(교과서/설명서) 없는 개념에 설명서 생성. source_for(concept)->(원문, url). 반환: 새로 쓴 이름들."""
    have = {r.get("concept_cid") for r in load_records(records_dir)}
    made: list[str] = []
    for c in registry.all():
        if c.cid in have:
            continue
        try:
            body, url = source_for(c)
        except Exception:  # noqa: BLE001
            body, url = "", ""
        if not (body or "").strip():
            continue
        try:
            tb = write_manual(c.canonical, body, url=url, nature="저장소", grade="2", llm_call=llm_call)
            save_textbook(tb, provider=provider, out_dir=records_dir,
                          concept_cid=c.cid, concept_name=c.canonical, depth="설명서")
            made.append(c.canonical)
        except Exception as e:  # noqa: BLE001
            logger.warning("설명서 실패(%s): %s", c.canonical, e)
            continue
        if len(made) >= limit:
            break
    return made
