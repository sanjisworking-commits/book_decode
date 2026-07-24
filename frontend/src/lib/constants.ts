import type { NodeType, SourceStatus } from "../types/api";

export const MAX_EPUB_SIZE_MB = 50;
export const MAX_EPUB_SIZE_BYTES = MAX_EPUB_SIZE_MB * 1024 * 1024;
export const LOW_CONFIDENCE_THRESHOLD = 0.55;

export const UI_STAGES: { key: string; label: string }[] = [
  { key: "uploading", label: "Uploading EPUB" },
  { key: "reading_structure", label: "Reading book structure" },
  { key: "detecting_chapters", label: "Detecting chapters" },
  { key: "preparing_blocks", label: "Preparing chapter blocks" },
  { key: "analysing_chapters", label: "Analysing chapters" },
  { key: "constructing_spines", label: "Constructing Argument Spines" },
  { key: "creating_hinglish", label: "Creating Hindi-English versions" },
  { key: "validating", label: "Validating output" },
  { key: "saving", label: "Saving decoded book" },
  { key: "completed", label: "Book ready" },
];

export const NODE_LABELS: Record<NodeType, string> = {
  chapter_question: "Chapter question",
  central_claim: "Central claim",
  reasoning_steps: "Reasoning steps",
  evidence_and_examples: "Evidence & examples",
  hidden_assumptions: "Hidden assumptions",
  tensions_or_gaps: "Tensions or gaps",
  strongest_counter_position: "Strongest counter-position",
  consequence_if_correct: "Consequence if correct",
  role_in_book: "Role in book",
  one_sentence_decode: "One-sentence decode",
  confidence_and_unresolved: "Confidence & unresolved",
  source_block_references: "Source block references",
};

export const NODE_SHORT: Record<NodeType, string> = {
  chapter_question: "QUESTION",
  central_claim: "CENTRAL CLAIM",
  reasoning_steps: "REASONING",
  evidence_and_examples: "EVIDENCE",
  hidden_assumptions: "ASSUMPTIONS",
  tensions_or_gaps: "TENSIONS",
  strongest_counter_position: "COUNTER",
  consequence_if_correct: "CONSEQUENCE",
  role_in_book: "ROLE IN BOOK",
  one_sentence_decode: "ONE-SENTENCE DECODE",
  confidence_and_unresolved: "CONFIDENCE",
  source_block_references: "SOURCE INDEX",
};

/** Approximate canvas positions for 1a desktop layout (percent-ish px offsets). */
export const NODE_CANVAS_LAYOUT: Record<
  NodeType,
  { left: number; top: number; width: number }
> = {
  chapter_question: { left: 60, top: 20, width: 180 },
  central_claim: { left: 50, top: 120, width: 200 },
  reasoning_steps: { left: 0, top: 250, width: 180 },
  evidence_and_examples: { left: 220, top: 250, width: 190 },
  hidden_assumptions: { left: 440, top: 120, width: 180 },
  tensions_or_gaps: { left: 440, top: 250, width: 180 },
  strongest_counter_position: { left: 440, top: 380, width: 190 },
  consequence_if_correct: { left: 210, top: 470, width: 180 },
  role_in_book: { left: 0, top: 470, width: 170 },
  one_sentence_decode: { left: 160, top: 560, width: 210 },
  confidence_and_unresolved: { left: 550, top: 470, width: 180 },
  source_block_references: { left: 575, top: 20, width: 190 },
};

export function sourceStatusClass(status: SourceStatus): string {
  switch (status) {
    case "explicit_author":
      return "status-explicit";
    case "author_paraphrase":
      return "status-paraphrase";
    case "ai_inference":
      return "status-inference";
    case "external_counter":
      return "status-counter";
  }
}

export function sourceStatusColor(status: SourceStatus): string {
  switch (status) {
    case "explicit_author":
      return "var(--bd-explicit)";
    case "author_paraphrase":
      return "var(--bd-paraphrase)";
    case "ai_inference":
      return "var(--bd-inference)";
    case "external_counter":
      return "var(--bd-counter)";
  }
}

export function isTerminalBookStatus(status: string): boolean {
  return (
    status === "completed" ||
    status === "completed_with_errors" ||
    status === "failed" ||
    status === "cancelled"
  );
}

export function isBookReady(status: string): boolean {
  return status === "completed" || status === "completed_with_errors";
}

export function isChapterReady(status: string): boolean {
  return status === "completed";
}

export function validateEpubClient(file: File): { code: string; message: string } | null {
  const name = file.name.toLowerCase();
  if (!name.endsWith(".epub")) {
    return {
      code: "invalid_extension",
      message: "File must have a .epub extension.",
    };
  }
  if (file.size > MAX_EPUB_SIZE_BYTES) {
    return {
      code: "file_too_large",
      message: `EPUB exceeds the maximum size of ${MAX_EPUB_SIZE_MB} MB.`,
    };
  }
  return null;
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function shortBlockId(blockId: string): string {
  const parts = blockId.split(".");
  if (parts.length >= 2) {
    return parts.slice(-2).join(".");
  }
  return blockId;
}
