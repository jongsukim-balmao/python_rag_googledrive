"""PDF/텍스트 파일 파싱: PyMuPDF를 이용한 구조 인식 텍스트 추출."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf


@dataclass
class ParsedBlock:
    """파싱된 텍스트 블록."""
    text: str
    block_type: str  # prose | code | table | heading
    page_number: int
    heading_level: int = 0  # heading인 경우 1~3


@dataclass
class ParsedDocument:
    """파싱된 문서 전체."""
    source_file: str
    drive_id: str
    blocks: list[ParsedBlock] = field(default_factory=list)
    total_pages: int = 0


# 고정폭 폰트 패턴 (코드 블록 감지용)
_MONO_FONTS = re.compile(
    r"(courier|consolas|mono|menlo|source.?code|fira.?code|dejavu.?sans.?mono"
    r"|liberation.?mono|roboto.?mono|inconsolata)",
    re.IGNORECASE,
)


def _is_monospace(font_name: str) -> bool:
    return bool(_MONO_FONTS.search(font_name))


def _detect_heading(span: dict, page_median_size: float) -> int:
    """폰트 크기와 볼드 여부로 heading 레벨 추정."""
    size = span.get("size", 0)
    flags = span.get("flags", 0)
    is_bold = bool(flags & 2 ** 4)  # bit 4 = bold

    if size >= page_median_size * 1.8:
        return 1
    if size >= page_median_size * 1.4 and is_bold:
        return 2
    if size >= page_median_size * 1.2 and is_bold:
        return 3
    return 0


def _get_median_font_size(page: pymupdf.Page) -> float:
    """페이지의 중앙값 폰트 크기 반환."""
    sizes: list[float] = []
    blocks = page.get_text("dict", flags=pymupdf.TEXT_PRESERVE_WHITESPACE)
    for block in blocks.get("blocks", []):
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                if span.get("text", "").strip():
                    sizes.append(span["size"])
    if not sizes:
        return 12.0
    sizes.sort()
    return sizes[len(sizes) // 2]


def parse_pdf(file_path: Path, source_file: str, drive_id: str) -> ParsedDocument:
    """PDF 파일을 구조 인식하여 블록 리스트로 파싱."""
    doc = pymupdf.open(str(file_path))
    parsed = ParsedDocument(
        source_file=source_file,
        drive_id=drive_id,
        total_pages=len(doc),
    )

    for page_num, page in enumerate(doc, start=1):
        median_size = _get_median_font_size(page)

        # 테이블 감지
        tables = page.find_tables()
        table_rects = [t.bbox for t in tables.tables] if tables else []

        # dict 모드로 텍스트 추출
        page_dict = page.get_text("dict", flags=pymupdf.TEXT_PRESERVE_WHITESPACE)

        current_code: list[str] = []
        current_prose: list[str] = []

        def _flush_prose():
            text = "\n".join(current_prose).strip()
            if text:
                parsed.blocks.append(ParsedBlock(
                    text=text, block_type="prose", page_number=page_num,
                ))
            current_prose.clear()

        def _flush_code():
            text = "\n".join(current_code).strip()
            if text:
                parsed.blocks.append(ParsedBlock(
                    text=text, block_type="code", page_number=page_num,
                ))
            current_code.clear()

        for block in page_dict.get("blocks", []):
            if block.get("type") != 0:  # 이미지 블록 스킵
                continue

            # 테이블 영역 내 블록은 건너뜀 (별도 처리)
            block_rect = pymupdf.Rect(block["bbox"])
            in_table = any(
                block_rect.intersects(pymupdf.Rect(tr)) for tr in table_rects
            )
            if in_table:
                continue

            for line in block.get("lines", []):
                line_text_parts: list[str] = []
                line_is_code = False
                line_heading_level = 0

                for span in line.get("spans", []):
                    text = span.get("text", "")
                    if not text.strip():
                        line_text_parts.append(text)
                        continue

                    if _is_monospace(span.get("font", "")):
                        line_is_code = True

                    hl = _detect_heading(span, median_size)
                    if hl > line_heading_level:
                        line_heading_level = hl

                    line_text_parts.append(text)

                line_text = "".join(line_text_parts).rstrip()
                if not line_text.strip():
                    continue

                # heading 감지
                if line_heading_level > 0:
                    _flush_code()
                    _flush_prose()
                    parsed.blocks.append(ParsedBlock(
                        text=line_text.strip(),
                        block_type="heading",
                        page_number=page_num,
                        heading_level=line_heading_level,
                    ))
                    continue

                # 코드 vs 산문 분리
                if line_is_code:
                    _flush_prose()
                    current_code.append(line_text)
                else:
                    _flush_code()
                    current_prose.append(line_text)

        _flush_code()
        _flush_prose()

        # 테이블 처리
        if tables:
            for table in tables.tables:
                md_lines: list[str] = []
                data = table.extract()
                if not data:
                    continue
                # 헤더
                header = data[0]
                md_lines.append("| " + " | ".join(str(c or "") for c in header) + " |")
                md_lines.append("| " + " | ".join("---" for _ in header) + " |")
                for row in data[1:]:
                    md_lines.append("| " + " | ".join(str(c or "") for c in row) + " |")
                parsed.blocks.append(ParsedBlock(
                    text="\n".join(md_lines),
                    block_type="table",
                    page_number=page_num,
                ))

    doc.close()
    return parsed


def parse_text_file(file_path: Path, source_file: str, drive_id: str) -> ParsedDocument:
    """텍스트/CSV 파일 파싱."""
    text = file_path.read_text(encoding="utf-8", errors="replace")
    return ParsedDocument(
        source_file=source_file,
        drive_id=drive_id,
        blocks=[ParsedBlock(text=text, block_type="prose", page_number=1)],
        total_pages=1,
    )


def parse_file(file_path: Path, source_file: str, drive_id: str) -> ParsedDocument:
    """파일 확장자에 따라 적절한 파서 선택."""
    suffix = file_path.suffix.lower()
    if suffix == ".pdf":
        return parse_pdf(file_path, source_file, drive_id)
    elif suffix in (".txt", ".csv", ".html"):
        return parse_text_file(file_path, source_file, drive_id)
    else:
        return parse_text_file(file_path, source_file, drive_id)
