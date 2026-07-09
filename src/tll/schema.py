"""브리핑 데이터 계약 (Data Contract) — TLL '정체 브리핑' JSON 스키마.

이 모듈이 "진실의 형식"을 정한다:
  - 지금은 샘플 브리핑(status="sample")을, 나중엔 진짜 파이프라인이
    같은 형식으로 data/briefs/*.json 을 쌓는다.
  - 대시보드(tll.dashboard)는 이 스키마를 통해서만 데이터를 읽는다.

설계 원칙(프로젝트 DNA와 정렬):
  - **결정론·투명**: pydantic 같은 "마법" 대신 stdlib dataclass + 눈에 보이는 검증.
    같은 입력 → 같은 판정. 검증 규칙이 코드에 그대로 드러난다.
  - **측정 없는 주장 금지**: metrics 의 지지율/정밀도/재현율은 0~1 실수로 강제,
    범위를 벗어나면 계약 위반으로 거부한다.
  - **정직**: status 로 sample/draft/verified 를 구분(화면 배지의 근거).

근거: docs/TLL_기획서_v2.1.md §3(정체 브리핑 표준 양식), §5(충실도 측정).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

# ─────────────────────────────────────────────────────────────────────────────
# 상수 (허용값) — 화면 배지/라벨과 검증의 단일 근거
# ─────────────────────────────────────────────────────────────────────────────

SCHEMA_VERSION = "1.0"

# 브리핑 신뢰 단계. 화면에 반드시 배지로 노출.
#   sample   = 샘플/자리표시(측정값 아님) → 대시보드가 경고 배너 표시
#   draft    = 집필됨, 아직 검증·측정 전
#   verified = 검증기·지표 통과(측정된 실수치)
STATUSES = ("sample", "draft", "verified")
STATUS_LABELS = {
    "sample": "샘플 데이터",
    "draft": "초안(미검증)",
    "verified": "검증됨",
}

# 출처 등급: 1=최상(공식/1차) … 3=약함(블로그/여론성)
SOURCE_GRADES = (1, 2, 3)

# 여론(반응)의 감성 — 사실이 아니라 감성임을 명시하기 위한 값
SENTIMENTS = ("positive", "negative", "mixed", "neutral")

# 판단 도우미의 수준
JUDGMENT_LEVELS = ("high", "medium", "low")

# §3 본문 섹션(1~6)의 화면 표시 순서/번호/라벨.
# render.py 가 이 순서 그대로 그린다. (0=one_liner, 7~9는 media/reactions/judgment)
SECTION_ORDER: tuple[tuple[str, int, str], ...] = (
    ("skeleton", 1, "큰 뼈대 (구조/틀)"),
    ("background", 2, "왜 나왔나 (배경·계보)"),
    ("contrast_analogy", 3, "대조·유추 (뭐가 비슷/다른가)"),
    ("why_needed", 4, "왜 필요한가 / 어떤 문제를 푸나"),
    ("outlook", 5, "전망 (채택신호·한계·리스크)"),
    ("quickstart", 6, "바로 따라하기 (quickstart)"),
)

# 0~1 실수로 강제되는 metrics 필드(개수 필드 제외)
_RATE_FIELDS = (
    "atomic_support_rate",
    "citation_precision",
    "citation_recall",
    "ragas_faithfulness",
)


class SchemaError(ValueError):
    """브리핑 데이터가 계약을 위반했을 때. 메시지에 위반 목록을 담는다."""


# ─────────────────────────────────────────────────────────────────────────────
# 파싱 헬퍼 — 구조(키 존재/타입)를 확인하며 dict → dataclass
# ─────────────────────────────────────────────────────────────────────────────


def _require_dict(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SchemaError(f"{path}: 객체(dict)여야 하는데 {type(value).__name__} 임")
    return value


def _get(d: dict[str, Any], key: str, path: str) -> Any:
    if key not in d:
        raise SchemaError(f"{path}.{key}: 필수 키가 없음")
    return d[key]


def _as_list(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        raise SchemaError(f"{path}: 배열(list)여야 하는데 {type(value).__name__} 임")
    return value


# ─────────────────────────────────────────────────────────────────────────────
# 데이터 클래스 (계약 본체)
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class Metrics:
    """측정된 충실도 지표. sample 이라도 형식은 이걸 지켜야 함(값이 진짜인지는 status 로)."""

    atomic_support_rate: float  # FActScore식 원자사실 지지율 (0~1)
    citation_precision: float  # ALCE 인용 정밀도 (0~1)
    citation_recall: float  # ALCE 인용 재현율 (0~1)
    ragas_faithfulness: float  # RAGAS faithfulness (0~1)
    source_count: int  # 출처 개수 (>=0)

    @classmethod
    def from_dict(cls, d: Any, path: str = "metrics") -> "Metrics":
        d = _require_dict(d, path)
        return cls(
            atomic_support_rate=_get(d, "atomic_support_rate", path),
            citation_precision=_get(d, "citation_precision", path),
            citation_recall=_get(d, "citation_recall", path),
            ragas_faithfulness=_get(d, "ragas_faithfulness", path),
            source_count=_get(d, "source_count", path),
        )


@dataclass
class Sections:
    """§3 본문 섹션 1~6. (0=one_liner 는 Brief 상단에 별도.)"""

    skeleton: str
    background: str
    contrast_analogy: str
    why_needed: str
    outlook: str
    quickstart: str

    @classmethod
    def from_dict(cls, d: Any, path: str = "sections") -> "Sections":
        d = _require_dict(d, path)
        return cls(
            skeleton=_get(d, "skeleton", path),
            background=_get(d, "background", path),
            contrast_analogy=_get(d, "contrast_analogy", path),
            why_needed=_get(d, "why_needed", path),
            outlook=_get(d, "outlook", path),
            quickstart=_get(d, "quickstart", path),
        )


@dataclass
class MediaItem:
    """유튜브 등 미디어 1건. 링크·조회수는 나중에 API 원본에서만 채운다(LLM 생성 금지)."""

    video_id: str
    title: str
    channel: str
    url: str
    view_count: int | None = None  # API 실데이터에서만. 미확보면 None.
    published_at: str | None = None

    @classmethod
    def from_dict(cls, d: Any, path: str) -> "MediaItem":
        d = _require_dict(d, path)
        return cls(
            video_id=_get(d, "video_id", path),
            title=_get(d, "title", path),
            channel=_get(d, "channel", path),
            url=_get(d, "url", path),
            view_count=d.get("view_count"),
            published_at=d.get("published_at"),
        )


@dataclass
class Media:
    youtube_global: list[MediaItem] = field(default_factory=list)
    youtube_kr: list[MediaItem] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: Any, path: str = "media") -> "Media":
        d = _require_dict(d, path)
        g = _as_list(d.get("youtube_global", []), f"{path}.youtube_global")
        k = _as_list(d.get("youtube_kr", []), f"{path}.youtube_kr")
        return cls(
            youtube_global=[
                MediaItem.from_dict(x, f"{path}.youtube_global[{i}]") for i, x in enumerate(g)
            ],
            youtube_kr=[MediaItem.from_dict(x, f"{path}.youtube_kr[{i}]") for i, x in enumerate(k)],
        )


@dataclass
class Reaction:
    """사람들의 반응(여론) — 사실이 아니라 감성. 링크와 함께 정직하게 표시."""

    source: str  # "Hacker News", "Reddit" 등
    sentiment: str  # SENTIMENTS 중 하나
    summary: str
    url: str
    collected_at: str

    @classmethod
    def from_dict(cls, d: Any, path: str) -> "Reaction":
        d = _require_dict(d, path)
        return cls(
            source=_get(d, "source", path),
            sentiment=_get(d, "sentiment", path),
            summary=_get(d, "summary", path),
            url=_get(d, "url", path),
            collected_at=_get(d, "collected_at", path),
        )


@dataclass
class JudgmentItem:
    level: str  # JUDGMENT_LEVELS 중 하나
    note: str

    @classmethod
    def from_dict(cls, d: Any, path: str) -> "JudgmentItem":
        d = _require_dict(d, path)
        return cls(level=_get(d, "level", path), note=_get(d, "note", path))


@dataclass
class Judgment:
    """판단 도우미(§9): 배울 가치·성숙도·나와의 관련성."""

    worth_learning: JudgmentItem  # 배울 가치
    maturity: JudgmentItem  # 성숙도
    relevance: JudgmentItem  # 나와의 관련성

    @classmethod
    def from_dict(cls, d: Any, path: str = "judgment") -> "Judgment":
        d = _require_dict(d, path)
        return cls(
            worth_learning=JudgmentItem.from_dict(
                _get(d, "worth_learning", path), f"{path}.worth_learning"
            ),
            maturity=JudgmentItem.from_dict(_get(d, "maturity", path), f"{path}.maturity"),
            relevance=JudgmentItem.from_dict(_get(d, "relevance", path), f"{path}.relevance"),
        )


@dataclass
class Source:
    """출처(provenance) 한 건. [S#] 로 본문에서 참조된다."""

    sid: str  # "S1", "S2" …
    title: str
    org: str  # 기관/발행처
    date: str  # 발행일 (YYYY-MM-DD 권장)
    grade: int  # 1~3
    url: str
    collected_at: str  # 수집시각 (ISO)

    @classmethod
    def from_dict(cls, d: Any, path: str) -> "Source":
        d = _require_dict(d, path)
        return cls(
            sid=_get(d, "sid", path),
            title=_get(d, "title", path),
            org=_get(d, "org", path),
            date=_get(d, "date", path),
            grade=_get(d, "grade", path),
            url=_get(d, "url", path),
            collected_at=_get(d, "collected_at", path),
        )


@dataclass
class Unverified:
    """미확인·출처충돌 주장 (정직 원칙). 근거 약한 것을 숨기지 않고 드러낸다."""

    claim: str
    reason: str  # 왜 미확인인가 / 무엇과 충돌하는가
    conflicting_sids: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: Any, path: str) -> "Unverified":
        d = _require_dict(d, path)
        sids = _as_list(d.get("conflicting_sids", []), f"{path}.conflicting_sids")
        return cls(
            claim=_get(d, "claim", path),
            reason=_get(d, "reason", path),
            conflicting_sids=[str(s) for s in sids],
        )


@dataclass
class Brief:
    """정체 브리핑 1건 = JSON 파일 1개. (docs/TLL_기획서_v2.1.md §3)"""

    id: str
    tech_name: str
    first_seen: str  # 최초확인 날짜 (YYYY-MM-DD)
    status: str  # STATUSES 중 하나
    one_liner: str  # 0. 한 줄 정체
    metrics: Metrics
    sections: Sections  # 1~6
    media: Media  # 7
    reactions: list[Reaction]  # 8
    judgment: Judgment  # 9
    sources: list[Source]  # provenance
    unverified: list[Unverified]  # ⚠️ 미확인·충돌
    schema_version: str = SCHEMA_VERSION

    # ── 편의 프로퍼티 ────────────────────────────────────────────────
    @property
    def is_sample(self) -> bool:
        return self.status == "sample"

    @property
    def status_label(self) -> str:
        return STATUS_LABELS.get(self.status, self.status)

    # ── 직렬화 ──────────────────────────────────────────────────────
    @classmethod
    def from_dict(cls, d: Any, path: str = "brief") -> "Brief":
        d = _require_dict(d, path)
        reactions = _as_list(d.get("reactions", []), f"{path}.reactions")
        sources = _as_list(_get(d, "sources", path), f"{path}.sources")
        unverified = _as_list(d.get("unverified", []), f"{path}.unverified")
        return cls(
            id=_get(d, "id", path),
            tech_name=_get(d, "tech_name", path),
            first_seen=_get(d, "first_seen", path),
            status=_get(d, "status", path),
            one_liner=_get(d, "one_liner", path),
            metrics=Metrics.from_dict(_get(d, "metrics", path), f"{path}.metrics"),
            sections=Sections.from_dict(_get(d, "sections", path), f"{path}.sections"),
            media=Media.from_dict(d.get("media", {}), f"{path}.media"),
            reactions=[Reaction.from_dict(x, f"{path}.reactions[{i}]") for i, x in enumerate(reactions)],
            judgment=Judgment.from_dict(_get(d, "judgment", path), f"{path}.judgment"),
            sources=[Source.from_dict(x, f"{path}.sources[{i}]") for i, x in enumerate(sources)],
            unverified=[
                Unverified.from_dict(x, f"{path}.unverified[{i}]") for i, x in enumerate(unverified)
            ],
            schema_version=d.get("schema_version", SCHEMA_VERSION),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ─────────────────────────────────────────────────────────────────────────────
# 값 검증 — 구조 통과 후 "값이 계약을 지키는가"를 전부 모아 검사
# ─────────────────────────────────────────────────────────────────────────────


def _check_rate(value: Any, path: str, problems: list[str]) -> None:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        problems.append(f"{path}: 0~1 실수여야 하는데 {type(value).__name__} 임")
    elif not (0.0 <= float(value) <= 1.0):
        problems.append(f"{path}: 0~1 범위를 벗어남 ({value})")


def validate_brief(brief: Brief) -> list[str]:
    """계약 위반을 전부 모아 문자열 목록으로 반환. 빈 리스트면 유효.

    (첫 오류에서 멈추지 않고 모으는 이유: 샘플 작성 시 한 번에 다 고치려고.)
    """
    problems: list[str] = []

    if not brief.id:
        problems.append("id: 비어 있음")
    if not brief.tech_name:
        problems.append("tech_name: 비어 있음")
    if brief.status not in STATUSES:
        problems.append(f"status: {STATUSES} 중 하나여야 함 (받은 값: {brief.status!r})")
    if not brief.one_liner:
        problems.append("one_liner: 비어 있음")

    # metrics
    m = brief.metrics
    for f_name in _RATE_FIELDS:
        _check_rate(getattr(m, f_name), f"metrics.{f_name}", problems)
    if not isinstance(m.source_count, int) or isinstance(m.source_count, bool):
        problems.append(f"metrics.source_count: 정수여야 함 ({m.source_count!r})")
    elif m.source_count < 0:
        problems.append(f"metrics.source_count: 음수 불가 ({m.source_count})")

    # source_count 와 실제 sources 길이 일치(측정 무결성) — 경고 아닌 계약 위반으로 취급
    if isinstance(m.source_count, int) and not isinstance(m.source_count, bool):
        if m.source_count != len(brief.sources):
            problems.append(
                f"metrics.source_count({m.source_count}) != 실제 sources 개수({len(brief.sources)})"
            )

    # sections: 여섯 칸 모두 내용이 있어야(빈 섹션은 '미확인'으로 명시해야지 공백 금지)
    for key, _num, label in SECTION_ORDER:
        text = getattr(brief.sections, key)
        if not isinstance(text, str) or not text.strip():
            problems.append(f"sections.{key}({label}): 비어 있음")

    # reactions
    for i, r in enumerate(brief.reactions):
        if r.sentiment not in SENTIMENTS:
            problems.append(f"reactions[{i}].sentiment: {SENTIMENTS} 중 하나여야 함 ({r.sentiment!r})")

    # judgment
    for jname in ("worth_learning", "maturity", "relevance"):
        item: JudgmentItem = getattr(brief.judgment, jname)
        if item.level not in JUDGMENT_LEVELS:
            problems.append(
                f"judgment.{jname}.level: {JUDGMENT_LEVELS} 중 하나여야 함 ({item.level!r})"
            )

    # sources
    seen_sids: set[str] = set()
    for i, s in enumerate(brief.sources):
        if s.grade not in SOURCE_GRADES:
            problems.append(f"sources[{i}].grade: {SOURCE_GRADES} 중 하나여야 함 ({s.grade!r})")
        if not s.sid:
            problems.append(f"sources[{i}].sid: 비어 있음")
        elif s.sid in seen_sids:
            problems.append(f"sources[{i}].sid: 중복된 sid ({s.sid})")
        else:
            seen_sids.add(s.sid)

    # unverified 의 conflicting_sids 가 실제 존재하는 출처를 가리키는가
    for i, u in enumerate(brief.unverified):
        for sid in u.conflicting_sids:
            if sid not in seen_sids:
                problems.append(f"unverified[{i}].conflicting_sids: 존재하지 않는 출처 {sid}")

    return problems


# ─────────────────────────────────────────────────────────────────────────────
# 로딩 — 파일/폴더에서 브리핑을 읽어 검증까지
# ─────────────────────────────────────────────────────────────────────────────

# 이 파일: src/tll/schema.py → 레포 루트는 parents[2]
_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BRIEFS_DIR = _REPO_ROOT / "data" / "briefs"


def parse_brief(data: dict[str, Any], *, strict: bool = True) -> Brief:
    """dict → Brief. strict 면 값 검증까지 하고 위반 시 SchemaError."""
    brief = Brief.from_dict(data)
    if strict:
        problems = validate_brief(brief)
        if problems:
            joined = "\n  - ".join(problems)
            raise SchemaError(f"브리핑 계약 위반 {len(problems)}건:\n  - {joined}")
    return brief


def load_brief(path: str | Path, *, strict: bool = True) -> Brief:
    """JSON 파일 1개 → 검증된 Brief."""
    path = Path(path)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise SchemaError(f"{path.name}: JSON 파싱 실패 — {e}") from e
    try:
        return parse_brief(raw, strict=strict)
    except SchemaError as e:
        # 어느 파일에서 났는지 파일명을 앞에 붙여 다시 던진다.
        raise SchemaError(f"[{path.name}] {e}") from e


def load_all_briefs(
    briefs_dir: str | Path | None = None, *, strict: bool = True
) -> list[Brief]:
    """폴더의 모든 *.json 을 읽어 Brief 목록으로. (.gitkeep 등 비-json 은 무시)

    파일명 오름차순 정렬 → 목록 화면 순서가 결정론적.
    """
    d = Path(briefs_dir) if briefs_dir is not None else DEFAULT_BRIEFS_DIR
    briefs: list[Brief] = []
    for p in sorted(d.glob("*.json")):
        briefs.append(load_brief(p, strict=strict))
    return briefs
