import { Link } from "react-router-dom";

type Props = {
  right?: React.ReactNode;
  compact?: boolean;
};

export function BrandHeader({ right, compact }: Props) {
  return (
    <header
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: 16,
        marginBottom: compact ? 20 : 36,
      }}
    >
      <Link to="/" style={{ display: "flex", alignItems: "center", gap: 11 }}>
        <span
          style={{
            width: 26,
            height: 26,
            borderRadius: 6,
            background: "var(--bd-ink)",
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            color: "var(--bd-surface)",
            font: "600 13px var(--bd-font-mono)",
          }}
        >
          /
        </span>
        <span style={{ fontWeight: 600, fontSize: 15 }}>According to Logic</span>
      </Link>
      {right}
    </header>
  );
}
