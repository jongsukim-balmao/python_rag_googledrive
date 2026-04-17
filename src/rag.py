"""RAG 파이프라인: Google Drive 동기화 + Gemini 파일 기반 질의응답."""

from google import genai

from src.config import GEMINI_MODEL, GOOGLE_API_KEY, GOOGLE_DRIVE_FOLDER_ID
from src.drive import download_all
from src.gemini_files import (
    delete_all,
    get_file_references,
    get_uploaded_files,
    upload_file,
)

_client = genai.Client(api_key=GOOGLE_API_KEY)

SEARCH_INSTRUCTION = (
    "You are a document search assistant. "
    "Extract information relevant to the user's question from the provided document. "
    "If the document contains no relevant information, respond with exactly: NO_RELEVANT_INFO. "
    "Be concise and quote key passages. "
    "Respond in the same language as the user's question."
)

SYNTHESIZE_INSTRUCTION = (
    "You are a document assistant. "
    "Synthesize the search results from multiple documents into a coherent answer. "
    "Always cite which document the information comes from. "
    "If no documents had relevant information, say so clearly. "
    "Respond in the same language as the user's question."
)


def sync_files() -> list[dict]:
    """Google Drive에서 파일을 다운로드하고 Gemini File API에 업로드.

    Returns:
        업로드된 파일 정보 리스트
    """
    # 기존 파일 정리
    delete_all()

    # Drive에서 다운로드
    downloaded = download_all(GOOGLE_DRIVE_FOLDER_ID)

    # Gemini에 업로드
    results: list[dict] = []
    for item in downloaded:
        uploaded = upload_file(
            local_path=item["local_path"],
            display_name=item["name"],
            drive_id=item["drive_id"],
        )
        results.append(
            {
                "name": item["name"],
                "gemini_file": uploaded.name,
                "state": str(uploaded.state),
            }
        )

    return results


def _search_single_file(file_ref, file_name: str, question: str) -> str | None:
    """단일 파일에서 질문과 관련된 정보 검색."""
    try:
        response = _client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[file_ref, question],
            config={
                "system_instruction": SEARCH_INSTRUCTION,
                "temperature": 0.1,
            },
        )
        text = response.text.strip()
        if text == "NO_RELEVANT_INFO":
            return None
        return f"[{file_name}]\n{text}"
    except Exception as e:
        return f"[{file_name}] 검색 오류: {e}"


def query(question: str) -> str:
    """업로드된 문서들을 개별 검색 후 종합 응답 생성.

    각 파일을 개별적으로 검색하여 관련 정보를 추출한 후,
    결과를 종합하여 최종 답변을 생성합니다.
    """
    uploaded = get_uploaded_files()

    if not uploaded:
        return "동기화된 문서가 없습니다. 먼저 sync_files를 실행해주세요."

    # 1단계: 각 파일에서 관련 정보 검색
    search_results: list[str] = []
    for drive_id, file_ref in uploaded.items():
        result = _search_single_file(file_ref, drive_id, question)
        if result:
            search_results.append(result)

    if not search_results:
        return "업로드된 문서에서 관련 정보를 찾을 수 없습니다."

    # 2단계: 검색 결과 종합
    combined = "\n\n---\n\n".join(search_results)
    synthesis_prompt = (
        f"다음은 여러 문서에서 검색한 결과입니다:\n\n"
        f"{combined}\n\n"
        f"위 정보를 바탕으로 다음 질문에 답해주세요: {question}"
    )

    response = _client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[synthesis_prompt],
        config={
            "system_instruction": SYNTHESIZE_INSTRUCTION,
            "temperature": 0.3,
        },
    )

    return response.text


def list_sources() -> list[dict]:
    """현재 업로드된 문서 소스 목록 반환."""
    uploaded = get_uploaded_files()
    sources: list[dict] = []
    for key, f in uploaded.items():
        sources.append(
            {
                "name": key,
                "gemini_name": f.name,
                "size_bytes": f.size_bytes if hasattr(f, "size_bytes") else None,
                "state": str(f.state) if f.state else "ACTIVE",
            }
        )
    return sources
