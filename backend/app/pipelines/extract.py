"""Phase 3: Argument Spine extraction via reasoning LLM (per chunk)."""

from __future__ import annotations

import json
import logging
from typing import Any

from app.config import Settings
from app.domain.enums import BookProcessingStatus, ChapterStatus, UIStage
from app.pipelines.chunk import estimate_request_tokens
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

    def extract_chapter_oneshot(
        self,
        book_id: str,
        chapter: dict[str, Any],
        *,
        book: dict[str, Any] | None = None,
        persist_status: bool = True,
    ) -> dict[str, Any]:
        """Adaptive two-pass: discovery → synthesis for one chapter (EN-only artefacts).

        When the chapter fits the prompt budget: one discovery call + one synthesis
        call. Oversized chapters: per-chunk discovery → merge → synthesis.
        Hinglish fields stay null. Writes ``*.discovery.json``, ``*.spine.en.json``,
        ``*.spine.json``, and ``*.spine.candidate.json``.
        """
        return self._extract_adaptive_two_pass(
            book_id,
            chapter,
            book=book,
            persist_status=persist_status,
            extract_mode="oneshot",
        )

    def _extract_adaptive_two_pass(
        self,
        book_id: str,
        chapter: dict[str, Any],
        *,
        book: dict[str, Any] | None = None,
        persist_status: bool = True,
        extract_mode: str = "oneshot",
    ) -> dict[str, Any]:
        from app.pipelines.adaptive_synthesis import run_adaptive_synthesis
        from app.pipelines.chunk import chunk_source_chapter
        from app.pipelines.discovery import (
            chapter_fits_discovery_budget,
            run_discovery_call,
        )
        from app.pipelines.discovery_merge import run_discovery_merge
        from app.prompts.loader import load_prompt

        book = book or self.db.get_book(book_id)
        if not book:
            raise KeyError(book_id)

        chapter_id = chapter["chapter_id"]
        _, discovery_prompt_hash = load_prompt("argument_discovery.md")

        try:
            source_path = self.fs.chapter_source_path(book_id, chapter_id)
            if not source_path.exists():
                raise RuntimeError("Missing source artefact for chapter.")

            source = self.fs.read_json(source_path)
            all_blocks = list(source.get("source_blocks") or [])
            if not all_blocks:
                raise RuntimeError("Chapter has no source blocks.")

            prompt_budget = self.settings.extract_prompt_token_budget()
            fits = chapter_fits_discovery_budget(
                settings=self.settings,
                book=book,
                chapter=chapter,
                blocks=all_blocks,
            )

            ch_working = {
                **chapter,
                "status": ChapterStatus.EXTRACTING.value,
                "error": None,
                "preview": {
                    **(chapter.get("preview") or {}),
                    "extract_mode": extract_mode,
                    "extract_pass": "discovery",
                    "prompt_budget": prompt_budget,
                    "adaptive_fits_budget": fits,
                },
            }
            if persist_status:
                self._patch_chapter(book_id, chapter_id, ch_working)
                self.db.update_book(book_id, current_chapter_id=chapter_id)

            chunk_discoveries: list[dict[str, Any]] = []
            if fits:
                logger.info(
                    "Adaptive discovery oneshot chapter=%s book=%s blocks=%s",
                    chapter_id,
                    book_id,
                    len(all_blocks),
                )
                discovery = run_discovery_call(
                    self.llm,
                    settings=self.settings,
                    book=book,
                    chapter=chapter,
                    blocks=all_blocks,
                    chunk_id=f"{chapter_id}.discovery",
                )
                chunk_discoveries = [discovery]
            else:
                # Prefer existing chunk plan; else build token packs for discovery.
                chunks_path = self.fs.chapter_chunks_path(book_id, chapter_id)
                if chunks_path.exists():
                    chunk_plan = self.fs.read_json(chunks_path)
                else:
                    chunk_plan = chunk_source_chapter(
                        source,
                        token_limit=max(2000, self.settings.chunk_token_limit),
                        overlap_blocks=self.settings.chunk_overlap_blocks,
                    )
                    self.fs.write_json(chunks_path, chunk_plan)

                blocks_by_id = {b["block_id"]: b for b in all_blocks if b.get("block_id")}
                chunks = chunk_plan.get("chunks") or []
                if not chunks:
                    raise RuntimeError("Chunk plan empty for oversized chapter discovery.")

                for i, chunk in enumerate(chunks):
                    chunk_id = chunk.get("chunk_id") or f"{chapter_id}.c{i:02d}"
                    allow_ids = list(chunk.get("block_ids") or [])
                    raw_blocks = [
                        blocks_by_id[bid] for bid in allow_ids if bid in blocks_by_id
                    ]
                    ch_working = {
                        **ch_working,
                        "preview": {
                            **(ch_working.get("preview") or {}),
                            "extract_pass": "discovery",
                            "extract_chunk_index": i + 1,
                            "extract_chunk_total": len(chunks),
                            "extract_chunk_id": chunk_id,
                        },
                    }
                    if persist_status:
                        self._patch_chapter(book_id, chapter_id, ch_working)
                        self.db.update_book(book_id, current_chapter_id=chapter_id)

                    logger.info(
                        "Adaptive discovery chunk %s/%s chapter=%s book=%s",
                        i + 1,
                        len(chunks),
                        chapter_id,
                        book_id,
                    )
                    chunk_discoveries.append(
                        run_discovery_call(
                            self.llm,
                            settings=self.settings,
                            book=book,
                            chapter=chapter,
                            blocks=raw_blocks,
                            chunk_id=chunk_id,
                        )
                    )

                discovery = run_discovery_merge(
                    self.llm,
                    settings=self.settings,
                    book=book,
                    chapter=chapter,
                    blocks=all_blocks,
                    chunk_discoveries=chunk_discoveries,
                )

            discovery_path = self.fs.chapter_discovery_path(book_id, chapter_id)
            self.fs.write_json(discovery_path, discovery)

            ch_working = {
                **ch_working,
                "preview": {
                    **(ch_working.get("preview") or {}),
                    "extract_pass": "adaptive_synthesis",
                },
            }
            if persist_status:
                self._patch_chapter(book_id, chapter_id, ch_working)

            spine = run_adaptive_synthesis(
                self.llm,
                settings=self.settings,
                book=book,
                chapter=chapter,
                blocks=all_blocks,
                discovery=discovery,
                discovery_prompt_hash=discovery_prompt_hash,
            )

            en_path = self.fs.chapter_spine_en_path(book_id, chapter_id)
            spine_path = self.fs.chapter_spine_path(book_id, chapter_id)
            cand_path = self.fs.chapter_spine_candidate_path(book_id, chapter_id)
            self.fs.write_json(en_path, spine)
            self.fs.write_json(spine_path, spine)
            self.fs.write_json(cand_path, spine)

            llm_calls = len(chunk_discoveries) + (0 if fits else 1) + 1
            done = {
                **ch_working,
                "status": ChapterStatus.PENDING.value,
                "preview": {
                    **(ch_working.get("preview") or {}),
                    "partial_count": 1,
                    "needs_synthesis": False,
                    "extraction": "ok",
                    "extract_mode": extract_mode,
                    "adaptive_two_pass": True,
                    "discovery_chunks": len(chunk_discoveries),
                    "llm_calls": llm_calls,
                    "node_count": len(spine.get("nodes") or []),
                    "relation_count": len(spine.get("relations") or []),
                },
            }
            return {
                "chapter": done,
                "summary": {
                    "chapter_id": chapter_id,
                    "ok": True,
                    "partial_count": 1,
                    "needs_synthesis": False,
                    "extract_mode": extract_mode,
                    "adaptive_two_pass": True,
                    "llm_calls": llm_calls,
                    "node_count": len(spine.get("nodes") or []),
                },
            }
        except Exception as exc:
            logger.exception(
                "Adaptive extraction failed chapter=%s book=%s mode=%s",
                chapter_id,
                book_id,
                extract_mode,
            )
            failed = {
                **chapter,
                "status": ChapterStatus.FAILED.value,
                "error": {
                    "code": "extraction_failed",
                    "message": str(exc),
                    "details": {"extract_mode": extract_mode, "adaptive_two_pass": True},
                },
            }
            return {
                "chapter": failed,
                "summary": {
                    "chapter_id": chapter_id,
                    "ok": False,
                    "reason": str(exc),
                    "extract_mode": extract_mode,
                    "adaptive_two_pass": True,
                },
            }

    def _fit_blocks_to_prompt_budget(
        self,
        *,
        book: dict[str, Any],
        chapter: dict[str, Any],
        system: str,
        blocks: list[dict[str, Any]],
        prompt_budget: int,
        chunk_id: str,
        partial: bool,
    ) -> tuple[list[dict[str, Any]], str, int]:
        """Pack a prefix of blocks so system+user stay under ``prompt_budget``.

        Budgets the *serialized* extract prompt (not raw block text). Life Ch1
        showed JSON envelopes inflating ~7k text tokens into ~21k prompt tokens
        (~29k on Groq's tokenizer).
        """
        if not blocks:
            raise RuntimeError("No blocks available for extract prompt.")

        conservative = self.settings.is_groq()
        slim = [
            {
                "block_id": b["block_id"],
                "block_type": b.get("block_type"),
                "text": b.get("text"),
            }
            for b in blocks
            if b.get("block_id")
        ]
        if not slim:
            raise RuntimeError("No blocks with block_id for extract prompt.")

        def build(n: int) -> tuple[list[dict[str, Any]], str, int]:
            chosen = slim[: max(1, n)]
            chunk = {
                "chunk_id": chunk_id,
                "block_ids": [b["block_id"] for b in chosen],
            }
            user = self._user_prompt(
                book=book,
                chapter=chapter,
                chunk=chunk,
                blocks=chosen,
                partial=partial,
            )
            tokens = estimate_request_tokens(
                system, conservative=conservative
            ) + estimate_request_tokens(user, conservative=conservative)
            return chosen, user, tokens

        # Fast path: everything fits.
        all_blocks, all_user, all_tokens = build(len(slim))
        if all_tokens <= prompt_budget:
            return all_blocks, all_user, all_tokens

        lo, hi = 1, len(slim)
        best_n = 1
        while lo <= hi:
            mid = (lo + hi) // 2
            _, _, tokens = build(mid)
            if tokens <= prompt_budget:
                best_n = mid
                lo = mid + 1
            else:
                hi = mid - 1

        chosen, user, tokens = build(best_n)
        # If even one block overflows, truncate its text so the call can proceed.
        if tokens > prompt_budget and len(chosen) == 1:
            chosen, user, tokens = self._truncate_single_block_prompt(
                book=book,
                chapter=chapter,
                system=system,
                block=chosen[0],
                prompt_budget=prompt_budget,
                chunk_id=chunk_id,
                partial=partial,
                conservative=conservative,
            )

        if len(chosen) < len(slim):
            logger.warning(
                "Extract prompt truncated chapter=%s chunk=%s blocks=%s/%s "
                "prompt_tokens_est=%s budget=%s",
                chapter.get("chapter_id"),
                chunk_id,
                len(chosen),
                len(slim),
                tokens,
                prompt_budget,
            )
        return chosen, user, tokens

    def _truncate_single_block_prompt(
        self,
        *,
        book: dict[str, Any],
        chapter: dict[str, Any],
        system: str,
        block: dict[str, Any],
        prompt_budget: int,
        chunk_id: str,
        partial: bool,
        conservative: bool,
    ) -> tuple[list[dict[str, Any]], str, int]:
        text = block.get("text") or ""
        # Binary-search character length that fits.
        lo, hi = 200, len(text)
        best = text[:200]
        while lo <= hi:
            mid = (lo + hi) // 2
            trial = {
                **block,
                "text": text[:mid] + ("…" if mid < len(text) else ""),
            }
            user = self._user_prompt(
                book=book,
                chapter=chapter,
                chunk={"chunk_id": chunk_id, "block_ids": [block["block_id"]]},
                blocks=[trial],
                partial=partial,
            )
            tokens = estimate_request_tokens(
                system, conservative=conservative
            ) + estimate_request_tokens(user, conservative=conservative)
            if tokens <= prompt_budget:
                best = trial["text"]
                lo = mid + 1
            else:
                hi = mid - 1
        final = {**block, "text": best}
        user = self._user_prompt(
            book=book,
            chapter=chapter,
            chunk={"chunk_id": chunk_id, "block_ids": [block["block_id"]]},
            blocks=[final],
            partial=partial,
        )
        tokens = estimate_request_tokens(
            system, conservative=conservative
        ) + estimate_request_tokens(user, conservative=conservative)
        return [final], user, tokens

    def extract_chapter(
        self,
        book_id: str,
        chapter: dict[str, Any],
        *,
        book: dict[str, Any] | None = None,
        persist_status: bool = True,
    ) -> dict[str, Any]:
        """Extract English Argument Spine via adaptive two-pass discovery+synthesis.

        Legacy multi-partial extract remains available only by calling deprecated
        prompts directly; the default English path no longer emits needs_synthesis.
        """
        return self._extract_adaptive_two_pass(
            book_id,
            chapter,
            book=book,
            persist_status=persist_status,
            extract_mode="adaptive",
        )

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
