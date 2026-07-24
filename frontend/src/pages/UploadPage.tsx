import { useState } from "react";
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

export function UploadPage() {
  const navigate = useNavigate();
  const [state, setState] = useState<UploadUiState>({ kind: "idle" });
  const [busy, setBusy] = useState(false);

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
      const book = await uploadBook(file);
      setState({
        kind: "success",
        filename: meta.filename,
        bookId: book.book_id,
        title: book.title,
      });
      await startProcessing(book.book_id);
      navigate(`/books/${book.book_id}/processing`);
    } catch (err) {
      const apiErr = err instanceof ApiError ? err : null;
      setState({
        kind: "error",
        code: apiErr?.code ?? "upload_failed",
        message: apiErr?.message ?? (err instanceof Error ? err.message : "Upload failed"),
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
      <div className="eyebrow" style={{ marginBottom: 8 }}>Upload</div>
      <h1 style={{ fontSize: 28, fontWeight: 600, letterSpacing: "-0.02em", margin: "0 0 8px" }}>
        Add an EPUB to decode
      </h1>
      <p className="muted" style={{ margin: "0 0 22px", lineHeight: 1.5 }}>
        We validate the file, then start the Argument Spine pipeline.
      </p>
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
