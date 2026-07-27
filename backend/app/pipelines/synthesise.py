"""Phase 4: synthesise partial Argument Spines into one English chapter spine."""

from __future__ import annotations

import json
import logging
from typing import Any

from app.config import Settings
from app.domain.enums import BookProcessingStatus, ChapterStatus, UIStage
from app.pipelines.llm_bind import bind_llm
from app.pipelines.merge_spines import (
    claim_supported_by_partials,
    collect_claim_statements,
    merge_partial_spines,
)
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


class SynthesisePipeline:
    def __init__(
        self, db: SqliteStore, fs: FilesystemStore, settings: Settings | None = None
    ) -> None:
        self.db = db
        self.fs = fs
        self.settings, self.llm = bind_llm(settings)

    def reload_llm(self, settings: Settings | None = None) -> None:
        self.settings, self.llm = bind_llm(settings)

    def run(self, book_id: str) -> None:
        book = self.db.get_book(book_id)
        if not book:
            logger.error("Synthesise requested for unknown book_id=%s", book_id)
            return

        job_id = book.get("job_id")
        chapters = self.db.list_chapters(book_id)
        if not chapters:
            self._fail(book, job_id, "No chapters available for synthesis.")
            return

        prompt_text, prompt_hash = load_prompt("argument_spine_synthesis.md")
        system = self._system_prompt(prompt_text)

        self.db.update_book(
            book_id,
            processing_status=BookProcessingStatus.CONSTRUCTING_SPINES.value,
            current_stage=UIStage.CONSTRUCTING_ARGUMENT_SPINES.value,
            job_id=job_id,
        )

        updated: list[dict[str, Any]] = []
        summaries: list[dict[str, Any]] = []

        for ch in chapters:
            if ch.get("status") == ChapterStatus.FAILED.value:
                updated.append(ch)
                continue

            chapter_id = ch["chapter_id"]
            self.db.update_book(book_id, current_chapter_id=chapter_id)
            result = self.synthesise_chapter(
                book_id,
                ch,
                book=book,
                system=system,
                prompt_hash=prompt_hash,
            )
            updated.append(result["chapter"])
            summaries.append(result["summary"])

        self.db.replace_chapters(book_id, updated)
        failed = sum(1 for c in updated if c["status"] == ChapterStatus.FAILED.value)
        ok = len(updated) - failed
        if ok == 0:
            self._fail(book, job_id, "All chapters failed Argument Spine synthesis.")
            return

        meta_path = self.fs.metadata_path(book_id)
        metadata = self.fs.read_json(meta_path) if meta_path.exists() else {}
        metadata.update(
            {
                "schema_version": "1.0",
                "book_id": book_id,
                "title": book["title"],
                "author": book.get("author"),
                "epub_filename": book["epub_filename"],
                "processing_status": BookProcessingStatus.CONSTRUCTING_SPINES.value,
                "language": book.get("language"),
                "chapter_count": len(updated),
                "processed_chapter_count": 0,
                "failed_chapter_count": failed,
                "upload_timestamp": book["upload_timestamp"],
                "completion_timestamp": None,
                "error": None,
                "phase4": {
                    "note": "Phase 4 complete: English chapter spines synthesised "
                    "(*.spine.en.json). Phase 5 adapts Hindi-English.",
                    "prompt": "argument_spine_synthesis.md",
                    "llm_mock": self.settings.llm_mock,
                    "llm_provider": self.settings.llm_provider,
                    "llm_model": self.settings.llm_model
                    if not self.settings.llm_mock
                    else "mock",
                    "chapters": summaries,
                },
            }
        )
        self.db.update_book(
            book_id,
            processing_status=BookProcessingStatus.CONSTRUCTING_SPINES.value,
            current_stage=UIStage.CONSTRUCTING_ARGUMENT_SPINES.value,
            chapter_count=len(updated),
            failed_chapter_count=failed,
            current_chapter_id=None,
            job_id=job_id,
            error=None,
        )
        self.fs.write_json(meta_path, metadata)
        logger.info("Phase 4 complete book_id=%s ok=%s failed=%s", book_id, ok, failed)

    def synthesise_chapter(
        self,
        book_id: str,
        chapter: dict[str, Any],
        *,
        book: dict[str, Any] | None = None,
        system: str | None = None,
        prompt_hash: str | None = None,
    ) -> dict[str, Any]:
        """Synthesise one chapter's English spine. Returns {chapter, summary}."""
        book = book or self.db.get_book(book_id)
        if not book:
            raise KeyError(book_id)

        chapter_id = chapter["chapter_id"]
        if system is None or prompt_hash is None:
            prompt_text, prompt_hash = load_prompt("argument_spine_synthesis.md")
            system = self._system_prompt(prompt_text)

        try:
            spine = self._synthesise_chapter(
                book=book,
                chapter=chapter,
                system=system,
                prompt_hash=prompt_hash,
            )
            en_path = self.fs.chapter_spine_en_path(book_id, chapter_id)
            candidate_path = self.fs.chapter_spine_candidate_path(book_id, chapter_id)
            self.fs.write_json(en_path, spine)
            self.fs.write_json(candidate_path, spine)

            done = {
                **chapter,
                "status": ChapterStatus.PENDING.value,
                "error": None,
                "preview": {
                    **(chapter.get("preview") or {}),
                    "synthesis": "ok",
                    "needs_synthesis": False,
                    "node_count": len(spine.get("nodes") or []),
                },
            }
            return {
                "chapter": done,
                "summary": {
                    "chapter_id": chapter_id,
                    "ok": True,
                    "node_count": len(spine.get("nodes") or []),
                    "path": str(en_path),
                },
            }
        except Exception as exc:
            logger.exception(
                "Synthesis failed chapter=%s book=%s", chapter_id, book_id
            )
            failed = {
                **chapter,
                "status": ChapterStatus.FAILED.value,
                "error": {
                    "code": "synthesis_failed",
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

    def _synthesise_chapter(
        self,
        *,
        book: dict[str, Any],
        chapter: dict[str, Any],
        system: str,
        prompt_hash: str,
    ) -> dict[str, Any]:
        book_id = book["book_id"]
        chapter_id = chapter["chapter_id"]
        source = self.fs.read_json(self.fs.chapter_source_path(book_id, chapter_id))
        allowed = {b["block_id"] for b in (source.get("source_blocks") or [])}

        candidate_path = self.fs.chapter_spine_candidate_path(book_id, chapter_id)
        if not candidate_path.exists():
            raise RuntimeError("Missing spine candidate for chapter.")
        candidate = self.fs.read_json(candidate_path)

        # Single-chunk (or already synthesised): promote candidate as English spine
        if candidate.get("status") != "needs_synthesis" and candidate.get("nodes"):
            return self._finalise(
                candidate,
                book_id=book_id,
                chapter_id=chapter_id,
                allowed=allowed,
                prompt_hash=prompt_hash,
                via="passthrough",
            )

        partial_metas = candidate.get("partials") or []
        if not partial_metas:
            # Fallback: discover partial files from chunk plan
            chunk_plan = self.fs.read_json(self.fs.chapter_chunks_path(book_id, chapter_id))
            partial_metas = [
                {"chunk_id": c["chunk_id"]} for c in (chunk_plan.get("chunks") or [])
            ]

        partials: list[dict[str, Any]] = []
        for meta in partial_metas:
            chunk_id = meta.get("chunk_id")
            path = meta.get("path")
            if path:
                from pathlib import Path

                p = Path(path)
                if p.exists():
                    partials.append(self.fs.read_json(p))
                    continue
            if not chunk_id:
                continue
            p = self.fs.chapter_spine_partial_path(book_id, chapter_id, chunk_id)
            if not p.exists():
                raise RuntimeError(f"Missing partial spine for chunk {chunk_id}")
            partials.append(self.fs.read_json(p))

        if not partials:
            raise RuntimeError("No partial spines available for synthesis.")
        if len(partials) == 1:
            return self._finalise(
                partials[0],
                book_id=book_id,
                chapter_id=chapter_id,
                allowed=allowed,
                prompt_hash=prompt_hash,
                via="single_partial",
            )

        # Mark chapter synthesising
        working = {
            **chapter,
            "status": ChapterStatus.SYNTHESISING.value,
            "error": None,
        }
        self.db.replace_chapters(
            book_id,
            [
                working if c["chapter_id"] == chapter_id else c
                for c in self.db.list_chapters(book_id)
            ],
        )

        user = self._user_prompt(
            book=book,
            chapter=chapter,
            partials=partials,
            allowed_block_ids=sorted(allowed),
            source=source,
        )
        raw = self.llm.complete_json(system=system, user=user)
        spine = self._postprocess_llm_spine(
            raw,
            book_id=book_id,
            chapter_id=chapter_id,
            allowed=allowed,
            partials=partials,
            prompt_hash=prompt_hash,
        )
        return spine

    def _postprocess_llm_spine(
        self,
        raw: dict[str, Any],
        *,
        book_id: str,
        chapter_id: str,
        allowed: set[str],
        partials: list[dict[str, Any]],
        prompt_hash: str,
    ) -> dict[str, Any]:
        partial_claims = collect_claim_statements(partials)
        spine = dict(raw)
        spine["schema_version"] = "1.0"
        spine["book_id"] = book_id
        spine["chapter_id"] = chapter_id
        spine["language_modes"] = ["en"]
        spine.setdefault("nodes", [])

        # Drop nodes that invent claims absent from partials
        kept: list[dict[str, Any]] = []
        for node in spine["nodes"]:
            node.setdefault("statement_hinglish", None)
            node.setdefault("explanation_hinglish", None)
            node.setdefault("warnings", [])
            if not claim_supported_by_partials(node.get("statement_en"), partial_claims):
                warnings = list(node.get("warnings") or [])
                warnings.append("dropped_unsupported_new_claim")
                node["warnings"] = warnings
                continue
            kept.append(node)
        spine["nodes"] = kept

        if not spine["nodes"]:
            # Hard fallback: deterministic merge
            logger.warning(
                "LLM synthesis produced no supported nodes; using deterministic merge "
                "book=%s chapter=%s",
                book_id,
                chapter_id,
            )
            spine = merge_partial_spines(
                book_id=book_id,
                chapter_id=chapter_id,
                partials=partials,
                allowed_block_ids=allowed,
            )

        return self._finalise(
            spine,
            book_id=book_id,
            chapter_id=chapter_id,
            allowed=allowed,
            prompt_hash=prompt_hash,
            via="llm",
        )

    def _finalise(
        self,
        spine: dict[str, Any],
        *,
        book_id: str,
        chapter_id: str,
        allowed: set[str],
        prompt_hash: str,
        via: str,
    ) -> dict[str, Any]:
        out = dict(spine)
        out.pop("status", None)
        out.pop("partials", None)
        out["schema_version"] = "1.0"
        out["book_id"] = book_id
        out["chapter_id"] = chapter_id
        out["language_modes"] = ["en"]
        out.setdefault("nodes", [])
        for node in out["nodes"]:
            node.setdefault("statement_hinglish", None)
            node.setdefault("explanation_hinglish", None)
            node.setdefault("warnings", [])

        out = strip_invalid_source_refs(out, allowed)
        schema_errors = validate_spine_schema(out)
        ref_errors = validate_source_refs(out, allowed)
        if not out.get("nodes"):
            raise LLMError(
                "Synthesis produced no nodes: " + "; ".join(schema_errors[:5] or ["empty"])
            )
        if ref_errors:
            raise LLMError(
                "Invalid source refs after synthesis: " + "; ".join(ref_errors[:5])
            )

        now = utc_now_iso()
        prev = out.get("processing") if isinstance(out.get("processing"), dict) else {}
        prompt_versions = dict(prev.get("prompt_versions") or {})
        prompt_versions["argument_spine_synthesis"] = f"4.0.0:{prompt_hash}"
        out["processing"] = {
            "model": self.settings.llm_model if not self.settings.llm_mock else "mock",
            "prompt_versions": prompt_versions,
            "created_at": prev.get("created_at") or now,
            "updated_at": now,
        }
        notes = (out.get("confidence_summary") or {}).get("notes") or ""
        if schema_errors:
            notes = (
                notes + f" | schema_warnings: {'; '.join(schema_errors[:5])}"
            ).strip(" |")
        notes = (notes + f" | synthesis_via={via}").strip(" |")
        out["confidence_summary"] = {
            "overall": (out.get("confidence_summary") or {}).get("overall"),
            "notes": notes,
        }
        out["validation"] = {
            "schema_valid": len(schema_errors) == 0,
            "source_refs_valid": len(ref_errors) == 0,
            "bilingual_aligned": False,
            "checked_at": now,
        }
        return out

    def _fail(self, book: dict[str, Any], job_id: str | None, message: str) -> None:
        book_id = book["book_id"]
        error = {"code": "synthesis_failed", "message": message, "details": None}
        self.db.update_book(
            book_id,
            processing_status=BookProcessingStatus.FAILED.value,
            current_stage=UIStage.CONSTRUCTING_ARGUMENT_SPINES.value,
            error=error,
            job_id=job_id,
        )

    def _system_prompt(self, prompt_markdown: str) -> str:
        return (
            "Follow the Argument Spine synthesis instructions below.\n"
            "Return JSON only.\n\n"
            f"{prompt_markdown}"
        )

    def _user_prompt(
        self,
        *,
        book: dict[str, Any],
        chapter: dict[str, Any],
        partials: list[dict[str, Any]],
        allowed_block_ids: list[str],
        source: dict[str, Any],
    ) -> str:
        # Small excerpts for cited blocks only
        blocks_by_id = {b["block_id"]: b for b in (source.get("source_blocks") or [])}
        cited: set[str] = set()
        for partial in partials:
            for node in partial.get("nodes") or []:
                cited.update(node.get("source_block_ids") or [])
        excerpts = []
        for bid in sorted(cited):
            if bid not in blocks_by_id:
                continue
            text = (blocks_by_id[bid].get("text") or "")[:240]
            excerpts.append({"block_id": bid, "text": text})

        payload = {
            "book_id": book["book_id"],
            "book_title": book.get("title"),
            "chapter_id": chapter["chapter_id"],
            "chapter_title": chapter.get("title"),
            "chapter_number": chapter.get("chapter_number"),
            "allow_listed_block_ids": allowed_block_ids,
            "partials": partials,
            "source_excerpts": excerpts[:40],
        }
        return (
            "Synthesise one English Argument Spine from these partial spines.\n"
            "Do not invent claims absent from the partials.\n"
            "Set hinglish fields to null.\n\n"
            "===PARTIAL_SPINES_JSON===\n"
            f"{json.dumps(payload, ensure_ascii=False)}"
        )
