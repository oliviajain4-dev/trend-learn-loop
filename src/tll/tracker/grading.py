"""출처 등급 — '원천(1차)에 얼마나 가깝냐' + 성격 태그. (기획서 v3 정제)

등급은 '학술이냐'가 아니라 '원천에 얼마나 가깝냐'로 매긴다:
- 1급(1차): 논문(arxiv 등) · 제작사 공식 발표 · 코드/모델 레포. "이게 뭔지"의 원천.
- 2급(2차): 테크 뉴스(받아서 설명·검증).
- 3급(3차): 블로그·커뮤니티(반응·의견).

같은 1급이라도 성격이 다르므로(제작사=자기발표라 미검증 / 논문=외부검증) nature 태그를 함께 준다.
→ '누가 맞나'(제작사 주장 vs 논문)는 등급이 아니라 다출처 대조·충돌표기(Author/Verifier)가 처리.

한계(정직): 도메인 화이트리스트라 불완전 — 못 잡는 공식 기관은 3급으로 나올 수 있다
(→ 목록 점진 보강, 놓친 건 '미확인' 표기). 레포는 '3자 레포'(남의 걸 돌려본 것)인지 등급만으론 못 가린다.
"""

from __future__ import annotations

from urllib.parse import urlparse

_PAPER = ("arxiv.org", "aclanthology.org", "openreview.net", "biorxiv.org", "medrxiv.org", "ssrn.com")
_OFFICIAL = (  # 제작사/기관 공식 (점진 보강 대상)
    "openai.com", "anthropic.com", "meta.com", "google", "deepmind", "microsoft", "apple.com",
    "nvidia.com", "tencent.com", "qwen", "alibaba", "mistral.ai", "cohere.com", "stability.ai",
    "databricks.com", "zhipu", "01.ai", "x.ai", "perplexity.ai", "ibm.com", "amazon.science",
)
_REPO = ("github.com", "gitlab.com", "gitee.com", "bitbucket.org", "huggingface.co")
_PRESS = (
    "arstechnica.com", "theverge.com", "zdnet.com", "zdnet.co.kr", "techcrunch.com", "wired.com",
    "venturebeat.com", "infoworld.com", "technologyreview.com", "theregister.com", "engadget.com",
    "bloomberg.com", "reuters.com", "nytimes.com", "bbc.",
)
_COMMUNITY = ("news.ycombinator.com", "reddit.com", "lobste.rs", "news.hada.io")


def domain_of(url: str) -> str:
    net = urlparse(url).netloc.lower()
    return net[4:] if net.startswith("www.") else net


def classify_source(url: str) -> tuple[int, str, str]:
    """url → (grade 1~3, nature, tier_label). 도메인 화이트리스트 휴리스틱(불완전, 정직 고지)."""
    d = domain_of(url)
    if any(h in d for h in _PAPER):
        return 1, "논문", "1차·논문"
    if any(h in d for h in _OFFICIAL):
        return 1, "제작사", "1차·제작사"
    if any(h in d for h in _REPO):
        return 1, "레포", "1차·레포"
    if any(h in d for h in _PRESS):
        return 2, "뉴스", "2차·뉴스"
    if any(h in d for h in _COMMUNITY):
        return 3, "커뮤니티", "3차·커뮤니티"
    return 3, "블로그", "3차·블로그"
