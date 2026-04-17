"""Gemini embedding API 기반 ChromaDB 임베딩 함수 (rate limit 대응)."""

from __future__ import annotations

import time

from chromadb.api.types import Documents, EmbeddingFunction, Embeddings
from google import genai
from google.genai.errors import ClientError

from src.config import EMBEDDING_BATCH_SIZE, EMBEDDING_MODEL, GOOGLE_API_KEY

_client = genai.Client(api_key=GOOGLE_API_KEY)

# 배치당 최대 텍스트 수 (API 부하 분산)
_BATCH_SIZE = min(EMBEDDING_BATCH_SIZE, 50)
# rate limit 초과 시 재시도 설정
_MAX_RETRIES = 5
_BASE_WAIT = 20  # 초


def _embed_batch(texts: list[str], task_type: str) -> list[list[float]]:
    """Gemini API로 배치 임베딩. rate limit 시 자동 재시도."""
    for attempt in range(_MAX_RETRIES):
        try:
            result = _client.models.embed_content(
                model=EMBEDDING_MODEL,
                contents=texts,
                config={"task_type": task_type},
            )
            return [e.values for e in result.embeddings]
        except ClientError as e:
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                wait = _BASE_WAIT * (attempt + 1)
                print(f"  Rate limit hit, waiting {wait}s... (attempt {attempt + 1}/{_MAX_RETRIES})", flush=True)
                time.sleep(wait)
            else:
                raise
    raise RuntimeError(f"Embedding failed after {_MAX_RETRIES} retries")


class GeminiDocumentEmbedding(EmbeddingFunction[Documents]):
    """문서 저장용 임베딩 (RETRIEVAL_DOCUMENT)."""

    def __call__(self, input: Documents) -> Embeddings:
        all_embeddings: list[list[float]] = []
        total = len(input)
        for i in range(0, total, _BATCH_SIZE):
            batch = input[i : i + _BATCH_SIZE]
            embeddings = _embed_batch(batch, "RETRIEVAL_DOCUMENT")
            all_embeddings.extend(embeddings)
            done = min(i + _BATCH_SIZE, total)
            if done < total:
                # 분당 3000 요청 한도 대응: 배치 간 간격
                time.sleep(1.5)
        return all_embeddings


class GeminiQueryEmbedding(EmbeddingFunction[Documents]):
    """검색 쿼리용 임베딩 (RETRIEVAL_QUERY)."""

    def __call__(self, input: Documents) -> Embeddings:
        return _embed_batch(input, "RETRIEVAL_QUERY")


# 싱글턴 인스턴스
doc_embedding_fn = GeminiDocumentEmbedding()
query_embedding_fn = GeminiQueryEmbedding()
