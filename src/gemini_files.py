"""Gemini File API를 통한 파일 업로드 및 관리."""

from pathlib import Path

from google import genai
from google.genai.types import File

from src.config import GOOGLE_API_KEY

_client = genai.Client(api_key=GOOGLE_API_KEY)

# 업로드된 파일 추적: drive_id → Gemini File 객체
_uploaded: dict[str, File] = {}


def _sanitize_name(name: str) -> str:
    """display_name을 ASCII 안전 문자열로 변환."""
    safe = name.encode("ascii", errors="replace").decode("ascii")
    return safe.replace("?", "_")


def upload_file(local_path: str, display_name: str, drive_id: str) -> File:
    """로컬 파일을 Gemini File API에 업로드."""
    uploaded = _client.files.upload(
        file=local_path,
        config={"display_name": _sanitize_name(display_name)},
    )

    # 처리 완료 대기 (동영상 등 대용량 파일의 경우)
    import time

    while uploaded.state and uploaded.state.name == "PROCESSING":
        time.sleep(2)
        uploaded = _client.files.get(name=uploaded.name)

    _uploaded[drive_id] = uploaded
    return uploaded


def get_uploaded_files() -> dict[str, File]:
    """현재 업로드된 파일 목록 반환."""
    return dict(_uploaded)


def get_file_references() -> list[File]:
    """generate_content에 전달할 파일 레퍼런스 리스트."""
    return list(_uploaded.values())


def refresh_from_remote() -> None:
    """Gemini 서버에 남아있는 파일 목록으로 로컬 캐시 갱신."""
    _uploaded.clear()
    for f in _client.files.list():
        # display_name을 키로 사용 (drive_id를 복원할 수 없으므로)
        _uploaded[f.display_name] = f


def delete_all() -> int:
    """업로드된 모든 파일 삭제."""
    count = 0
    for drive_id, f in list(_uploaded.items()):
        _client.files.delete(name=f.name)
        del _uploaded[drive_id]
        count += 1
    return count
