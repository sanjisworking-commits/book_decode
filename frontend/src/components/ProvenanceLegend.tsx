import { NODE_LABELS, sourceStatusColor } from "../lib/constants";
import type { SourceStatus } from "../types/api";

const LEGEND: { status: SourceStatus; label: string }[] = [
  { status: "explicit_author", label: "Explicit author" },
  { status: "author_paraphrase", label: "Author paraphrase" },
  { status: "ai_inference", label: "AI inference" },
  { status: "external_counter", label: "External counter" },
];

export function ProvenanceLegend() {
  return (
    <div
      style={{
        display: "flex",
        flexWrap: "wrap",
        gap: 14,
        fontSize: 12,
        color: "var(--bd-muted)",
      }}
    >
      {LEGEND.map((item) => (
        <span key={item.status} style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
          <span
            className="status-dot"
            style={{ background: sourceStatusColor(item.status) }}
          />
          {item.label}
        </span>
      ))}
    </div>
  );
}

export function nodeTypeLabel(nodeType: keyof typeof NODE_LABELS): string {
  return NODE_LABELS[nodeType];
}
