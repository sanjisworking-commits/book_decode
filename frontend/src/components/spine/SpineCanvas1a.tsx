import {
  NODE_CANVAS_LAYOUT,
  NODE_SHORT,
  sourceStatusColor,
} from "../../lib/constants";
import type { LanguageMode, SpineNode } from "../../types/api";
import { isNullNode, NodeDetailPanel, statementFor } from "./nodeHelpers";

type Props = {
  nodes: SpineNode[];
  selectedId: string | null;
  lang: LanguageMode;
  onSelect: (id: string) => void;
  onOpenSources: (ids: string[]) => void;
};

export function SpineCanvas1a({
  nodes,
  selectedId,
  lang,
  onSelect,
  onOpenSources,
}: Props) {
  const selected = nodes.find((n) => n.id === selectedId) ?? nodes[0] ?? null;

  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "minmax(0, 1.35fr) minmax(280px, 0.9fr)",
        gap: 16,
        minHeight: 640,
      }}
    >
      <div
        className="surface"
        style={{
          position: "relative",
          minHeight: 640,
          overflow: "auto",
          background: "var(--bd-canvas)",
        }}
      >
        <div style={{ position: "relative", width: 780, height: 640, margin: "12px auto" }}>
          {nodes.map((node) => {
            const layout = NODE_CANVAS_LAYOUT[node.node_type] ?? {
              left: 20,
              top: 20,
              width: 180,
            };
            const selectedNode = selected?.id === node.id;
            const nullish = isNullNode(node);
            const color = sourceStatusColor(node.source_status);
            const line = statementFor(node, lang);
            return (
              <button
                key={node.id}
                type="button"
                onClick={() => onSelect(node.id)}
                style={{
                  position: "absolute",
                  left: layout.left,
                  top: layout.top,
                  width: layout.width,
                  textAlign: "left",
                  background: nullish ? "var(--bd-surface-2)" : "#fff",
                  border: `1px solid ${selectedNode ? color : "var(--bd-border)"}`,
                  borderLeft: `3px solid ${color}`,
                  borderRadius: 9,
                  padding: "10px 12px",
                  boxShadow: selectedNode
                    ? `0 0 0 3px color-mix(in srgb, ${color} 25%, transparent), var(--bd-shadow-2)`
                    : "var(--bd-shadow-1)",
                  cursor: "pointer",
                  font: "inherit",
                  color: "inherit",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
                  <span className="status-dot" style={{ background: color }} />
                  <span
                    className="mono"
                    style={{
                      fontSize: 11,
                      fontWeight: 600,
                      color,
                    }}
                  >
                    {String(node.order + 1).padStart(2, "0")} · {NODE_SHORT[node.node_type]}
                  </span>
                </div>
                <div
                  style={{
                    fontSize: selectedNode ? 12.5 : 12,
                    fontWeight: selectedNode && !nullish ? 600 : 400,
                    color: nullish ? "var(--bd-faint)" : selectedNode ? "var(--bd-ink)" : "var(--bd-muted)",
                    lineHeight: 1.35,
                  }}
                >
                  {nullish
                    ? "Not established from text"
                    : line
                      ? line.length > 90
                        ? `${line.slice(0, 87)}…`
                        : line
                      : "—"}
                </div>
              </button>
            );
          })}
        </div>
      </div>

      <div className="surface" style={{ padding: "20px 22px", overflow: "auto" }}>
        {selected ? (
          <NodeDetailPanel node={selected} lang={lang} onOpenSources={onOpenSources} />
        ) : (
          <div className="muted">Select a node to inspect.</div>
        )}
      </div>
    </div>
  );
}
