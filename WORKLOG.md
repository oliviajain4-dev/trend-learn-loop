# WORKLOG — TLL 구현 작업일지

> 시간순, 솔직하게. "무엇을 시도 / 뭐가 막힘 / 어떻게 뚫음 / 다음은".
> 완벽히 다듬지 않는다. 과정 자체가 과제 증거물.

---

## 2026-07-10 — Phase 1 착수 전 정리 + (1)단계: 데이터 계약 + 뼈대

### 환경 정리 (착수 전)
- git 상태가 꼬여 있었음:
  - `.git/index.lock` 찌꺼기(stale lock)가 남아 git 쓰기 명령이 전부 막혀 있었음 → 실행 중 git 프로세스 없음을 확인하고 lock 파일만 삭제해서 복구.
  - 첫 커밋 전엔 브랜치가 "unborn"(실체 없음)이라 `main`이 안 보였던 것. 초기 커밋(`3fe4b26`)으로 `main` 확정.
- 작업 브랜치를 요구대로 `ny` 하나로 통일: `git branch -m feat/ny ny`.
- `.env` 키 이름 표준화: `YouTube_Data_API_KEY` → `YOUTUBE_API_KEY`
  (값은 노출 안 하고 `sed` 로 키명만 치환). `.env` 는 `.gitignore` 로 이미 제외됨(재확인 OK).

### (1)단계 — requirements + 폴더 뼈대 + schema.py (데이터 계약)
- **왜 이 순서**: 데이터 계약(스키마)을 먼저 못 박아야, 이후 샘플 JSON·목록·상세 화면이
  전부 같은 형식을 공유한다. 나중에 진짜 파이프라인도 이 계약에 JSON 을 쌓기만 하면 됨.
- **requirements.txt**: streamlit / plotly / python-dotenv / ruff. "무거운 프레임워크 금지" 원칙에 맞춰 최소만.
- **폴더 뼈대**: `src/tll/{__init__.py, schema.py}`, `src/tll/dashboard/__init__.py`,
  `data/briefs/.gitkeep`.
- **schema.py 결정**: pydantic 대신 **stdlib dataclass + 명시적 검증** 선택.
  이유 = 프로젝트 DNA(결정론·투명·매직 없음). 검증 규칙이 코드에 그대로 드러나고,
  같은 입력 → 같은 판정(재현성). 추가 의존성도 없음.
  - `status` (sample/draft/verified) 를 계약에 넣어 화면 배지의 근거로 삼음.
  - metrics 의 4개 지지율/정밀도/재현율은 **0~1 실수 강제**, source_count 는 실제 sources 개수와 일치 강제(측정 무결성).
  - `validate_brief()` 는 첫 오류에서 멈추지 않고 위반을 전부 모아 반환(샘플 작성 편의).
  - `load_all_briefs()` 가 `data/briefs/*.json` 을 파일명순으로 읽음 → 목록 순서 결정론적.

### 검증 방법
- (예정) `.venv` 에 requirements 설치 → `python -c "import tll.schema"` 로 임포트 확인
  + 최소 브리핑 dict 를 `parse_brief` 에 통과시켜 검증 로직이 도는지 확인.

### 다음
- (2)단계: 샘플 브리핑 JSON 2~3건(RAG, MCP 등) 작성 → 계약대로 검증 통과시키기.

---

## 2026-07-10 — [2단계] 샘플 브리핑 3건 (커밋 40c9768)
- RAG·MCP·벡터DB 3건을 `data/briefs/`에 작성. 전부 `status="sample"`.
- 결정: 미디어는 빈 배열(링크·조회수는 나중에 YouTube API 실데이터만), 2차자료 URL은 `example.com`으로 자리표시+등급3. metrics는 일부러 편차(RAG 94%/MCP 81%)를 줘 게이지 표현 확인용.
- 각 건에 `unverified`(미확인) 1건씩 심음(정직 원칙 데모).
- **검증**: 눈으로만 보지 않고 1단계 검증기 `load_all_briefs`에 통과시킴 → source_count=실제 출처수 일치 등 계약 만족.

## 2026-07-10 — [3단계] 목록 화면 + 진입점 (커밋 c5d97df)
- `render.py`(카드 그리드·상태 배지·충실도 색상 공용 헬퍼) + `app.py`(로드·라우팅) + `.streamlit/config.toml`.
- **막힘→뚫음**: 헤드리스 부팅 로그에서 Streamlit이 External URL(공인 IP)까지 바인딩하는 걸 발견 → "내 PC 전용 로컬" 요구에 맞춰 config로 `address="localhost"` 고정.
- **검증**: ruff(미사용 import 1건 잡아 수정) → 헤드리스 부팅 `/_stcore/health` HTTP 200.

## 2026-07-10 — [4단계] 상세 화면 (커밋 대기)
- `render_detail` 본체 구현: 측정지표 4게이지(plotly) + 샘플 경고배너 + §3 0~9 섹션 + 출처표(st.dataframe LinkColumn) + ⚠️미확인.
- **막힘→뚫음**: "임포트 OK"만으론 렌더 런타임 오류를 못 잡음 → **Streamlit AppTest**로 목록+상세 3건을 브라우저 없이 실제 렌더해 예외 0 확인. 그 과정에서 `use_container_width` 지원종료 경고 발견 → `width="stretch"`로 전량 교체(ERRORS #2).
- **검증**: ruff 통과 + AppTest 4화면(목록+상세3) 예외 없음 + 핵심 섹션 존재 단언 통과.

### 다음
- [5단계]: `streamlit run`으로 실제 실행 → 스크린샷으로 시각 확인.

## 2026-07-10 — [5단계] 실제 실행 & 시각 확인 (Phase 1 대시보드 MVP 완료)
- `streamlit run src/tll/dashboard/app.py --server.headless true` 로 실제 구동.
- **로컬 전용 바인딩 실측**: 이전 헤드리스 실행 땐 로그에 External/Network URL(공인 IP)이
  떴으나, config 적용 후엔 `Uvicorn server started on localhost:8501` / `URL: http://localhost:8501`
  만 남음 → 외부 노출 없음 확인.
- **가동 검증**: `/_stcore/health` 200, 메인 200, 로그에 에러/트레이스백 없음.
- 시각 확인 방식은 사용자 선택으로 **직접 브라우저 확인**(Playwright 미설치, 추가 의존성 0).
- 실행법(재현):
  ```
  .\.venv\Scripts\Activate.ps1
  streamlit run src/tll/dashboard/app.py   # → http://localhost:8501
  ```

### Phase 1 대시보드 정리
- 데이터 계약(schema) → 샘플 3건 → 목록 → 상세 → 실행까지 end-to-end 동작.
- 다음 큰 흐름(로드맵): 진짜 파이프라인(Collector·Analyst·Verifier·Metrics)이 같은
  `data/briefs/*.json` 계약에 실데이터를 쌓으면 이 대시보드가 그대로 실측값을 보여줌.

---

## 2026-07-10 — [Phase 2 착수] 해커뉴스 실데이터 트렌드 피드
- 사용자 요청: (1)`ny` 원격 푸시 (2)실행 앱 종료 (3)Phase 2 착수 + "이 해커뉴스 같은 사이트 자체도 있었으면".
  → 셋째 요청이 Phase 2의 자연스러운 첫 결과물(핸드오프 §2: HN 공식 API=무키 소스).
- **`ny` origin 푸시 완료**(안전점검: 추적되는 비밀키 없음 확인 후).
- **HN 트렌드 피드** `src/tll/collector/trends.py` (패키지명은 `collector` 단수로 통일):
  - 공식 API(hacker-news.firebaseio.com, 무키)에서 topstories + item 병렬 수집.
  - `HNStory`(점수·댓글·url·도메인·HN토론링크), `HNFeed`(+수집시각 provenance).
  - **원칙 준수**: 점수·댓글수·URL은 API 원본만, 제목도 원문(영어) 그대로 — 번역해 지어내지 않음.
    (캡처의 한글은 브라우저 자동번역이었음. 실데이터와 대조해 확인: GLM 5.2/Chat Control/GPT-5.6 일치)
- **대시보드 연결**: 사이드바 radio 로 '정체 브리핑 ↔ 트렌드·해커뉴스' 전환. `_load_hn` 5분 캐시(API 예의).
  네트워크 실패는 숨기지 않고 화면에 노출.
- **검증**: HN 수집기 실호출(상위 5건 실데이터 확인) → ruff 통과 → AppTest 로 두 화면 모두 예외 0,
  피드 항목·점수 표기 존재 단언 통과.
- **재사용성**: 이 트렌드 피드는 대시보드용. 파이프라인 '주제 수집기'는 별도(아래).

---

## 2026-07-10 — [Collector 1단계] 데이터 계약 + 안전장치
- 목표: LLM 없는 순수 결정론 수집기의 토대. 파이프라인이 topic 으로 여러 소스를 모아
  CollectedDoc 로 정규화하고, 나중에 ReAct 루프가 collect(topic, source) 액션으로 호출.
- **models.py**: `CollectedDoc`(source_type/title/org/url/published_at/collected_at/grade/text/content_hash),
  `CollectionResult`(topic/documents/summary), `to_source()`(→ schema.Source 형식),
  `compute_content_hash`(url+title, 중복제거), `grade_from_domain`(1=arxiv 등, 2=공식/기관, 3=블로그).
  - `content_hash` 는 `__post_init__` 에서 자동 채움.
- **rate_limiter.py**: 도메인별 최소간격(기본 1.5s). 다음 허용시각을 락 안에서 예약,
  sleep 은 락 밖 → 스레드 안전. **전역 상태 없음**(호출마다 인스턴스, ReAct 호환).
- **robots_guard.py**: robots.txt Disallow 면 스킵. 실패/없음 → 보수적 허용. 도메인별 캐시.
  UA="TLLCollector/0.1". (HN API 는 이 가드 예외, 예의상 rate limit 만.)
- **검증**(자기검증 스크립트, 실행 원문 남김):
  1) content_hash 결정론(같은 입력 동일/다른 입력 상이)
  2) grade 휴리스틱(arxiv=1/openai=2/blog=3)
  3) **to_source → schema.Source 실제 편입**: sid 만 붙이면 유효한 Source 가 됨(date=published_at 대응)
  4) RateLimiter: 같은 도메인 2번째 0.5s 대기, 다른 도메인 0s(간격 정확)
  5) RobotsGuard 라이브: news.hada.io / news.ycombinator.com allowed=True
  → ruff 통과 + [ALL PASS].
- **다음**: (2단계) HackerNewsProvider — HN Algolia 검색 API 실호출로 진짜 title/url 확인.

---

## 2026-07-10 — [Collector 2단계] HackerNewsProvider (Algolia 검색, 실데이터)
- provider 레지스트리 구조: `providers/base.py`(BaseProvider) + `providers/__init__.py`
  (get_provider/all_providers/provider_names) + `providers/hackernews.py`.
- **막힘→뚫음 (추측 금지의 실증)**: 코드 짜기 전에 Algolia 응답을 먼저 실호출로 열어봄.
  → `query=RAG` 가 **"GameStop Is Rage Against the Financial Machine"** 를 물어옴.
  Algolia 오타허용(fuzzy) 검색이 "RAG"↔"Rage" 를 매칭한 것. 추측했으면 쓰레기 데이터를
  그대로 넣을 뻔. **해결**: 클라이언트에 결정론 관련성 필터(`\btoken\b` 단어경계, 다어절 AND)
  → "RAG" 는 "Rage" 를 거부. (변형/복수형 일부는 놓치지만 fuzzy 오탐보다 낫다는 판단.)
- provider 규칙 준수: robots 는 HN API 라 예외, rate limit 만. 실패해도 빈 리스트(전체 안 죽음).
  points/num_comments 는 API 원본 수치를 '반응 신호'로 text 에 기록(지어내지 않음).
- **검증(실호출 원문 남김)**: topic="RAG" → 6건 전부 진짜 RAG 관련(Production RAG·FastGraphRAG·
  Meta RAG 논문·Ask HN 로컬 RAG…), **Rage 오탐 0**, url·created_at(발행일)·points 원본 채워짐.
  grade 는 도메인 휴리스틱(github.com=2, 개인블로그=3). ruff 통과.
- **다음**: (3단계) GeekNewsProvider — news.hada.io RSS 실호출.

---

## 2026-07-10 — [Collector 3단계] GeekNewsProvider (news.hada.io, 실데이터)
- **막힘→뚫음 (또 추측 금지의 실증)**: "RSS"라고 했지만 실제로 열어보니 **Atom 형식**
  (<feed>/<entry>, <link href=...> 속성, <published>). RSS 2.0(<item>/<pubDate>/<link>텍스트)
  로 짰으면 전부 빗나갔을 것. → stdlib `xml.etree` 로 Atom 파싱(feedparser 등 새 의존성 불필요).
- **robots 확인**: news.hada.io/robots.txt 의 `User-agent: *` 는 `/rss/` 미포함(Allow). 우리
  RobotsGuard 도 allowed=True. RSS 는 API 예외가 아니라 robots_guard 를 실제로 적용.
  (`Content-Signal: ai-train=no` 있으나 우리는 학습이 아니라 링크·제목·날짜를 provenance 로
   기록하는 수집이고, 이 피드는 봇 구독용으로 공개됨.)
- 공통 관련성 필터를 `base.topic_matches()` 로 추출(HN 필터와 동일 규칙 공유).
- 성격 차이 명시: HN 은 검색, GeekNews 는 **최근 피드** → topic 이 최근에 없으면 0건이 정상.
- **검증(실호출 원문)**: 피드 50개 파싱. `search("RAG")`=0건(최근 피드에 없음, 정직).
  실재 단어 `search("미첼")`=1건 → 실제 url(topic?id=31294)·published(2026-07-10) 원본 채워짐.
  grade=2 고정(국내 IT 기관). ruff 통과.
- **다음**: (4단계) engine.collect() — 두 provider 를 돌려 중복제거·다양성·summary, RAG end-to-end.

---

## 2026-07-10 — [Collector 4단계] engine.collect() (end-to-end)
- `collect(topic, sources=None, max_per_source=10, *, save, min_interval, max_total)`.
  provider 선택 → 수집 → content_hash 중복제거 → 소스 round-robin 인터리브(다양성) → summary.
- **설계 판단(중요)**: 한 소스만 결과가 있어도 **가짜 균형을 만들지 않는다**. 좋은 데이터를 버려
  균형 맞추는 대신 summary(per_source_raw/final)에 불균형을 그대로 노출 → ReAct 루프의 관찰이
  되어 "다른 소스 더 돌릴까"(전환점 1)를 모델이 판단하게 한다. (억지 균형 = 데이터 손실)
- 전역 상태 없음: rate_limiter/robots_guard 를 collect() 호출마다 생성해 provider 에 주입.
- `data/collected/<slug>.json` 저장은 디버그용(원자료, 최종 브리핑 아님) → `.gitignore` 추가.
- **검증(실호출 원문 남김)**:
  - `collect("RAG")` → HN 8 / GeekNews 0 (정직), dedup 0, total 8. summary 가 소스별 수를 그대로 노출.
  - sources=["hackernews"] 필터 동작, 미지 provider "nope" 무시, save 로 rag.json 생성(+gitignore 확인).
  - `_interleave` 단위검증: HN3+GN2 → [hn,gn,hn,gn,hn] 정확. `_dedup`: 중복 1건 제거 확인.
  - ruff 통과.
- **다음**: (5단계) provenance 검증 — 수집물의 url·날짜·수집시각이 실제로 차 있고 지어낸 값이 없는지 최종 확인.

---

## 2026-07-10 — [Collector 5단계] provenance 검증 (지어낸 값 없음 증명)
- 방법: 수집 후 **원천 API 를 독립적으로 재호출**해 각 문서의 title/url/수치가 원본에
  실제로 있는지 대조(passthrough 증명). "지어냄 없음"을 눈이 아니라 대조로 확인.
- **결과(실행 원문)**:
  - HN 6건: 제목·url·points·발행일(created_at) 이 재호출 원본과 **완전 일치**.
  - GeekNews 2건(topic="디지털"): 제목·url 이 피드 원본과 일치.
  - 필드 완전성(url=http·grade 1~3) + content_hash 재계산 일치 + collected_at 이 실제로 방금(10분 이내).
- → **[ALL PASS] 수집물 provenance 실재·일치, 지어낸 값 없음.** 링크·날짜·수치는 전부 원본 유래.

## 2026-07-10 — [shared/llm 3-1] 설정 로더 + LLM 추상 인터페이스
- 전체 진도 재정의(분모 7): 1.대시보드 2.Collector ✅ / 3.shared/llm 4.Analyst 5.Verifier 6.Metrics+Harness 7.파이프라인.
- `shared/config.py`: .env 에서만 키 로드(하드코딩 금지). get_key/has_key, 없으면 ConfigError.
- `shared/llm/base.py`: LLMProvider(추상)·LLMResponse·LLMError. temperature 는 선택
  (Opus 4.8 은 temperature 주면 400 이라 각 프로바이더가 알아서 처리).
- 새 의존성(사유): `google-genai`(Gemini 집필 주력), `anthropic`(교차모델 검증). requirements 반영.
- 검증: ruff + base/config 임포트·동작(키 존재·없는키 ConfigError) 통과.
- 다음: (3-2) GeminiProvider 를 실제 1회 호출로 검증.

## 2026-07-10 — [shared/llm 3-2] GeminiProvider (실호출 그린패스)
- google-genai 확정 API: `client.models.generate_content(model, contents, config=GenerateContentConfig(...))`,
  응답 `r.text` / `r.usage_metadata`. Gemini 은 temperature 허용.
- **막힘→뚫음(실측)**: 기본 모델 첫 추측 `gemini-2.5-flash` = 404(이 키에선 호출불가).
  실호출 스윕으로 실제 되는 모델 발견 → **`gemini-flash-lite-latest` 그린패스**(다른 flash 는 429 쿼터). (ERRORS #3)
- APIError(429/404/인증) → LLMError 로 통일. usage(토큰) 수집.
- **검증(실호출 원문)**: 기본값으로 `generate('한국어 한 단어…')` → `'안녕하세요.'`, usage in22/out2. ruff 통과.
- 다음: (3-3) AnthropicProvider — Claude Opus 4.8 실호출(temperature 미전달).

## 2026-07-10 — [shared/llm 3-3] AnthropicProvider (Claude, 키 미발급 확인)
- claude-api 레퍼런스대로: messages.create(model=claude-opus-4-8, max_tokens, system?, messages).
  **temperature 의도적 미전달**(Opus 4.8 은 주면 400). usage 수집, 에러→LLMError.
- **막힘(외부 요인)**: 실호출하니 httpx 가 `UnicodeEncodeError` 로 깊게 크래시.
  진단(값 노출 없이) → .env 의 ANTHROPIC_API_KEY 가 실제 키가 아니라 **한글 자리표시
  "여기에…"**(길이9, 비-ASCII). 핸드오프의 "Claude 키 아직 없음"과 일치.
- **뚫음**: 생성자에 ASCII 가드 추가 → 자리표시면 즉시 명확한 LLMError(원인·해법 안내).
- **검증(실호출)**: ① 자리표시 키 → 깔끔한 LLMError(크래시 아님). ② 가짜 sk-ant(ASCII) 키 →
  생성자 통과, generate() 가 **실제 API 에 도달해 401 을 LLMError 로 표면화**(연동 정상). ruff 통과.
- **미결(정직 고지)**: Claude 성공 생성(그린패스)은 **실제 키 필요** → 사용자가 .env 에
  진짜 ANTHROPIC_API_KEY 넣으면 즉시 동작. 그때까지 파이프라인은 Gemini 로 진행 가능.
- 다음: (3-4) 레지스트리 — 키 있는 프로바이더만 자동 등록, 기본=Gemini.

## 2026-07-10 — [shared/llm 3-4] 레지스트리 (piece 3 완성)
- `get_provider(name=None)`(지연생성·캐시, 기본=Gemini), `available_providers()`(유효키만),
  `default_provider_name()`. 미지/키없음 → LLMError.
- **검증(실호출)**: 기본 Gemini 그린패스('감사합니다.'), available=['gemini'](anthropic 자리표시라 제외),
  anthropic/미지 → LLMError, 캐시(동일 인스턴스) 확인. ruff 통과.
- **piece 3(shared/llm) 완료**: config + LLMProvider 추상 + Gemini(그린) + Anthropic(가드) + 레지스트리.
  → Analyst/Verifier 가 `get_provider()` 로 벤더 무관하게 LLM 사용 가능.
- 다음: piece 4 Analyst — 수집물(CollectedDoc)로 문장별 [S#] 브리핑 초안 집필.

## 2026-07-10 — [piece 4] Analyst 집필기 (수집→[S#] 초안)
- `analyst/writer.py: write_brief(topic, collection) -> Brief(status="draft")`.
- 설계: **sid(S1..Sn)는 코드가 결정론적으로 부여**(LLM 아님). LLM 은 그 출처만 근거로
  §3 섹션·판단을 **JSON 으로** 집필, 각 사실 문장에 [S#]. URL·수치 생성 금지(프롬프트+DNA).
- 견고화: ```json 펜스 제거·JSON 추출, 섹션 빈칸→"미확인", judgment level 정규화(→medium),
  unverified 의 conflicting_sids 를 실존 sid 로 필터. 마지막에 parse_brief(strict) 로 계약 자동보증.
- 지표는 0(미측정) + status="draft" → 대시보드가 "초안(미검증)" 배지로 정직 표기, Metrics 단계가 채움.
- **검증(실 LLM 호출)**: collect("RAG",hackernews,5) → write_brief → 계약 통과 draft.
  본문 [S#] 인용 실재(S1/S2/S3/S5), **인용 sid ⊆ 유효 sid(유령 인용 0)**, judgment 정상. ruff 통과.
- 다음: piece 5 Verifier — CoVe + L1 인용 앵커링(결정론) + L4 NLI 인용검사.

## 2026-07-10 — [piece 5] Verifier: L1 인용 앵커링 (결정론, LLM=0)
- **정직한 범위 결정**: L4 NLI·CoVe 는 '출처 원문 전체'가 있어야 검증기 자신이 환각 안 함.
  현재 Collector 는 본문 전체 미수집 → 근거 없이 돌리면 검증기가 환각(설계 철학 위반) → **유보**.
  대신 결정론 L1 을 확실히. (이 유보 자체가 기획서 §2.5 "검증기가 환각하면 안 된다"의 실천.)
- `verifier/anchoring.py`:
  - `verify_brief(brief)`: 문장분할 → [S#] 추출 → 판정(phantom_citation/quote_mismatch/uncited/ok). LLM 판단 0.
  - `apply_verification`: 위반(phantom/quote) 문장 제거 + unverified 이동(CoVe 삭제/수정의 결정론판), 계약 유지.
- **검증(결정론, LLM 불필요)**: 깨끗한 rag.json → 위반0 passed. **[S9] 유령인용 주입 → 결정론 검출**,
  apply 로 제거·이동·재검증 위반0·계약 유지. ruff 통과.
- 이 검출 메커니즘이 piece 6 Eval-Harness 의 '환각 검출률' 측정 대상이 된다.
- 다음: piece 6 Metrics+Eval-Harness — 골드셋·환각주입으로 Verifier 검출률 실측.

## 2026-07-10 — [piece 6-1] Metrics: 결정론 충실도 지표
- `metrics/compute.py`: compute_metrics(브리핑→지표), apply_metrics(반영 + 통과시 status="verified").
- **정직 고지**: 진짜 FActScore/RAGAS/ALCE-NLI 는 본문 원문 필요 → 지금은 **결정론 프록시**:
  atomic_support_rate=신뢰(1-2급)출처 인용비율, citation_precision=유효율(1-유령율),
  citation_recall=커버리지, ragas=커버리지 프록시. '인용 구조 건전성'을 잰다(과장 금지).
- **막힘→뚫음**(ERRORS #4): 정밀도에도 사실문 길이필터(≥20자)를 재사용해 **짧은 유령인용을 놓침**.
  → 정밀도는 '인용 달린 모든 문장' 기준으로 분리. 주입 후 precision 0.875 로 정확 하락.
- **검증**: rag.json → precision1.0/coverage0.467, status verified. 유령인용 주입 → precision 0.875, status draft. ruff 통과.
- 다음: (6-2) Eval-Harness — 환각 주입 → Verifier 검출률(recall)·오탐 실측.

## 2026-07-10 — [piece 6-2] ★ Eval-Harness (환각 검출률 실측)
- `metrics/harness.py`: 골드셋(data/briefs)에 조작 문장 3유형 주입 → verify_brief → 검출 집계.
  - phantom_citation(유효 아닌 [S99]) = 잡아야 함(violation)
  - uncited_fabrication(인용없는 거짓) = 표시해야 함(uncited)
  - plausible_fabrication(유효 [S1]+거짓 내용) = **L1 은 구조적으로 못 잡음**(본문 NLI 필요) → 정직 노출
- **실측 리포트(원문)**: 브리핑 3건·주입 9건 → **검출률(recall)=1.0, 오탐=0**.
  phantom 3/3, uncited 3/3, plausible 0/3(못 잡는 게 정답 — 숨기지 않음).
- 이게 과제의 "AI가 틀리는 순간과 그걸 잡는 법" 실측 증거. 못 잡는 유형까지 드러내는 게 핵심.
- **piece 6 완료**: 결정론 지표 + 검출률 실측 하네스.
- 다음: piece 7 파이프라인 연결 — collect→write→verify→metrics → data/briefs 에 실제 브리핑 저장.

## 2026-07-10 — [piece 7] 파이프라인 연결 (Phase 1 전체 완성)
- `pipeline/run.py: run_pipeline(topic) -> PipelineResult`. 순서(결정론 워크플로우):
  collect → write_brief(초안) → verify→apply_verification(L1 정리) → apply_metrics → data/briefs 저장.
  LLM 은 집필에서만, 진위 판정은 결정론 코어(L1)가. CLI: `python -m tll.pipeline.run "<topic>"`.
- **검증(실 end-to-end, 임시폴더)**: run_pipeline("LangChain",hackernews,6) →
  status=verified, 지지율0.714/정밀도1.0/커버리지1.0/출처6, 위반0, 미확인1. 저장파일 재로딩 계약통과. ruff 통과.
- **Phase 1 전체 7조각 완료**: 대시보드·Collector·shared/llm·Analyst·Verifier·Metrics+Harness·파이프라인.
- 남은 한계(정직): 본문 원문 미수집 → L4/CoVe·진짜 FActScore/RAGAS 유보(프록시로 대체), Anthropic 실키 미발급.

## 2026-07-10 — Collector 정리 (③ 조각 완료)
- models(계약)·rate_limiter·robots_guard → HackerNewsProvider → GeekNewsProvider → engine → provenance검증.
- 순수 결정론(LLM 0), 전역상태 없음, to_source 로 schema.Source 편입 가능 → 나중 ReAct 의
  collect(topic, source) 액션으로 그대로 호출 가능. summary 가 재수집 판단(전환점 1)의 관찰이 된다.
- 실측 함정 2개를 '추측 금지·실응답 먼저'로 코딩 전에 차단: HN fuzzy(RAG↔Rage), GeekNews RSS→실제 Atom.

---

## 2026-07-10 — [v3 전환] 자율 에이전트 재설계 + Scout(정찰) 1조각

### 방향 전환 (기획서 v3)
- 사용자 재확정: 주제를 사람이 넣는 게 아니라 **에이전트가 스스로 최신 기술을 발견**해 실시간으로
  한국어 교과서를 만든다. 충실도는 북극성에서 **배경(최신성을 가능케 하는 안전벨트)**으로 재배치.
- `docs/TLL_기획서_v3.md` 신설: 에이전트 작동 순서(Scout→Triage→Tracker→Reader→Author→
  Fact-Check→Memory→Dashboard)를 척추로, 빌드도 그 순서. 기억(KB)을 Phase3→**중심**으로 승격.
- 근거: STORM/Co-STORM(조사→집필·계속 갱신되는 마인드맵), deep research agent(브리핑+기억 루프),
  CoALA/ReAct/Reflexion/Anthropic.

### Scout(정찰) — `src/tll/scout/` (에이전트 순서 1단계)
- 하는 일: 실시간 소스(HN 프론트페이지 + GeekNews 최근 피드) 폴링 → TrendCandidate 정규화
  (등급·신선도·안정 id) → 최소 Memory(seen 로그)로 '지난 확인 이후 **새 것만**'.
- **경계 라벨 정직화(중요, ERRORS #5)**: v3 초안은 Scout를 [에이전트]로 적었으나, '훑어서 새 것만'은
  실제론 **결정론(폴링+집합차)**이다. 가치 판단('교과서 감이냐')은 다음 단계 **Triage(에이전트)**로 분리.
- 재사용: `trends.fetch_top_stories`(HN 실시간), `compute_content_hash`(안정 id),
  `grade_from_domain`(등급), `GeekNewsProvider.search("")`(빈 topic=토큰0=최근 피드 전체).
- 신선도: `freshness.age_label` — 발행시각→"3시간 전"(한국어). now 주입식(테스트 가능).
- 최소 Memory: `seen_store.SeenStore`(`data/memory/seen.json`). first_seen 박제, 원자적 저장,
  키 정렬 출력 = 결정론. 이후 개념 KB로 확장(v3 §7).

### 막힘→뚫음
- **(샌드박스 네트워크)** allowlist 상 PyPI만 열리고 HN/GeekNews/GitHub는 프록시 403 →
  **실호출은 사용자 머신**(`python -m tll.scout.scout`), 결정론 로직은 목(mock) 피드로 오프라인 완전 검증.
- **(테스트 몽키패치)** `tll.scout` 의 `scout` 함수가 동명 서브모듈을 가려 `sys.modules["tll.scout.scout"]`로 패치.
- **(샌드박스 git/삭제 잠금)** 이 마운트는 파일 생성·수정은 되나 **삭제(unlink)를 EPERM 으로 막음** →
  `.git/index.lock` 을 못 지워 **커밋은 사용자 머신에서**. 파일 도구의 기존파일 수정(임시→교체)도 실패해
  WORKLOG/ERRORS 는 bash append 로 기입.

### 검증 (오프라인, 결정론) — 25개 체크 전부 PASS
- age_label/unix_to_iso, HN 정규화(arxiv=1급·blog=3급·순위·cid), 신규성(run1 new=2→run2 0→run3 +1=1),
  first_seen 박제, seen.json 키정렬, 소스 실패 격리(HN 403이어도 GeekNews 생존), 결정론(복제 store→같은 new).
- ruff 0.15.21 → All checks passed.
- 남은 것(정직): 실제 폴링·git 커밋은 사용자 머신. 다음 조각 = **Triage(에이전트 판단)**.

## 2026-07-10 — [Triage] 선별 (에이전트 순서 2단계, 첫 '에이전트' 조각)
- 하는 일: Scout 후보를 LLM이 '배울 가치 있는 IT/AI 기술이냐(교과서 감)' 판단 →
  keep/category/worth/reason → 상위 N 선별. `src/tll/triage/`.
- **경계**: 판단은 LLM(에이전트), 최종 선별(top-N 정렬)·집계는 결정론. LLM은 제목·소스·등급·신호만
  보고 분류/가치판단만 — 원문 fetch·수치 생성 없음(DNA). 여기부터 '모델이 다음 행동을 고른다'.
- 재사용: `shared/llm get_provider().generate(system=...)`, writer 의 JSON 추출 패턴
  (펜스 제거 → `[ ]` 슬라이스 → json.loads).
- 견고화: 잘못된 JSON/키없음/LLM에러 → 지어내지 않고 `summary.mode="error"` 정직 노출.
  미판단 후보는 keep=False("미판단")로 누락 숨김 방지. 범위밖/중복 i 무시.
  소스 라운드로빈(max_judge 컷에서 한국어 소스 보호).
- 검증(오프라인, 목 LLM): **14체크 PASS** — 파싱·선별순서(worth desc)·top_n컷·펜스·
  malformed 격리·미판단·빈입력·결정론·interleave 공정. ruff 통과.
- 실제 LLM(Gemini) 호출은 사용자 머신: `python -m tll.triage.triage` (scout→triage 데모, res.candidates 전체 판단).
- 다음: **Tracker** — 선별 주제의 공식 문서 '본문' 수집(그 "반쪽" 구멍 메우기).

## 2026-07-10 — [Tracker] 추적 — 공식 문서 '본문' 수집 (에이전트 순서 3단계)
- 하는 일: Triage 선별 주제의 링크를 따라가 **본문을 실제로 수집**(그 "검증 반쪽" 구멍 메우기). `src/tll/tracker/`.
- **등급 정제(사용자 합의)**: '학술이냐'가 아니라 **원천 근접도(1차/2차/3차)**로. **제작사 공식 발표=1급(1차)**.
  같은 1급도 성격 태그: `제작사`(자기발표=미검증)/`논문`(외부검증)/`레포`. 2차=뉴스, 3차=블로그·커뮤니티.
  "제작사 주장 vs 논문 충돌"은 등급이 아니라 다출처 대조·충돌표기(Author/Verifier)가 처리 — 여기선 등급·태그만.
- 구성: `grading.classify_source`(도메인→등급·성격), `extract.extract_text`(stdlib html.parser, 의존성0),
  `tracker.track`(robots·rate limit 준수).
- 정직 처리(지어내지 않음): 공식링크없음(HN 토론)=no_official, robots=blocked, 비HTML=non_html,
  실패=fetch_error, 본문<200자='JS 렌더 가능' 경고, 레포='3자 여부 미확인' note.
- 한계(정직): 등급표가 화이트리스트라 불완전(Tencent 등 놓치면 3급). '진짜 공식 소스 검색'은 다음 개선.
- 검증(오프라인, 목 fetcher/robots): **23체크 PASS** — 등급분류·본문추출(script/style 제외)·상태 5종·
  github note·본문빈약·max_docs·summary. ruff 통과.
- 실제 fetch 는 사용자 머신: `python -m tll.tracker.tracker` (scout→triage→track 데모).
- 다음: **Reader** — 가져온 본문을 읽고 이해·부족판정("더 찾자" ReAct 결정점).

## 2026-07-10 — [Reader] 독해 — ReAct 결정점 (에이전트 순서 4단계)
- 하는 일: Tracker 본문을 LLM이 읽고 "이걸로 이 기술이 뭔지 교과서를 쓸 수 있나" 판단 →
  충분=proceed(집필) / 부족=collect_more("더 찾자"). **모델이 다음 행동을 고름 = 진짜 ReAct.**
- 본문 근거 이해 요지(understanding) 추출(지어내지 않음). 부족하면 뭐가 없는지(missing) → 재수집 힌트.
- 경계: 판단은 LLM. 단 status!=ok·본문<80자는 **결정론 precheck**로 LLM 없이 '부족'(뻔한 실패에 토큰 0).
  실패·JSON 오류는 지어내지 않고 '부족+error'.
- 검증(오프라인, 목 LLM): **13체크 PASS** — 충분/부족 분기·precheck(비ok·빈약)·이해추출·missing·
  malformed 격리·펜스·결정론·**precheck는 LLM 미호출(호출 카운트로 증명)**. ruff 통과.
- 실제 LLM은 사용자 머신: `python -m tll.reader.reader` (scout→triage→track→read 데모).
- **'가져오기' 절반 완료**: Scout(찾기)→Triage(고르기)→Tracker(본문)→Reader(독해·판단).
  다음부터 '집필' 절반: **Author**(한국어 교과서·대조유추).

## 2026-07-10 — [Author] 집필 — 한국어 교과서 (에이전트 순서 5단계, '집필' 절반 시작)
- 하는 일: Reader가 '충분' 판정한 본문으로 **한국어 교과서(정체 브리핑)** 집필. `src/tll/author/`.
  §3 6섹션(뼈대·배경·**대조유추**·필요성·전망·quickstart) + one_liner + judgment + unverified. 문장별 [S1].
- **원문 보존**: Source.body_text 에 원문을 담아 넘김 → **Fact-Check(L1)가 실제 문자열 대조** 가능
  (그 "반쪽" 구멍이 여기서 데이터로 준비됨).
- 대조·유추: 원문 근거는 [S1], 원문 밖 일반지식 비교는 (일반지식) 표시 → 이후 미확인(정직).
- 재사용/적응: `analyst/writer.py` 패턴(프롬프트·JSON 파싱·정규화)을 단일 출처(TrackedDoc)용으로.
- 견고화: 빈 본문·malformed JSON → AuthorError. author_all 은 한 건 실패가 전체를 안 죽임(개별 격리).
  섹션 누락→"미확인" 채움, judgment level 정규화, unverified conflicting_sids 실존 sid만.
- 검증(오프라인, 목 LLM): **18체크 PASS** — 조립·6섹션·대조·원문보존·[S1]·정규화·conflicting 필터·
  섹션누락·빈본문·malformed·펜스·author_all 격리·결정론. ruff 통과.
- 실제 LLM은 사용자 머신: `python -m tll.author.author` (scout→…→author, 실제 한국어 교과서 생성).
- 다음: **Fact-Check** — 교과서 [S1] 인용을 원문(body_text)과 문자열 대조(L1) + 번역 대조.

## 2026-07-10 — [Fact-Check] 검증 — 원문 대조 L1 + 수치 앵커링 (6단계, '반쪽' 구멍 메움)
- 하는 일: Author 교과서를 **원문(body_text)과 대조**하는 결정론 검증(LLM=0). `src/tll/factcheck/`.
  - phantom_citation(실존X 인용)·quote_mismatch(따옴표 인용이 원문에 없음) = 위반 → 제거.
  - unsupported_number(원문에 없는 숫자)·uncited(미인용 사실문)·general_knowledge((일반지식)) = 미확인 플래그.
  - **충실도%(원문근거)** = ok 사실문 / 전체 사실문. apply 로 위반 제거·비-ok 전부 unverified 이동, status 설정.
- **"반쪽" 구멍 메움**: Phase 1 anchoring 은 원문 text 필드가 없어 title 을 근사로 썼다(프록시).
  이제 Tracker→Author 가 body_text 를 보존 → **진짜 본문 문자열 대조**. 프록시였던 충실도가 **실측으로 승격**.
- 결정론(LLM=0): 같은 입력 → 같은 판정(재현성). 검증기 자신은 환각 안 함(닻).
- **정직한 한계**: '인용·수치·따옴표'의 원문 앵커링이지 완전한 의미 함의(NLI)는 아니다.
  인용·숫자가 맞아도 의미가 미묘히 틀릴 수 있음(그건 LLM 판정 영역 → 코어에서 제외). 과장 금지.
- 검증(오프라인, LLM 0): **18체크 PASS** — 6판정 분류·충실도 3/8·apply(제거·미확인5)·clean=verified 100%·
  인용문 원문존재·결정론. ruff 통과.
- 데모(사용자 머신): `python -m tll.factcheck.factcheck` (scout→…→author→factcheck, 충실도% 표시).
- 다음: **Memory**(개념 KB=대조근거 + 신규성) → Dashboard → Loop.

## 2026-07-10 — [Memory] 기억 — 개념 KB(대조·유추 엔진) + Reflexion lessons (7단계)
- 하는 일: `src/tll/memory/`.
  - **개념 KB(의미기억)**: 검증 교과서 → 개념 카드 upsert(같은 주제면 times_seen++·first_seen 보존).
  - **recall/contrast_context**: 관련 개념 회상(용어 겹침) → Author 대조·유추 근거("기존과 뭐가 다른지"의 재료).
  - **lessons(에피소드, Reflexion)**: 실패·교훈 기록 → 다음 시도 회피(loop 에서 사용).
- **'스스로 학습'의 실체**: KB가 쌓일수록 대조가 좋아짐(Co-STORM 마인드맵 취지). '중심으로 올린' 조각.
- CoALA 매핑: 의미기억=개념 KB, 에피소드=lessons, 절차=프롬프트/프로바이더(코드).
- 저장 결정론(JSON·정렬·원자적), 전역상태 없음. **정직한 한계**: 회상은 영문 tech 토큰 겹침(어휘)이지
  임베딩(의미) 아님 — 다른 이름의 유사 기술은 놓칠 수 있음(임베딩은 Phase 4).
- Author 연결(contrast_context 주입)은 **Loop 단계에서** 배선(지금은 Memory 독립 완성).
- 검증(오프라인, 순수 데이터): **18체크 PASS** — remember·upsert·recall(겹침·자기제외·무관제외)·
  contrast_context·lessons(최신·kind)·정렬저장·손상복원. ruff 통과.
- 데모(사용자 머신): `python -m tll.memory.memory` (전체 체인 → 검증 교과서 기억 → KB·회상 표시).
- 다음: **Dashboard**(한국어 통합 뷰) → **Loop**(30분 자동).

## 2026-07-10 — [Dashboard/Present] 한국어 대시보드 — 자체 완결 HTML (8단계)
- 하는 일: 검증 교과서를 **서버 없이 브라우저로 여는 단일 HTML**로 산출. `src/tll/present/`.
  최신순 카드 · 신선도("N시간 전") · **충실도%(색 배지)** · status · **원문 보기 링크** · 6섹션 · 미확인.
- 왜 HTML(Streamlit 아님): 서버 불필요(파일 열기만)·의존성 0·순수 함수라 검증 용이·항상 최신.
  기존 Streamlit 대시보드(`tll.dashboard`)는 그대로 — 이건 자율 교과서용 새 Presenter.
- store: 교과서+지표를 JSON 저장(slug.json, 같은 주제 덮어써 최신 유지) → load_records → 렌더.
- 안전: 모든 사용자 콘텐츠 HTML escape(스크립트 주입 차단). 순수 함수(같은 입력→같은 HTML).
- 검증(오프라인, 순수): **12체크 PASS** — 주제·충실도배지·신선도·원문링크·섹션라벨·미확인·status·
  최신순·유효HTML·escape·빈목록·store 왕복. ruff 통과. + 샘플 미리보기 HTML 생성.
- 데모(사용자 머신): `python -m tll.present.html` (전체 체인 → 저장 → data/dashboard.html, 브라우저로 열기).
- 다음(마지막): **Loop** — 전부를 30분마다 자동으로 감싸는 ReAct 스케줄러.
