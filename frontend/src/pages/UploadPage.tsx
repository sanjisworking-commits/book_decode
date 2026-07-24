import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { BrandHeader } from "../components/BrandHeader";
import {
  describeFile,
  UploadDropzone,
  type UploadUiState,
} from "../components/UploadDropzone";
import { validateEpubClient } from "../lib/constants";
import { startProcessing, uploadBook } from "../services/api";
import { ApiError } from "../types/api";

const UPLOAD_TIMEOUT_MS = 60_000;

export function UploadPage() {
  const navigate = useNavigate();
  const [state, setState] = useState<UploadUiState>({ kind: "idle" });
  const [busy, setBusy] = useState(false);
  const [apiHint, setApiHint] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const ctrl = new AbortController();
    const timer = window.setTimeout(() => ctrl.abort(), 4000);
    fetch("/health", { signal: ctrl.signal })
      .then(async (res) => {
        if (cancelled) return;
        if (!res.ok) {
          setApiHint(
            "API /health failed. Is uvicorn running? Check the Vite proxy port matches the API port.",
          );
          return;
        }
        const body = (await res.json()) as {
          llm_mock?: boolean;
          llm_provider?: string;
          llm_api_key_configured?: boolean;
        };
        if (body.llm_mock) {
          setApiHint(
            "API is in LLM_MOCK mode — spines will be placeholders. Set LLM_MOCK=false and restart uvicorn.",
          );
        } else if (body.llm_api_key_configured === false) {
          setApiHint("API key not configured on the server (.env LLM_API_KEY).");
        } else {
          setApiHint(null);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setApiHint(
            "Cannot reach the API via the Vite proxy. Start uvicorn (e.g. port 8003) and ensure frontend/.env.development VITE_API_PROXY_TARGET matches.",
          );
        }
      })
      .finally(() => window.clearTimeout(timer));
    return () => {
      cancelled = true;
      ctrl.abort();
    };
  }, []);

  async function handleFile(file: File) {
    const clientErr = validateEpubClient(file);
    const meta = describeFile(file);
    if (clientErr) {
      setState({
        kind: "error",
        code: clientErr.code,
        message: clientErr.message,
        filename: meta.filename,
        sizeLabel: meta.sizeLabel,
      });
      return;
    }

    setBusy(true);
    setState({ kind: "uploading", ...meta });
    try {
      const book = await uploadBook(file, UPLOAD_TIMEOUT_MS);
      setState({
        kind: "success",
        filename: meta.filename,
        bookId: book.book_id,
        title: book.title,
      });
      // Leave Uploading as soon as the book exists; start pipeline without blocking navigation.
      void startProcessing(book.book_id).catch(() => {
        /* ProcessingPage will surface status / allow retry via reprocess */
      });
      navigate(`/books/${book.book_id}/processing`);
    } catch (err) {
      const apiErr = err instanceof ApiError ? err : null;
      const message =
        apiErr?.message ??
        (err instanceof Error ? err.message : "Upload failed");
      const timedOut =
        err instanceof DOMException && err.name === "AbortError"
          ? true
          : /aborted|timeout/i.test(message);
      setState({
        kind: "error",
        code: timedOut ? "upload_timeout" : apiErr?.code ?? "upload_failed",
        message: timedOut
          ? "Upload timed out — is the API running on the proxy port (see frontend/.env.development)?"
          : message,
        filename: meta.filename,
        sizeLabel: meta.sizeLabel,
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="page page-narrow">
      <BrandHeader
        compact
        right={
          <Link to="/" className="mono muted" style={{ fontSize: 12 }}>
            ← Home
          </Link>
        }
      />
      <div className="eyebrow" style={{ marginBottom: 8 }}>
        Upload
      </div>
      <h1 style={{ fontSize: 28, fontWeight: 600, letterSpacing: "-0.02em", margin: "0 0 8px" }}>
        Add an EPUB to decode
      </h1>
      <p className="muted" style={{ margin: "0 0 22px", lineHeight: 1.5 }}>
        We validate the file, then start the Argument Spine pipeline.
      </p>
      {apiHint && (
        <div
          className="surface"
          style={{
            padding: "12px 16px",
            marginBottom: 16,
            borderColor: "#d8b6ab",
            background: "#fbf6f4",
            color: "#934231",
            fontSize: 13,
            lineHeight: 1.45,
          }}
        >
          {apiHint}
        </div>
      )}
      <UploadDropzone
        state={state}
        disabled={busy}
        onFile={handleFile}
        onClearError={() => setState({ kind: "idle" })}
      />
      {state.kind === "success" && (
        <p className="muted" style={{ marginTop: 16, textAlign: "center" }}>
          Starting decode…
        </p>
      )}
    </div>
  );
}
