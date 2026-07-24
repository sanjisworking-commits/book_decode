import { NODE_SHORT, sourceStatusColor } from "../../lib/constants";
import type { LanguageMode, SpineNode } from "../../types/api";
import {
  explanationFor,
  isNullNode,
  isWarningNode,
  statementFor,
} from "./nodeHelpers";
import { shortBlockId } from "../../lib/constants";

type Props = {
  nodes: SpineNode[];
  expandedId: string | null;
  lang: LanguageMode;
  onToggle: (id: string) => void;
  onOpenSources: (ids: string[]) => void;
};

export function SpineThreaded1b({
  nodes,
  expandedId,
  lang,
  onToggle,
  onOpenSources,
}: Props) {
  return (
    <div className="surface" style={{ padding: "8px 0" }}>
      {nodes.map((node, idx) => {
        const expanded = expandedId === node.id;
        const color = sourceStatusColor(node.source_status);
        const nullish = isNullNode(node);
        const warn = isWarningNode(node);
        const statement = statementFor(node, lang);
        const explanation = explanationFor(node, lang);
        return (
          <div key={node.id} style={{ display: "flex", gap: 0 }}>
            <div
              style={{
                width: 28,
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                flexShrink: 0,
              }}
            >
              <span
                style={{
                  width: 10,
                  height: 10,
                  borderRadius: "50%",
                  background: color,
                  marginTop: 18,
                  zIndex: 1,
                }}
              />
              {idx < nodes.length - 1 && (
                <span
                  style={{
                    width: 2,
                    flex: 1,
                    background: "var(--bd-border)",
                    marginTop: 4,
                  }}
                />
              )}
            </div>
            <div style={{ flex: 1, padding: "10px 16px 10px 4px", borderBottom: "1px solid var(--bd-hairline)" }}>
              <button
                type="button"
                onClick={() => onToggle(node.id)}
                style={{
                  width: "100%",
                  textAlign: "left",
                  background: "transparent",
                  border: 0,
                  padding: 0,
                  font: "inherit",
                  color: "inherit",
                  cursor: "pointer",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
                  <span className="mono" style={{ fontSize: 11, fontWeight: 600, color }}>
                    {String(node.order + 1).padStart(2, "0")} · {NODE_SHORT[node.node_type]}
                  </span>
                  {warn && (
                    <span className="mono" style={{ fontSize: 10, color: "#8a6318" }}>
                      warn
                    </span>
                  )}
                  <span className="mono faint" style={{ marginLeft: "auto", fontSize: 11 }}>
                    {expanded ? "▾" : "▸"}
                  </span>
                </div>
                <div
                  style={{
                    fontSize: 14.5,
                    fontWeight: expanded ? 600 : 500,
                    color: nullish ? "var(--bd-faint)" : "var(--bd-ink)",
                    lineHeight: 1.4,
                  }}
                >
                  {nullish ? "Not established from text" : statement || "—"}
                </div>
              </button>

              {expanded && (
                <div className="anim-fade" style={{ marginTop: 10 }}>
                  {nullish ? (
                    <p className="muted" style={{ fontSize: 13, lineHeight: 1.5, margin: 0 }}>
                      The pipeline could not ground this node in allow-listed source blocks.
                    </p>
                  ) : (
                    explanation && (
                      <p className="muted" style={{ fontSize: 13, lineHeight: 1.55, margin: "0 0 10px" }}>
                        {explanation}
                      </p>
                    )
                  )}
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                    {node.confidence != null && (
                      <span className="mono faint" style={{ fontSize: 11, alignSelf: "center" }}>
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
                  </div>
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
