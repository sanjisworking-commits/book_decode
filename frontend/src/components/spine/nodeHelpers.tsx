import {
  LOW_CONFIDENCE_THRESHOLD,
  NODE_LABELS,
  NODE_SHORT,
  shortBlockId,
  sourceStatusClass,
  sourceStatusColor,
} from "../../lib/constants";
import type { LanguageMode, SpineNode } from "../../types/api";

export function statementFor(node: SpineNode, lang: LanguageMode): string | null {
  if (lang === "hinglish") {
    return node.statement_hinglish ?? node.statement_en;
  }
  return node.statement_en;
}

export function explanationFor(node: SpineNode, lang: LanguageMode): string | null {
  if (lang === "hinglish") {
    return node.explanation_hinglish ?? node.explanation_en ?? null;
  }
  return node.explanation_en ?? null;
}

export function isNullNode(node: SpineNode): boolean {
  const stmt = node.statement_en;
  const emptyStmt = stmt == null || String(stmt).trim() === "";
  const noSources =
    node.node_type !== "source_block_references" &&
    (node.source_block_ids?.length ?? 0) === 0;
  return emptyStmt || (noSources && node.confidence != null && node.confidence < 0.3);
}

export function isWarningNode(node: SpineNode): boolean {
  if (node.warnings && node.warnings.length > 0) return true;
  if (node.confidence != null && node.confidence <= LOW_CONFIDENCE_THRESHOLD) return true;
  return false;
}

type DetailProps = {
  node: SpineNode;
  lang: LanguageMode;
  onOpenSources: (ids: string[]) => void;
};

export function NodeDetailPanel({ node, lang, onOpenSources }: DetailProps) {
  const nullish = isNullNode(node);
  const warn = isWarningNode(node);
  const statement = statementFor(node, lang);
  const explanation = explanationFor(node, lang);
  const color = sourceStatusColor(node.source_status);

  return (
    <div className={`anim-fade ${sourceStatusClass(node.source_status)}`} style={{ padding: 4 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
        <span className="status-dot" style={{ background: color }} />
        <span className="eyebrow" style={{ color }}>
          {String(node.order + 1).padStart(2, "0")} · {NODE_SHORT[node.node_type]}
        </span>
        {warn && (
          <span
            className="mono"
            style={{
              marginLeft: "auto",
              fontSize: 11,
              color: "#8a6318",
              background: "var(--bd-inference-tint)",
              border: "1px solid #e4d7b8",
              borderRadius: 5,
              padding: "2px 7px",
            }}
          >
            low confidence
            {node.confidence != null ? ` · ${node.confidence.toFixed(2)}` : ""}
          </span>
        )}
      </div>

      {nullish ? (
        <div
          style={{
            border: "1px dashed var(--bd-border-strong)",
            borderRadius: 9,
            padding: "18px 16px",
            background: "var(--bd-surface-2)",
          }}
        >
          <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 6, color: "var(--bd-muted)" }}>
            Not established from text
          </div>
          <div className="muted" style={{ fontSize: 13, lineHeight: 1.5 }}>
            The pipeline could not ground this node in allow-listed source blocks. No statement is shown.
          </div>
        </div>
      ) : (
        <>
          <p style={{ fontSize: 18, lineHeight: 1.45, fontWeight: 600, margin: "0 0 14px" }}>
            {statement}
          </p>
          {explanation && (
            <p className="muted" style={{ fontSize: 14, lineHeight: 1.6, margin: "0 0 16px" }}>
              {explanation}
            </p>
          )}
        </>
      )}

      <div style={{ display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center" }}>
        {node.confidence != null && !warn && (
          <span className="mono faint" style={{ fontSize: 11 }}>
            conf {node.confidence.toFixed(2)}
          </span>
        )}
        {(node.source_block_ids ?? []).map((id) => (
          <button
            key={id}
            type="button"
            className="mono"
            onClick={() => onOpenSources([id])}
            style={{
              fontSize: 11,
              padding: "5px 9px",
              borderRadius: 6,
              border: "1px solid var(--bd-border)",
              background: "#fff",
              color: "var(--bd-muted)",
            }}
          >
            {shortBlockId(id)}
          </button>
        ))}
        {(node.source_block_ids?.length ?? 0) > 1 && (
          <button
            type="button"
            className="btn btn-secondary"
            style={{ padding: "5px 10px", fontSize: 12 }}
            onClick={() => onOpenSources(node.source_block_ids)}
          >
            View all sources
          </button>
        )}
      </div>

      <div className="muted" style={{ fontSize: 12, marginTop: 16 }}>
        {NODE_LABELS[node.node_type]} · {node.source_status.replaceAll("_", " ")}
      </div>
    </div>
  );
}
