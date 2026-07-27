/** Test-facing re-exports / mirrors of app helpers (avoids JSX transform issues). */
export {
  MAX_EPUB_SIZE_BYTES,
  isBookReady,
  validateEpubClient,
} from "../src/lib/constants";

import { isNullNode } from "../src/components/spine/nodeHelpers";
import type { SpineNode } from "../src/types/api";

export function isNullNodeLike(
  partial: Pick<SpineNode, "statement_en" | "source_block_ids" | "confidence" | "node_type">,
): boolean {
  return isNullNode({
    id: "n1",
    order: 0,
    source_status: "ai_inference",
    ...partial,
  });
}
