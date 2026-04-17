# Google Drive RAG MCP Server

## Project Overview
Google Drive 폴더의 문서를 Gemini File API에 업로드하여 검색/질의응답을 수행하고,
이를 MCP(Model Context Protocol) 서버로 래핑하여 외부 AI 클라이언트에서 사용하는 프로젝트.

## Tech Stack
- **Language**: Python 3.12
- **LLM & File Search**: Google Gemini API - File API (`google-genai`)
- **Document Source**: Google Drive API (`google-api-python-client`)
- **MCP Server**: `mcp` Python SDK (stdio transport)
- **Auth**: Google OAuth 2.0 (Desktop App)

## Architecture
```
Google Drive Folder
        │
        ▼  (google-api-python-client)
   Download Files (PDF/Docs/Sheets export)
        │
        ▼  (google-genai File API)
   Upload to Gemini File Storage
        │
        ▼  (google-genai generate_content)
   Per-file search → Synthesize answer
        │
        ▼  (mcp SDK)
   MCP Server (stdio) → Claude Desktop / Claude Code / etc.
```

## Project Structure
```
Python_rag/
├── CLAUDE.md
├── README.md
├── requirements.txt
├── .env.example
├── .gitignore
├── src/
│   ├── __init__.py
│   ├── config.py         # 환경변수 로드 및 설정
│   ├── drive.py          # Google Drive 문서 다운로드
│   ├── gemini_files.py   # Gemini File API 업로드/관리
│   ├── rag.py            # RAG 파이프라인 (파일 컨텍스트 + 생성)
│   └── mcp_server.py     # MCP 서버 엔트리포인트
├── data/
│   └── downloads/        # (gitignore) Drive에서 다운로드한 파일 임시 저장
├── credentials/          # (gitignore) Google OAuth 자격증명
└── tests/
    ├── __init__.py
    └── test_rag.py
```

## Key Commands
```bash
# 가상환경 활성화
source .venv/Scripts/activate    # Windows Git Bash
.venv\Scripts\activate           # Windows CMD

# 의존성 설치
pip install -r requirements.txt

# MCP 서버 실행 (stdio)
python -m src.mcp_server

# 테스트
pytest tests/ -v
```

## Environment Variables (.env)
```
GOOGLE_API_KEY=              # Gemini API 키 (Google AI Studio에서 발급)
GOOGLE_DRIVE_FOLDER_ID=      # 대상 Google Drive 폴더 ID
GOOGLE_CREDENTIALS_PATH=credentials/credentials.json
GEMINI_MODEL=gemini-2.0-flash
```

## MCP Tools (exposed to AI clients)
- `sync_files`: Google Drive → Gemini File API 동기화
- `query`: 업로드된 문서 기반 질의응답
- `list_sources`: 동기화된 문서 목록 조회

## Architecture Decisions
- **Gemini File API**: 자체 임베딩/벡터DB 없이 Gemini가 파일을 직접 파싱하고 검색 (PDF, Docs, Sheets 등 네이티브 지원)
- **파일별 개별 검색 + 종합**: Gemini 1000페이지 제한 대응. 각 파일을 개별 검색 후 결과를 종합하여 최종 답변 생성
- **MCP stdio transport**: Claude Desktop, Claude Code 등에서 프로세스 기반으로 바로 연결
- **Google Workspace export**: Docs→PDF, Sheets→CSV, Slides→PDF로 변환 후 Gemini에 업로드

## Conventions
- 모든 소스 코드는 `src/` 하위에 위치
- 환경변수는 `python-dotenv`로 로드, 절대 하드코딩 금지
- 타입 힌트 적극 사용
- 한국어 주석 허용
