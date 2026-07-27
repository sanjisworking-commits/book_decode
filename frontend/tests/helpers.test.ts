import { describe, expect, it } from "vitest";
import {
  isBookReady,
  isNullNodeLike,
  validateSourceJsonClient,
  MAX_JSON_SIZE_BYTES,
} from "./helpers";

describe("validateSourceJsonClient", () => {
  it("rejects non-json extension", () => {
    const file = new File(["x"], "notes.pdf", { type: "application/pdf" });
    const err = validateSourceJsonClient(file);
    expect(err?.code).toBe("invalid_extension");
  });

  it("rejects oversized json", () => {
    const file = new File([new Uint8Array(MAX_JSON_SIZE_BYTES + 1)], "big.json");
    const err = validateSourceJsonClient(file);
    expect(err?.code).toBe("file_too_large");
  });

  it("accepts small json", () => {
    const file = new File(["{}"], "ok.json");
    expect(validateSourceJsonClient(file)).toBeNull();
  });
});

describe("book ready mapping", () => {
  it("treats completed and completed_with_errors as ready", () => {
    expect(isBookReady("completed")).toBe(true);
    expect(isBookReady("completed_with_errors")).toBe(true);
    expect(isBookReady("analysing_chapters")).toBe(false);
    expect(isBookReady("failed")).toBe(false);
  });
});

describe("null node heuristic", () => {
  it("flags empty statement", () => {
    expect(
      isNullNodeLike({
        statement_en: null,
        source_block_ids: [],
        confidence: null,
        node_type: "central_claim",
      }),
    ).toBe(true);
  });

  it("keeps grounded statement", () => {
    expect(
      isNullNodeLike({
        statement_en: "A real claim from the pipeline",
        source_block_ids: ["b.ch01.sec01.block001"],
        confidence: 0.9,
        node_type: "central_claim",
      }),
    ).toBe(false);
  });
});
