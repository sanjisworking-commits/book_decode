export type ChapterMode = "decode" | "remember";

type Props = {
  mode: ChapterMode;
  onChange: (mode: ChapterMode) => void;
};

export function ModeSwitcher({ mode, onChange }: Props) {
  return (
    <div title="switch view · keeps your place">
      <div
        style={{
          display: "inline-flex",
          background: "var(--bd-hairline)",
          borderRadius: 7,
          padding: 2,
        }}
      >
        <button
          type="button"
          onClick={() => onChange("decode")}
          style={{
            padding: "5px 11px",
            borderRadius: 5,
            border: 0,
            background: mode === "decode" ? "var(--bd-primary)" : "transparent",
            color: mode === "decode" ? "#fff" : "var(--bd-muted)",
            font: "600 11.5px var(--bd-font-sans)",
            cursor: "pointer",
          }}
        >
          Decode
        </button>
        <button
          type="button"
          onClick={() => onChange("remember")}
          style={{
            padding: "5px 11px",
            borderRadius: 5,
            border: 0,
            background: mode === "remember" ? "var(--bd-primary)" : "transparent",
            color: mode === "remember" ? "#fff" : "var(--bd-muted)",
            font: "600 11.5px var(--bd-font-sans)",
            cursor: "pointer",
          }}
        >
          Remember
        </button>
      </div>
      <div
        className="mono faint"
        style={{ fontSize: 9, letterSpacing: "0.08em", marginTop: 4, textAlign: "center" }}
      >
        switch view · keeps your place
      </div>
    </div>
  );
}
