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
- **재사용성**: 이 수집기는 대시보드용이자 나중 파이프라인 Collector 단계 그대로 재사용.
