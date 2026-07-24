"""Phase 6: final schema/source validation, repair retries, and persistence."""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from app.config import Settings
from app.domain.enums import BookProcessingStatus, ChapterStatus, UIStage
from app.pipelines.align_spine import check_bilingual_alignment
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


class ValidatePersistPipeline:
    """Fail-closed finalisation: invalid spines are never marked completed."""

    def __init__(
        self, db: SqliteStore, fs: FilesystemStore, settings: Settings | None = None
    ) -> None:
        self.db = db
        self.fs = fs
        self.settings, self.llm = bind_llm(settings)
        self.max_retries = max(0, int(self.settings.max_chapter_retries))
        self.backoff = float(self.settings.retry_backoff_seconds)

    def reload_llm(self, settings: Settings | None = None) -> None:
        self.settings, self.llm = bind_llm(settings)
        self.max_retries = max(0, int(self.settings.max_chapter_retries))
        self.backoff = float(self.settings.retry_backoff_seconds)

    def run(self, book_id: str) -> None:
        book = self.db.get_book(book_id)
        if not book:
            logger.error("Validate requested for unknown book_id=%s", book_id)
            return

        job_id = book.get("job_id")
        chapters = self.db.list_chapters(book_id)
        if not chapters:
            self._fail_book(book, job_id, "No chapters available for validation.")
            return

        self.db.update_book(
            book_id,
            processing_status=BookProcessingStatus.VALIDATING.value,
            current_stage=UIStage.VALIDATING_OUTPUT.value,
            job_id=job_id,
        )

        updated: list[dict[str, Any]] = []
        summaries: list[dict[str, Any]] = []

        for ch in chapters:
            if ch.get("status") == ChapterStatus.FAILED.value and not (
                ch.get("preview") or {}
            ).get("adaptation"):
                # Failed earlier in the pipeline — keep failed
                updated.append(ch)
                continue

            chapter_id = ch["chapter_id"]
            self.db.update_book(book_id, current_chapter_id=chapter_id)
            result = self.validate_chapter(book_id, chapter_id, chapter=ch)
            updated.append(result["chapter"])
            summaries.append(result["summary"])

        self.db.replace_chapters(book_id, updated)
        self._finalise_book(book, job_id, updated, summaries)

    def validate_chapter(
        self,
        book_id: str,
        chapter_id: str,
        *,
        chapter: dict[str, Any] | None = None,
        force: bool = False,
    ) -> dict[str, Any]:
        """Validate + repair one chapter. Returns {chapter, summary}."""
        chapters = {c["chapter_id"]: c for c in self.db.list_chapters(book_id)}
        ch = chapter or chapters.get(chapter_id)
        if not ch:
            raise KeyError(chapter_id)

        retry_count = int(ch.get("retry_count") or 0)
        if not force and retry_count > self.max_retries:
            failed = {
                **ch,
                "status": ChapterStatus.FAILED.value,
                "error": {
                    "code": "max_retries_exceeded",
                    "message": f"Chapter exceeded max retries ({self.max_retries}).",
                    "details": {"retry_count": retry_count},
                },
            }
            return {
                "chapter": failed,
                "summary": {
                    "chapter_id": chapter_id,
                    "ok": False,
                    "reason": "max_retries_exceeded",
                },
            }

        try:
            source = self.fs.read_json(self.fs.chapter_source_path(book_id, chapter_id))
            allowed = {b["block_id"] for b in (source.get("source_blocks") or [])}
            spine = self._load_spine(book_id, chapter_id)
        except Exception as exc:
            failed = {
                **ch,
                "status": ChapterStatus.FAILED.value,
                "error": {
                    "code": "validation_failed",
                    "message": str(exc),
                    "details": None,
                },
            }
            return {
                "chapter": failed,
                "summary": {"chapter_id": chapter_id, "ok": False, "reason": str(exc)},
            }

        working = {
            **ch,
            "status": ChapterStatus.VALIDATING.value,
            "error": None,
        }
        attempts = 0
        last_errors: list[str] = []

        while True:
            schema_errors = validate_spine_schema(spine)
            ref_errors = validate_source_refs(spine, allowed)
            align_errors: list[str] = []
            en_path = self.fs.chapter_spine_en_path(book_id, chapter_id)
            if en_path.exists() and "hinglish" in (spine.get("language_modes") or []):
                try:
                    english = self.fs.read_json(en_path)
                    align_errors = check_bilingual_alignment(english, spine)
                except Exception:
                    align_errors = ["could_not_check_bilingual_alignment"]

            if not schema_errors and not ref_errors and not align_errors:
                final = self._mark_valid(spine, attempts=attempts)
                self.fs.write_json(self.fs.chapter_spine_path(book_id, chapter_id), final)
                self.fs.write_json(
                    self.fs.chapter_spine_candidate_path(book_id, chapter_id), final
                )
                completed = {
                    **working,
                    "status": ChapterStatus.COMPLETED.value,
                    "retry_count": retry_count,
                    "error": None,
                    "preview": {
                        **(working.get("preview") or {}),
                        "validation": "ok",
                        "repair_attempts": attempts,
                        "node_count": len(final.get("nodes") or []),
                    },
                }
                return {
                    "chapter": completed,
                    "summary": {
                        "chapter_id": chapter_id,
                        "ok": True,
                        "repair_attempts": attempts,
                        "path": str(self.fs.chapter_spine_path(book_id, chapter_id)),
                    },
                }

            last_errors = schema_errors + ref_errors + align_errors
            if attempts >= self.max_retries:
                break

            attempts += 1
            working = {
                **working,
                "status": ChapterStatus.RETRYING.value,
                "retry_count": retry_count + attempts,
            }
            self._sleep(attempts)

            try:
                if schema_errors:
                    spine = self._repair_schema(spine, schema_errors)
                    spine = strip_invalid_source_refs(spine, allowed)
                elif ref_errors:
                    # Deterministic strip first, then LLM repair if still dirty
                    spine = strip_invalid_source_refs(spine, allowed)
                    still = validate_source_refs(spine, allowed)
                    if still:
                        spine = self._repair_sources(spine, allowed, still)
                elif align_errors:
                    # Restore hinglish overlay from English if alignment broke
                    if en_path.exists():
                        from app.pipelines.align_spine import mock_adapt_spine

                        spine = mock_adapt_spine(self.fs.read_json(en_path))
            except Exception as exc:
                logger.exception(
                    "Repair attempt failed book=%s chapter=%s attempt=%s",
                    book_id,
                    chapter_id,
                    attempts,
                )
                last_errors.append(str(exc))
                break

        # Fail-closed: do not save as success
        invalid_path = self.fs.chapter_spine_invalid_path(book_id, chapter_id)
        invalid = dict(spine)
        invalid["validation"] = {
            "schema_valid": False,
            "source_refs_valid": False,
            "bilingual_aligned": False,
            "checked_at": utc_now_iso(),
            "errors": last_errors[:20],
        }
        self.fs.write_json(invalid_path, invalid)
        failed = {
            **working,
            "status": ChapterStatus.FAILED.value,
            "retry_count": retry_count + attempts,
            "error": {
                "code": "validation_failed",
                "message": "Spine failed validation after repairs; not saved as success.",
                "details": {"errors": last_errors[:10], "attempts": attempts},
            },
            "preview": {
                **(working.get("preview") or {}),
                "validation": "failed",
                "repair_attempts": attempts,
            },
        }
        return {
            "chapter": failed,
            "summary": {
                "chapter_id": chapter_id,
                "ok": False,
                "repair_attempts": attempts,
                "errors": last_errors[:10],
                "invalid_path": str(invalid_path),
            },
        }

    def _load_spine(self, book_id: str, chapter_id: str) -> dict[str, Any]:
        path = self.fs.chapter_spine_path(book_id, chapter_id)
        if path.exists():
            return self.fs.read_json(path)
        en = self.fs.chapter_spine_en_path(book_id, chapter_id)
        if en.exists():
            return self.fs.read_json(en)
        cand = self.fs.chapter_spine_candidate_path(book_id, chapter_id)
        if cand.exists():
            data = self.fs.read_json(cand)
            if data.get("status") == "needs_synthesis":
                raise RuntimeError("Spine still needs_synthesis.")
            return data
        raise RuntimeError("No spine artefact found for validation.")

    def _mark_valid(self, spine: dict[str, Any], *, attempts: int) -> dict[str, Any]:
        out = dict(spine)
        now = utc_now_iso()
        prev = out.get("processing") if isinstance(out.get("processing"), dict) else {}
        prompt_versions = dict(prev.get("prompt_versions") or {})
        out["processing"] = {
            "model": prev.get("model")
            or (self.settings.llm_model if not self.settings.llm_mock else "mock"),
            "prompt_versions": prompt_versions,
            "created_at": prev.get("created_at") or now,
            "updated_at": now,
        }
        notes = (out.get("confidence_summary") or {}).get("notes") or ""
        notes = (notes + f" | validated attempts={attempts}").strip(" |")
        out["confidence_summary"] = {
            "overall": (out.get("confidence_summary") or {}).get("overall"),
            "notes": notes,
        }
        out["validation"] = {
            "schema_valid": True,
            "source_refs_valid": True,
            "bilingual_aligned": "hinglish" in (out.get("language_modes") or []),
            "checked_at": now,
        }
        return out

    def _repair_schema(
        self, spine: dict[str, Any], schema_errors: list[str]
    ) -> dict[str, Any]:
        prompt_text, prompt_hash = load_prompt("output_repair.md")
        system = (
            "Follow the output repair instructions.\nReturn JSON only.\n\n" + prompt_text
        )
        payload = {
            "spine": spine,
            "schema_errors": schema_errors,
            "target_schema": "argument_spine",
        }
        user = (
            "Repair this Argument Spine so it passes JSON Schema.\n"
            "Do not invent new claims.\n\n"
            "===REPAIR_SPINE_JSON===\n"
            f"{json.dumps(payload, ensure_ascii=False)}"
        )
        repaired = self.llm.complete_json(system=system, user=user)
        # Preserve identity fields
        repaired["book_id"] = spine.get("book_id") or repaired.get("book_id")
        repaired["chapter_id"] = spine.get("chapter_id") or repaired.get("chapter_id")
        repaired["schema_version"] = "1.0"
        if not repaired.get("language_modes"):
            repaired["language_modes"] = spine.get("language_modes") or ["en"]
        prev = repaired.get("processing") if isinstance(repaired.get("processing"), dict) else {}
        versions = dict(prev.get("prompt_versions") or {})
        versions["output_repair"] = f"6.0.0:{prompt_hash}"
        repaired["processing"] = {
            **prev,
            "prompt_versions": versions,
            "updated_at": utc_now_iso(),
        }
        return repaired

    def _repair_sources(
        self,
        spine: dict[str, Any],
        allowed: set[str],
        ref_errors: list[str],
    ) -> dict[str, Any]:
        prompt_text, prompt_hash = load_prompt("source_validation.md")
        system = (
            "Follow the source validation repair instructions.\n"
            "Return JSON only.\n\n" + prompt_text
        )
        invalid_ids: list[str] = []
        for err in ref_errors:
            # "unknown source_block_id on n1: bad.id"
            if ":" in err:
                invalid_ids.append(err.rsplit(":", 1)[-1].strip())
        payload = {
            "spine": spine,
            "allow_listed_block_ids": sorted(allowed),
            "invalid_ids": sorted(set(invalid_ids)),
        }
        user = (
            "Repair source_block_ids so all citations are allow-listed.\n"
            "Prefer removing invalid IDs over inventing new ones.\n\n"
            "===SOURCE_REPAIR_JSON===\n"
            f"{json.dumps(payload, ensure_ascii=False)}"
        )
        repaired = self.llm.complete_json(system=system, user=user)
        repaired = strip_invalid_source_refs(repaired, allowed)
        repaired["book_id"] = spine.get("book_id") or repaired.get("book_id")
        repaired["chapter_id"] = spine.get("chapter_id") or repaired.get("chapter_id")
        repaired["schema_version"] = "1.0"
        prev = repaired.get("processing") if isinstance(repaired.get("processing"), dict) else {}
        versions = dict(prev.get("prompt_versions") or {})
        versions["source_validation"] = f"6.0.0:{prompt_hash}"
        repaired["processing"] = {
            **prev,
            "prompt_versions": versions,
            "updated_at": utc_now_iso(),
        }
        return repaired

    def _sleep(self, attempt: int) -> None:
        if self.settings.llm_mock or self.backoff <= 0:
            return
        delay = self.backoff * (2 ** (attempt - 1))
        time.sleep(min(delay, 30.0))

    def _finalise_book(
        self,
        book: dict[str, Any],
        job_id: str | None,
        updated: list[dict[str, Any]],
        summaries: list[dict[str, Any]],
    ) -> None:
        book_id = book["book_id"]
        completed = sum(
            1 for c in updated if c["status"] == ChapterStatus.COMPLETED.value
        )
        failed = sum(1 for c in updated if c["status"] == ChapterStatus.FAILED.value)

        self.db.update_book(
            book_id,
            processing_status=BookProcessingStatus.SAVING.value,
            current_stage=UIStage.SAVING_DECODED_BOOK.value,
            processed_chapter_count=completed,
            failed_chapter_count=failed,
            current_chapter_id=None,
            job_id=job_id,
        )

        if completed == 0:
            self._fail_book(
                book,
                job_id,
                "No chapters produced a validated Argument Spine.",
            )
            return

        if failed > 0:
            final_status = BookProcessingStatus.COMPLETED_WITH_ERRORS
        else:
            final_status = BookProcessingStatus.COMPLETED

        now = utc_now_iso()
        meta_path = self.fs.metadata_path(book_id)
        metadata = self.fs.read_json(meta_path) if meta_path.exists() else {}
        metadata.update(
            {
                "schema_version": "1.0",
                "book_id": book_id,
                "title": book["title"],
                "author": book.get("author"),
                "epub_filename": book["epub_filename"],
                "processing_status": final_status.value,
                "language": book.get("language"),
                "chapter_count": len(updated),
                "processed_chapter_count": completed,
                "failed_chapter_count": failed,
                "upload_timestamp": book["upload_timestamp"],
                "completion_timestamp": now,
                "error": None,
                "phase6": {
                    "note": "Phase 6 complete: validated spines persisted; "
                    "invalid output never marked completed.",
                    "chapters": summaries,
                },
            }
        )
        self.db.update_book(
            book_id,
            processing_status=final_status.value,
            current_stage=UIStage.BOOK_READY.value,
            chapter_count=len(updated),
            processed_chapter_count=completed,
            failed_chapter_count=failed,
            current_chapter_id=None,
            job_id=job_id,
            error=None,
            completion_timestamp=now,
        )
        self.fs.write_json(meta_path, metadata)
        logger.info(
            "Phase 6 complete book_id=%s status=%s completed=%s failed=%s",
            book_id,
            final_status.value,
            completed,
            failed,
        )

    def _fail_book(
        self, book: dict[str, Any], job_id: str | None, message: str
    ) -> None:
        book_id = book["book_id"]
        error = {"code": "validation_failed", "message": message, "details": None}
        self.db.update_book(
            book_id,
            processing_status=BookProcessingStatus.FAILED.value,
            current_stage=UIStage.VALIDATING_OUTPUT.value,
            error=error,
            job_id=job_id,
        )
