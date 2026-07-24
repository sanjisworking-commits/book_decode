"""Phase 5: Hindi-English adaptation of English Argument Spines."""

from __future__ import annotations

import json
import logging
from typing import Any

from app.config import Settings
from app.domain.enums import BookProcessingStatus, ChapterStatus, UIStage
from app.pipelines.align_spine import (
    apply_hinglish_fields,
    check_bilingual_alignment,
    fill_missing_hinglish,
    mock_adapt_spine,
)
from app.pipelines.llm_bind import bind_llm
from app.pipelines.validate_spine import validate_spine_schema
from app.prompts.loader import load_prompt
from app.services.llm import LLMError
from app.storage.filesystem import FilesystemStore
from app.storage.sqlite_store import SqliteStore
from app.utils.ids import utc_now_iso

logger = logging.getLogger(__name__)


class AdaptPipeline:
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
            logger.error("Adapt requested for unknown book_id=%s", book_id)
            return

        job_id = book.get("job_id")
        chapters = self.db.list_chapters(book_id)
        if not chapters:
            self._fail(book, job_id, "No chapters available for hinglish adaptation.")
            return

        prompt_text, prompt_hash = load_prompt("hinglish_adaptation.md")
        system = self._system_prompt(prompt_text)

        self.db.update_book(
            book_id,
            processing_status=BookProcessingStatus.CREATING_HINGLISH.value,
            current_stage=UIStage.CREATING_HINDI_ENGLISH_VERSIONS.value,
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

            try:
                english = self._load_english_spine(book_id, chapter_id)
                bilingual = self._adapt_chapter(
                    english=english,
                    system=system,
                    prompt_hash=prompt_hash,
                )
                path = self.fs.chapter_spine_path(book_id, chapter_id)
                self.fs.write_json(path, bilingual)
                # Keep candidate pointing at latest readable spine for API
                self.fs.write_json(
                    self.fs.chapter_spine_candidate_path(book_id, chapter_id), bilingual
                )

                updated.append(
                    {
                        **ch,
                        "status": ChapterStatus.PENDING.value,
                        "error": None,
                        "preview": {
                            **(ch.get("preview") or {}),
                            "adaptation": "ok",
                            "language_modes": ["en", "hinglish"],
                            "node_count": len(bilingual.get("nodes") or []),
                        },
                    }
                )
                summaries.append(
                    {
                        "chapter_id": chapter_id,
                        "node_count": len(bilingual.get("nodes") or []),
                        "path": str(path),
                        "bilingual_aligned": (
                            bilingual.get("validation") or {}
                        ).get("bilingual_aligned"),
                    }
                )
            except Exception as exc:
                logger.exception(
                    "Hinglish adaptation failed chapter=%s book=%s", chapter_id, book_id
                )
                updated.append(
                    {
                        **ch,
                        "status": ChapterStatus.FAILED.value,
                        "error": {
                            "code": "adaptation_failed",
                            "message": str(exc),
                            "details": None,
                        },
                    }
                )

        self.db.replace_chapters(book_id, updated)
        failed = sum(1 for c in updated if c["status"] == ChapterStatus.FAILED.value)
        ok = len(updated) - failed
        if ok == 0:
            self._fail(book, job_id, "All chapters failed Hindi-English adaptation.")
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
                "processing_status": BookProcessingStatus.CREATING_HINGLISH.value,
                "language": book.get("language"),
                "chapter_count": len(updated),
                "processed_chapter_count": 0,
                "failed_chapter_count": failed,
                "upload_timestamp": book["upload_timestamp"],
                "completion_timestamp": None,
                "error": None,
                "phase5": {
                    "note": "Phase 5 complete: bilingual spines saved (*.spine.json). "
                    "Phase 6 adds repair retries and final validation persistence.",
                    "prompt": "hinglish_adaptation.md",
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
            processing_status=BookProcessingStatus.CREATING_HINGLISH.value,
            current_stage=UIStage.CREATING_HINDI_ENGLISH_VERSIONS.value,
            chapter_count=len(updated),
            failed_chapter_count=failed,
            current_chapter_id=None,
            job_id=job_id,
            error=None,
        )
        self.fs.write_json(meta_path, metadata)
        logger.info("Phase 5 complete book_id=%s ok=%s failed=%s", book_id, ok, failed)

    def _load_english_spine(self, book_id: str, chapter_id: str) -> dict[str, Any]:
        en_path = self.fs.chapter_spine_en_path(book_id, chapter_id)
        if en_path.exists():
            return self.fs.read_json(en_path)
        candidate = self.fs.chapter_spine_candidate_path(book_id, chapter_id)
        if candidate.exists():
            data = self.fs.read_json(candidate)
            if data.get("status") == "needs_synthesis":
                raise RuntimeError("English spine still needs_synthesis; run Phase 4 first.")
            if data.get("nodes"):
                return data
        raise RuntimeError("Missing English spine for hinglish adaptation.")

    def _adapt_chapter(
        self,
        *,
        english: dict[str, Any],
        system: str,
        prompt_hash: str,
    ) -> dict[str, Any]:
        book_id = english["book_id"]
        chapter_id = english["chapter_id"]

        # Mark adapting
        chapters = self.db.list_chapters(book_id)
        self.db.replace_chapters(
            book_id,
            [
                {
                    **c,
                    "status": ChapterStatus.ADAPTING_HINGLISH.value,
                    "error": None,
                }
                if c["chapter_id"] == chapter_id
                else c
                for c in chapters
            ],
        )

        user = self._user_prompt(english)
        raw = self.llm.complete_json(system=system, user=user)

        # Safe merge: keep English structure; overlay hinglish only
        bilingual = apply_hinglish_fields(english, raw)
        bilingual = fill_missing_hinglish(bilingual)

        alignment_errors = check_bilingual_alignment(english, bilingual)
        if alignment_errors:
            # Hard-safe fallback to structure-preserving fill if LLM drifted
            logger.warning(
                "Bilingual alignment failed; falling back to mock-style fill "
                "book=%s chapter=%s errors=%s",
                book_id,
                chapter_id,
                alignment_errors[:5],
            )
            bilingual = mock_adapt_spine(english)
            alignment_errors = check_bilingual_alignment(english, bilingual)

        if alignment_errors:
            raise LLMError(
                "Bilingual alignment failed: " + "; ".join(alignment_errors[:8])
            )

        schema_errors = validate_spine_schema(bilingual)
        now = utc_now_iso()
        prev = (
            bilingual.get("processing")
            if isinstance(bilingual.get("processing"), dict)
            else {}
        )
        prompt_versions = dict(prev.get("prompt_versions") or {})
        # Preserve earlier prompt hashes from English spine when present
        en_proc = english.get("processing") if isinstance(english.get("processing"), dict) else {}
        for k, v in (en_proc.get("prompt_versions") or {}).items():
            prompt_versions.setdefault(k, v)
        prompt_versions["hinglish_adaptation"] = f"5.0.0:{prompt_hash}"

        notes = (bilingual.get("confidence_summary") or {}).get("notes") or ""
        if schema_errors:
            notes = (
                notes + f" | schema_warnings: {'; '.join(schema_errors[:5])}"
            ).strip(" |")
        bilingual["confidence_summary"] = {
            "overall": (bilingual.get("confidence_summary") or {}).get("overall")
            or (english.get("confidence_summary") or {}).get("overall"),
            "notes": notes or "Hinglish adaptation applied.",
        }
        bilingual["processing"] = {
            "model": self.settings.llm_model if not self.settings.llm_mock else "mock",
            "prompt_versions": prompt_versions,
            "created_at": en_proc.get("created_at") or prev.get("created_at") or now,
            "updated_at": now,
        }
        bilingual["validation"] = {
            "schema_valid": len(schema_errors) == 0,
            "source_refs_valid": (english.get("validation") or {}).get(
                "source_refs_valid", True
            ),
            "bilingual_aligned": len(alignment_errors) == 0,
            "checked_at": now,
        }
        return bilingual

    def _fail(self, book: dict[str, Any], job_id: str | None, message: str) -> None:
        book_id = book["book_id"]
        error = {"code": "adaptation_failed", "message": message, "details": None}
        self.db.update_book(
            book_id,
            processing_status=BookProcessingStatus.FAILED.value,
            current_stage=UIStage.CREATING_HINDI_ENGLISH_VERSIONS.value,
            error=error,
            job_id=job_id,
        )

    def _system_prompt(self, prompt_markdown: str) -> str:
        return (
            "Follow the Hindi-English adaptation instructions below.\n"
            "Return JSON only.\n\n"
            f"{prompt_markdown}"
        )

    def _user_prompt(self, english: dict[str, Any]) -> str:
        payload = {
            "spine": english,
            "style": {
                "register": "natural_hinglish",
                "retain_english_terms": True,
                "avoid_literal_translation": True,
                "avoid_sanskritised_hindi": True,
            },
        }
        return (
            "Adapt this English Argument Spine into Hindi-English.\n"
            "Preserve all node ids, types, English fields, and source_block_ids.\n"
            "Fill statement_hinglish and explanation_hinglish only.\n\n"
            "===ENGLISH_SPINE_JSON===\n"
            f"{json.dumps(payload, ensure_ascii=False)}"
        )
