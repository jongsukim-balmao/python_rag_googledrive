# Google Drive RAG MCP Server

## Project Overview
Google Drive 폴더의 문서를 파싱 → 청킹 → 임베딩하여 ChromaDB에 저장하고,
하이브리드 검색(벡터+BM25) + Gemini 생성으로 질의응답을 수행하는 MCP 서버.

## Tech Stack
- **Language**: Python 3.12
- **LLM**: Google Gemini API - gemini-2.5-flash (`google-genai`)
- **Embedding**: Gemini gemini-embedding-001 (무료)
- **Vector Store**: ChromaDB (로컬 PersistentClient)
- **Keyword Search**: BM25 (`rank-bm25`)
- **PDF Parsing**: PyMuPDF (`pymupdf`)
- **Document Source**: Google Drive API (`google-api-python-client`)
- **MCP Server**: `mcp` Python SDK (stdio transport)

## Architecture
```
Google Drive Folder
        │
        ▼  google-api-python-client
   Download Files (PDF export)
        │
        ▼  PyMuPDF (parser.py)
   구조 인식 파싱 (heading/code/table/prose 감지)
        │
        ▼  chunker.py
   Parent-Child 계층 청킹 (800토큰 child + 4000토큰 parent)
        │
        ▼  Gemini embedding API (embeddings.py)
   임베딩 생성 → ChromaDB 저장 (vectorstore.py)
        │
        ▼  search.py
   하이브리드 검색 (벡터 + BM25 + RRF 병합)
        │
        ▼  Gemini generate_content (rag.py)
   Parent 청크 컨텍스트로 답변 생성
        │
        ▼  mcp_server.py
   MCP Server (stdio) → Claude Desktop / Claude Code
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
│   ├── __main__.py        # python -m src 진입점
│   ├── config.py          # 환경변수 및 상수
│   ├── drive.py           # Google Drive OAuth + 파일 다운로드
│   ├── parser.py          # PyMuPDF PDF 구조 인식 파싱
│   ├── chunker.py         # Parent-Child 계층 청킹
│   ├── embeddings.py      # Gemini 임베딩 함수 (ChromaDB 연동)
│   ├── vectorstore.py     # ChromaDB CRUD
│   ├── search.py          # 하이브리드 검색 (벡터+BM25+RRF)
│   ├── sync.py            # 증분 동기화 (매니페스트 기반)
│   ├── rag.py             # RAG 파이프라인 (검색 + 생성)
│   └── mcp_server.py      # MCP 서버 (tool 노출)
├── data/
│   ├── chroma_db/         # (gitignore) ChromaDB 영구 저장소
│   ├── downloads/         # (gitignore) Drive 다운로드 임시 파일
│   └── sync_manifest.json # (gitignore) 동기화 상태
├── credentials/           # (gitignore) Google OAuth 자격증명
└── tests/
    ├── __init__.py
    └── test_rag.py
```

## Key Commands
```bash
source .venv/Scripts/activate    # Windows Git Bash
pip install -r requirements.txt
python -m src.mcp_server         # MCP 서버 실행
pytest tests/ -v                 # 테스트
```

## MCP Tools
- `sync_drive_files`: Google Drive → ChromaDB 증분 동기화
- `query_documents(question, source_filter?)`: 하이브리드 검색 + 답변 생성
- `list_synced_sources`: 동기화된 문서 목록 및 통계

## Architecture Decisions
- **Parent-Child 청킹**: child(800토큰)으로 정밀 검색, parent(4000토큰)로 맥락 제공
- **하이브리드 검색**: 벡터(의미) + BM25(키워드) + RRF 병합 → 코드 함수명 등 정확 매칭 보강
- **증분 동기화**: sync_manifest.json으로 변경 파일만 재처리
- **ChromaDB PersistentClient**: 서버 재시작 후 즉시 검색 가능, 별도 DB 서버 불필요

## Conventions
- 모든 소스 코드는 `src/` 하위에 위치
- 환경변수는 `python-dotenv`로 로드, 절대 하드코딩 금지
- 타입 힌트 적극 사용
- 한국어 주석 허용
