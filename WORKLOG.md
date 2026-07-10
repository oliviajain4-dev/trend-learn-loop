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

## 2026-07-10 — Collector 정리 (③ 조각 완료)
- models(계약)·rate_limiter·robots_guard → HackerNewsProvider → GeekNewsProvider → engine → provenance검증.
- 순수 결정론(LLM 0), 전역상태 없음, to_source 로 schema.Source 편입 가능 → 나중 ReAct 의
  collect(topic, source) 액션으로 그대로 호출 가능. summary 가 재수집 판단(전환점 1)의 관찰이 된다.
- 실측 함정 2개를 '추측 금지·실응답 먼저'로 코딩 전에 차단: HN fuzzy(RAG↔Rage), GeekNews RSS→실제 Atom.
