import type {
  ArgumentSpine,
  LanguageMode,
  NodeType,
  SourceStatus,
  SpineNode,
} from "../types/api";

export type ViewText = {
  statement: string;
  explanation: string | null;
  status: SourceStatus;
  blockIds: string[];
};

export type DecodeView = {
  claim: ViewText | null;
  meaning: ViewText | null;
  logicChain: ViewText[];
  example: ViewText | null;
  counter: ViewText | null;
};

export type RememberView = {
  takeaway: ViewText | null;
  keyPoints: ViewText[];
  hook: ViewText | null;
  flashFront: ViewText | null;
  flashBack: ViewText | null;
  /** When true, front is a fallback recall of the central claim (no chapter_question). */
  flashFrontIsClaimFallback: boolean;
};

function pick(n: SpineNode | undefined, lang: LanguageMode): ViewText | null {
  if (!n) return null;
  const st =
    lang === "hinglish" ? n.statement_hinglish ?? n.statement_en : n.statement_en;
  if (!st || !String(st).trim()) return null;
  const ex =
    lang === "hinglish"
      ? n.explanation_hinglish ?? n.explanation_en ?? null
      : n.explanation_en ?? null;
  return {
    statement: st,
    explanation: ex,
    status: n.source_status,
    blockIds: n.source_block_ids ?? [],
  };
}

function byType(spine: ArgumentSpine, t: NodeType): SpineNode | undefined {
  return spine.nodes.find((n) => n.node_type === t);
}

function allByType(spine: ArgumentSpine, t: NodeType): SpineNode[] {
  return spine.nodes
    .filter((n) => n.node_type === t)
    .sort((a, b) => a.order - b.order);
}

export function toDecodeView(spine: ArgumentSpine, lang: LanguageMode): DecodeView {
  const claimNode = byType(spine, "central_claim");
  const claim = pick(claimNode, lang);
  const onesentence = pick(byType(spine, "one_sentence_decode"), lang);

  let meaning: ViewText | null = null;
  if (claim?.explanation) {
    meaning = {
      statement: claim.explanation,
      explanation: null,
      status: claim.status,
      blockIds: claim.blockIds,
    };
  } else if (onesentence) {
    meaning = onesentence;
  }

  const logicChain = allByType(spine, "reasoning_steps")
    .map((n) => pick(n, lang))
    .filter((v): v is ViewText => v != null);

  const examples = allByType(spine, "evidence_and_examples")
    .map((n) => pick(n, lang))
    .filter((v): v is ViewText => v != null);
  const example = examples[0] ?? null;

  const counter = pick(byType(spine, "strongest_counter_position"), lang);

  return { claim, meaning, logicChain, example, counter };
}

export function toRememberView(
  spine: ArgumentSpine,
  lang: LanguageMode,
): RememberView {
  const claim = pick(byType(spine, "central_claim"), lang);
  const hook = pick(byType(spine, "one_sentence_decode"), lang);
  const keyPoints = allByType(spine, "reasoning_steps")
    .map((n) => pick(n, lang))
    .filter((v): v is ViewText => v != null)
    .slice(0, 3);

  const question = pick(byType(spine, "chapter_question"), lang);
  const flashFrontIsClaimFallback = !question && Boolean(claim);
  const flashFront = question ?? (claim ? { ...claim } : null);

  let flashBack: ViewText | null = null;
  if (claim) {
    flashBack = {
      statement: claim.statement,
      explanation: hook?.statement ?? claim.explanation,
      status: claim.status,
      blockIds: claim.blockIds,
    };
  }

  return {
    takeaway: claim,
    keyPoints,
    hook,
    flashFront,
    flashBack,
    flashFrontIsClaimFallback,
  };
}
