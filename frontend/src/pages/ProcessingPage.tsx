import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { BrandHeader } from "../components/BrandHeader";
import { ProcessingView } from "../components/ProcessingView";
import { isBookReady, isTerminalBookStatus } from "../lib/constants";
import { getStatus } from "../services/api";
import type { ProcessingStatus } from "../types/api";
import { ApiError } from "../types/api";

export function ProcessingPage() {
  const { bookId = "" } = useParams();
  const navigate = useNavigate();
  const [status, setStatus] = useState<ProcessingStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    let timer: number | undefined;

    async function tick() {
      try {
        const next = await getStatus(bookId);
        if (cancelled) return;
        setStatus(next);
        setError(null);
        if (!isTerminalBookStatus(next.processing_status)) {
          timer = window.setTimeout(tick, 1500);
        }
      } catch (err) {
        if (cancelled) return;
        const msg =
          err instanceof ApiError
            ? err.message
            : err instanceof Error
              ? err.message
              : "Failed to load status";
        setError(msg);
        timer = window.setTimeout(tick, 3000);
      }
    }

    void tick();
    return () => {
      cancelled = true;
      if (timer) window.clearTimeout(timer);
    };
  }, [bookId]);

  const ready = status ? isBookReady(status.processing_status) : false;
  const failed = status?.processing_status === "failed";

  return (
    <div className="page">
      <BrandHeader
        compact
        right={
          <Link to="/upload" className="mono muted" style={{ fontSize: 12 }}>
            ← Upload
          </Link>
        }
      />

      {error && !status && (
        <div className="surface" style={{ padding: 24 }}>
          <div style={{ fontWeight: 600, marginBottom: 8 }}>Couldn’t load processing status</div>
          <div className="muted">{error}</div>
        </div>
      )}

      {status && <ProcessingView status={status} />}

      <div style={{ marginTop: 20, display: "flex", gap: 12, flexWrap: "wrap" }}>
        {ready && (
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => navigate(`/books/${bookId}/map`)}
          >
            Open Book Map →
          </button>
        )}
        {failed && (
          <>
            <Link to="/upload" className="btn btn-secondary">
              Upload a different EPUB
            </Link>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => navigate(`/books/${bookId}/map`)}
            >
              View Book Map
            </button>
          </>
        )}
      </div>
    </div>
  );
}
