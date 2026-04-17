"""RAG 파이프라인: ChromaDB 하이브리드 검색 + Gemini 생성."""

from __future__ import annotations

from google import genai

from src.config import GEMINI_MODEL, GOOGLE_API_KEY
from src.search import build_bm25_index, hybrid_search
from src.sync import sync
from src.vectorstore import get_collection_stats

_client = genai.Client(api_key=GOOGLE_API_KEY)

SYSTEM_INSTRUCTION = (
    "You are a document assistant. "
    "Answer questions based ONLY on the provided document excerpts. "
    "If the answer is not in the excerpts, say so clearly. "
    "Always cite the source document and page number. "
    "Respond in the same language as the user's question."
)


def sync_files() -> dict:
    """Google Drive와 ChromaDB를 증분 동기화."""
    return sync()


def query(question: str, source_filter: str | None = None) -> str:
    """하이브리드 검색 + Gemini 생성으로 질의응답.

    Args:
        question: 사용자 질문
        source_filter: 특정 파일만 검색 (선택)
    """
    # BM25 인덱스가 없으면 구축 시도
    build_bm25_index()

    # 검색 필터 구성
    where = None
    if source_filter:
        where = {"source_file": source_filter}

    # 하이브리드 검색 → parent 청크 반환
    parents = hybrid_search(question, where=where)

    if not parents:
        return "관련 문서를 찾을 수 없습니다. sync_drive_files를 먼저 실행해주세요."

    # 컨텍스트 구성
    context_parts: list[str] = []
    for p in parents:
        meta = p["metadata"]
        header = (
            f"[{meta['source_file']} | {meta['chapter']} > {meta['section']} "
            f"| p.{meta['page_start']}-{meta['page_end']}]"
        )
        context_parts.append(f"{header}\n{p['text']}")

    context = "\n\n---\n\n".join(context_parts)

    prompt = (
        f"다음은 관련 문서 발췌입니다:\n\n{context}\n\n"
        f"위 문서를 바탕으로 다음 질문에 답해주세요:\n{question}"
    )

    response = _client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[prompt],
        config={
            "system_instruction": SYSTEM_INSTRUCTION,
            "temperature": 0.3,
        },
    )

    return response.text


def list_sources() -> dict:
    """동기화된 문서 및 ChromaDB 통계 반환."""
    stats = get_collection_stats()

    # sync manifest에서 파일별 정보 로드
    from src.sync import _load_manifest
    manifest = _load_manifest()

    sources = []
    for fid, info in manifest.items():
        sources.append({
            "name": info["name"],
            "drive_id": fid,
            "chunk_count": info.get("chunk_count", 0),
            "last_synced": info.get("last_synced", ""),
        })

    return {
        "total_chunks": stats["total_chunks"],
        "sources": sources,
    }
