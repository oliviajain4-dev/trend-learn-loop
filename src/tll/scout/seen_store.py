"""최소 Memory — '이미 본' 트렌드 항목 로그(신규성 판단용).

JSON 파일 하나(data/memory/seen.json). 무거운 DB 없음(프로젝트 DNA).
- 결정론: 같은 seen.json + 같은 입력 → 같은 is_new 판정(재현성).
- 전역 상태 없음: 호출마다 인스턴스.
- first_seen 을 박제해 '처음 본 시각'을 안정적으로 유지(재폴링해도 안 바뀜).

이건 Memory 의 **최소형**이다. 이후 개념 KB(대조·유추 근거)로 확장된다(기획서 v3 §7).
"""

from __future__ import annotations

import json
import os


class SeenStore:
    def __init__(self, path: str) -> None:
        self.path = path
        self._data: dict = {"last_check": None, "seen": {}}
        self._load()

    def _load(self) -> None:
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, encoding="utf-8") as f:
                d = json.load(f)
        except (json.JSONDecodeError, OSError):
            return  # 손상 시 빈 상태로 시작(보수적)
        if isinstance(d, dict):
            self._data = {"last_check": d.get("last_check"), "seen": d.get("seen") or {}}

    @property
    def last_check(self) -> str | None:
        return self._data["last_check"]

    def is_new(self, cid: str) -> bool:
        return cid not in self._data["seen"]

    def first_seen_of(self, cid: str) -> str | None:
        rec = self._data["seen"].get(cid)
        return rec.get("first_seen") if rec else None

    def mark_seen(self, cid: str, *, first_seen: str, title: str = "", source: str = "") -> None:
        if cid not in self._data["seen"]:
            self._data["seen"][cid] = {
                "first_seen": first_seen,
                "title": title,
                "source": source,
            }

    def commit(self, *, now: str) -> None:
        """last_check 갱신 + 원자적으로 파일 저장(정렬 → 결정론 출력)."""
        self._data["last_check"] = now
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        tmp = f"{self.path}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2, sort_keys=True)
        os.replace(tmp, self.path)  # 원자적 교체(중간 크래시에도 손상 방지)
