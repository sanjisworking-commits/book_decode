/** Types aligned with backend schemas / API models. */

export type SourceStatus =
  | "explicit_author"
  | "author_paraphrase"
  | "ai_inference"
  | "external_counter";

export type NodeType =
  | "chapter_question"
  | "central_claim"
  | "reasoning_steps"
  | "evidence_and_examples"
  | "hidden_assumptions"
  | "tensions_or_gaps"
  | "strongest_counter_position"
  | "consequence_if_correct"
  | "role_in_book"
  | "one_sentence_decode"
  | "confidence_and_unresolved"
  | "source_block_references";

export type LanguageMode = "en" | "hinglish";

export type ApiErrorBody = {
  code: string;
  message: string;
  details?: Record<string, unknown> | null;
};

export type BookMetadata = {
  schema_version: string;
  book_id: string;
  title: string;
  author: string | null;
  epub_filename: string;
  processing_status: string;
  language: string | null;
  chapter_count: number;
  processed_chapter_count: number;
  failed_chapter_count: number;
  upload_timestamp: string;
  completion_timestamp: string | null;
  error: ApiErrorBody | null;
};

export type ChapterSummary = {
  chapter_id: string;
  title: string | null;
  chapter_number: number | null;
  status: string;
  retry_count: number;
  error: ApiErrorBody | null;
  /** Mid-phase progress, e.g. "chunk 3/26" while extracting. */
  progress?: string | null;
};

export type ProcessingStatus = {
  schema_version: string;
  book_id: string;
  job_id: string | null;
  processing_status: string;
  current_stage: string;
  stage_index: number;
  stages_total: number;
  chapter_count: number;
  processed_chapter_count: number;
  failed_chapter_count: number;
  current_chapter_id: string | null;
  partial_success: boolean;
  error: ApiErrorBody | null;
  chapters: ChapterSummary[];
  updated_at: string | null;
};

export type ChapterListResponse = {
  book_id: string;
  chapters: ChapterSummary[];
};

export type SpineNode = {
  id: string;
  node_type: NodeType;
  statement_en: string | null;
  explanation_en?: string | null;
  statement_hinglish?: string | null;
  explanation_hinglish?: string | null;
  source_status: SourceStatus;
  source_block_ids: string[];
  confidence: number | null;
  order: number;
  prev_id?: string | null;
  next_id?: string | null;
  warnings?: string[];
};

export type ArgumentSpine = {
  schema_version: string;
  book_id: string;
  chapter_id: string;
  language_modes: LanguageMode[];
  nodes: SpineNode[];
  confidence_summary?: {
    overall: number | null;
    notes: string | null;
  } | null;
  processing?: Record<string, unknown> | null;
  validation?: Record<string, unknown> | null;
};

export type SourceBlock = {
  block_id: string;
  block_type: string;
  text: string;
  order_index: number;
  section_id?: string | null;
  chapter_id?: string | null;
};

export type SourceChapter = {
  schema_version: string;
  book_id: string;
  chapter_id: string;
  chapter_number: number | null;
  chapter_title: string;
  heading_hierarchy: string[];
  source_blocks: SourceBlock[];
};

export class ApiError extends Error {
  status: number;
  code: string;
  details: Record<string, unknown> | null;

  constructor(
    status: number,
    code: string,
    message: string,
    details: Record<string, unknown> | null = null,
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}
