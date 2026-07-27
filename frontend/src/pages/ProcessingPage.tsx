import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { BrandHeader } from "../components/BrandHeader";
import { ProcessingView } from "../components/ProcessingView";
import { isBookReady, isChapterReady, isTerminalBookStatus } from "../lib/constants";
import { getStatus, startProcessing } from "../services/api";
import type { ProcessingStatus } from "../types/api";
import { ApiError } from "../types/api";

function formatElapsed(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  if (m <= 0) return `${s}s`;
  return `${m}m ${s.toString().padStart(2, "0")}s`;
}

export function ProcessingPage() {
  const { bookId = "" } = useParams();
  const navigate = useNavigate();
  const [status, setStatus] = useState<ProcessingStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [elapsedSec, setElapsedSec] = useState(0);
  const [sinceStatusChangeSec, setSinceStatusChangeSec] = useState(0);

  useEffect(() => {
    let cancelled = false;
    let timer: number | undefined;
    let kickstarted = false;
    let lastFingerprint = "";

    async function tick() {
      try {
        const next = await getStatus(bookId);
        if (cancelled) return;
        const fingerprint = [
          next.processing_status,
          next.current_stage,
          next.processed_chapter_count,
          next.current_chapter_id,
          next.chapters
            .map((c) => `${c.chapter_id}:${c.status}:${c.progress ?? ""}`)
            .join("|"),
          next.updated_at ?? "",
        ].join("::");
        if (fingerprint !== lastFingerprint) {
          lastFingerprint = fingerprint;
          setSinceStatusChangeSec(0);
        }
        setStatus(next);
        setError(null);

        if (!kickstarted && next.processing_status === "uploaded") {
          kickstarted = true;
          try {
            await startProcessing(bookId);
          } catch {
            /* poll continues */
          }
        }

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

  useEffect(() => {
    if (!status || isTerminalBookStatus(status.processing_status)) return;
    const id = window.setInterval(() => {
      setElapsedSec((n) => n + 1);
      setSinceStatusChangeSec((n) => n + 1);
    }, 1000);
    return () => window.clearInterval(id);
  }, [status?.processing_status, status?.book_id]);

  useEffect(() => {
    setElapsedSec(0);
    setSinceStatusChangeSec(0);
  }, [bookId]);

  const ready = status ? isBookReady(status.processing_status) : false;
  const failed = status?.processing_status === "failed";
  const firstReady = status?.chapters.find((c) => isChapterReady(c.status));
  const stillProcessing = status ? !isTerminalBookStatus(status.processing_status) : false;
  const canOpenEarly = Boolean(firstReady) && stillProcessing;

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

      {status && (
        <ProcessingView
          status={status}
          elapsedLabel={stillProcessing ? formatElapsed(elapsedSec) : undefined}
          waitingOnLlm={
            stillProcessing &&
            sinceStatusChangeSec >= 8 &&
            (status.processing_status === "analysing_chapters" ||
              status.processing_status === "constructing_spines" ||
              status.processing_status === "creating_hinglish" ||
              status.processing_status === "validating")
          }
        />
      )}

      <div style={{ marginTop: 20, display: "flex", gap: 12, flexWrap: "wrap" }}>
        {canOpenEarly && firstReady && (
          <>
            <button
              type="button"
              className="btn btn-primary"
              onClick={() =>
                navigate(`/books/${bookId}/chapters/${firstReady.chapter_id}`)
              }
            >
              Open first chapter →
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => navigate(`/books/${bookId}/map`)}
            >
              Open Book Map
            </button>
          </>
        )}
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
