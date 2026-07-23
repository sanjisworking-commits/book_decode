"""Filesystem artefact helpers."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from app.config import Settings


class FilesystemStore:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def book_upload_dir(self, book_id: str) -> Path:
        path = self.settings.upload_dir / book_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def book_processed_dir(self, book_id: str) -> Path:
        path = self.settings.processed_dir / book_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def book_dir(self, book_id: str) -> Path:
        path = self.settings.books_dir / book_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def epub_path(self, book_id: str, filename: str) -> Path:
        return self.book_upload_dir(book_id) / filename

    def docling_json_path(self, book_id: str) -> Path:
        return self.book_processed_dir(book_id) / "docling.json"

    def chapters_preview_path(self, book_id: str) -> Path:
        return self.book_processed_dir(book_id) / "chapters_preview.json"

    def metadata_path(self, book_id: str) -> Path:
        return self.book_dir(book_id) / "metadata.json"

    def write_json(self, path: Path, payload: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def read_json(self, path: Path) -> Any:
        return json.loads(path.read_text(encoding="utf-8"))

    def delete_book_artefacts(self, book_id: str) -> None:
        for root in (
            self.settings.upload_dir / book_id,
            self.settings.processed_dir / book_id,
            self.settings.books_dir / book_id,
        ):
            if root.exists():
                shutil.rmtree(root)

    def reset_all(self) -> None:
        for root in (
            self.settings.upload_dir,
            self.settings.processed_dir,
            self.settings.books_dir,
            self.settings.log_dir,
        ):
            if root.exists():
                shutil.rmtree(root)
            root.mkdir(parents=True, exist_ok=True)
