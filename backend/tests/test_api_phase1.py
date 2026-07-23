"""API integration tests for upload / process / status (Phase 1)."""

from __future__ import annotations

import time

from fastapi.testclient import TestClient


def test_health(client: TestClient) -> None:
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["phase"] == "1"


def test_upload_rejects_bad_extension(client: TestClient, mini_epub_bytes: bytes) -> None:
    res = client.post(
        "/books/upload",
        files={"file": ("notes.txt", mini_epub_bytes, "application/octet-stream")},
    )
    assert res.status_code == 400
    body = res.json()
    assert body["error"]["code"] == "invalid_extension"


def test_upload_and_process_detects_chapters(client: TestClient, mini_epub_bytes: bytes) -> None:
    upload = client.post(
        "/books/upload",
        files={"file": ("mini.epub", mini_epub_bytes, "application/epub+zip")},
    )
    assert upload.status_code == 201, upload.text
    meta = upload.json()
    book_id = meta["book_id"]
    assert meta["processing_status"] == "uploaded"
    assert meta["title"]

    process = client.post(f"/books/{book_id}/process")
    assert process.status_code == 202, process.text

    # Poll until Phase 1 finishes (chapters detected or failed)
    deadline = time.time() + 120
    status = None
    while time.time() < deadline:
        status_res = client.get(f"/books/{book_id}/status")
        assert status_res.status_code == 200
        status = status_res.json()
        if status["processing_status"] == "failed":
            break
        if status["chapter_count"] > 0 and status["processing_status"] == "detecting_chapters":
            # Idle-complete Phase 1
            if status.get("chapters"):
                break
        time.sleep(0.5)

    assert status is not None
    assert status["processing_status"] != "failed", status
    assert status["chapter_count"] >= 1
    assert len(status["chapters"]) >= 1
    assert status["current_stage"] == "detecting_chapters"

    chapters = client.get(f"/books/{book_id}/chapters")
    assert chapters.status_code == 200
    assert len(chapters.json()["chapters"]) >= 1

    got = client.get(f"/books/{book_id}")
    assert got.status_code == 200
    assert got.json()["book_id"] == book_id


def test_process_unknown_book(client: TestClient) -> None:
    res = client.post("/books/missing-book/process")
    assert res.status_code == 404


def test_delete_book(client: TestClient, mini_epub_bytes: bytes) -> None:
    upload = client.post(
        "/books/upload",
        files={"file": ("mini.epub", mini_epub_bytes, "application/epub+zip")},
    )
    book_id = upload.json()["book_id"]
    deleted = client.delete(f"/books/{book_id}")
    assert deleted.status_code == 204
    assert client.get(f"/books/{book_id}").status_code == 404
