import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

GOOGLE_API_KEY: str = os.environ["GOOGLE_API_KEY"]
GOOGLE_DRIVE_FOLDER_ID: str = os.environ["GOOGLE_DRIVE_FOLDER_ID"]
GOOGLE_CREDENTIALS_PATH: str = os.getenv(
    "GOOGLE_CREDENTIALS_PATH", "credentials/credentials.json"
)
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
DOWNLOAD_DIR: Path = PROJECT_ROOT / "data" / "downloads"
TOKEN_PATH: Path = PROJECT_ROOT / "credentials" / "token.json"

# Google Drive API scopes
DRIVE_SCOPES: list[str] = ["https://www.googleapis.com/auth/drive.readonly"]

# Google Workspace MIME type → export format 매핑
EXPORT_MAP: dict[str, tuple[str, str]] = {
    "application/vnd.google-apps.document": ("application/pdf", ".pdf"),
    "application/vnd.google-apps.spreadsheet": ("text/csv", ".csv"),
    "application/vnd.google-apps.presentation": ("application/pdf", ".pdf"),
}

# Gemini File API가 지원하는 MIME types
SUPPORTED_MIME_TYPES: set[str] = {
    "application/pdf",
    "text/plain",
    "text/csv",
    "text/html",
    "application/vnd.google-apps.document",
    "application/vnd.google-apps.spreadsheet",
    "application/vnd.google-apps.presentation",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}

# ── Chunking ──
CHUNK_SIZE_TOKENS: int = 800
CHUNK_OVERLAP_TOKENS: int = 200
PARENT_CHUNK_MAX_TOKENS: int = 4000
MIN_CHUNK_SIZE_TOKENS: int = 50
CODE_BLOCK_MAX_TOKENS: int = 1500
CHARS_PER_TOKEN: float = 4.0  # 영어 기준 근사치

# ── Embedding ──
EMBEDDING_MODEL: str = "gemini-embedding-001"
EMBEDDING_BATCH_SIZE: int = 100

# ── ChromaDB ──
CHROMA_DB_PATH: Path = PROJECT_ROOT / "data" / "chroma_db"
CHROMA_COLLECTION: str = "rag_chunks"

# ── Search ──
SEARCH_TOP_K: int = 30
RRF_K: int = 60
FINAL_TOP_K: int = 5

# ── Sync ──
SYNC_MANIFEST_PATH: Path = PROJECT_ROOT / "data" / "sync_manifest.json"
