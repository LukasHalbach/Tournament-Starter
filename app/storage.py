"""Storage interface for uploaded design files.

Phase 1 implements local-folder storage behind this interface. Phase 2 swaps
in an S3-compatible backend (Railway bucket) with presigned direct-to-bucket
uploads, without routes or models needing to change — they only ever see
`storage_key`, `save()`, `open_stream()`, and `delete()`.
"""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import BinaryIO


class LocalStorage:
    def __init__(self, base_dir: str | Path):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save(self, file_storage, submission_token: str) -> tuple[str, int]:
        """Saves an uploaded werkzeug FileStorage. Returns (storage_key, size_bytes)."""
        ext = Path(file_storage.filename or "").suffix
        storage_key = f"{submission_token}/{uuid.uuid4().hex}{ext}"
        dest = self.base_dir / storage_key
        dest.parent.mkdir(parents=True, exist_ok=True)
        file_storage.save(dest)
        return storage_key, dest.stat().st_size

    def open_stream(self, storage_key: str) -> BinaryIO:
        return open(self.base_dir / storage_key, "rb")

    def delete(self, storage_key: str) -> None:
        path = self.base_dir / storage_key
        if path.exists():
            path.unlink()

    def path_for(self, storage_key: str) -> Path:
        return self.base_dir / storage_key
