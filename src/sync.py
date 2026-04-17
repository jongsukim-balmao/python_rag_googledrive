"""증분 동기화: Drive 변경 파일만 감지하여 재임베딩."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from src.chunker import chunk_document
from src.config import GOOGLE_DRIVE_FOLDER_ID, SYNC_MANIFEST_PATH
from src.drive import download_file, list_files
from src.parser import parse_file
from src.search import build_bm25_index
from src.vectorstore import delete_by_drive_id, upsert_chunks


def _load_manifest() -> dict:
    if SYNC_MANIFEST_PATH.exists():
        return json.loads(SYNC_MANIFEST_PATH.read_text(encoding="utf-8"))
    return {}


def _save_manifest(manifest: dict) -> None:
    SYNC_MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    SYNC_MANIFEST_PATH.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def sync(folder_id: str | None = None) -> dict:
    """Google Drive와 ChromaDB를 증분 동기화.

    Returns:
        {"added": [...], "updated": [...], "unchanged": [...], "deleted": [...]}
    """
    folder_id = folder_id or GOOGLE_DRIVE_FOLDER_ID
    manifest = _load_manifest()
    drive_files = list_files(folder_id)

    result: dict[str, list] = {
        "added": [],
        "updated": [],
        "unchanged": [],
        "deleted": [],
    }

    drive_ids_current = set()

    for f in drive_files:
        fid = f["id"]
        fname = f["name"]
        modified = f.get("modifiedTime", "")
        drive_ids_current.add(fid)

        prev = manifest.get(fid)

        # 변경 여부 판단
        if prev and prev.get("modified_time") == modified:
            result["unchanged"].append(fname)
            continue

        action = "updated" if prev else "added"

        # 기존 청크 삭제 (업데이트인 경우)
        if prev:
            delete_by_drive_id(fid)

        # 다운로드 → 파싱 → 청킹 → 임베딩 → 저장
        print(f"  [{action}] {fname}: downloading...", flush=True)
        local_path = download_file(fid, fname, f["mimeType"])
        print(f"  [{action}] {fname}: parsing...", flush=True)
        parsed = parse_file(local_path, fname, fid)
        print(f"  [{action}] {fname}: chunking ({len(parsed.blocks)} blocks)...", flush=True)
        chunks = chunk_document(parsed)
        print(f"  [{action}] {fname}: embedding {len(chunks)} chunks...", flush=True)
        upsert_chunks(chunks)
        print(f"  [{action}] {fname}: done!", flush=True)

        # 매니페스트 업데이트
        manifest[fid] = {
            "name": fname,
            "modified_time": modified,
            "chunk_count": len(chunks),
            "last_synced": datetime.now(timezone.utc).isoformat(),
        }

        result[action].append(fname)

    # 삭제된 파일 감지
    for fid in list(manifest.keys()):
        if fid not in drive_ids_current:
            delete_by_drive_id(fid)
            result["deleted"].append(manifest[fid]["name"])
            del manifest[fid]

    _save_manifest(manifest)

    # BM25 인덱스 재구축
    build_bm25_index()

    return result
