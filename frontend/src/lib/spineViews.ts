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
  /** When true, front is a fallback recall of the claim (no question/objective). */
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

function byTypes(spine: ArgumentSpine, types: NodeType[]): SpineNode | undefined {
  for (const t of types) {
    const found = spine.nodes.find((n) => n.node_type === t);
    if (found) return found;
  }
  return undefined;
}

function allByTypes(spine: ArgumentSpine, types: NodeType[]): SpineNode[] {
  const wanted = new Set(types);
  return spine.nodes
    .filter((n) => wanted.has(n.node_type))
    .sort((a, b) => a.order - b.order);
}

export function toDecodeView(spine: ArgumentSpine, lang: LanguageMode): DecodeView {
  const claimNode = byTypes(spine, ["central_claim", "organising_idea"]);
  const claim = pick(claimNode, lang);
  const onesentence = pick(byTypes(spine, ["one_sentence_decode"]), lang);

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

  const logicChain = allByTypes(spine, [
    "reasoning_step",
    "reasoning_steps",
    "supporting_claim",
  ])
    .map((n) => pick(n, lang))
    .filter((v): v is ViewText => v != null);

  const examples = allByTypes(spine, [
    "evidence",
    "example",
    "evidence_and_examples",
  ])
    .map((n) => pick(n, lang))
    .filter((v): v is ViewText => v != null);
  const example = examples[0] ?? null;

  // Prefer source-grounded objections; keep legacy strongest_counter_position.
  const counter = pick(
    byTypes(spine, ["objection", "strongest_counter_position"]),
    lang,
  );

  return { claim, meaning, logicChain, example, counter };
}

export function toRememberView(
  spine: ArgumentSpine,
  lang: LanguageMode,
): RememberView {
  const claim = pick(byTypes(spine, ["central_claim", "organising_idea"]), lang);
  const hook = pick(byTypes(spine, ["one_sentence_decode"]), lang);
  const keyPoints = allByTypes(spine, [
    "reasoning_step",
    "reasoning_steps",
    "supporting_claim",
  ])
    .map((n) => pick(n, lang))
    .filter((v): v is ViewText => v != null)
    .slice(0, 3);

  const question = pick(
    byTypes(spine, ["chapter_question", "chapter_objective"]),
    lang,
  );
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
