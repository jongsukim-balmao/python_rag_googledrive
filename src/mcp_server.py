"""MCP Server: Google Drive RAG를 외부 AI 클라이언트에 노출."""

import json

from mcp.server.fastmcp import FastMCP

from src.rag import list_sources, query, sync_files

mcp = FastMCP(
    "google-drive-rag",
    instructions=(
        "Google Drive 문서 기반 RAG 서버입니다. "
        "먼저 sync_files로 문서를 동기화한 후, query로 질문하세요."
    ),
)


@mcp.tool()
def sync_drive_files() -> str:
    """Google Drive 폴더에서 문서를 가져와 Gemini에 업로드합니다.

    Drive 폴더의 모든 지원 문서(PDF, Docs, Sheets, Slides 등)를
    다운로드하고 Gemini File API에 업로드하여 검색 가능하게 합니다.
    """
    results = sync_files()
    return json.dumps(
        {"status": "success", "synced_files": results, "count": len(results)},
        ensure_ascii=False,
        indent=2,
    )


@mcp.tool()
def query_documents(question: str) -> str:
    """동기화된 문서들에서 질문에 대한 답변을 검색합니다.

    Args:
        question: 문서에서 찾고 싶은 질문 (한국어/영어 모두 가능)
    """
    answer = query(question)
    return answer


@mcp.tool()
def list_synced_sources() -> str:
    """현재 동기화되어 검색 가능한 문서 목록을 반환합니다."""
    sources = list_sources()
    if not sources:
        return json.dumps(
            {"status": "empty", "message": "동기화된 문서가 없습니다."},
            ensure_ascii=False,
        )
    return json.dumps(
        {"status": "success", "sources": sources, "count": len(sources)},
        ensure_ascii=False,
        indent=2,
    )


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
