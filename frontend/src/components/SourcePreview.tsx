import { shortBlockId } from "../lib/constants";
import type { SourceBlock } from "../types/api";

export type SourcePreviewState =
  | { status: "closed" }
  | { status: "loading"; blockIds: string[] }
  | { status: "ready"; blocks: SourceBlock[]; missingIds: string[] }
  | { status: "missing"; blockIds: string[] }
  | { status: "error"; message: string };

type Props = {
  state: SourcePreviewState;
  onClose: () => void;
  activeBlockId?: string | null;
  onSelectBlock?: (id: string) => void;
};

export function SourcePreview({ state, onClose, activeBlockId, onSelectBlock }: Props) {
  if (state.status === "closed") return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Source preview"
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(35,32,27,.35)",
        display: "flex",
        alignItems: "flex-end",
        justifyContent: "center",
        zIndex: 50,
        padding: 16,
      }}
      onClick={onClose}
    >
      <div
        className="anim-fade surface"
        style={{
          width: "min(560px, 100%)",
          maxHeight: "78vh",
          overflow: "auto",
          padding: "22px 24px 24px",
          borderRadius: 14,
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: 14,
          }}
        >
          <div className="eyebrow">Source preview</div>
          <button type="button" className="btn btn-secondary" style={{ padding: "6px 12px" }} onClick={onClose}>
            Close
          </button>
        </div>

        {state.status === "loading" && (
          <div>
            <div
              className="anim-pulse"
              style={{
                height: 14,
                borderRadius: 6,
                background: "var(--bd-surface-2)",
                marginBottom: 10,
                width: "40%",
              }}
            />
            <div
              className="anim-pulse"
              style={{
                height: 72,
                borderRadius: 8,
                background: "var(--bd-surface-2)",
              }}
            />
            <div className="mono faint" style={{ fontSize: 11, marginTop: 12 }}>
              Loading {state.blockIds.map(shortBlockId).join(", ")}
            </div>
          </div>
        )}

        {state.status === "missing" && (
          <div style={{ textAlign: "center", padding: "24px 8px" }}>
            <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 6 }}>Source block not found</div>
            <div className="muted" style={{ fontSize: 13, lineHeight: 1.5, maxWidth: 280, margin: "0 auto" }}>
              This reference couldn’t be matched to a stored block — it may have shifted during re-processing.
            </div>
            <div className="mono faint" style={{ fontSize: 11, marginTop: 12 }}>
              {state.blockIds.join(", ")}
            </div>
          </div>
        )}

        {state.status === "error" && (
          <div className="muted">{state.message}</div>
        )}

        {state.status === "ready" && (
          <div>
            {(state.blocks.length > 1 || state.missingIds.length > 0) && (
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 14 }}>
                {state.blocks.map((b) => (
                  <button
                    key={b.block_id}
                    type="button"
                    className="mono"
                    onClick={() => onSelectBlock?.(b.block_id)}
                    style={{
                      fontSize: 11,
                      padding: "5px 9px",
                      borderRadius: 6,
                      border: `1px solid ${
                        activeBlockId === b.block_id ? "var(--bd-primary)" : "var(--bd-border)"
                      }`,
                      background: activeBlockId === b.block_id ? "var(--bd-primary)" : "#fff",
                      color: activeBlockId === b.block_id ? "#fff" : "var(--bd-muted)",
                    }}
                  >
                    {shortBlockId(b.block_id)}
                  </button>
                ))}
                {state.missingIds.map((id) => (
                  <span
                    key={id}
                    className="mono"
                    style={{
                      fontSize: 11,
                      padding: "5px 9px",
                      borderRadius: 6,
                      border: "1px dashed #d8b6ab",
                      color: "#934231",
                    }}
                  >
                    {shortBlockId(id)} · missing
                  </span>
                ))}
              </div>
            )}
            {state.blocks
              .filter((b) => !activeBlockId || b.block_id === activeBlockId)
              .map((b) => (
                <div key={b.block_id} style={{ marginBottom: 16 }}>
                  <div className="mono faint" style={{ fontSize: 11, marginBottom: 8 }}>
                    {b.block_id} · {b.block_type}
                  </div>
                  <div style={{ fontSize: 14.5, lineHeight: 1.6, color: "var(--bd-body)", whiteSpace: "pre-wrap" }}>
                    {b.text}
                  </div>
                </div>
              ))}
            {state.blocks.length === 0 && (
              <div className="muted">No matching source text for these IDs.</div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
