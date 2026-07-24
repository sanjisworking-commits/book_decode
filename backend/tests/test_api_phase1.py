"""API integration tests for Phase 1–6 (mock LLM)."""

from __future__ import annotations

import time

from fastapi.testclient import TestClient


def test_health(client: TestClient) -> None:
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["phase"] == "6"


def test_upload_rejects_bad_extension(client: TestClient, mini_epub_bytes: bytes) -> None:
    res = client.post(
        "/books/upload",
        files={"file": ("notes.txt", mini_epub_bytes, "application/octet-stream")},
    )
    assert res.status_code == 400
    body = res.json()
    assert body["error"]["code"] == "invalid_extension"


def test_upload_and_process_completes_validated_spine(
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
        if status["processing_status"] in {"completed", "completed_with_errors"}:
            break
        time.sleep(0.5)

    assert status is not None
    assert status["processing_status"] != "failed", status
    assert status["processing_status"] in {"completed", "completed_with_errors"}
    assert status["current_stage"] == "book_ready"
    assert status["chapter_count"] >= 1
    assert status["processed_chapter_count"] >= 1

    chapters = client.get(f"/books/{book_id}/chapters")
    assert chapters.status_code == 200
    chapter = chapters.json()["chapters"][0]
    chapter_id = chapter["chapter_id"]
    assert chapter["status"] == "completed"

    source = client.get(f"/books/{book_id}/chapters/{chapter_id}/source")
    assert source.status_code == 200, source.text
    source_body = source.json()
    assert source_body["schema_version"] == "2.0"
    block_ids = [b["block_id"] for b in source_body["source_blocks"]]
    allowed = set(block_ids)

    spine = client.get(f"/books/{book_id}/chapters/{chapter_id}/spine")
    assert spine.status_code == 200, spine.text
    body = spine.json()
    assert body["language_modes"] == ["en", "hinglish"]
    assert body.get("nodes")
    assert body.get("validation", {}).get("schema_valid") is True
    assert body.get("validation", {}).get("source_refs_valid") is True
    for node in body["nodes"]:
        assert set(node.get("source_block_ids") or []).issubset(allowed)
        if node.get("statement_en"):
            assert node.get("statement_hinglish")


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
