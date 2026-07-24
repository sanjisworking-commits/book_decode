import { Link } from "react-router-dom";
import { useState } from "react";
import { BrandHeader } from "../components/BrandHeader";
import { MAX_EPUB_SIZE_MB } from "../lib/constants";
import "../styles/pages.css";

export function LandingPage() {
  const [howOpen, setHowOpen] = useState(false);

  return (
    <div className="page">
      <BrandHeader
        right={
          <button
            type="button"
            className="muted"
            style={{ background: "none", border: 0, fontSize: 14 }}
            onClick={() => setHowOpen((v) => !v)}
          >
            How it works
          </button>
        }
      />

      <section className="landing-hero">
        <div>
          <div className="eyebrow" style={{ marginBottom: 12 }}>
            Book Decode
          </div>
          <h1
            style={{
              fontSize: "clamp(32px, 5vw, 46px)",
              lineHeight: 1.08,
              letterSpacing: "-0.03em",
              fontWeight: 600,
              margin: "0 0 16px",
            }}
          >
            According to Logic
          </h1>
          <p className="muted" style={{ fontSize: 18, lineHeight: 1.55, margin: "0 0 24px", maxWidth: 480 }}>
            Upload an EPUB, get a source-grounded{" "}
            <strong style={{ color: "var(--bd-ink)", fontWeight: 600 }}>Argument Spine</strong> per
            chapter — in English and Hindi-English.
          </p>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 12, alignItems: "center" }}>
            <Link to="/upload" className="btn btn-primary">
              Decode an EPUB
            </Link>
            <span className="mono faint" style={{ fontSize: 12 }}>
              .epub · up to {MAX_EPUB_SIZE_MB} MB · no DRM
            </span>
          </div>
        </div>

        <div className="surface" style={{ padding: 22, background: "var(--bd-canvas)" }}>
          <div className="eyebrow" style={{ marginBottom: 14 }}>
            Argument Spine · preview shape
          </div>
          <div style={{ display: "grid", gap: 8 }}>
            {[
              { label: "Central claim", color: "var(--bd-explicit)" },
              { label: "Reasoning steps", color: "var(--bd-paraphrase)" },
              { label: "Hidden assumptions", color: "var(--bd-inference)" },
              { label: "Strongest counter", color: "var(--bd-counter)" },
            ].map((row) => (
              <div
                key={row.label}
                style={{
                  borderLeft: `3px solid ${row.color}`,
                  padding: "10px 12px",
                  background: "#fff",
                  borderRadius: 5,
                  fontSize: 13,
                  fontWeight: 600,
                }}
              >
                {row.label}
              </div>
            ))}
          </div>
          <p className="mono faint" style={{ fontSize: 11, margin: "14px 0 0" }}>
            Node bodies come from the pipeline — never hardcoded claims.
          </p>
        </div>
      </section>

      {howOpen && (
        <section className="anim-fade surface" style={{ marginTop: 40, padding: "28px 28px 24px" }}>
          <div className="eyebrow" style={{ marginBottom: 8 }}>
            How it works
          </div>
          <h2 style={{ fontSize: 22, fontWeight: 600, margin: "0 0 20px" }}>
            Three steps to a decode
          </h2>
          <div className="how-grid">
            {[
              {
                n: "01",
                t: "Upload",
                d: `Drop a DRM-free .epub under ${MAX_EPUB_SIZE_MB} MB. We read its structure and split it into chapters.`,
              },
              {
                n: "02",
                t: "Decode",
                d: "Each chapter becomes a 12-node Argument Spine with provenance and source block citations.",
              },
              {
                n: "03",
                t: "Explore",
                d: "Explore the spine in English or Hindi-English, inspect any node, and verify claims against the original text.",
              },
            ].map((step) => (
              <div key={step.n}>
                <div className="mono faint" style={{ fontSize: 12, marginBottom: 8 }}>
                  {step.n}
                </div>
                <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 8 }}>{step.t}</div>
                <p className="muted" style={{ fontSize: 13.5, lineHeight: 1.6, margin: 0 }}>
                  {step.d}
                </p>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
