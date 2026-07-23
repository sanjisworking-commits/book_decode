"""API integration tests for Phase 1–3 (mock LLM)."""

from __future__ import annotations

import time

from fastapi.testclient import TestClient


def test_health(client: TestClient) -> None:
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["phase"] == "3"


def test_upload_rejects_bad_extension(client: TestClient, mini_epub_bytes: bytes) -> None:
    res = client.post(
        "/books/upload",
        files={"file": ("notes.txt", mini_epub_bytes, "application/octet-stream")},
    )
    assert res.status_code == 400
    body = res.json()
    assert body["error"]["code"] == "invalid_extension"


def test_upload_and_process_extracts_spine_candidate(
    client: TestClient, mini_epub_bytes: bytes
) -> None:
    upload = client.post(
        "/books/upload",
        files={"file": ("mini.epub", mini_epub_bytes, "application/epub+zip")},
    )
    assert upload.status_code == 201, upload.text
    book_id = upload.json()["book_id"]

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
            and status["processing_status"] == "analysing_chapters"
            and status.get("chapters")
        ):
            break
        time.sleep(0.5)

    assert status is not None
    assert status["processing_status"] != "failed", status
    assert status["processing_status"] == "analysing_chapters"
    assert status["current_stage"] == "analysing_chapters"
    assert status["chapter_count"] >= 1

    chapters = client.get(f"/books/{book_id}/chapters")
    assert chapters.status_code == 200
    chapter_id = chapters.json()["chapters"][0]["chapter_id"]

    source = client.get(f"/books/{book_id}/chapters/{chapter_id}/source")
    assert source.status_code == 200
    assert source.json()["source_blocks"]

    spine = client.get(f"/books/{book_id}/chapters/{chapter_id}/spine")
    assert spine.status_code == 200, spine.text
    body = spine.json()
    assert body["book_id"] == book_id
    assert body["chapter_id"] == chapter_id
    assert body["language_modes"] == ["en"]
    assert body.get("nodes")
    assert all(n.get("statement_hinglish") is None for n in body["nodes"])
    allowed = {b["block_id"] for b in source.json()["source_blocks"]}
    for node in body["nodes"]:
        assert set(node.get("source_block_ids") or []).issubset(allowed)


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
