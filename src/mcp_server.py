"""MCP Server: Google Drive RAG를 외부 AI 클라이언트에 노출."""

import json

from mcp.server.fastmcp import FastMCP

from src.rag import list_sources, query, sync_files

mcp = FastMCP(
    "google-drive-rag",
    instructions=(
        "Google Drive 문서 기반 RAG 서버입니다. "
        "먼저 sync_drive_files로 문서를 동기화한 후, query_documents로 질문하세요."
    ),
)


@mcp.tool()
def sync_drive_files() -> str:
    """Google Drive 폴더의 문서를 ChromaDB에 동기화합니다.

    Drive 폴더의 문서를 다운로드 → 파싱 → 청킹 → 임베딩하여
    로컬 ChromaDB에 저장합니다. 변경된 파일만 처리합니다(증분 동기화).
    최초 실행 시 시간이 소요될 수 있습니다.
    """
    result = sync_files()
    summary = {
        "status": "success",
        "added": result["added"],
        "updated": result["updated"],
        "unchanged": result["unchanged"],
        "deleted": result["deleted"],
        "summary": (
            f"추가 {len(result['added'])}개, "
            f"업데이트 {len(result['updated'])}개, "
            f"변경없음 {len(result['unchanged'])}개, "
            f"삭제 {len(result['deleted'])}개"
        ),
    }
    return json.dumps(summary, ensure_ascii=False, indent=2)


@mcp.tool()
def query_documents(question: str, source_filter: str = "") -> str:
    """동기화된 문서에서 질문에 대한 답변을 검색합니다.

    하이브리드 검색(벡터 + 키워드)으로 관련 문서를 찾고,
    Gemini로 답변을 생성합니다.

    Args:
        question: 문서에서 찾고 싶은 질문 (한국어/영어 모두 가능)
        source_filter: 특정 파일명으로 검색 범위 제한 (선택, 예: "mql5book.pdf")
    """
    answer = query(question, source_filter=source_filter or None)
    return answer


@mcp.tool()
def list_synced_sources() -> str:
    """현재 동기화되어 검색 가능한 문서 목록과 통계를 반환합니다."""
    info = list_sources()
    if not info["sources"]:
        return json.dumps(
            {"status": "empty", "message": "동기화된 문서가 없습니다. sync_drive_files를 실행해주세요."},
            ensure_ascii=False,
        )
    return json.dumps(
        {"status": "success", **info},
        ensure_ascii=False,
        indent=2,
    )


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
