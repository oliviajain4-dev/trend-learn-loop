"""수집기(Collector) 패키지 — LLM 없이 API·RSS 에서 실데이터를 가져오는 결정론 코드.

원칙: 링크·날짜·수치는 **전부 원본에서만**. 코드가 지어내지 않는다.

두 갈래가 이 패키지에 산다:
  1) 대시보드용 **트렌드 피드** (trends.py) — HN topstories 를 순위대로(주제 무관).
  2) 파이프라인용 **주제 수집기** (models/engine/providers) — 특정 topic 으로
     여러 소스를 검색·수집해 CollectedDoc 로 정규화. 나중에 ReAct 루프가
     collect(topic, source) 액션으로 호출한다.

두 갈래 모두 무키(HN·GeekNews) 이므로 .env 가 필요 없다.
"""
