"""Google Drive 파일 목록 조회 및 다운로드."""

import io
import os
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

from src.config import (
    DOWNLOAD_DIR,
    DRIVE_SCOPES,
    EXPORT_MAP,
    GOOGLE_CREDENTIALS_PATH,
    SUPPORTED_MIME_TYPES,
    TOKEN_PATH,
)


def _get_drive_service():
    """OAuth 인증 후 Drive API 서비스 반환."""
    creds = None

    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), DRIVE_SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                GOOGLE_CREDENTIALS_PATH, DRIVE_SCOPES
            )
            creds = flow.run_local_server(port=0)

        TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        TOKEN_PATH.write_text(creds.to_json())

    return build("drive", "v3", credentials=creds)


def list_files(folder_id: str) -> list[dict]:
    """Google Drive 폴더 내 지원 파일 목록 반환."""
    service = _get_drive_service()
    results: list[dict] = []
    page_token = None

    while True:
        response = (
            service.files()
            .list(
                q=f"'{folder_id}' in parents and trashed = false",
                spaces="drive",
                fields="nextPageToken, files(id, name, mimeType, modifiedTime, size)",
                pageToken=page_token,
            )
            .execute()
        )
        for f in response.get("files", []):
            if f["mimeType"] in SUPPORTED_MIME_TYPES:
                results.append(f)
        page_token = response.get("nextPageToken")
        if not page_token:
            break

    return results


def download_file(file_id: str, file_name: str, mime_type: str) -> Path:
    """Drive 파일을 로컬에 다운로드. Google Workspace 파일은 export."""
    service = _get_drive_service()
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

    if mime_type in EXPORT_MAP:
        export_mime, ext = EXPORT_MAP[mime_type]
        request = service.files().export_media(fileId=file_id, mimeType=export_mime)
        dest = DOWNLOAD_DIR / f"{file_id}{ext}"
    else:
        request = service.files().get_media(fileId=file_id)
        # 확장자 보존, 파일명은 file_id 사용 (비ASCII 문자 회피)
        suffix = Path(file_name).suffix or ""
        dest = DOWNLOAD_DIR / f"{file_id}{suffix}"

    with io.FileIO(str(dest), "wb") as fh:
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()

    return dest


def download_all(folder_id: str) -> list[dict]:
    """폴더 내 모든 지원 파일을 다운로드하고 메타데이터 반환."""
    files = list_files(folder_id)
    downloaded: list[dict] = []

    for f in files:
        path = download_file(f["id"], f["name"], f["mimeType"])
        downloaded.append(
            {
                "drive_id": f["id"],
                "name": f["name"],
                "mime_type": f["mimeType"],
                "local_path": str(path),
            }
        )

    return downloaded
