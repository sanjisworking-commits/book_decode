"""SQLite persistence for books, chapters, and job status."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from app.config import Settings
from app.domain.enums import BookProcessingStatus, ChapterStatus
from app.utils.ids import utc_now_iso


class SqliteStore:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.path = settings.sqlite_path
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS books (
                    book_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    author TEXT,
                    epub_filename TEXT NOT NULL,
                    processing_status TEXT NOT NULL,
                    language TEXT,
                    chapter_count INTEGER NOT NULL DEFAULT 0,
                    processed_chapter_count INTEGER NOT NULL DEFAULT 0,
                    failed_chapter_count INTEGER NOT NULL DEFAULT 0,
                    upload_timestamp TEXT NOT NULL,
                    completion_timestamp TEXT,
                    error_json TEXT,
                    current_stage TEXT,
                    current_chapter_id TEXT,
                    job_id TEXT,
                    converter TEXT,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS chapters (
                    book_id TEXT NOT NULL,
                    chapter_id TEXT NOT NULL,
                    title TEXT,
                    chapter_number INTEGER,
                    status TEXT NOT NULL,
                    retry_count INTEGER NOT NULL DEFAULT 0,
                    error_json TEXT,
                    order_index INTEGER NOT NULL DEFAULT 0,
                    preview_json TEXT,
                    PRIMARY KEY (book_id, chapter_id),
                    FOREIGN KEY (book_id) REFERENCES books(book_id) ON DELETE CASCADE
                );
                """
            )
            conn.commit()

    def insert_book(self, record: dict[str, Any]) -> None:
        now = utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO books (
                    book_id, title, author, epub_filename, processing_status,
                    language, chapter_count, processed_chapter_count, failed_chapter_count,
                    upload_timestamp, completion_timestamp, error_json, current_stage,
                    current_chapter_id, job_id, converter, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record["book_id"],
                    record["title"],
                    record.get("author"),
                    record["epub_filename"],
                    record["processing_status"],
                    record.get("language"),
                    record.get("chapter_count", 0),
                    record.get("processed_chapter_count", 0),
                    record.get("failed_chapter_count", 0),
                    record["upload_timestamp"],
                    record.get("completion_timestamp"),
                    json.dumps(record["error"]) if record.get("error") else None,
                    record.get("current_stage"),
                    record.get("current_chapter_id"),
                    record.get("job_id"),
                    record.get("converter"),
                    now,
                ),
            )
            conn.commit()

    def get_book(self, book_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM books WHERE book_id = ?", (book_id,)).fetchone()
        return self._book_row_to_dict(row) if row else None

    def list_books(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM books ORDER BY upload_timestamp DESC").fetchall()
        return [self._book_row_to_dict(r) for r in rows]

    def update_book(self, book_id: str, **fields: Any) -> None:
        if not fields:
            return
        fields = dict(fields)
        if "error" in fields:
            err = fields.pop("error")
            fields["error_json"] = json.dumps(err) if err else None
        fields["updated_at"] = utc_now_iso()
        columns = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [book_id]
        with self._connect() as conn:
            conn.execute(f"UPDATE books SET {columns} WHERE book_id = ?", values)
            conn.commit()

    def replace_chapters(self, book_id: str, chapters: list[dict[str, Any]]) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM chapters WHERE book_id = ?", (book_id,))
            for ch in chapters:
                conn.execute(
                    """
                    INSERT INTO chapters (
                        book_id, chapter_id, title, chapter_number, status,
                        retry_count, error_json, order_index, preview_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        book_id,
                        ch["chapter_id"],
                        ch.get("title"),
                        ch.get("chapter_number"),
                        ch.get("status", ChapterStatus.PENDING.value),
                        ch.get("retry_count", 0),
                        json.dumps(ch["error"]) if ch.get("error") else None,
                        ch.get("order_index", 0),
                        json.dumps(ch.get("preview")) if ch.get("preview") is not None else None,
                    ),
                )
            conn.commit()

    def list_chapters(self, book_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM chapters WHERE book_id = ? ORDER BY order_index ASC",
                (book_id,),
            ).fetchall()
        return [self._chapter_row_to_dict(r) for r in rows]

    def delete_book(self, book_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM chapters WHERE book_id = ?", (book_id,))
            conn.execute("DELETE FROM books WHERE book_id = ?", (book_id,))
            conn.commit()

    def reset_all(self) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM chapters")
            conn.execute("DELETE FROM books")
            conn.commit()

    @staticmethod
    def _book_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        error_json = data.pop("error_json", None)
        data["error"] = json.loads(error_json) if error_json else None
        return data

    @staticmethod
    def _chapter_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        error_json = data.pop("error_json", None)
        preview_json = data.pop("preview_json", None)
        data["error"] = json.loads(error_json) if error_json else None
        data["preview"] = json.loads(preview_json) if preview_json else None
        return data


# Re-export for type clarity in services
__all__ = ["SqliteStore", "BookProcessingStatus", "ChapterStatus"]
