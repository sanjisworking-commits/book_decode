import { UI_STAGES } from "../lib/constants";
import type { ChapterSummary, ProcessingStatus } from "../types/api";

type Props = {
  status: ProcessingStatus;
};

function stageState(
  index: number,
  currentIndex: number,
  done: boolean,
): "done" | "active" | "pending" {
  if (done || index < currentIndex) return "done";
  if (index === currentIndex) return "active";
  return "pending";
}

function chapterTone(status: string): { label: string; color: string } {
  if (status === "completed") return { label: "Ready", color: "#2f6640" };
  if (status === "failed") return { label: "Failed", color: "#934231" };
  if (status === "retrying") return { label: "Retrying", color: "#8a6318" };
  if (
    status === "extracting" ||
    status === "synthesising" ||
    status === "adapting_hinglish" ||
    status === "validating" ||
    status === "chunking"
  ) {
    return { label: "Working", color: "var(--bd-primary)" };
  }
  return { label: "Pending", color: "var(--bd-faint)" };
}

export function ProcessingView({ status }: Props) {
  const done = status.processing_status === "completed" ||
    status.processing_status === "completed_with_errors";
  const failed = status.processing_status === "failed";
  const currentIndex = Math.max(0, Math.min(status.stage_index - 1, UI_STAGES.length - 1));

  return (
    <div className="surface" style={{ padding: "28px 28px 24px" }}>
      <div className="eyebrow" style={{ marginBottom: 8 }}>
        Decoding
      </div>
      <h1 style={{ fontSize: 28, fontWeight: 600, letterSpacing: "-0.02em", margin: "0 0 8px" }}>
        {failed ? "Couldn’t decode this book" : done ? "Book ready" : "Working through your book"}
      </h1>
      <p className="muted" style={{ margin: "0 0 24px", lineHeight: 1.5 }}>
        {failed
          ? status.error?.message ?? "A book-level failure stopped the pipeline."
          : done
            ? `${status.processed_chapter_count} of ${status.chapter_count} chapters decoded.`
            : `Stage ${status.stage_index} of ${status.stages_total} · ${status.processed_chapter_count}/${status.chapter_count || "?"} chapters ready`}
      </p>

      {!failed && (
        <div style={{ marginBottom: 28 }}>
          {UI_STAGES.map((stage, i) => {
            const st = stageState(i, currentIndex, done);
            return (
              <div
                key={stage.key}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 12,
                  padding: "8px 0",
                  fontSize: 14,
                  fontWeight: st === "active" ? 600 : 400,
                  color:
                    st === "pending"
                      ? "var(--bd-disabled)"
                      : st === "active"
                        ? "var(--bd-ink)"
                        : "var(--bd-muted)",
                }}
              >
                <span
                  className={st === "active" ? "anim-pulse" : undefined}
                  style={{
                    width: 16,
                    height: 16,
                    borderRadius: "50%",
                    border:
                      st === "done"
                        ? "2px solid var(--bd-explicit)"
                        : st === "active"
                          ? "2px solid var(--bd-primary)"
                          : "2px solid var(--bd-border)",
                    background: st === "done" ? "var(--bd-explicit)" : "transparent",
                    flexShrink: 0,
                  }}
                />
                {stage.label}
              </div>
            );
          })}
        </div>
      )}

      {failed && status.error && (
        <div
          className="mono faint"
          style={{
            fontSize: 11.5,
            background: "var(--bd-surface-2)",
            border: "1px solid var(--bd-border)",
            borderRadius: 7,
            padding: "8px 12px",
            marginBottom: 20,
          }}
        >
          failed at stage {status.stage_index} / {status.stages_total} · error: {status.error.code}
        </div>
      )}

      {status.chapters.length > 0 && !failed && (
        <ChapterGrid chapters={status.chapters} currentId={status.current_chapter_id} />
      )}
    </div>
  );
}

function ChapterGrid({
  chapters,
  currentId,
}: {
  chapters: ChapterSummary[];
  currentId: string | null;
}) {
  return (
    <div>
      <div className="eyebrow" style={{ marginBottom: 12 }}>
        Chapters
      </div>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(140px, 1fr))",
          gap: 10,
        }}
      >
        {chapters.map((ch) => {
          const tone = chapterTone(ch.status);
          const active = ch.chapter_id === currentId;
          return (
            <div
              key={ch.chapter_id}
              style={{
                border: `1px solid ${active ? "var(--bd-primary)" : "var(--bd-border)"}`,
                borderRadius: 11,
                padding: "12px 14px",
                background: "#fff",
              }}
            >
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  marginBottom: 6,
                  gap: 8,
                }}
              >
                <span className="mono faint" style={{ fontSize: 11 }}>
                  {ch.chapter_id.toUpperCase()}
                </span>
                <span
                  style={{
                    fontSize: 11,
                    fontWeight: 600,
                    color: tone.color,
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 5,
                  }}
                >
                  <span
                    className={
                      tone.label === "Working" || tone.label === "Retrying"
                        ? "status-dot anim-pulse"
                        : "status-dot"
                    }
                    style={{ background: tone.color }}
                  />
                  {tone.label}
                </span>
              </div>
              <div
                style={{
                  fontSize: 13,
                  fontWeight: 500,
                  lineHeight: 1.3,
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
              >
                {ch.title || ch.chapter_id}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
