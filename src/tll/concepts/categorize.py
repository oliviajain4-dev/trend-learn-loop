"""기능 카테고리 분류 + AI/LLM 범위 게이트 — 결정론(키워드 규칙). (규칙문서 §5·§8)

목표 두 가지를 한 분류기가 겸한다:
 ① 기능 카테고리 고정 — 개념을 '무슨 일을 하는 기술이냐'로 7개 고정 목록 중 하나에 넣는다.
    ("발견"=출처, 빈칸, "AI 모델"/"AI모델" 불일치 같은 자유형 category 를 규칙으로 통일)
 ② 범위 좁히기 — AI/LLM 분야가 아닌 것(Node.js·PgBouncer·폰트 등)은 '범위 밖'으로 박제(삭제 아님).

전부 결정론(이름·별칭·토픽·기존 category 힌트의 키워드 매칭). LLM 안 부른다 → 재현가능·감사가능·공짜.
정직한 한계: 이름만으로는 완벽친 않다. 명시한 비-AI 는 걸러지고, 애매하면 기본 '기타'(과잉 제외 방지).
본문(요약)까지 보면 더 정확 → 다음 보정거리(§10).
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Iterable

# 사용자 확정 7개 고정 카테고리(코워크). 표시용 이모지는 EMOJI.
CATEGORIES = (
    "AI 모델", "RAG·검색", "에이전트·자동화", "개발도구·프레임워크",
    "데이터·DB·인프라", "기법·최적화", "기타",
)
OUT_OF_SCOPE = "범위 밖"

EMOJI = {
    "AI 모델": "🧠", "RAG·검색": "🔍", "에이전트·자동화": "🤖",
    "개발도구·프레임워크": "🛠️", "데이터·DB·인프라": "🗄️", "기법·최적화": "⚙️",
    "기타": "🌐", OUT_OF_SCOPE: "🚫",
}

# 우선순위 순서(먼저 맞는 카테고리로). 구체 제품·기법이 타입보다 앞.
_CATEGORY_ORDER: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("RAG·검색", (
        "rag", "retrieval", "retrieval-augmented", "vector", "embedding", "embeddings",
        "faiss", "milvus", "qdrant", "weaviate", "chroma", "chromadb", "pgvector",
        "rerank", "reranker", "retriever", "vector db", "vector database", "vector store",
        "vector search", "semantic search", "meilisearch", "검색증강", "임베딩", "벡터", "리트리버",
    )),
    ("에이전트·자동화", (
        "agent", "agents", "agentic", "autogpt", "autogen", "mcp", "model context protocol",
        "tool-use", "tool use", "tool calling", "function calling", "browser-use", "crewai",
        "crew ai", "multi-agent", "orchestration", "orchestrator", "copilot", "assistant",
        "에이전트", "자동화", "오케스트레이션",
    )),
    ("개발도구·프레임워크", (
        "langchain", "langgraph", "llama-index", "llama_index", "llamaindex", "ollama",
        "vllm", "litellm", "dify", "ragflow", "open-webui", "openwebui", "anything-llm",
        "anythingllm", "dspy", "semantic-kernel", "gemini-cli", "framework", "sdk",
        "guidance", "instructor", "pydantic-ai", "프레임워크", "개발도구", "라이브러리",
    )),
    ("AI 모델", (
        "gpt", "claude", "gemini", "llama", "mistral", "qwen", "deepseek", "grok", "phi",
        "transformer", "diffusion", "stable diffusion", "jepa", "moe", "mixture of experts",
        "foundation model", "language model", "vision model", "multimodal", "bert",
        "whisper", "sora", "dall-e", "gan", "언어모델", "생성모델", "멀티모달", "파운데이션", "모델",
    )),
    ("기법·최적화", (
        "prompt", "prompt engineering", "fine-tune", "finetune", "fine-tuning", "finetuning",
        "quantization", "quantize", "quantized", "distillation", "distill", "lora", "qlora",
        "peft", "rlhf", "dpo", "chain of thought", "chain-of-thought", "cot", "harness",
        "context engineering", "in-context", "flash attention", "speculative decoding",
        "kv cache", "inference optimization", "하네스", "프롬프트", "파인튜닝", "양자화", "증류", "최적화", "기법",
    )),
    ("데이터·DB·인프라", (
        "dataset", "data pipeline", "data engineering", "model serving", "inference server",
        "serving", "gpu", "cuda", "tpu", "managed compute", "foundry", "mlflow", "triton",
        "ray serve", "feature store", "nemo", "데이터셋", "서빙", "추론서버", "인프라", "데이터파이프라인",
    )),
)

# AI 근거(카테고리엔 안 걸려도 'AI 관련'이면 기타로 남김)
_AI_GENERAL = (
    "ai", "a.i.", "artificial intelligence", "machine learning", "ml", "deep learning",
    "neural", "genai", "gen ai", "llm", "gpt", "nlp", "openai", "anthropic", "huggingface",
    "hugging face", "inference", "training", "embedding", "model", "인공지능", "머신러닝", "딥러닝", "신경망",
)

# 명백한 비-AI(범용 런타임·DB·OS·폰트 등) — AI 근거가 전혀 없을 때만 '범위 밖'
_NON_AI = (
    "node.js", "nodejs", "node js", "deno", "bun", "pgbouncer", "postgres", "postgresql",
    "mysql", "mariadb", "sqlite", "redis", "memcached", "nginx", "apache", "kubernetes",
    "k8s", "docker", "podman", "terraform", "turing machine", "turing", "font", "ghostty",
    "zig", "lisp", "leap second", "ambulance", "mpmc", "kernel", "filesystem", "file system",
    "compiler", "train sim", "dotenv", "tls", "ssl certificate", "폰트", "커널", "컴파일러", "터미널",
)

# 힌트가 이미 AI 출처/카테고리면 AI 근거로 인정
_AI_HINTS = {"발견", "기법"} | set(CATEGORIES) - {"기타"}


def _hit(hay: str, kws: Iterable[str]) -> bool:
    """hay(소문자) 안에 키워드가 '단어'로 있으면 True. 영숫자 키워드는 경계 매칭(rag≠storage), 한글은 부분 매칭."""
    for kw in kws:
        if kw.isascii():
            if re.search(r"(?<![a-z0-9])" + re.escape(kw) + r"(?![a-z0-9])", hay):
                return True
        elif kw in hay:
            return True
    return False


def categorize(name: str, *, text: str = "", topics: Iterable[str] = (), hint: str = "") -> str:
    """개념 → 7개 카테고리 중 하나, 또는 '범위 밖'. 순수 결정론.

    hint: 기존 category(발견/기법/자유형) — AI 출처 근거로 참고.
    """
    hay = " ".join([name or "", text or "", " ".join(topics or ()), hint or ""]).lower()
    # 1) 기능 카테고리(AI) — 우선순위대로
    for cat, kws in _CATEGORY_ORDER:
        if _hit(hay, kws):
            return cat
    # 2) AI 근거는 있으나 세분류 안 됨 → 기타
    if (hint or "").strip() in _AI_HINTS or _hit(hay, _AI_GENERAL):
        return "기타"
    # 3) 명백한 비-AI → 범위 밖(박제)
    if _hit(hay, _NON_AI):
        return OUT_OF_SCOPE
    # 4) 근거 없음 → 기본 기타(진짜 AI 를 이름만으로 잘못 버리지 않게). 중요도 랭킹이 소음을 가라앉힘.
    return "기타"


def recategorize(registry) -> dict[str, int]:
    """레지스트리의 모든 개념 category 를 규칙으로 재분류(자유형·발견·빈칸 통일 + 범위 밖 박제). 반환: 카테고리별 개수."""
    counts: Counter[str] = Counter()
    for c in registry.all():
        cat = categorize(c.canonical, text=" ".join(getattr(c, "aliases", []) or []), hint=getattr(c, "category", ""))
        c.category = cat
        counts[cat] += 1
    return dict(counts)
