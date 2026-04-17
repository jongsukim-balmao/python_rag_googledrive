"""하이브리드 검색: 벡터 검색 + BM25 + RRF 병합."""

from __future__ import annotations

import re
from collections import defaultdict

from rank_bm25 import BM25Okapi

from src.config import FINAL_TOP_K, RRF_K, SEARCH_TOP_K
from src.vectorstore import get_all_documents_text, get_chunks_by_ids, search_children

# BM25 인덱스 (메모리 캐시)
_bm25_index: BM25Okapi | None = None
_bm25_ids: list[str] = []
_bm25_corpus: list[list[str]] = []


def _tokenize(text: str) -> list[str]:
    """간단한 다국어 토크나이저."""
    return re.findall(r"[\w]+", text.lower())


def build_bm25_index() -> int:
    """ChromaDB의 child 청크로 BM25 인덱스 구축."""
    global _bm25_index, _bm25_ids, _bm25_corpus

    docs = get_all_documents_text()
    if not docs:
        _bm25_index = None
        return 0

    _bm25_ids = [d[0] for d in docs]
    _bm25_corpus = [_tokenize(d[1]) for d in docs]
    _bm25_index = BM25Okapi(_bm25_corpus)
    return len(_bm25_ids)


def _bm25_search(query: str, top_k: int) -> list[str]:
    """BM25 키워드 검색. chunk_id 리스트 반환."""
    if _bm25_index is None:
        return []
    tokens = _tokenize(query)
    if not tokens:
        return []
    scores = _bm25_index.get_scores(tokens)
    ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    return [_bm25_ids[i] for i in ranked[:top_k]]


def _rrf_merge(
    semantic_ids: list[str],
    keyword_ids: list[str],
    k: int = RRF_K,
) -> list[str]:
    """Reciprocal Rank Fusion으로 두 결과 병합."""
    scores: dict[str, float] = defaultdict(float)
    for rank, doc_id in enumerate(semantic_ids):
        scores[doc_id] += 1.0 / (k + rank + 1)
    for rank, doc_id in enumerate(keyword_ids):
        scores[doc_id] += 1.0 / (k + rank + 1)
    return sorted(scores, key=lambda x: scores[x], reverse=True)


def hybrid_search(
    query: str,
    top_k: int = FINAL_TOP_K,
    where: dict | None = None,
) -> list[dict]:
    """하이브리드 검색: 벡터 + BM25 + RRF + Parent 확장.

    Returns:
        parent 청크 리스트 (전체 맥락 포함)
    """
    # 1. 벡터 검색
    semantic_results = search_children(query, top_k=SEARCH_TOP_K, where=where)
    semantic_ids = [r["chunk_id"] for r in semantic_results]

    # 2. BM25 검색
    keyword_ids = _bm25_search(query, top_k=SEARCH_TOP_K)

    # 3. RRF 병합
    merged_ids = _rrf_merge(semantic_ids, keyword_ids)

    # 4. 상위 child 선택 → parent ID 수집
    # child 메타데이터 조회
    top_child_ids = merged_ids[: top_k * 2]  # parent 중복 대비 여유
    children = get_chunks_by_ids(top_child_ids)

    # child → parent 매핑 (중복 제거, 순서 유지)
    seen_parents: set[str] = set()
    parent_ids: list[str] = []
    child_context: list[dict] = []

    for child in children:
        pid = child["metadata"]["parent_id"]
        if pid not in seen_parents:
            seen_parents.add(pid)
            parent_ids.append(pid)
        child_context.append(child)
        if len(parent_ids) >= top_k:
            break

    # 5. Parent 청크 조회
    parents = get_chunks_by_ids(parent_ids)

    return parents
