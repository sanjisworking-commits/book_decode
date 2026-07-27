import type { NodeType, SourceStatus } from "../types/api";

export const MAX_EPUB_SIZE_MB = 50;
export const MAX_EPUB_SIZE_BYTES = MAX_EPUB_SIZE_MB * 1024 * 1024;
export const MAX_JSON_SIZE_MB = 50;
export const MAX_JSON_SIZE_BYTES = MAX_JSON_SIZE_MB * 1024 * 1024;
export const LOW_CONFIDENCE_THRESHOLD = 0.55;

export const UI_STAGES: { key: string; label: string }[] = [
  { key: "uploading", label: "Uploading source JSON" },
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
  chapter_objective: "Chapter objective",
  chapter_question: "Chapter question",
  central_claim: "Central claim",
  organising_idea: "Organising idea",
  supporting_claim: "Supporting claim",
  reasoning_step: "Reasoning step",
  reasoning_steps: "Reasoning steps",
  definition: "Definition",
  evidence: "Evidence",
  example: "Example",
  analogy: "Analogy",
  quotation: "Quotation",
  evidence_and_examples: "Evidence & examples",
  assumption: "Assumption",
  hidden_assumptions: "Hidden assumptions",
  qualification: "Qualification",
  objection: "Objection",
  response: "Response",
  implication: "Implication",
  consequence_if_correct: "Consequence if correct",
  narrative_context: "Narrative context",
  historical_context: "Historical context",
  transition: "Transition",
  tensions_or_gaps: "Tensions or gaps",
  strongest_counter_position: "Strongest counter-position",
  role_in_book: "Role in book",
  one_sentence_decode: "One-sentence decode",
  unresolved_question: "Unresolved question",
  confidence_and_unresolved: "Confidence & unresolved",
  source_block_references: "Source block references",
};

export const NODE_SHORT: Record<NodeType, string> = {
  chapter_objective: "OBJECTIVE",
  chapter_question: "QUESTION",
  central_claim: "CENTRAL CLAIM",
  organising_idea: "ORGANISING IDEA",
  supporting_claim: "SUPPORTING CLAIM",
  reasoning_step: "REASONING",
  reasoning_steps: "REASONING",
  definition: "DEFINITION",
  evidence: "EVIDENCE",
  example: "EXAMPLE",
  analogy: "ANALOGY",
  quotation: "QUOTATION",
  evidence_and_examples: "EVIDENCE",
  assumption: "ASSUMPTION",
  hidden_assumptions: "ASSUMPTIONS",
  qualification: "QUALIFICATION",
  objection: "OBJECTION",
  response: "RESPONSE",
  implication: "IMPLICATION",
  consequence_if_correct: "CONSEQUENCE",
  narrative_context: "NARRATIVE",
  historical_context: "HISTORICAL",
  transition: "TRANSITION",
  tensions_or_gaps: "TENSIONS",
  strongest_counter_position: "COUNTER",
  role_in_book: "ROLE IN BOOK",
  one_sentence_decode: "ONE-SENTENCE DECODE",
  unresolved_question: "UNRESOLVED",
  confidence_and_unresolved: "CONFIDENCE",
  source_block_references: "SOURCE INDEX",
};

/** Approximate canvas positions for 1a desktop layout (percent-ish px offsets). */
export const NODE_CANVAS_LAYOUT: Record<
  NodeType,
  { left: number; top: number; width: number }
> = {
  chapter_objective: { left: 60, top: 0, width: 180 },
  chapter_question: { left: 60, top: 20, width: 180 },
  central_claim: { left: 50, top: 120, width: 200 },
  organising_idea: { left: 260, top: 80, width: 190 },
  supporting_claim: { left: 0, top: 200, width: 180 },
  reasoning_step: { left: 0, top: 250, width: 180 },
  reasoning_steps: { left: 0, top: 250, width: 180 },
  definition: { left: 220, top: 200, width: 170 },
  evidence: { left: 220, top: 250, width: 190 },
  example: { left: 220, top: 320, width: 180 },
  analogy: { left: 420, top: 200, width: 170 },
  quotation: { left: 420, top: 270, width: 170 },
  evidence_and_examples: { left: 220, top: 250, width: 190 },
  assumption: { left: 440, top: 120, width: 180 },
  hidden_assumptions: { left: 440, top: 120, width: 180 },
  qualification: { left: 440, top: 250, width: 180 },
  objection: { left: 440, top: 380, width: 190 },
  response: { left: 440, top: 460, width: 180 },
  implication: { left: 210, top: 470, width: 180 },
  consequence_if_correct: { left: 210, top: 470, width: 180 },
  narrative_context: { left: 0, top: 380, width: 180 },
  historical_context: { left: 0, top: 430, width: 180 },
  transition: { left: 210, top: 380, width: 160 },
  tensions_or_gaps: { left: 440, top: 250, width: 180 },
  strongest_counter_position: { left: 440, top: 380, width: 190 },
  role_in_book: { left: 0, top: 470, width: 170 },
  one_sentence_decode: { left: 160, top: 560, width: 210 },
  unresolved_question: { left: 550, top: 470, width: 180 },
  confidence_and_unresolved: { left: 550, top: 470, width: 180 },
  source_block_references: { left: 575, top: 20, width: 190 },
};

export function sourceStatusClass(status: SourceStatus): string {
  switch (status) {
    case "explicit_author":
      return "status-explicit";
    case "author_paraphrase":
      return "status-paraphrase";
    case "quoted_position":
      return "status-quoted";
    case "source_based_inference":
      return "status-source-inference";
    case "source_based_objection":
      return "status-source-objection";
    case "ai_inference":
      return "status-inference";
    case "external_counter":
      return "status-counter";
    default:
      return "status-inference";
  }
}

export function sourceStatusColor(status: SourceStatus): string {
  switch (status) {
    case "explicit_author":
      return "var(--bd-explicit)";
    case "author_paraphrase":
      return "var(--bd-paraphrase)";
    case "quoted_position":
      return "var(--bd-quoted, var(--bd-paraphrase))";
    case "source_based_inference":
      return "var(--bd-source-inference, var(--bd-inference))";
    case "source_based_objection":
      return "var(--bd-source-objection, #8a5a2b)";
    case "ai_inference":
      return "var(--bd-inference)";
    case "external_counter":
      return "var(--bd-counter)";
    default:
      return "var(--bd-inference)";
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
  return validateSourceJsonClient(file);
}

export function validateSourceJsonClient(
  file: File,
): { code: string; message: string } | null {
  const name = file.name.toLowerCase();
  if (!name.endsWith(".json")) {
    return {
      code: "invalid_extension",
      message: "File must have a .json extension.",
    };
  }
  if (file.size > MAX_JSON_SIZE_BYTES) {
    return {
      code: "file_too_large",
      message: `JSON exceeds the maximum size of ${MAX_JSON_SIZE_MB} MB.`,
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
