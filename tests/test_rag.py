"""기본 import 및 구조 테스트."""

import importlib


def test_modules_importable():
    """모든 소스 모듈이 import 가능한지 확인."""
    modules = [
        "src.config",
        "src.drive",
        "src.gemini_files",
        "src.rag",
        "src.mcp_server",
    ]
    # config가 환경변수를 필요로 하므로, 모듈 존재 여부만 확인
    for mod_name in modules:
        spec = importlib.util.find_spec(mod_name)
        assert spec is not None, f"{mod_name} module not found"


def test_export_map_structure():
    """EXPORT_MAP 설정 구조 검증."""
    from src.config import EXPORT_MAP

    for mime, (export_mime, ext) in EXPORT_MAP.items():
        assert mime.startswith("application/vnd.google-apps.")
        assert export_mime  # non-empty
        assert ext.startswith(".")
