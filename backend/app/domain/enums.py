"""Domain enums for book and chapter processing."""

from enum import Enum


class BookProcessingStatus(str, Enum):
    UPLOADED = "uploaded"
    QUEUED = "queued"
    UPLOADING = "uploading"
    READING_STRUCTURE = "reading_structure"
    DETECTING_CHAPTERS = "detecting_chapters"
    PREPARING_BLOCKS = "preparing_blocks"
    ANALYSING_CHAPTERS = "analysing_chapters"
    CONSTRUCTING_SPINES = "constructing_spines"
    CREATING_HINGLISH = "creating_hinglish"
    VALIDATING = "validating"
    SAVING = "saving"
    COMPLETED = "completed"
    COMPLETED_WITH_ERRORS = "completed_with_errors"
    FAILED = "failed"
    CANCELLED = "cancelled"


class UIStage(str, Enum):
    UPLOADING_EPUB = "uploading_epub"
    READING_BOOK_STRUCTURE = "reading_book_structure"
    DETECTING_CHAPTERS = "detecting_chapters"
    PREPARING_CHAPTER_BLOCKS = "preparing_chapter_blocks"
    ANALYSING_CHAPTERS = "analysing_chapters"
    CONSTRUCTING_ARGUMENT_SPINES = "constructing_argument_spines"
    CREATING_HINDI_ENGLISH_VERSIONS = "creating_hindi_english_versions"
    VALIDATING_OUTPUT = "validating_output"
    SAVING_DECODED_BOOK = "saving_decoded_book"
    BOOK_READY = "book_ready"


class ChapterStatus(str, Enum):
    PENDING = "pending"
    CHUNKING = "chunking"
    EXTRACTING = "extracting"
    SYNTHESISING = "synthesising"
    ADAPTING_HINGLISH = "adapting_hinglish"
    VALIDATING = "validating"
    RETRYING = "retrying"
    COMPLETED = "completed"
    FAILED = "failed"


# Map book status → UI stage for status API (Phase 1 subset + future stages).
BOOK_STATUS_TO_UI_STAGE: dict[BookProcessingStatus, UIStage] = {
    BookProcessingStatus.UPLOADING: UIStage.UPLOADING_EPUB,
    BookProcessingStatus.UPLOADED: UIStage.UPLOADING_EPUB,
    BookProcessingStatus.QUEUED: UIStage.READING_BOOK_STRUCTURE,
    BookProcessingStatus.READING_STRUCTURE: UIStage.READING_BOOK_STRUCTURE,
    BookProcessingStatus.DETECTING_CHAPTERS: UIStage.DETECTING_CHAPTERS,
    BookProcessingStatus.PREPARING_BLOCKS: UIStage.PREPARING_CHAPTER_BLOCKS,
    BookProcessingStatus.ANALYSING_CHAPTERS: UIStage.ANALYSING_CHAPTERS,
    BookProcessingStatus.CONSTRUCTING_SPINES: UIStage.CONSTRUCTING_ARGUMENT_SPINES,
    BookProcessingStatus.CREATING_HINGLISH: UIStage.CREATING_HINDI_ENGLISH_VERSIONS,
    BookProcessingStatus.VALIDATING: UIStage.VALIDATING_OUTPUT,
    BookProcessingStatus.SAVING: UIStage.SAVING_DECODED_BOOK,
    BookProcessingStatus.COMPLETED: UIStage.BOOK_READY,
    BookProcessingStatus.COMPLETED_WITH_ERRORS: UIStage.BOOK_READY,
    BookProcessingStatus.FAILED: UIStage.READING_BOOK_STRUCTURE,
    BookProcessingStatus.CANCELLED: UIStage.UPLOADING_EPUB,
}

UI_STAGE_ORDER: list[UIStage] = list(UIStage)
