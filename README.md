# Google Drive RAG MCP Server

Google Drive 폴더의 문서를 **Gemini File API**로 검색하고, **MCP 서버**로 제공하는 프로젝트입니다.

## Features

- Google Drive 폴더의 문서 자동 동기화
- Gemini File API를 활용한 문서 검색 및 질의응답
- MCP(Model Context Protocol) 서버로 Claude Desktop, Claude Code 등에 연결

## Setup

### 1. Prerequisites

- Python 3.12+
- Google Cloud 프로젝트 (Drive API + Gemini API 활성화)

### 2. Google Cloud 설정

1. [Google Cloud Console](https://console.cloud.google.com/)에서 프로젝트 생성
2. **Google Drive API** 활성화
3. **OAuth 2.0 클라이언트 ID** 생성 (데스크톱 앱 유형)
4. JSON 파일 다운로드 → `credentials/credentials.json`에 저장
5. [Google AI Studio](https://aistudio.google.com/apikey)에서 **Gemini API 키** 발급

### 3. 설치

```bash
# 가상환경 생성 및 활성화
python -m venv .venv
source .venv/Scripts/activate    # Windows Git Bash
# .venv\Scripts\activate         # Windows CMD

# 의존성 설치
pip install -r requirements.txt
```

### 4. 환경변수 설정

```bash
cp .env.example .env
```

`.env` 파일을 편집하여 값을 입력:

```env
GOOGLE_API_KEY=your-gemini-api-key
GOOGLE_DRIVE_FOLDER_ID=your-folder-id
GOOGLE_CREDENTIALS_PATH=credentials/credentials.json
GEMINI_MODEL=gemini-2.0-flash
```

> **Drive 폴더 ID 확인**: Google Drive에서 대상 폴더를 열면 URL이
> `https://drive.google.com/drive/folders/XXXXXXX` 형태입니다. `XXXXXXX` 부분이 폴더 ID입니다.

### 5. 최초 인증

첫 실행 시 브라우저가 열리며 Google 계정 인증을 요청합니다. 인증 후 `credentials/token.json`에 토큰이 저장됩니다.

## Usage

### MCP 서버 실행

```bash
python -m src.mcp_server
```

### Claude Desktop 연결

`claude_desktop_config.json`에 추가:

```json
{
  "mcpServers": {
    "google-drive-rag": {
      "command": "python",
      "args": ["-m", "src.mcp_server"],
      "cwd": "/path/to/Python_rag",
      "env": {
        "GOOGLE_API_KEY": "your-key"
      }
    }
  }
}
```

### MCP Tools

| Tool | Description |
|------|-------------|
| `sync_drive_files` | Google Drive 폴더에서 문서를 가져와 Gemini에 업로드 |
| `query_documents` | 동기화된 문서에서 질의응답 |
| `list_synced_sources` | 동기화된 문서 목록 조회 |

## Supported File Types

| Google Workspace | Export Format |
|------------------|---------------|
| Google Docs | PDF |
| Google Sheets | CSV |
| Google Slides | PDF |

일반 파일: PDF, TXT, CSV, HTML, DOCX, XLSX, PPTX

## License

MIT
