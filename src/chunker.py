"""계층적 청킹: Parent-Child 구조로 문서를 분할."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from src.config import (
    CHARS_PER_TOKEN,
    CHUNK_OVERLAP_TOKENS,
    CHUNK_SIZE_TOKENS,
    CODE_BLOCK_MAX_TOKENS,
    MIN_CHUNK_SIZE_TOKENS,
    PARENT_CHUNK_MAX_TOKENS,
)
from src.parser import ParsedBlock, ParsedDocument


@dataclass
class ChunkMetadata:
    source_file: str
    drive_id: str
    chapter: str
    section: str
    page_start: int
    page_end: int
    block_type: str  # prose | code | table | mixed
    is_parent: bool
    parent_id: str
    language: str  # ko | en


@dataclass
class Chunk:
    chunk_id: str
    text: str
    metadata: ChunkMetadata


def _estimate_tokens(text: str) -> int:
    """토큰 수 근사 추정."""
    # 한국어 비율에 따라 조정 (한국어는 글자당 ~1 토큰)
    korean_chars = sum(1 for c in text if "\uac00" <= c <= "\ud7a3")
    total_chars = len(text)
    if total_chars == 0:
        return 0
    ko_ratio = korean_chars / total_chars
    chars_per_tok = 1.5 * ko_ratio + CHARS_PER_TOKEN * (1 - ko_ratio)
    return int(total_chars / chars_per_tok)


def _detect_language(text: str) -> str:
    """한국어/영어 감지."""
    korean_chars = sum(1 for c in text if "\uac00" <= c <= "\ud7a3")
    return "ko" if korean_chars > len(text) * 0.15 else "en"


_id_counter: int = 0


def _make_id(text: str, prefix: str) -> str:
    """텍스트 + 카운터 기반 고유 ID 생성."""
    global _id_counter
    _id_counter += 1
    h = hashlib.sha256(f"{text}{_id_counter}".encode()).hexdigest()[:16]
    return f"{prefix}_{h}"


def _split_text(text: str, chunk_chars: int, overlap_chars: int) -> list[str]:
    """텍스트를 지정 크기로 분할. 문단 → 문장 경계 우선."""
    if len(text) <= chunk_chars:
        return [text]

    chunks: list[str] = []
    start = 0

    while start < len(text):
        end = start + chunk_chars

        if end >= len(text):
            chunks.append(text[start:])
            break

        # 문단 경계 탐색
        split_at = text.rfind("\n\n", start, end)
        if split_at <= start:
            # 문장 경계 탐색
            split_at = text.rfind(". ", start, end)
            if split_at <= start:
                split_at = text.rfind(" ", start, end)
                if split_at <= start:
                    split_at = end

        split_at += 1  # 구분자 포함
        chunks.append(text[start:split_at].strip())
        start = max(start + 1, split_at - overlap_chars)

    return [c for c in chunks if c]


def _build_sections(blocks: list[ParsedBlock]) -> list[dict]:
    """블록 리스트를 섹션 단위로 그룹화."""
    sections: list[dict] = []
    current_chapter = ""
    current_section = ""
    current_blocks: list[ParsedBlock] = []

    def _flush():
        if current_blocks:
            sections.append({
                "chapter": current_chapter,
                "section": current_section,
                "blocks": list(current_blocks),
            })
            current_blocks.clear()

    for block in blocks:
        if block.block_type == "heading":
            if block.heading_level == 1:
                _flush()
                current_chapter = block.text
                current_section = ""
            elif block.heading_level in (2, 3):
                _flush()
                current_section = block.text
            continue
        current_blocks.append(block)

    _flush()
    return sections


def chunk_document(doc: ParsedDocument) -> list[Chunk]:
    """ParsedDocument를 Parent-Child 청크로 분할."""
    chunk_chars = int(CHUNK_SIZE_TOKENS * CHARS_PER_TOKEN)
    overlap_chars = int(CHUNK_OVERLAP_TOKENS * CHARS_PER_TOKEN)
    parent_max_chars = int(PARENT_CHUNK_MAX_TOKENS * CHARS_PER_TOKEN)
    min_chars = int(MIN_CHUNK_SIZE_TOKENS * CHARS_PER_TOKEN)
    code_max_chars = int(CODE_BLOCK_MAX_TOKENS * CHARS_PER_TOKEN)

    sections = _build_sections(doc.blocks)
    all_chunks: list[Chunk] = []

    for section in sections:
        blocks: list[ParsedBlock] = section["blocks"]
        if not blocks:
            continue

        chapter = section["chapter"]
        section_name = section["section"]
        page_start = blocks[0].page_number
        page_end = blocks[-1].page_number

        # ── Parent Chunk 생성 ──
        parent_text_parts: list[str] = []
        block_types: set[str] = set()
        for b in blocks:
            parent_text_parts.append(b.text)
            block_types.add(b.block_type)

        parent_text = "\n\n".join(parent_text_parts)
        # parent가 너무 크면 분할
        if len(parent_text) > parent_max_chars:
            parent_text = parent_text[:parent_max_chars]

        parent_type = "mixed" if len(block_types) > 1 else block_types.pop()
        lang = _detect_language(parent_text)
        parent_id = _make_id(parent_text, "parent")

        parent_chunk = Chunk(
            chunk_id=parent_id,
            text=parent_text,
            metadata=ChunkMetadata(
                source_file=doc.source_file,
                drive_id=doc.drive_id,
                chapter=chapter,
                section=section_name,
                page_start=page_start,
                page_end=page_end,
                block_type=parent_type,
                is_parent=True,
                parent_id=parent_id,
                language=lang,
            ),
        )
        all_chunks.append(parent_chunk)

        # ── Child Chunks 생성 ──
        for block in blocks:
            if _estimate_tokens(block.text) < MIN_CHUNK_SIZE_TOKENS:
                continue

            if block.block_type == "code":
                # 코드 블록: 가능한 한 통째로 유지
                if len(block.text) <= code_max_chars:
                    child_texts = [block.text]
                else:
                    child_texts = _split_text(block.text, chunk_chars, overlap_chars)
                for ct in child_texts:
                    # 코드 청크에 컨텍스트 접두사 추가
                    prefix = ""
                    if chapter or section_name:
                        prefix = f"// [{chapter}: {section_name}]\n"
                    tagged = prefix + ct
                    cid = _make_id(tagged, "child")
                    all_chunks.append(Chunk(
                        chunk_id=cid,
                        text=tagged,
                        metadata=ChunkMetadata(
                            source_file=doc.source_file,
                            drive_id=doc.drive_id,
                            chapter=chapter,
                            section=section_name,
                            page_start=block.page_number,
                            page_end=block.page_number,
                            block_type="code",
                            is_parent=False,
                            parent_id=parent_id,
                            language=lang,
                        ),
                    ))

            elif block.block_type == "table":
                # 테이블: 통째로 유지
                cid = _make_id(block.text, "child")
                all_chunks.append(Chunk(
                    chunk_id=cid,
                    text=block.text,
                    metadata=ChunkMetadata(
                        source_file=doc.source_file,
                        drive_id=doc.drive_id,
                        chapter=chapter,
                        section=section_name,
                        page_start=block.page_number,
                        page_end=block.page_number,
                        block_type="table",
                        is_parent=False,
                        parent_id=parent_id,
                        language=lang,
                    ),
                ))

            else:
                # 산문: 재귀적 분할
                parts = _split_text(block.text, chunk_chars, overlap_chars)
                for part in parts:
                    if len(part) < min_chars:
                        continue
                    cid = _make_id(part, "child")
                    all_chunks.append(Chunk(
                        chunk_id=cid,
                        text=part,
                        metadata=ChunkMetadata(
                            source_file=doc.source_file,
                            drive_id=doc.drive_id,
                            chapter=chapter,
                            section=section_name,
                            page_start=block.page_number,
                            page_end=block.page_number,
                            block_type="prose",
                            is_parent=False,
                            parent_id=parent_id,
                            language=lang,
                        ),
                    ))

    return all_chunks
