"""Phase 3: Argument Spine extraction via reasoning LLM (per chunk)."""

from __future__ import annotations

import json
import logging
from typing import Any

from app.config import Settings
from app.domain.enums import BookProcessingStatus, ChapterStatus, UIStage
from app.pipelines.llm_bind import bind_llm
from app.pipelines.validate_spine import (
    strip_invalid_source_refs,
    validate_source_refs,
    validate_spine_schema,
)
from app.prompts.loader import load_prompt
from app.services.llm import LLMError
from app.storage.filesystem import FilesystemStore
from app.storage.sqlite_store import SqliteStore
from app.utils.ids import utc_now_iso

logger = logging.getLogger(__name__)


class ExtractPipeline:
    def __init__(self, db: SqliteStore, fs: FilesystemStore, settings: Settings | None = None) -> None:
        self.db = db
        self.fs = fs
        self.settings, self.llm = bind_llm(settings)

    def reload_llm(self, settings: Settings | None = None) -> None:
        self.settings, self.llm = bind_llm(settings)

    def run(self, book_id: str) -> None:
        book = self.db.get_book(book_id)
        if not book:
            logger.error("Extract requested for unknown book_id=%s", book_id)
            return

        job_id = book.get("job_id")
        chapters = self.db.list_chapters(book_id)
        if not chapters:
            self._fail(book, job_id, "No chapters available for extraction.")
            return

        self.db.update_book(
            book_id,
            processing_status=BookProcessingStatus.ANALYSING_CHAPTERS.value,
            current_stage=UIStage.ANALYSING_CHAPTERS.value,
            job_id=job_id,
        )

        updated: list[dict[str, Any]] = []
        extract_summaries: list[dict[str, Any]] = []

        for ch in chapters:
            if ch.get("status") == ChapterStatus.FAILED.value:
                updated.append(ch)
                continue

            chapter_id = ch["chapter_id"]
            self.db.update_book(book_id, current_chapter_id=chapter_id)
            result = self.extract_chapter(book_id, ch, book=book)
            updated.append(result["chapter"])
            extract_summaries.append(result["summary"])

        self.db.replace_chapters(book_id, updated)
        failed = sum(1 for c in updated if c["status"] == ChapterStatus.FAILED.value)
        ok = len(updated) - failed
        if ok == 0:
            first_err = next(
                (
                    (c.get("error") or {}).get("message")
                    for c in updated
                    if (c.get("error") or {}).get("message")
                ),
                None,
            )
            message = "All chapters failed Argument Spine extraction."
            if first_err:
                message = f"{message} First error: {first_err}"
            self._fail(
                book,
                job_id,
                message,
                details={
                    "chapter_errors": [
                        {
                            "chapter_id": c["chapter_id"],
                            "message": ((c.get("error") or {}).get("message")),
                        }
                        for c in updated
                        if c.get("status") == ChapterStatus.FAILED.value
                    ][:12],
                },
            )
            return

        # Phase 3 idle-complete at analysing_chapters
        meta_path = self.fs.metadata_path(book_id)
        metadata = self.fs.read_json(meta_path) if meta_path.exists() else {}
        metadata.update(
            {
                "schema_version": "1.0",
                "book_id": book_id,
                "title": book["title"],
                "author": book.get("author"),
                "epub_filename": book["epub_filename"],
                "processing_status": BookProcessingStatus.ANALYSING_CHAPTERS.value,
                "language": book.get("language"),
                "chapter_count": len(updated),
                "processed_chapter_count": 0,
                "failed_chapter_count": failed,
                "upload_timestamp": book["upload_timestamp"],
                "completion_timestamp": None,
                "error": None,
                "phase3": {
                    "note": "Phase 3 complete: English Argument Spine partials/candidates saved. "
                    "Phase 4 synthesises multi-chunk chapters.",
                    "prompt": "argument_spine_extraction.md",
                    "llm_mock": self.settings.llm_mock,
                    "llm_provider": self.settings.llm_provider,
                    "llm_model": self.settings.llm_model if not self.settings.llm_mock else "mock",
                    "chapters": extract_summaries,
                },
            }
        )
        self.db.update_book(
            book_id,
            processing_status=BookProcessingStatus.ANALYSING_CHAPTERS.value,
            current_stage=UIStage.ANALYSING_CHAPTERS.value,
            chapter_count=len(updated),
            failed_chapter_count=failed,
            current_chapter_id=None,
            job_id=job_id,
            error=None,
        )
        self.fs.write_json(meta_path, metadata)
        logger.info(
            "Phase 3 complete book_id=%s ok=%s failed=%s", book_id, ok, failed
        )

    def extract_chapter(
        self,
        book_id: str,
        chapter: dict[str, Any],
        *,
        book: dict[str, Any] | None = None,
        persist_status: bool = True,
    ) -> dict[str, Any]:
        """Extract Argument Spine partials for one chapter. Returns {chapter, summary}."""
        book = book or self.db.get_book(book_id)
        if not book:
            raise KeyError(book_id)

        chapter_id = chapter["chapter_id"]
        prompt_text, prompt_hash = load_prompt("argument_spine_extraction.md")
        system = self._system_prompt(prompt_text)

        try:
            source_path = self.fs.chapter_source_path(book_id, chapter_id)
            chunks_path = self.fs.chapter_chunks_path(book_id, chapter_id)
            if not source_path.exists() or not chunks_path.exists():
                raise RuntimeError("Missing source or chunk artefacts for chapter.")

            source = self.fs.read_json(source_path)
            chunk_plan = self.fs.read_json(chunks_path)
            blocks_by_id = {
                b["block_id"]: b for b in (source.get("source_blocks") or [])
            }
            chunks = chunk_plan.get("chunks") or []
            if not chunks:
                raise RuntimeError("Chunk plan is empty.")

            ch_working = {
                **chapter,
                "status": ChapterStatus.EXTRACTING.value,
                "error": None,
                "preview": {
                    **(chapter.get("preview") or {}),
                    "extract_chunk_index": 0,
                    "extract_chunk_total": len(chunks),
                },
            }
            if persist_status:
                self._patch_chapter(book_id, chapter_id, ch_working)

            partials: list[dict[str, Any]] = []

            for i, chunk in enumerate(chunks):
                chunk_id = chunk["chunk_id"]
                ch_working = {
                    **ch_working,
                    "preview": {
                        **(ch_working.get("preview") or {}),
                        "extract_chunk_index": i + 1,
                        "extract_chunk_total": len(chunks),
                        "extract_chunk_id": chunk_id,
                    },
                }
                if persist_status:
                    self._patch_chapter(book_id, chapter_id, ch_working)
                    # Touch book so status.updated_at moves and clients see activity.
                    self.db.update_book(book_id, current_chapter_id=chapter_id)

                logger.info(
                    "Extracting chunk %s/%s chapter=%s book=%s chunk_id=%s",
                    i + 1,
                    len(chunks),
                    chapter_id,
                    book_id,
                    chunk_id,
                )

                allow_ids = list(chunk.get("block_ids") or [])
                chunk_blocks = [
                    {
                        "block_id": bid,
                        "block_type": (blocks_by_id.get(bid) or {}).get("block_type"),
                        "text": (blocks_by_id.get(bid) or {}).get("text"),
                    }
                    for bid in allow_ids
                    if bid in blocks_by_id
                ]
                user = self._user_prompt(
                    book=book,
                    chapter=chapter,
                    chunk=chunk,
                    blocks=chunk_blocks,
                    partial=len(chunks) > 1,
                )
                raw = self.llm.complete_json(system=system, user=user)
                spine = self._postprocess_spine(
                    raw,
                    book_id=book_id,
                    chapter_id=chapter_id,
                    allowed={b["block_id"] for b in chunk_blocks},
                    model=self.settings.llm_model if not self.settings.llm_mock else "mock",
                    prompt_hash=prompt_hash,
                )
                partial_path = self.fs.chapter_spine_partial_path(
                    book_id, chapter_id, chunk_id
                )
                self.fs.write_json(partial_path, spine)
                partials.append(
                    {
                        "chunk_id": chunk_id,
                        "path": str(partial_path),
                        "node_count": len(spine.get("nodes") or []),
                    }
                )

            # Single-chunk chapters: candidate spine is the one partial
            if len(partials) == 1:
                candidate = self.fs.read_json(
                    self.fs.chapter_spine_partial_path(
                        book_id, chapter_id, chunks[0]["chunk_id"]
                    )
                )
                self.fs.write_json(
                    self.fs.chapter_spine_candidate_path(book_id, chapter_id),
                    candidate,
                )
            else:
                # Multi-chunk: write a manifest candidate pointer for Phase 4 synthesis
                self.fs.write_json(
                    self.fs.chapter_spine_candidate_path(book_id, chapter_id),
                    {
                        "schema_version": "1.0",
                        "book_id": book_id,
                        "chapter_id": chapter_id,
                        "language_modes": ["en"],
                        "status": "needs_synthesis",
                        "partials": partials,
                        "nodes": [],
                        "processing": {
                            "model": self.settings.llm_model
                            if not self.settings.llm_mock
                            else "mock",
                            "prompt_versions": {
                                "argument_spine_extraction": f"3.0.0:{prompt_hash}"
                            },
                            "created_at": utc_now_iso(),
                            "updated_at": utc_now_iso(),
                        },
                        "validation": {
                            "schema_valid": False,
                            "source_refs_valid": False,
                            "bilingual_aligned": False,
                            "checked_at": utc_now_iso(),
                        },
                    },
                )

            done = {
                **ch_working,
                "status": ChapterStatus.PENDING.value,
                "preview": {
                    **(chapter.get("preview") or {}),
                    "partial_count": len(partials),
                    "needs_synthesis": len(partials) > 1,
                    "extraction": "ok",
                },
            }
            return {
                "chapter": done,
                "summary": {
                    "chapter_id": chapter_id,
                    "ok": True,
                    "partial_count": len(partials),
                    "needs_synthesis": len(partials) > 1,
                },
            }
        except Exception as exc:
            logger.exception("Extraction failed chapter=%s book=%s", chapter_id, book_id)
            failed = {
                **chapter,
                "status": ChapterStatus.FAILED.value,
                "error": {
                    "code": "extraction_failed",
                    "message": str(exc),
                    "details": None,
                },
            }
            return {
                "chapter": failed,
                "summary": {
                    "chapter_id": chapter_id,
                    "ok": False,
                    "reason": str(exc),
                },
            }

    def _patch_chapter(
        self, book_id: str, chapter_id: str, chapter: dict[str, Any]
    ) -> None:
        chapters = self.db.list_chapters(book_id)
        self.db.replace_chapters(
            book_id,
            [chapter if c["chapter_id"] == chapter_id else c for c in chapters],
        )

    def _fail(
        self,
        book: dict[str, Any],
        job_id: str | None,
        message: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        book_id = book["book_id"]
        error = {
            "code": "extraction_failed",
            "message": message,
            "details": details,
        }
        self.db.update_book(
            book_id,
            processing_status=BookProcessingStatus.FAILED.value,
            current_stage=UIStage.ANALYSING_CHAPTERS.value,
            error=error,
            job_id=job_id,
        )

    def _system_prompt(self, prompt_markdown: str) -> str:
        return (
            "Follow the Argument Spine extraction instructions below.\n"
            "Return JSON only.\n\n"
            f"{prompt_markdown}"
        )

    def _user_prompt(
        self,
        *,
        book: dict[str, Any],
        chapter: dict[str, Any],
        chunk: dict[str, Any],
        blocks: list[dict[str, Any]],
        partial: bool,
    ) -> str:
        payload = {
            "book_id": book["book_id"],
            "book_title": book.get("title"),
            "chapter_id": chapter["chapter_id"],
            "chapter_title": chapter.get("title"),
            "chunk_id": chunk.get("chunk_id"),
            "is_partial_chunk": partial,
            "allow_listed_block_ids": [b["block_id"] for b in blocks],
            "blocks": blocks,
        }
        return (
            "Extract the Argument Spine for this chapter material.\n"
            "Use only the allow-listed block IDs.\n"
            "Set hinglish fields to null.\n\n"
            "===SOURCE_BLOCKS_JSON===\n"
            f"{json.dumps(payload, ensure_ascii=False)}"
        )

    def _postprocess_spine(
        self,
        raw: dict[str, Any],
        *,
        book_id: str,
        chapter_id: str,
        allowed: set[str],
        model: str,
        prompt_hash: str,
    ) -> dict[str, Any]:
        spine = dict(raw)
        spine["schema_version"] = "1.0"
        spine["book_id"] = book_id
        spine["chapter_id"] = chapter_id
        spine["language_modes"] = ["en"]
        spine.setdefault("nodes", [])
        for node in spine["nodes"]:
            node.setdefault("statement_hinglish", None)
            node.setdefault("explanation_hinglish", None)
            node.setdefault("warnings", [])

        spine = strip_invalid_source_refs(spine, allowed)
        schema_errors = validate_spine_schema(spine)
        ref_errors = validate_source_refs(spine, allowed)
        # If schema fails because needs_synthesis empty nodes — not used here
        if schema_errors:
            # Soft: keep payload but mark invalid; raise if completely unusable
            if not spine.get("nodes"):
                raise LLMError("Extraction produced no nodes: " + "; ".join(schema_errors[:5]))
            # Attach warnings on confidence_summary
            notes = (spine.get("confidence_summary") or {}).get("notes") or ""
            spine["confidence_summary"] = {
                "overall": (spine.get("confidence_summary") or {}).get("overall"),
                "notes": (notes + " | schema_warnings: " + "; ".join(schema_errors[:5])).strip(
                    " |"
                ),
            }

        now = utc_now_iso()
        spine["processing"] = {
            "model": model,
            "prompt_versions": {"argument_spine_extraction": f"3.0.0:{prompt_hash}"},
            "created_at": now,
            "updated_at": now,
        }
        spine["validation"] = {
            "schema_valid": len(schema_errors) == 0,
            "source_refs_valid": len(ref_errors) == 0,
            "bilingual_aligned": False,
            "checked_at": now,
        }
        if ref_errors:
            raise LLMError("Invalid source refs after repair: " + "; ".join(ref_errors[:5]))
        return spine
