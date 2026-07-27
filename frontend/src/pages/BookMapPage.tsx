import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { BrandHeader } from "../components/BrandHeader";
import { isBookReady, isChapterReady, isTerminalBookStatus } from "../lib/constants";
import {
  deleteBook,
  getBook,
  listChapters,
  retryChapter,
  startProcessing,
} from "../services/api";
import type { BookMetadata, ChapterSummary } from "../types/api";
import { ApiError } from "../types/api";

export function BookMapPage() {
  const { bookId = "" } = useParams();
  const navigate = useNavigate();
  const [book, setBook] = useState<BookMetadata | null>(null);
  const [chapters, setChapters] = useState<ChapterSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    let timer: number | undefined;

    async function tick() {
      try {
        const [b, ch] = await Promise.all([getBook(bookId), listChapters(bookId)]);
        if (cancelled) return;
        setBook(b);
        setChapters(ch.chapters);
        setError(null);
        if (!isTerminalBookStatus(b.processing_status)) {
          timer = window.setTimeout(tick, 2000);
        }
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof ApiError ? err.message : "Failed to load book map");
        timer = window.setTimeout(tick, 3000);
      }
    }

    void tick();
    return () => {
      cancelled = true;
      if (timer) window.clearTimeout(timer);
    };
  }, [bookId]);

  async function onDelete() {
    if (!window.confirm("Delete this book and all decoded artefacts?")) return;
    setBusy(true);
    try {
      await deleteBook(bookId);
      navigate("/");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Delete failed");
    } finally {
      setBusy(false);
    }
  }

  async function onReprocess() {
    if (!window.confirm("Reprocess this book from the start?")) return;
    setBusy(true);
    try {
      await startProcessing(bookId);
      navigate(`/books/${bookId}/processing`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Reprocess failed");
      setBusy(false);
    }
  }

  async function onRetryChapter(chapterId: string) {
    setBusy(true);
    try {
      await retryChapter(bookId, chapterId);
      navigate(`/books/${bookId}/processing`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Retry failed");
      setBusy(false);
    }
  }

  if (error && !book) {
    return (
      <div className="page">
        <BrandHeader compact />
        <div className="surface" style={{ padding: 24 }}>
          <div style={{ fontWeight: 600 }}>{error}</div>
        </div>
      </div>
    );
  }

  const readyCount = chapters.filter((c) => isChapterReady(c.status)).length;
  const failedCount = chapters.filter((c) => c.status === "failed").length;
  const stillProcessing = book
    ? !isTerminalBookStatus(book.processing_status)
    : false;
  const partial =
    book?.processing_status === "completed_with_errors" ||
    failedCount > 0 ||
    (stillProcessing && readyCount > 0);
  const bookReady = book ? isBookReady(book.processing_status) : false;

  return (
    <div className="page">
      <BrandHeader
        compact
        right={
          <Link
            to={
              stillProcessing || bookReady
                ? `/books/${bookId}/processing`
                : "/upload"
            }
            className="mono muted"
            style={{ fontSize: 12 }}
          >
            ← Back
          </Link>
        }
      />

      <div className="surface" style={{ overflow: "hidden" }}>
        <div
          style={{
            padding: "24px 28px",
            borderBottom: "1px solid var(--bd-hairline)",
            display: "flex",
            justifyContent: "space-between",
            gap: 16,
            flexWrap: "wrap",
            alignItems: "flex-end",
          }}
        >
          <div>
            <div className="eyebrow" style={{ marginBottom: 8 }}>
              {stillProcessing ? "Decoding in progress" : "Decoded book"}
            </div>
            <h1 style={{ fontSize: 28, fontWeight: 600, letterSpacing: "-0.01em", margin: "0 0 6px" }}>
              {book?.title || "Untitled book"}
            </h1>
            <div className="muted" style={{ fontSize: 14 }}>
              {book?.author || "Unknown author"} · {chapters.length} ch ·{" "}
              {partial ? (
                <span style={{ color: "#8a6318", fontWeight: 500 }}>
                  {readyCount} ready
                  {stillProcessing
                    ? " · decoding remaining…"
                    : failedCount > 0
                      ? ` · ${failedCount} attention`
                      : ""}
                </span>
              ) : (
                <span style={{ color: "#2f6640", fontWeight: 500 }}>{readyCount} ready</span>
              )}
            </div>
          </div>
          <div style={{ display: "flex", gap: 10 }}>
            <button type="button" className="btn btn-secondary" disabled={busy} onClick={onReprocess}>
              ↻ Reprocess book
            </button>
            <button type="button" className="btn btn-danger" disabled={busy} onClick={onDelete}>
              🗑 Delete book
            </button>
          </div>
        </div>

        {error && (
          <div style={{ padding: "12px 28px", color: "#934231", fontSize: 13 }}>{error}</div>
        )}

        <div
          style={{
            padding: 24,
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))",
            gap: 12,
          }}
        >
          {chapters.map((ch) => {
            const ready = isChapterReady(ch.status);
            const failed = ch.status === "failed";
            return (
              <div
                key={ch.chapter_id}
                className="surface"
                style={{
                  padding: "18px 20px",
                  boxShadow: "none",
                  cursor: ready ? "pointer" : "default",
                  background: "#fff",
                }}
                onClick={() => {
                  if (ready) navigate(`/books/${bookId}/chapters/${ch.chapter_id}`);
                }}
                onKeyDown={(e) => {
                  if (ready && (e.key === "Enter" || e.key === " ")) {
                    navigate(`/books/${bookId}/chapters/${ch.chapter_id}`);
                  }
                }}
                role={ready ? "button" : undefined}
                tabIndex={ready ? 0 : undefined}
              >
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    marginBottom: 10,
                    gap: 8,
                  }}
                >
                  <span className="mono faint" style={{ fontSize: 11 }}>
                    {ch.chapter_id.toUpperCase()}
                  </span>
                  <span
                    style={{
                      fontSize: 11.5,
                      fontWeight: 600,
                      color: ready ? "#2f6640" : failed ? "#934231" : "var(--bd-muted)",
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 5,
                    }}
                  >
                    <span
                      className="status-dot"
                      style={{
                        background: ready
                          ? "var(--bd-explicit)"
                          : failed
                            ? "var(--bd-counter)"
                            : "var(--bd-faint)",
                      }}
                    />
                    {ready ? "Ready" : failed ? "Failed" : ch.status}
                  </span>
                </div>
                <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 12 }}>
                  {ch.title || ch.chapter_id}
                </div>
                {ready ? (
                  <div className="mono faint" style={{ fontSize: 12.5 }}>
                    12 nodes · view spine →
                  </div>
                ) : failed ? (
                  <button
                    type="button"
                    className="btn btn-secondary"
                    style={{ padding: "7px 12px", fontSize: 12.5 }}
                    disabled={busy}
                    onClick={(e) => {
                      e.stopPropagation();
                      void onRetryChapter(ch.chapter_id);
                    }}
                  >
                    Retry chapter
                  </button>
                ) : (
                  <div className="mono faint" style={{ fontSize: 12.5 }}>
                    {stillProcessing ? "Working…" : "Not ready yet"}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
