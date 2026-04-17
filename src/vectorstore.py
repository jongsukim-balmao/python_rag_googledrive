"""ChromaDB 벡터 저장소 관리."""

from __future__ import annotations

import chromadb

from src.chunker import Chunk
from src.config import CHROMA_COLLECTION, CHROMA_DB_PATH
from src.embeddings import doc_embedding_fn, query_embedding_fn

EMBEDDING_BATCH_SIZE = 500  # ChromaDB upsert 배치 크기


def _get_client() -> chromadb.ClientAPI:
    CHROMA_DB_PATH.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(CHROMA_DB_PATH))


def _get_collection(client: chromadb.ClientAPI):
    return client.get_or_create_collection(
        name=CHROMA_COLLECTION,
        embedding_function=doc_embedding_fn,
        metadata={
            "hnsw:space": "cosine",
            "hnsw:M": 32,
            "hnsw:construction_ef": 200,
            "hnsw:search_ef": 100,
        },
    )


def upsert_chunks(chunks: list[Chunk]) -> int:
    """청크를 ChromaDB에 배치 upsert."""
    if not chunks:
        return 0

    client = _get_client()
    collection = _get_collection(client)

    # 전체 중복 ID 제거
    seen_ids: set[str] = set()
    deduped: list[Chunk] = []
    for c in chunks:
        if c.chunk_id not in seen_ids:
            seen_ids.add(c.chunk_id)
            deduped.append(c)
    chunks = deduped

    for i in range(0, len(chunks), EMBEDDING_BATCH_SIZE):
        batch = chunks[i : i + EMBEDDING_BATCH_SIZE]
        ids = [c.chunk_id for c in batch]
        documents = [c.text for c in batch]
        metadatas = [
            {
                "source_file": c.metadata.source_file,
                "drive_id": c.metadata.drive_id,
                "chapter": c.metadata.chapter,
                "section": c.metadata.section,
                "page_start": c.metadata.page_start,
                "page_end": c.metadata.page_end,
                "block_type": c.metadata.block_type,
                "is_parent": c.metadata.is_parent,
                "parent_id": c.metadata.parent_id,
                "language": c.metadata.language,
            }
            for c in batch
        ]
        collection.upsert(ids=ids, documents=documents, metadatas=metadatas)

    return len(chunks)


def search_children(
    query_text: str,
    top_k: int = 30,
    where: dict | None = None,
) -> list[dict]:
    """Child 청크에서 유사도 검색."""
    client = _get_client()
    collection = _get_collection(client)

    # child만 검색
    base_where = {"is_parent": False}
    if where:
        base_where = {"$and": [base_where, where]}

    # 쿼리용 임베딩 사용
    query_emb = query_embedding_fn([query_text])

    results = collection.query(
        query_embeddings=query_emb,
        n_results=top_k,
        where=base_where,
        include=["documents", "metadatas", "distances"],
    )

    hits: list[dict] = []
    if results["ids"] and results["ids"][0]:
        for j in range(len(results["ids"][0])):
            hits.append({
                "chunk_id": results["ids"][0][j],
                "text": results["documents"][0][j],
                "metadata": results["metadatas"][0][j],
                "distance": results["distances"][0][j],
            })
    return hits


def get_chunks_by_ids(chunk_ids: list[str]) -> list[dict]:
    """ID로 청크 조회 (parent 조회용)."""
    if not chunk_ids:
        return []

    client = _get_client()
    collection = _get_collection(client)

    results = collection.get(
        ids=chunk_ids,
        include=["documents", "metadatas"],
    )

    items: list[dict] = []
    if results["ids"]:
        for j in range(len(results["ids"])):
            items.append({
                "chunk_id": results["ids"][j],
                "text": results["documents"][j],
                "metadata": results["metadatas"][j],
            })
    return items


def delete_by_drive_id(drive_id: str) -> None:
    """특정 Drive 파일의 모든 청크 삭제."""
    client = _get_client()
    collection = _get_collection(client)
    collection.delete(where={"drive_id": drive_id})


def get_collection_stats() -> dict:
    """컬렉션 통계 반환."""
    client = _get_client()
    collection = _get_collection(client)
    count = collection.count()

    # 소스 파일별 카운트
    return {"total_chunks": count, "collection": CHROMA_COLLECTION}


def get_all_documents_text() -> list[tuple[str, str]]:
    """BM25 인덱스 구축용: (chunk_id, text) 리스트 반환. child만."""
    client = _get_client()
    collection = _get_collection(client)
    results = collection.get(
        where={"is_parent": False},
        include=["documents"],
    )
    return list(zip(results["ids"], results["documents"]))
