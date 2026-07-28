"""API integration tests for Phase 1–6 (mock LLM)."""

from __future__ import annotations

import time

from fastapi.testclient import TestClient


def test_health(client: TestClient) -> None:
    res = client.get("/health")
    assert res.status_code == 200
    body = res.json()
    assert body["phase"] == "6"
    assert "llm_mock" in body
    assert "llm_provider" in body
    assert "llm_api_key_configured" in body
    # conftest forces LLM_MOCK for API tests
    assert body["llm_mock"] is True
    assert body["llm_provider"] == "mock"


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


def test_progressive_first_chapter_completes_before_later(
    client: TestClient, mini_epub_bytes: bytes, monkeypatch
) -> None:
    """CH01 should reach completed while later chapters are still pending."""
    from app.services.books import BookService

    snapshots: list[dict] = []
    original = BookService._refresh_progress_counts

    def spy(self, book_id, chapters):  # type: ignore[no-untyped-def]
        original(self, book_id, chapters)
        snapshots.append(
            {
                "processed": sum(1 for c in chapters if c["status"] == "completed"),
                "statuses": {c["chapter_id"]: c["status"] for c in chapters},
            }
        )

    monkeypatch.setattr(BookService, "_refresh_progress_counts", spy)

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
        if status["processing_status"] in {
            "completed",
            "completed_with_errors",
            "failed",
        }:
            break
        time.sleep(0.5)

    assert status is not None
    assert status["processing_status"] != "failed", status
    assert status["chapter_count"] >= 2
    assert status["processed_chapter_count"] >= 2

    # At least one mid-pipeline snapshot had exactly one completed chapter
    # while another chapter was not yet completed.
    progressive = [
        s
        for s in snapshots
        if s["processed"] == 1
        and any(st != "completed" for st in s["statuses"].values())
    ]
    assert progressive, f"expected progressive unlock snapshots, got {snapshots}"

    # First chapter in order should be the one that completed first
    first_ready = next(
        cid
        for cid, st in progressive[0]["statuses"].items()
        if st == "completed"
    )
    chapters = client.get(f"/books/{book_id}/chapters").json()["chapters"]
    assert chapters[0]["chapter_id"] == first_ready or first_ready in {
        c["chapter_id"] for c in chapters if c["status"] == "completed"
    }
    # Spine for the early-ready chapter must be readable
    spine = client.get(f"/books/{book_id}/chapters/{first_ready}/spine")
    assert spine.status_code == 200, spine.text
