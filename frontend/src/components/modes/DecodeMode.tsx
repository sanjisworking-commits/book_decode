import { useState } from "react";
import { shortBlockId, sourceStatusColor } from "../../lib/constants";
import type { DecodeView, LogicStepView, ViewText } from "../../lib/spineViews";
import type { LanguageMode } from "../../types/api";

type Props = {
  view: DecodeView;
  lang: LanguageMode;
  onOpenSources: (ids: string[]) => void;
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

function SourceChips({
  item,
  onOpenSources,
}: {
  item: ViewText;
  onOpenSources: (ids: string[]) => void;
}) {
  if (!item.blockIds.length) return null;
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 10 }}>
      {item.blockIds.slice(0, 6).map((id) => (
        <button
          key={id}
          type="button"
          className="mono"
          onClick={() => onOpenSources([id])}
          style={{
            fontSize: 10,
            padding: "3px 7px",
            borderRadius: 2,
            border: `1px solid ${sourceStatusColor(item.status)}`,
            background: "transparent",
            color: sourceStatusColor(item.status),
            cursor: "pointer",
          }}
        >
          {shortBlockId(id)}
        </button>
      ))}
      {item.blockIds.length > 1 && (
        <button
          type="button"
          className="mono"
          onClick={() => onOpenSources(item.blockIds)}
          style={{
            fontSize: 10,
            padding: "3px 7px",
            border: 0,
            background: "transparent",
            color: "var(--dr-accent)",
            cursor: "pointer",
            textDecoration: "underline",
          }}
        >
          all sources
        </button>
      )}
    </div>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: string;
}) {
  return (
    <button
      type="button"
      className="mono"
      onClick={onClick}
      style={{
        fontSize: 10,
        fontWeight: 600,
        letterSpacing: "0.12em",
        textTransform: "uppercase",
        padding: "6px 12px",
        border: 0,
        borderBottom: `2px solid ${active ? "var(--dr-accent)" : "transparent"}`,
        background: "transparent",
        color: active ? "var(--dr-accent)" : "color-mix(in srgb, var(--dr-ink) 45%, transparent)",
        cursor: "pointer",
      }}
    >
      {children}
    </button>
  );
}

function LogicStep({
  step,
  onOpenSources,
}: {
  step: LogicStepView;
  onOpenSources: (ids: string[]) => void;
}) {
  const [open, setOpen] = useState(false);
  const hasWhy = Boolean(step.explanation && step.explanation.trim());
  const hasExample = Boolean(step.example);
  const [tab, setTab] = useState<"why" | "example">(hasWhy ? "why" : "example");
  const canExpand = hasWhy || hasExample || step.blockIds.length > 0;
  const showTabs = hasWhy && hasExample;
  const activeTab = showTabs ? tab : hasWhy ? "why" : "example";

  return (
    <div
      style={{
        background: "var(--dr-node)",
        border: "1px solid color-mix(in srgb, var(--dr-ink) 18%, transparent)",
        borderLeft: `3px solid ${sourceStatusColor(step.status)}`,
        borderRadius: 2,
        padding: "14px 16px",
      }}
    >
      <div style={{ display: "flex", gap: 12, alignItems: "flex-start" }}>
        <div
          className="mono"
          style={{ flex: 1, fontSize: 11, color: "var(--dr-ink)", lineHeight: 1.45 }}
        >
          {step.statement}
        </div>
        {canExpand && (
          <button
            type="button"
            className="mono"
            onClick={() => setOpen((o) => !o)}
            aria-expanded={open}
            style={{
              flex: "none",
              fontSize: 10,
              letterSpacing: "0.06em",
              textTransform: "uppercase",
              color: "var(--dr-accent)",
              background: "transparent",
              border: 0,
              cursor: "pointer",
              whiteSpace: "nowrap",
            }}
          >
            {open ? "collapse −" : "expand +"}
          </button>
        )}
      </div>

      {open && (
        <div style={{ marginTop: 12 }}>
          {showTabs && (
            <div
              style={{
                display: "flex",
                gap: 4,
                borderBottom: "1px solid color-mix(in srgb, var(--dr-ink) 14%, transparent)",
                marginBottom: 12,
              }}
            >
              <TabButton active={activeTab === "why"} onClick={() => setTab("why")}>
                Why it matters
              </TabButton>
              <TabButton active={activeTab === "example"} onClick={() => setTab("example")}>
                Example
              </TabButton>
            </div>
          )}

          {activeTab === "why" && hasWhy && (
            <div
              style={{
                background: "color-mix(in srgb, var(--dr-accent) 8%, transparent)",
                borderLeft: "3px solid var(--dr-accent)",
                borderRadius: 2,
                padding: "12px 14px",
              }}
            >
              {!showTabs && <MicroLabel>Why it matters</MicroLabel>}
              <div
                style={{
                  fontFamily: "var(--dr-font-serif)",
                  fontSize: 14.5,
                  lineHeight: 1.55,
                  color: "var(--dr-ink)",
                }}
              >
                {step.explanation}
              </div>
              <SourceChips item={step} onOpenSources={onOpenSources} />
            </div>
          )}

          {activeTab === "example" && step.example && (
            <div
              style={{
                background: "var(--dr-card)",
                border: "1px dashed color-mix(in srgb, var(--dr-accent) 55%, transparent)",
                borderRadius: 2,
                padding: "12px 14px",
              }}
            >
              {!showTabs && <MicroLabel>Example</MicroLabel>}
              {step.example.title && (
                <div
                  className="mono"
                  style={{
                    fontSize: 11,
                    fontWeight: 600,
                    letterSpacing: "0.04em",
                    color: "var(--dr-accent)",
                    marginBottom: 6,
                  }}
                >
                  {step.example.title}
                </div>
              )}
              <div
                style={{
                  fontFamily: "var(--dr-font-serif)",
                  fontStyle: "italic",
                  fontSize: 14.5,
                  lineHeight: 1.55,
                  color: "var(--dr-ink)",
                }}
              >
                {step.example.text}
              </div>
              <div
                className="mono"
                style={{
                  fontSize: 9,
                  letterSpacing: "0.08em",
                  textTransform: "uppercase",
                  color: "color-mix(in srgb, var(--dr-ink) 45%, transparent)",
                  marginTop: 10,
                }}
              >
                ✦ AI-generated example · not from the book
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function DecodeMode({ view, onOpenSources, isMobile }: Props) {
  const hasBody =
    view.claim ||
    view.logicChain.length > 0 ||
    view.meaning ||
    view.example ||
    view.counter;

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
          No decodeable nodes in this spine yet.
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
      <div style={{ maxWidth: 640, margin: "0 auto" }}>
        {view.claim && (
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1fr auto",
              background: "var(--dr-card)",
              border: "2px solid var(--dr-ink)",
              borderRadius: 2,
              marginBottom: 28,
              overflow: "hidden",
            }}
          >
            <div style={{ padding: "20px 22px" }}>
              <MicroLabel>Claim under test</MicroLabel>
              <div
                style={{
                  borderLeft: `3px solid ${sourceStatusColor(view.claim.status)}`,
                  paddingLeft: 12,
                }}
              >
                <div
                  style={{
                    fontFamily: "var(--dr-font-serif)",
                    fontSize: 21,
                    fontWeight: 600,
                    lineHeight: 1.28,
                    color: "var(--dr-ink)",
                  }}
                >
                  {view.claim.statement}
                </div>
                {view.claim.explanation && (
                  <div
                    style={{
                      fontFamily: "var(--dr-font-serif)",
                      fontSize: 14.5,
                      lineHeight: 1.55,
                      color: "color-mix(in srgb, var(--dr-ink) 70%, transparent)",
                      marginTop: 8,
                    }}
                  >
                    {view.claim.explanation}
                  </div>
                )}
              </div>
              <SourceChips item={view.claim} onOpenSources={onOpenSources} />
            </div>
            <div
              className="mono"
              style={{
                writingMode: "vertical-rl",
                transform: "rotate(180deg)",
                background: "var(--dr-accent)",
                color: "var(--dr-card)",
                letterSpacing: "0.22em",
                fontSize: 11,
                fontWeight: 600,
                padding: "14px 10px",
                textAlign: "center",
              }}
            >
              DECODED
            </div>
          </div>
        )}

        {view.logicChain.length > 0 && (
          <div style={{ marginBottom: 28 }}>
            <MicroLabel>Logic chain</MicroLabel>
            <div style={{ display: "flex", flexDirection: "column", alignItems: "stretch" }}>
              {view.logicChain.map((step, i) => (
                <div key={`${step.statement}-${i}`}>
                  <LogicStep step={step} onOpenSources={onOpenSources} />
                  {i < view.logicChain.length - 1 && (
                    <div
                      style={{
                        textAlign: "center",
                        color: "var(--dr-accent)",
                        fontSize: 16,
                        lineHeight: 1.4,
                        padding: "2px 0",
                      }}
                    >
                      ↓
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {(view.meaning || view.example) && (
          <div
            style={{
              display: "grid",
              gridTemplateColumns: isMobile || !(view.meaning && view.example) ? "1fr" : "1fr 1fr",
              gap: "var(--bd-3)",
              marginBottom: 28,
            }}
          >
            {view.meaning && (
              <div
                style={{
                  background: "var(--dr-card)",
                  border: "1px solid color-mix(in srgb, var(--dr-ink) 16%, transparent)",
                  borderRadius: 2,
                  padding: "16px 18px",
                }}
              >
                <MicroLabel>Meaning</MicroLabel>
                <div
                  style={{
                    fontFamily: "var(--dr-font-serif)",
                    fontSize: 15,
                    lineHeight: 1.45,
                    color: "var(--dr-ink)",
                    borderLeft: `3px solid ${sourceStatusColor(view.meaning.status)}`,
                    paddingLeft: 10,
                  }}
                >
                  {view.meaning.statement}
                </div>
                <SourceChips item={view.meaning} onOpenSources={onOpenSources} />
              </div>
            )}
            {view.example && (
              <div
                style={{
                  background: "var(--dr-card)",
                  border: "1px solid color-mix(in srgb, var(--dr-ink) 16%, transparent)",
                  borderRadius: 2,
                  padding: "16px 18px",
                }}
              >
                <MicroLabel>Evidence</MicroLabel>
                <div
                  style={{
                    fontFamily: "var(--dr-font-serif)",
                    fontSize: 15,
                    lineHeight: 1.45,
                    color: "var(--dr-ink)",
                    borderLeft: `3px solid ${sourceStatusColor(view.example.status)}`,
                    paddingLeft: 10,
                  }}
                >
                  {view.example.statement}
                </div>
                <SourceChips item={view.example} onOpenSources={onOpenSources} />
              </div>
            )}
          </div>
        )}

        {view.counter && (
          <div
            style={{
              marginLeft: isMobile ? 0 : 16,
              background: "var(--bd-counter-tint)",
              borderLeft: "4px solid var(--bd-counter)",
              borderRadius: 2,
              padding: "16px 18px",
            }}
          >
            <MicroLabel>Counter-logic</MicroLabel>
            <div
              style={{
                fontFamily: "var(--dr-font-serif)",
                fontSize: 15,
                lineHeight: 1.45,
                color: "var(--dr-ink)",
              }}
            >
              {view.counter.statement}
            </div>
            <SourceChips item={view.counter} onOpenSources={onOpenSources} />
          </div>
        )}
      </div>
    </div>
  );
}
