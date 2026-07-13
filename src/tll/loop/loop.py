"""Loop — ReAct 루프 + 30분 스케줄러. 전체 조각을 감싸 자율 사이클로 돌린다.

run_cycle: 한 사이클(관찰→판단→행동). 후보별 Track→Read, Reader 결정에 따라
  충분(proceed) → Author(+Memory 대조)→Fact-Check→Memory 기억→저장 / 부족(collect_more) → lesson→다음.
안전장치: target(발행 예산)·max_attempts(시도 상한=비용캡)·무진전 가드.
프로바이더: provider_name(gemini/anthropic) 선택 → TrackingProvider로 감싸 호출마다 토큰 로깅(관리>비용).
화면은 Streamlit 통합 앱(src/tll/manage/app.py) 하나 — 교과서 + 관리·비용. (data/dashboard.html 은 선택적 자동 export.)
run_forever: interval_minutes(기본 30)마다, only_new=True('새 것만').
테스트/재현: candidates·llm_call·fetcher·rate_limiter·robots_guard·paths 주입 → 완전 오프라인.
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime

from tll.author.author import write_textbook
from tll.cost.usage import DEFAULT_USAGE_PATH, TrackingProvider
from tll.factcheck.crosscheck import cross_verify, revise_textbook
from tll.factcheck.factcheck import apply, check_textbook
from tll.loop.models import CycleResult
from tll.memory.memory import (
    DEFAULT_KB,
    DEFAULT_LESSONS,
    contrast_context,
    record_lesson,
    remember_textbook,
)
from tll.present.html import save_dashboard
from tll.present.store import DEFAULT_DIR, load_records, save_textbook
from tll.reader.reader import read
from tll.scout.scout import DEFAULT_STORE, scout
from tll.shared.llm import get_provider
from tll.shared.llm.select import provider_label, resolve_model_name, resolve_provider_name
from tll.tracker.tracker import track
from tll.triage.triage import triage
from tll.concepts.categorize import recategorize
from tll.concepts.registry import DEFAULT_REGISTRY, ConceptRegistry
from tll.rank.board import build_board
from tll.signals.github import default_github_fetcher
from tll.signals.arxiv import refresh_research
from tll.signals.discover import refresh_discovered
from tll.signals.ingest import ingest_candidate
from tll.signals.store import DEFAULT_SIGNALS

logger = logging.getLogger(__name__)


def run_cycle(
    *,
    target: int = 3,
    max_attempts: int = 6,
    top_n: int = 5,
    only_new: bool = False,
    provider_name: str | None = None,
    model_name: str | None = None,
    scout_sources=None,
    seen_path: str | None = None,
    kb_path: str | None = None,
    lessons_path: str | None = None,
    textbook_dir: str | None = None,
    usage_path: str | None = None,
    dashboard_path: str = "data/dashboard.html",
    registry_path: str | None = None,
    signals_path: str | None = None,
    github_fetcher=None,
    llm_call=None,
    fetcher=None,
    rate_limiter=None,
    robots_guard=None,
    candidates=None,
    now: datetime | None = None,
) -> CycleResult:
    """한 사이클 실행. 관찰→판단→행동, 안전장치 안에서."""
    kb_path = kb_path or DEFAULT_KB
    lessons_path = lessons_path or DEFAULT_LESSONS
    textbook_dir = textbook_dir or DEFAULT_DIR
    seen_path = seen_path or DEFAULT_STORE
    usage_path = usage_path or DEFAULT_USAGE_PATH
    registry_path = registry_path or DEFAULT_REGISTRY
    signals_path = signals_path or DEFAULT_SIGNALS

    # 모델 선택 + 사용량 추적 래핑. llm_call 주입 시(테스트)엔 실제 생성/추적 생략.
    prov_name = resolve_provider_name(provider_name)
    model = resolve_model_name(model_name)
    prov = (
        TrackingProvider(get_provider(prov_name), provider_name=prov_name, path=usage_path)
        if llm_call is None
        else None
    )

    # 개념 레지스트리 + 신호 기록 준비 (v4 concept-centric 랭킹)
    registry = ConceptRegistry.load(registry_path)
    if llm_call is not None:
        concept_call = llm_call
    elif prov is not None:
        concept_call = lambda pr, sy: prov.generate(pr, system=sy, max_tokens=64, model=model).text  # noqa: E731
    else:
        concept_call = None
    gh_fetch = github_fetcher
    if gh_fetch is None and llm_call is None:
        gh_fetch = default_github_fetcher

    # 교차검증 모델 — 집필과 '다른' 프로바이더로 독립 채점(둘 다 .env 키 있을 때). 없으면 결정론 검증만.
    verifier_call = None
    verifier_label = ""
    if llm_call is None:
        _other = "anthropic" if prov_name == "gemini" else "gemini"
        try:
            from tll.shared.config import has_key
            if has_key("ANTHROPIC_API_KEY" if _other == "anthropic" else "GEMINI_API_KEY"):
                # 검증·재집필은 최고가(Opus) 대신 저렴한 모델로 기본 설정(비용↓). TLL_VERIFIER_MODEL 로 덮어쓰기 가능.
                _vmodel = os.environ.get("TLL_VERIFIER_MODEL") or ("claude-sonnet-5" if _other == "anthropic" else None)
                _vprov = TrackingProvider(get_provider(_other), provider_name=_other, path=usage_path)
                verifier_call = lambda pr, sy: _vprov.generate(pr, system=sy, max_tokens=1500, model=_vmodel).text  # noqa: E731
                verifier_label = provider_label(_other)
        except Exception as e:  # noqa: BLE001
            logger.warning("교차검증 모델 준비 실패(%s) — 결정론 검증만", e)
    # 교차검증 모드: verify(기본·저렴, Claude 검증만) | full(+재집필, 비쌈) | off. .env 의 TLL_CROSSCHECK.
    _xmode = os.environ.get("TLL_CROSSCHECK", "verify").lower()

    # GitHub 자동 발견: 개발자들이 많이 쓰는 AI/LLM 저장소를 캐와 개념·채택 신호로 (손목록 없음)
    if llm_call is None:  # 라이브에서만 네트워크
        repo_by_name: dict[str, str] = {}
        try:
            from tll.signals.discover import discover_repos
            repos = discover_repos(fetcher=default_github_fetcher)
            refresh_discovered(registry, repos=repos, signals_path=signals_path, now=now)
            repo_by_name = {r["name"]: r.get("full_name", "") for r in repos}
        except Exception as e:  # noqa: BLE001
            logger.warning("GitHub 자동 발견 실패: %s", e)
        # 모든 개념에 최소 '설명서'(README 근거) — '코끼리인데 설명 없음' 방지. 새 개념만·한 사이클 6개까지(비용).
        try:
            import urllib.request

            from tll.author.manuals import backfill_manuals
            from tll.signals.github import github_readme

            def _text_fetch(url: str) -> str:
                req = urllib.request.Request(url, headers={"User-Agent": "TLL"})
                with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310
                    return resp.read().decode("utf-8", "replace")

            def _source_for(c):
                fn = repo_by_name.get(c.canonical, "")
                return (github_readme(fn, _text_fetch), f"https://github.com/{fn}") if fn else ("", "")

            manual_call = lambda pr, sy: prov.generate(pr, system=sy, max_tokens=700, model=model).text  # noqa: E731
            made = backfill_manuals(registry, records_dir=textbook_dir, source_for=_source_for,
                                    llm_call=manual_call, provider=prov_name, limit=6)
            if made:
                logger.info("설명서 %d개 생성: %s", len(made), ", ".join(made))
        except Exception as e:  # noqa: BLE001
            logger.warning("설명서 백필 실패: %s", e)

    # 1) 후보 (Scout)
    if candidates is None:
        res = scout(sources=scout_sources, store_path=seen_path, now=now)
        cands = res.new_candidates if only_new else res.candidates
        cand_total = res.summary["polled"]
    else:
        cands = list(candidates)
        cand_total = len(cands)

    # 기법 발견: scout 제목에서 뜨는 용어(하네스·RAG 등 repo 없는 개념)를 잡아 개념화 → 바로 arXiv 로 측정.
    if llm_call is None:
        try:
            from tll.signals.terms import refresh_terms
            n_terms = refresh_terms(registry, titles=[getattr(c, "title", "") for c in cands],
                                    signals_path=signals_path, now=now, min_count=2)
            if n_terms:
                logger.info("기법 용어 %d개 발견", n_terms)
        except Exception as e:  # noqa: BLE001
            logger.warning("기법 발견 실패: %s", e)
        try:
            refresh_research(registry, signals_path=signals_path, now=now)  # 기법(발견분 포함)을 논문으로 잼(후행·고품질)
        except Exception as e:  # noqa: BLE001
            logger.warning("arXiv 연구 신호 실패: %s", e)
        try:
            from tll.signals.youtube import refresh_youtube
            refresh_youtube(registry, signals_path=signals_path, now=now)  # '대두' = 최근 유튜브 영상 수(주목·독립소스)
        except Exception as e:  # noqa: BLE001
            logger.warning("YouTube 신호 실패: %s", e)
        try:
            from tll.signals.discover import resolve_adoption
            n_res = resolve_adoption(registry, signals_path=signals_path, now=now)  # 버즈만·채택0 개념(Node.js 등) 구제
            if n_res:
                logger.info("미측정 개념 채택 구제 %d개", n_res)
        except Exception as e:  # noqa: BLE001
            logger.warning("채택 구제 실패: %s", e)

    # 2) Triage (에이전트)
    tr = triage(cands, top_n=top_n, provider=prov, model=model, llm_call=llm_call)
    selected = tr.selected
    cat_by_cid = {d.cid: d.category for d in tr.decisions}

    published: list[dict] = []
    lessons_out: list[dict] = []
    decisions: list[dict] = []
    attempts = 0

    for cand in selected:
        if attempts >= max_attempts or len(published) >= target:
            break
        attempts += 1

        tk = track([cand], fetcher=fetcher, rate_limiter=rate_limiter, robots_guard=robots_guard, now=now)
        doc = tk.docs[0]

        # 개념 resolve + 주목/채택 신호 로깅 (발행 여부와 무관하게 축적)
        concept_cid = ""
        try:
            concept_cid = ingest_candidate(
                cand, registry=registry, doc_url=getattr(doc, "url", "") or "",
                category=cat_by_cid.get(cand.cid, ""), llm_call=concept_call,
                github_fetcher=gh_fetch, signals_path=signals_path, now=now,
            )
        except Exception as e:  # noqa: BLE001 — 신호 기록 실패가 사이클을 죽이지 않게
            logger.warning("ingest 실패(%s): %s", getattr(cand, "title", "?"), e)
        verdict = read([doc], provider=prov, model=model, llm_call=llm_call).verdicts[0]
        decisions.append({"topic": cand.title, "next_action": verdict.next_action, "mode": verdict.mode})

        if verdict.sufficient and doc.status == "ok":
            hint = contrast_context(cand.title, kb_path=kb_path)
            book = write_textbook(doc, contrast_hint=hint, provider=prov, model=model, llm_call=llm_call)  # ① Gemini 집필
            cross = None
            if verifier_call is not None and _xmode != "off":
                try:
                    cross = cross_verify(cand.title, doc.body_text or "", book.sections,
                                         verifier_call=verifier_call, model_label=verifier_label)  # ② Claude 검증(저렴)
                    if _xmode == "full":  # ③ Claude 재집필(옵션 — TLL_CROSSCHECK=full)
                        rev = revise_textbook(cand.title, doc.body_text or "", book.sections, cross,
                                              reviser_call=verifier_call)
                        if rev:
                            import dataclasses
                            book = dataclasses.replace(book, one_liner=(rev["one_liner"] or book.one_liner),
                                                       sections=rev["sections"])
                except Exception as e:  # noqa: BLE001
                    logger.warning("교차검증/재집필 실패(%s): %s", cand.title, e)
            report = check_textbook(book)          # ④ 결정론 검증(최종본)
            verified = apply(book, report)
            remember_textbook(verified, category=cat_by_cid.get(cand.cid, ""), kb_path=kb_path, now=now)
            _cobj = registry.get(concept_cid) if concept_cid else None
            _metrics = dict(report.metrics)
            if cross is not None:
                _metrics["cross_check"] = cross
                _metrics["authored_by"] = f"{provider_label(prov_name)} 집필→{verifier_label} 검증·재집필"
            save_textbook(
                verified, metrics=_metrics, provider=prov_name, out_dir=textbook_dir, now=now,
                concept_cid=concept_cid, concept_name=(_cobj.canonical if _cobj else ""),
            )
            published.append(
                {"topic": cand.title, "support_rate": report.metrics.get("support_rate", 0.0), "status": verified.status}
            )
        else:
            reason = verdict.missing or verdict.reason or doc.status
            record_lesson(cand.title, "insufficient", reason, log_path=lessons_path, now=now)
            lessons_out.append({"topic": cand.title, "reason": reason})

    recategorize(registry)   # 기능 카테고리 고정 + 범위 밖 박제(결정론) — 저장 전에 통일
    registry.save(registry_path)
    board = build_board(registry=registry, signals_path=signals_path, now=now or datetime.now())
    tier_counts: dict[str, int] = {}
    for row in board:
        tier_counts[row.tier.tier] = tier_counts.get(row.tier.tier, 0) + 1

    # 5) (선택) HTML 자동 export — 주 화면은 Streamlit 통합 앱.
    save_dashboard(load_records(textbook_dir), dashboard_path, current_provider=prov_name)

    summary = {
        "provider": prov_name,
        "candidates": cand_total,
        "selected": len(selected),
        "attempts": attempts,
        "published": len(published),
        "lessons": len(lessons_out),
        "target_reached": len(published) >= target,
        "no_progress": attempts > 0 and len(published) == 0,
        "concepts": len(board),
        "tiers": tier_counts,
    }
    return CycleResult(published=published, lessons=lessons_out, decisions=decisions, summary=summary)


def run_forever(*, interval_minutes: int = 30, max_cycles: int | None = None, **cycle_kwargs) -> None:
    """interval_minutes 마다 run_cycle. only_new=True(새 것만). Ctrl-C 로 중단."""
    n = 0
    cycle_kwargs.pop("only_new", None)   # run_forever 는 항상 새 것만(only_new=True) — 중복 인자 방지
    while True:
        try:
            res = run_cycle(only_new=True, **cycle_kwargs)
            s = res.summary
            print(
                f"[cycle {n + 1}] 모델 {provider_label(s['provider'])} · 후보 {s['candidates']} · "
                f"선별 {s['selected']} · 발행 {s['published']} · 더찾자 {s['lessons']}"
            )
        except Exception as e:
            logger.warning("cycle 실패: %s", e)
            print(f"[cycle {n + 1}] 실패: {e}")
        n += 1
        if max_cycles is not None and n >= max_cycles:
            break
        time.sleep(interval_minutes * 60)


def _run_cli() -> None:  # python -m tll.loop.loop [--provider gemini|anthropic] [--watch]
    import sys

    from tll.rank.tier import TIERS

    try:  # cp949 콘솔에서도 이모지 출력이 안 죽게(발행 요약 print 크래시 방지)
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

    argv = sys.argv[1:]
    prov_arg = None
    if "--provider" in argv:
        i = argv.index("--provider")
        if i + 1 < len(argv):
            prov_arg = argv[i + 1]
    prov_name = resolve_provider_name(prov_arg)
    try:
        from tll.shared.llm import available_providers

        avail = available_providers()
    except Exception as e:  # noqa: BLE001
        avail = f"(확인 실패: {e})"
    print(f"모델: {provider_label(prov_name)} 선택됨 · 사용가능: {avail}")
    print("전환: --provider anthropic | --provider gemini | .env 의 TLL_PROVIDER")

    if "--watch" in argv:
        print("30분마다 자동 반복 시작 (Ctrl-C 로 중단)")
        run_forever(interval_minutes=30, target=3, provider_name=prov_name)
        return

    res = run_cycle(only_new=False, target=3, provider_name=prov_name)
    s = res.summary
    print(
        f"[1 사이클] 후보 {s['candidates']} · 선별 {s['selected']} · 시도 {s['attempts']} · "
        f"발행 {s['published']} · 더찾자 {s['lessons']}"
    )
    for p in res.published:
        print(f"  ✅ {p['topic']} — 충실도 {int(p['support_rate'] * 100)}% ({p['status']})")
    for les in res.lessons:
        print(f"  🔁 {les['topic']} — 더 찾자 ({les['reason'][:40]})")
    tiers = s.get("tiers", {})
    badge = " ".join(f"{TIERS[k][0]}{v}" for k, v in tiers.items() if v)
    print(f"  기술 티어({s['concepts']}개): {badge}")
    print("화면 (교과서 + 관리·비용) 한 곳: streamlit run src/tll/manage/app.py")
    print(f"현재 모델 {provider_label(prov_name)} · 자동 30분: python -m tll.loop.loop --watch · 모델 전환: --provider anthropic")


if __name__ == "__main__":
    _run_cli()
