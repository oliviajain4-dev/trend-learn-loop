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
