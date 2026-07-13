"""개념 레지스트리 — 표준 개념명+별칭을 관리하고, 제안된 이름을 '결정론'으로 중복 해소한다.

신뢰 설계: 포스트→개념 '추출'은 LLM 몫이지만, 그 결과를 기존 개념에 '붙이는' 판단은
여기서 결정론(정규화+별칭 매칭)으로 한다. 매칭 실패 시에만 신규 개념을 'provisional'로 만든다.
→ 새 LLM 판단 지점을 좁히고, 모든 병합이 규칙으로 설명·감사 가능하다.

한계(정직): 짧은 기호명은 과합침 위험이 있어 +,# 는 보존한다(C++/C# 구분). 그래도 완벽친 않다.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from tll.concepts.models import Concept

DEFAULT_REGISTRY = "data/memory/concepts_registry.json"

logger = logging.getLogger(__name__)

_NORM_RE = re.compile(r"[^0-9a-z가-힣+#]+")   # 영숫자·한글·+·# 유지(한글 개념 중복해소)
_SLUG_RE = re.compile(r"[^0-9a-z가-힣]+")     # cid: 영숫자·한글, 나머진 하이픈


def normalize(name: str) -> str:
    """매칭용 키 — 소문자, 공백/기호 제거(+,# 보존). 'Lang-Chain'/'lang chain'/'LangChain' → 'langchain'."""
    return _NORM_RE.sub("", (name or "").lower())


def slugify(name: str) -> str:
    """cid 슬러그 — 'Model Context Protocol' → 'model-context-protocol'."""
    return _SLUG_RE.sub("-", (name or "").lower()).strip("-") or "concept"


@dataclass
class ResolveResult:
    cid: str | None    # 매칭된 개념 id (없으면 None)
    canonical: str     # 매칭된 표준명 또는 입력 그대로
    matched: bool      # 기존 개념에 붙었나


class ConceptRegistry:
    """표준명/별칭 → 개념 매핑. 결정론 정규화로 중복을 합친다."""

    def __init__(self, concepts: dict[str, Concept] | None = None):
        self._by_cid: dict[str, Concept] = dict(concepts or {})
        self._alias_index: dict[str, str] = {}   # normalize(surface) -> cid
        for c in self._by_cid.values():
            self._index(c)

    def _index(self, c: Concept) -> None:
        for surface in [c.canonical, *c.aliases]:
            key = normalize(surface)
            if key:
                self._alias_index[key] = c.cid

    def resolve(self, name: str) -> ResolveResult:
        """기존 개념에 매칭만 시도(생성 없음)."""
        cid = self._alias_index.get(normalize(name))
        if cid:
            return ResolveResult(cid=cid, canonical=self._by_cid[cid].canonical, matched=True)
        return ResolveResult(cid=None, canonical=(name or "").strip(), matched=False)

    def add(self, canonical: str, *, aliases=None, category="", status="confirmed", now=None, created_at: str = "") -> str:
        """개념 추가/병합. 이미 아는 표기면 그 개념에 별칭만 보태고 기존 cid 반환(중복 방지)."""
        aliases = list(aliases or [])
        for surface in [canonical, *aliases]:
            cid = self._alias_index.get(normalize(surface))
            if cid:
                self._merge_aliases(cid, [canonical, *aliases])
                if created_at:
                    ex = self._by_cid[cid]
                    if not ex.created_at or created_at < ex.created_at:
                        ex.created_at = created_at
                return cid
        cid = self._unique_cid(slugify(canonical))
        _now = now or datetime.now(timezone.utc)
        ts = (_now.date() if isinstance(_now, datetime) else _now).isoformat()
        c = Concept(
            cid=cid, canonical=(canonical or "").strip(),
            aliases=[a.strip() for a in aliases if a and a.strip()],
            category=category, first_seen=ts, created_at=created_at, status=status,
        )
        self._by_cid[cid] = c
        self._index(c)
        return cid

    def resolve_or_add(self, name: str, *, category="", now=None) -> ResolveResult:
        """매칭되면 기존, 아니면 provisional 신규 생성(재등장해야 confirmed 로 승격)."""
        r = self.resolve(name)
        if r.matched:
            return r
        cid = self.add(name, category=category, status="provisional", now=now)
        return ResolveResult(cid=cid, canonical=self._by_cid[cid].canonical, matched=False)

    def set_status(self, cid: str, status: str) -> None:
        if cid in self._by_cid:
            self._by_cid[cid].status = status

    def _merge_aliases(self, cid: str, surfaces) -> None:
        c = self._by_cid[cid]
        known = {normalize(s) for s in [c.canonical, *c.aliases]}
        for s in surfaces:
            s = (s or "").strip()
            k = normalize(s)
            if s and k and k not in known:
                c.aliases.append(s)
                known.add(k)
                self._alias_index[k] = cid

    def _unique_cid(self, base: str) -> str:
        cid, n = base, 2
        while cid in self._by_cid:
            cid = f"{base}-{n}"
            n += 1
        return cid

    def get(self, cid: str):
        return self._by_cid.get(cid)

    def all(self):
        return list(self._by_cid.values())

    def __len__(self):
        return len(self._by_cid)

    @classmethod
    def _from_data(cls, data) -> "ConceptRegistry":
        if not isinstance(data, dict):
            raise ValueError("dict 아님")
        return cls({cid: Concept.from_dict(d) for cid, d in data.items() if isinstance(d, dict)})

    @classmethod
    def load(cls, path: str = DEFAULT_REGISTRY) -> "ConceptRegistry":
        """손상 시 '빈 것'으로 덮지 않는다 — 부분 살바지 → .bak 복구 순으로 최대한 살린다."""
        if not os.path.exists(path):
            return cls()
        try:
            with open(path, encoding="utf-8") as f:
                return cls._from_data(json.load(f))
        except (json.JSONDecodeError, OSError, ValueError) as e:
            logger.warning("레지스트리 손상(%s) — 복구 시도: %s", e, path)
        # 1) 부분 살바지: 마지막 완전 항목까지만 살려서 파싱
        try:
            txt = open(path, encoding="utf-8", errors="replace").read()
            idx = txt.rfind("  },")
            if idx != -1:
                reg = cls._from_data(json.loads(txt[:idx] + "  }\n}\n"))
                if len(reg):
                    logger.warning("레지스트리 부분 복구: %d개 살림", len(reg))
                    return reg
        except Exception:  # noqa: BLE001
            pass
        # 2) 백업(.bak)에서 복구
        bak = f"{path}.bak"
        if os.path.exists(bak):
            try:
                with open(bak, encoding="utf-8") as f:
                    reg = cls._from_data(json.load(f))
                logger.warning("레지스트리 .bak 에서 복구: %d개", len(reg))
                return reg
            except Exception:  # noqa: BLE001
                pass
        # 3) 다 실패 — 손상본 보존(덮어쓰기 방지) 후 빈 것
        try:
            os.replace(path, f"{path}.corrupt")
        except OSError:
            pass
        logger.error("레지스트리 복구 실패 — 손상본 %s.corrupt 보존, 빈 레지스트리 시작", path)
        return cls()

    def save(self, path: str = DEFAULT_REGISTRY) -> str:
        """원자적 저장. 임시파일명은 프로세스마다 고유(pid+uuid) — 두 프로세스(예: Streamlit
        백그라운드 자동수집 + 수동 CLI 실행)가 동시에 저장해도 같은 임시파일을 공유하지 않으므로
        os.replace() 의 원자성이 그대로 보장된다. 결과는 항상 둘 중 하나의 '완전한' 내용이지,
        섞여서 깨지는 중간상태는 구조적으로 불가능하다(레지스트리 손상 재발 방지, 근본 수정).

        Windows 한정 추가 방어: 두 프로세스가 '같은 목적지'로 거의 동시에 os.replace() 하면
        (임시파일은 달라도) OS 가 순간적으로 WinError 5(액세스 거부) 를 낼 수 있다(POSIX 와 다른 동작,
        테스트로 실측). 이건 아주 짧은 충돌이라 데이터 문제가 아니라 타이밍 문제 — 잠깐 재시도하면 풀린다."""
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        if os.path.exists(path):   # 직전본을 .bak 로(로드 실패 시 복구용)
            try:
                import shutil
                shutil.copy2(path, f"{path}.bak")
            except OSError:
                pass
        tmp = f"{path}.tmp.{os.getpid()}.{uuid.uuid4().hex[:8]}"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({c.cid: c.to_dict() for c in self._by_cid.values()}, f, ensure_ascii=False, indent=2)
        last_err: OSError | None = None
        for attempt in range(5):
            try:
                os.replace(tmp, path)   # 원자적 — 고유 임시파일이라 내용은 절대 안 섞임
                return path
            except OSError as e:   # WinError 5 등 순간 충돌 — 데이터 손상 아님, 짧게 재시도
                last_err = e
                time.sleep(0.05 * (attempt + 1))
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise last_err
