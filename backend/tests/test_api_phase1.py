"""API integration tests for Phase 1–2 upload → normalise → chunks."""

from __future__ import annotations

import time

from fastapi.testclient import TestClient


def test_health(client: TestClient) -> None:
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["phase"] == "2"


def test_upload_rejects_bad_extension(client: TestClient, mini_epub_bytes: bytes) -> None:
    res = client.post(
        "/books/upload",
        files={"file": ("notes.txt", mini_epub_bytes, "application/octet-stream")},
    )
    assert res.status_code == 400
    body = res.json()
    assert body["error"]["code"] == "invalid_extension"


def test_upload_and_process_normalises_and_chunks(
    client: TestClient, mini_epub_bytes: bytes
) -> None:
    upload = client.post(
        "/books/upload",
        files={"file": ("mini.epub", mini_epub_bytes, "application/epub+zip")},
    )
    assert upload.status_code == 201, upload.text
    meta = upload.json()
    book_id = meta["book_id"]
    assert meta["processing_status"] == "uploaded"

    process = client.post(f"/books/{book_id}/process")
    assert process.status_code == 202, process.text

    deadline = time.time() + 120
    status = None
    while time.time() < deadline:
        status_res = client.get(f"/books/{book_id}/status")
        assert status_res.status_code == 200
        status = status_res.json()
        if status["processing_status"] == "failed":
            break
        if (
            status["chapter_count"] > 0
            and status["processing_status"] == "preparing_blocks"
            and status.get("chapters")
        ):
            break
        time.sleep(0.5)

    assert status is not None
    assert status["processing_status"] != "failed", status
    assert status["processing_status"] == "preparing_blocks"
    assert status["current_stage"] == "preparing_chapter_blocks"
    assert status["chapter_count"] >= 1

    chapters = client.get(f"/books/{book_id}/chapters")
    assert chapters.status_code == 200
    chapter_id = chapters.json()["chapters"][0]["chapter_id"]

    source = client.get(f"/books/{book_id}/chapters/{chapter_id}/source")
    assert source.status_code == 200, source.text
    source_body = source.json()
    assert source_body["schema_version"] == "2.0"
    assert source_body["source_blocks"]
    block_ids = [b["block_id"] for b in source_body["source_blocks"]]
    assert len(block_ids) == len(set(block_ids))
    assert all(chapter_id in bid for bid in block_ids)

    canonical = client.get(f"/books/{book_id}/canonical")
    assert canonical.status_code == 200, canonical.text
    canonical_body = canonical.json()
    assert canonical_body["schema_version"] == "2.0"
    assert canonical_body["book_id"] == book_id
    assert canonical_body["chapters"]

    chunks = client.get(f"/books/{book_id}/chapters/{chapter_id}/chunks")
    assert chunks.status_code == 200, chunks.text
    chunk_body = chunks.json()
    assert chunk_body["chunks"]
    allowed = set(block_ids)
    for chunk in chunk_body["chunks"]:
        assert set(chunk["block_ids"]).issubset(allowed)


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
