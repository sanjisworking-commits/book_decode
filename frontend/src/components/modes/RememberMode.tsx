import { useEffect, useState } from "react";
import type { RememberView } from "../../lib/spineViews";
import type { LanguageMode } from "../../types/api";

type Props = {
  view: RememberView;
  lang: LanguageMode;
  chapterId: string;
  isMobile?: boolean;
};

function MicroLabel({ children }: { children: string }) {
  return (
    <div
      className="mono"
      style={{
        fontSize: 10,
        fontWeight: 600,
        letterSpacing: "0.14em",
        textTransform: "uppercase",
        color: "var(--dr-accent)",
        marginBottom: 8,
      }}
    >
      {children}
    </div>
  );
}

export function RememberMode({ view, chapterId, isMobile }: Props) {
  const [flashOpen, setFlashOpen] = useState(false);

  useEffect(() => {
    setFlashOpen(false);
  }, [chapterId, view.flashFront?.statement]);

  const hasBody =
    view.takeaway ||
    view.keyPoints.length > 0 ||
    view.hook ||
    view.flashFront;

  if (!hasBody) {
    return (
      <div
        style={{
          background: "var(--dr-page)",
          borderRadius: 2,
          padding: "40px 28px",
          textAlign: "center",
          color: "var(--dr-ink)",
        }}
      >
        <p style={{ margin: 0, fontFamily: "var(--dr-font-serif)", fontSize: 17 }}>
          No revision nodes in this spine yet.
        </p>
      </div>
    );
  }

  return (
    <div
      style={{
        background: "var(--dr-page)",
        borderRadius: 2,
        padding: isMobile ? "20px 16px 32px" : "28px 32px 40px",
      }}
    >
      <div style={{ maxWidth: 560, margin: "0 auto" }}>
        {view.takeaway && (
          <div
            style={{
              background: "var(--dr-card)",
              border: "2px dashed var(--dr-accent)",
              borderRadius: 2,
              padding: "18px 20px",
              marginBottom: 24,
              transform: "rotate(-0.6deg)",
            }}
          >
            <MicroLabel>If you remember one line</MicroLabel>
            <div
              style={{
                fontFamily: "var(--dr-font-serif)",
                fontSize: 18,
                fontWeight: 600,
                lineHeight: 1.35,
                color: "var(--dr-ink)",
              }}
            >
              {view.takeaway.statement}
            </div>
          </div>
        )}

        {view.keyPoints.length > 0 && (
          <div style={{ marginBottom: 24 }}>
            <MicroLabel>Three key points</MicroLabel>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: isMobile
                  ? "1fr"
                  : `repeat(${Math.min(3, view.keyPoints.length)}, 1fr)`,
                gap: "var(--bd-2)",
              }}
            >
              {view.keyPoints.map((pt, i) => (
                <div
                  key={`${pt.statement}-${i}`}
                  style={{
                    background: "var(--dr-card)",
                    border: "1px solid color-mix(in srgb, var(--dr-ink) 14%, transparent)",
                    borderTop: "6px solid var(--dr-accent)",
                    borderRadius: 2,
                    padding: "14px 14px 16px",
                  }}
                >
                  <div
                    className="mono"
                    style={{
                      fontSize: 11,
                      letterSpacing: "0.12em",
                      color: "var(--dr-accent)",
                      marginBottom: 8,
                    }}
                  >
                    {String(i + 1).padStart(2, "0")}
                  </div>
                  <div
                    style={{
                      fontFamily: "var(--dr-font-serif)",
                      fontSize: 14,
                      lineHeight: 1.4,
                      color: "var(--dr-ink)",
                    }}
                  >
                    {pt.statement}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {view.hook && (
          <div style={{ marginBottom: 28 }}>
            <MicroLabel>⚓ Memory hook</MicroLabel>
            <div
              style={{
                fontFamily: "var(--dr-font-serif)",
                fontStyle: "italic",
                fontSize: 16,
                lineHeight: 1.45,
                color: "var(--dr-ink)",
              }}
            >
              {view.hook.statement}
            </div>
          </div>
        )}

        {view.flashFront && (
          <button
            type="button"
            onClick={() => setFlashOpen((v) => !v)}
            style={{
              width: "100%",
              textAlign: "left",
              background: "var(--dr-ink)",
              color: "var(--dr-card)",
              border: 0,
              borderRadius: 2,
              padding: "22px 22px 18px",
              cursor: "pointer",
              font: "inherit",
            }}
          >
            <div
              className="mono"
              style={{
                fontSize: 10,
                letterSpacing: "0.14em",
                textTransform: "uppercase",
                opacity: 0.7,
                marginBottom: 12,
              }}
            >
              Flashcard · {flashOpen ? "answer" : "question"}
            </div>
            {!flashOpen ? (
              <>
                <div
                  style={{
                    fontFamily: "var(--dr-font-serif)",
                    fontSize: 17,
                    fontWeight: 500,
                    lineHeight: 1.4,
                  }}
                >
                  {view.flashFront.statement}
                </div>
                <div
                  className="mono"
                  style={{ fontSize: 11, opacity: 0.65, marginTop: 14 }}
                >
                  {view.flashFrontIsClaimFallback
                    ? "tap to recall the central claim"
                    : "tap to reveal the answer"}
                </div>
              </>
            ) : (
              <>
                <div
                  style={{
                    fontFamily: "var(--dr-font-serif)",
                    fontSize: 17,
                    fontWeight: 600,
                    lineHeight: 1.4,
                  }}
                >
                  {view.flashBack?.statement ?? view.flashFront.statement}
                </div>
                {view.flashBack?.explanation && (
                  <div
                    style={{
                      fontFamily: "var(--dr-font-serif)",
                      fontStyle: "italic",
                      fontSize: 14,
                      lineHeight: 1.45,
                      opacity: 0.85,
                      marginTop: 10,
                    }}
                  >
                    {view.flashBack.explanation}
                  </div>
                )}
                <div
                  className="mono"
                  style={{ fontSize: 11, opacity: 0.65, marginTop: 14 }}
                >
                  tap for the question
                </div>
              </>
            )}
          </button>
        )}
      </div>
    </div>
  );
}
