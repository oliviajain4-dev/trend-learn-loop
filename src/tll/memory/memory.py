"""Memory — 개념 KB(의미기억) + lessons(에피소드기억). 저장은 결정론(JSON), 회상은 용어 overlap.

- remember_textbook: 검증 교과서 → 개념 카드 upsert(같은 주제면 times_seen++·first_seen 보존).
- recall_related / contrast_context: 관련 개념 회상(용어 겹침) → Author 대조·유추 근거.
- record_lesson / recent_lessons: Reflexion 교훈 로그.

정직한 한계: 회상은 **영문 tech 토큰 겹침**(어휘 유사)이지 임베딩(의미 유사) 아님.
'GPT-5.6' vs 'GPT-6' 은 'gpt' 로 겹치지만, 다른 이름의 유사 기술은 놓칠 수 있다(임베딩은 Phase 4 로드맵).
전역 상태 없음: 호출마다 store 인스턴스.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone

from tll.memory.models import ConceptCard, Lesson

DEFAULT_KB = "data/memory/concepts.json"
DEFAULT_LESSONS = "data/memory/lessons.json"

_STOP = {
    "the", "a", "an", "of", "in", "to", "and", "for", "with", "on", "is", "are", "be",
    "new", "using", "use", "how", "why", "what", "your", "you", "it", "its", "as", "at",
    "show", "hn", "ask", "vs", "or", "by", "from", "this", "that",
}


def _slug(topic: str) -> str:
    s = re.sub(r"[^0-9A-Za-z가-힣]+", "-", (topic or "").strip().lower()).strip("-")
    return s or "topic"


def _terms(*texts: str) -> set[str]:
    """회상용 용어: 영문 단어 토큰(len>=2, 불용어 제외). 어휘 겹침 기반."""
    toks: set[str] = set()
    for t in texts:
        for m in re.findall(r"[A-Za-z]{2,}", t or ""):
            w = m.lower()
            if w not in _STOP:
                toks.add(w)
    return toks


def _clean(text: str) -> str:
    t = re.sub(r"\[S\d+\]", "", text or "")
    t = t.replace("(일반지식)", "")
    return re.sub(r"\s+", " ", t).strip()


def _load_json(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}  # 손상 → 빈 상태(보수적)


def _save_json(path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)
    os.replace(tmp, path)  # 원자적


class ConceptKB:
    """개념 카드 저장소(JSON). key → card."""

    def __init__(self, path: str = DEFAULT_KB) -> None:
        self.path = path
        self._cards: dict[str, dict] = _load_json(path).get("cards") or {}

    def remember(self, card: ConceptCard) -> ConceptCard:
        old = self._cards.get(card.key)
        if old:
            card.first_seen = old.get("first_seen") or card.first_seen
            card.times_seen = int(old.get("times_seen", 1)) + 1
        self._cards[card.key] = card.to_dict()
        return card

    def recall(self, query_terms: set[str], *, limit: int = 5, exclude_key: str | None = None) -> list[ConceptCard]:
        scored = []
        for key, c in self._cards.items():
            if key == exclude_key:
                continue
            overlap = len(query_terms & set(c.get("key_terms") or []))
            if overlap > 0:
                scored.append((overlap, int(c.get("times_seen", 1)), key, c))
        # 정렬: 겹침↓, times_seen↓, key↑(결정론 tiebreak)
        scored.sort(key=lambda x: (-x[0], -x[1], x[2]))
        return [ConceptCard.from_dict(c) for _, _, _, c in scored[:limit]]

    def all(self) -> list[ConceptCard]:
        return [ConceptCard.from_dict(c) for c in self._cards.values()]

    def save(self) -> None:
        _save_json(self.path, {"cards": self._cards})


class LessonLog:
    """Reflexion 교훈 로그(JSON, append)."""

    def __init__(self, path: str = DEFAULT_LESSONS) -> None:
        self.path = path
        self._items: list[dict] = _load_json(path).get("lessons") or []

    def add(self, lesson: Lesson) -> None:
        self._items.append(lesson.to_dict())

    def recent(self, *, limit: int = 10, kind: str | None = None) -> list[Lesson]:
        items = [x for x in self._items if kind is None or x.get("kind") == kind]
        return [Lesson.from_dict(x) for x in items[-limit:][::-1]]  # 최신 먼저

    def save(self) -> None:
        _save_json(self.path, {"lessons": self._items})


def remember_textbook(tb, *, category: str = "", kb_path: str = DEFAULT_KB, now: datetime | None = None) -> ConceptCard:
    now_iso = (now or datetime.now(timezone.utc)).isoformat(timespec="seconds")
    src = tb.sources[0] if tb.sources else None
    card = ConceptCard(
        key=_slug(tb.topic),
        topic=tb.topic,
        one_liner=_clean(tb.one_liner),
        category=category,
        key_terms=sorted(_terms(tb.topic, tb.one_liner)),
        grade=src.grade if src else 3,
        nature=src.nature if src else "",
        source_url=src.url if src else "",
        first_seen=now_iso,
        updated_at=now_iso,
        times_seen=1,
    )
    kb = ConceptKB(kb_path)
    kb.remember(card)
    kb.save()
    return card


def recall_related(topic: str, *, extra_terms=None, kb_path: str = DEFAULT_KB, limit: int = 5) -> list[ConceptCard]:
    q = _terms(topic) | set(extra_terms or [])
    return ConceptKB(kb_path).recall(q, limit=limit, exclude_key=_slug(topic))


def contrast_context(topic: str, *, kb_path: str = DEFAULT_KB, limit: int = 3) -> str:
    """Author 에 넣을 대조 컨텍스트 문자열. 관련 개념 없으면 빈 문자열."""
    rel = recall_related(topic, kb_path=kb_path, limit=limit)
    if not rel:
        return ""
    return "이미 아는 관련 개념: " + " / ".join(f"{c.topic}({c.one_liner[:40]})" for c in rel)


def record_lesson(topic: str, kind: str, note: str, *, log_path: str = DEFAULT_LESSONS, now: datetime | None = None) -> None:
    now_iso = (now or datetime.now(timezone.utc)).isoformat(timespec="seconds")
    log = LessonLog(log_path)
    log.add(Lesson(topic=topic, kind=kind, note=note, ts=now_iso))
    log.save()


def recent_lessons(*, log_path: str = DEFAULT_LESSONS, limit: int = 10, kind: str | None = None) -> list[Lesson]:
    return LessonLog(log_path).recent(limit=limit, kind=kind)


def _run_cli() -> None:  # 사용자 머신 데모: python -m tll.memory.memory
    from tll.author.author import author_all
    from tll.factcheck.factcheck import apply, check_textbook
    from tll.reader.reader import read
    from tll.scout.scout import scout
    from tll.tracker.tracker import track
    from tll.triage.triage import triage

    res = scout()
    tr = triage(res.candidates, top_n=5)
    if tr.summary.get("mode") == "error":
        print("[Triage] 실패:", tr.summary.get("error"))
        return
    tk = track(tr.selected)
    rd = read(tk.docs)
    if not rd.ready:
        print("충분한 본문 없음(전부 '더 찾자').")
        return
    books, _ = author_all(rd.ready[:3])
    remembered = []
    for tb in books:
        rep = check_textbook(tb)
        verified = apply(tb, rep)
        card = remember_textbook(verified)
        remembered.append((card, rep.metrics["support_rate"]))
    total = len(ConceptKB(DEFAULT_KB).all())
    print(f"[Memory] 이번에 기억 {len(remembered)}건 · KB 총 {total}건\n")
    for card, sr in remembered:
        print(f"  + {card.topic} (충실도 {int(sr * 100)}%) — {card.one_liner[:48]}")
        rel = recall_related(card.topic, limit=3)
        if rel:
            print(f"     ↳ 관련 개념 회상: {', '.join(c.topic for c in rel)}")
    print("\n== KB에 쌓인 개념(최근) ==")
    for c in ConceptKB(DEFAULT_KB).all()[:10]:
        print(f"  · {c.topic} [{c.nature}·{c.grade}급] terms={c.key_terms[:5]}")


if __name__ == "__main__":
    _run_cli()
