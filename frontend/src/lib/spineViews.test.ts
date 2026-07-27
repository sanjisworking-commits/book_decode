import { describe, expect, it } from "vitest";
import { toDecodeView, toRememberView } from "./spineViews";
import type { ArgumentSpine, SpineNode } from "../types/api";

function node(
  partial: Partial<SpineNode> & Pick<SpineNode, "id" | "node_type" | "order">,
): SpineNode {
  return {
    statement_en: null,
    explanation_en: null,
    statement_hinglish: null,
    explanation_hinglish: null,
    source_status: "explicit_author",
    source_block_ids: [],
    confidence: 0.9,
    ...partial,
  };
}

function spine(nodes: SpineNode[]): ArgumentSpine {
  return {
    schema_version: "2.0",
    book_id: "test-book",
    chapter_id: "ch01",
    language_modes: ["en", "hinglish"],
    nodes,
  };
}

const fullNodes: SpineNode[] = [
  node({
    id: "q",
    node_type: "chapter_question",
    order: 0,
    statement_en: "How does intelligence emerge?",
    statement_hinglish: "Intelligence kaise emerge hoti hai?",
    source_status: "author_paraphrase",
    source_block_ids: ["b1"],
  }),
  node({
    id: "c",
    node_type: "central_claim",
    order: 1,
    statement_en: "Many parallel models vote.",
    explanation_en: "Not one central processor.",
    statement_hinglish: "Kai parallel models vote.",
    explanation_hinglish: "Ek central processor nahi.",
    source_status: "explicit_author",
    source_block_ids: ["b2"],
  }),
  node({
    id: "r1",
    node_type: "reasoning_step",
    order: 2,
    statement_en: "Step one.",
    statement_hinglish: "Pehla step.",
  }),
  node({
    id: "r2",
    node_type: "reasoning_step",
    order: 3,
    statement_en: "Step two.",
  }),
  node({
    id: "r3",
    node_type: "supporting_claim",
    order: 4,
    statement_en: "Step three.",
  }),
  node({
    id: "r4",
    node_type: "reasoning_step",
    order: 5,
    statement_en: "Step four (decode only).",
  }),
  node({
    id: "e",
    node_type: "evidence",
    order: 6,
    statement_en: "Coffee cup recognition.",
    source_status: "author_paraphrase",
  }),
  node({
    id: "x",
    node_type: "objection",
    order: 7,
    statement_en: "Voting is underspecified.",
    source_status: "source_based_objection",
  }),
  node({
    id: "o",
    node_type: "one_sentence_decode",
    order: 8,
    statement_en: "Many models vote — not one processor.",
    statement_hinglish: "Kai models vote karte hain.",
  }),
];

describe("toDecodeView", () => {
  it("maps claim, chain, meaning, example, counter", () => {
    const view = toDecodeView(spine(fullNodes), "en");
    expect(view.claim?.statement).toContain("parallel models");
    expect(view.meaning?.statement).toBe("Not one central processor.");
    expect(view.logicChain).toHaveLength(4);
    expect(view.example?.statement).toContain("Coffee cup");
    expect(view.counter?.statement).toContain("underspecified");
  });

  it("falls back claim to organising_idea when central_claim missing", () => {
    const nodes = fullNodes
      .filter((n) => n.node_type !== "central_claim")
      .concat([
        node({
          id: "oi",
          node_type: "organising_idea",
          order: 1,
          statement_en: "Organising idea as claim.",
        }),
      ]);
    const view = toDecodeView(spine(nodes), "en");
    expect(view.claim?.statement).toContain("Organising idea");
  });

  it("falls back meaning to one_sentence_decode when claim has no explanation", () => {
    const nodes = fullNodes.map((n) =>
      n.node_type === "central_claim" ? { ...n, explanation_en: null } : n,
    );
    const view = toDecodeView(spine(nodes), "en");
    expect(view.meaning?.statement).toBe("Many models vote — not one processor.");
  });

  it("omits missing nodes instead of inventing", () => {
    const view = toDecodeView(
      spine([
        node({
          id: "c",
          node_type: "central_claim",
          order: 1,
          statement_en: "Only a claim.",
        }),
      ]),
      "en",
    );
    expect(view.claim?.statement).toBe("Only a claim.");
    expect(view.meaning).toBeNull();
    expect(view.logicChain).toEqual([]);
    expect(view.example).toBeNull();
    expect(view.counter).toBeNull();
  });

  it("uses hinglish with en fallback", () => {
    const view = toDecodeView(spine(fullNodes), "hinglish");
    expect(view.claim?.statement).toContain("parallel models");
    expect(view.logicChain[1]?.statement).toBe("Step two.");
  });

  it("prefers example over evidence_and_examples when both present", () => {
    const view = toDecodeView(
      spine([
        node({
          id: "ex",
          node_type: "example",
          order: 1,
          statement_en: "Concrete example.",
        }),
        node({
          id: "legacy",
          node_type: "evidence_and_examples",
          order: 2,
          statement_en: "Legacy blob.",
        }),
      ]),
      "en",
    );
    expect(view.example?.statement).toBe("Concrete example.");
  });
});

describe("toRememberView", () => {
  it("maps takeaway, three key points, hook, and flashcard", () => {
    const view = toRememberView(spine(fullNodes), "en");
    expect(view.takeaway?.statement).toContain("parallel models");
    expect(view.keyPoints).toHaveLength(3);
    expect(view.hook?.statement).toContain("Many models vote");
    expect(view.flashFront?.statement).toContain("How does intelligence");
    expect(view.flashBack?.statement).toContain("parallel models");
    expect(view.flashBack?.explanation).toContain("Many models vote");
    expect(view.flashFrontIsClaimFallback).toBe(false);
  });

  it("uses chapter_objective for flash front when question missing", () => {
    const nodes = fullNodes
      .filter((n) => n.node_type !== "chapter_question")
      .concat([
        node({
          id: "obj",
          node_type: "chapter_objective",
          order: 0,
          statement_en: "Learn the organising claim.",
        }),
      ]);
    const view = toRememberView(spine(nodes), "en");
    expect(view.flashFrontIsClaimFallback).toBe(false);
    expect(view.flashFront?.statement).toContain("organising claim");
  });

  it("falls back flash front to central claim when question missing", () => {
    const nodes = fullNodes.filter((n) => n.node_type !== "chapter_question");
    const view = toRememberView(spine(nodes), "en");
    expect(view.flashFrontIsClaimFallback).toBe(true);
    expect(view.flashFront?.statement).toContain("parallel models");
  });

  it("renders fewer than three key points when steps are missing", () => {
    const view = toRememberView(
      spine([
        node({
          id: "c",
          node_type: "central_claim",
          order: 1,
          statement_en: "Claim only.",
        }),
        node({
          id: "r1",
          node_type: "reasoning_step",
          order: 2,
          statement_en: "Only one step.",
        }),
      ]),
      "en",
    );
    expect(view.keyPoints).toHaveLength(1);
    expect(view.hook).toBeNull();
  });

  it("returns null fields when spine is empty", () => {
    const view = toRememberView(spine([]), "en");
    expect(view.takeaway).toBeNull();
    expect(view.keyPoints).toEqual([]);
    expect(view.flashFront).toBeNull();
    expect(view.flashBack).toBeNull();
  });
});
