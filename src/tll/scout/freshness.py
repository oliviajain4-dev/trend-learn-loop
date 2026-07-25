"""신선도 라벨 — 발행 시각을 '3시간 전' 같은 한국어 상대시간으로.

Scout 와 대시보드가 공유한다. 순수 함수(같은 입력→같은 출력, 결정론).
'지금(now)'을 주입받아 테스트 가능하게 한다(전역 시계 의존 없음).
"""

from __future__ import annotations

from datetime import datetime, timezone


def _parse(iso: str | None) -> datetime | None:
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(iso.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def unix_to_iso(ts: int) -> str | None:
    """unix seconds(HN time) → ISO8601(UTC). 0/오류면 None."""
    if not ts:
        return None
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat(timespec="seconds")
    except (ValueError, OSError, OverflowError):
        return None


def age_label(published_iso: str | None, now: datetime | None = None) -> str:
    """ISO8601 → '방금 / N분 전 / N시간 전 / N일 전'. 파싱불가·미래면 ''."""
    dt = _parse(published_iso)
    if dt is None:
        return ""
    now = now or datetime.now(timezone.utc)
    secs = (now - dt).total_seconds()
    if secs < 0:
        return ""  # 미래(시계 오차) → 표기 안 함(지어내지 않음)
    mins = int(secs // 60)
    if mins < 1:
        return "방금"
    if mins < 60:
        return f"{mins}분 전"
    hours = mins // 60
    if hours < 24:
        return f"{hours}시간 전"
    return f"{hours // 24}일 전"
