import { useCallback, useRef, useState } from "react";
import { formatBytes, MAX_JSON_SIZE_MB } from "../lib/constants";

export type UploadUiState =
  | { kind: "idle" }
  | { kind: "error"; code: string; message: string; filename?: string; sizeLabel?: string }
  | { kind: "uploading"; filename: string; sizeLabel: string }
  | { kind: "success"; filename: string; bookId: string; title: string };

type Props = {
  state: UploadUiState;
  onFile: (file: File) => void;
  onClearError?: () => void;
  disabled?: boolean;
};

const ERROR_COPY: Record<string, { title: string; body: string }> = {
  invalid_extension: {
    title: "Wrong file type",
    body: "Only clean source_chapter .json files are accepted.",
  },
  file_too_large: {
    title: "This file is too large",
    body: `JSON must be under ${MAX_JSON_SIZE_MB} MB.`,
  },
  invalid_source_json: {
    title: "Invalid source JSON",
    body: "The file must match the source_chapter shape (chapter_id, source_blocks with block_id / block_type / text).",
  },
  upload_timeout: {
    title: "Upload timed out",
    body: "The API did not respond. Confirm uvicorn is running and VITE_API_PROXY_TARGET matches its port.",
  },
  upload_failed: {
    title: "Upload failed",
    body: "Could not upload this JSON to the API.",
  },
};

export function UploadDropzone({ state, onFile, onClearError, disabled }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);

  const pick = useCallback(
    (file: File | undefined | null) => {
      if (!file || disabled) return;
      onFile(file);
    },
    [disabled, onFile],
  );

  const borderColor =
    state.kind === "error"
      ? "#d8b6ab"
      : dragOver
        ? "var(--bd-primary)"
        : "var(--bd-border-strong)";

  const bg =
    state.kind === "error"
      ? "#fbf6f4"
      : state.kind === "success"
        ? "#f5f9f6"
        : "var(--bd-canvas)";

  return (
    <div
      className="surface"
      style={{
        padding: "36px 32px",
        background: bg,
        borderColor,
        textAlign: "center",
        transition: "border-color 120ms var(--bd-ease)",
      }}
      onDragOver={(e) => {
        e.preventDefault();
        setDragOver(true);
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragOver(false);
        pick(e.dataTransfer.files?.[0]);
      }}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".json,application/json"
        className="sr-only"
        disabled={disabled || state.kind === "uploading"}
        onChange={(e) => {
          pick(e.target.files?.[0]);
          e.target.value = "";
        }}
      />

      {state.kind === "idle" && (
        <>
          <div style={{ fontSize: 28, fontWeight: 600, letterSpacing: "-0.02em", marginBottom: 10 }}>
            Drop your source JSON here
          </div>
          <div className="muted" style={{ marginBottom: 18, lineHeight: 1.5 }}>
            Clean chapter blocks go to the LLM to build a source-grounded Argument Spine.
          </div>
          <button
            type="button"
            className="btn btn-primary"
            disabled={disabled}
            onClick={() => inputRef.current?.click()}
          >
            Choose JSON
          </button>
          <div className="eyebrow" style={{ marginTop: 16 }}>
            .json only · max {MAX_JSON_SIZE_MB} MB · source_chapter schema
          </div>
        </>
      )}

      {state.kind === "uploading" && (
        <>
          <div
            className="anim-spin"
            style={{
              width: 28,
              height: 28,
              borderRadius: "50%",
              border: "3px solid var(--bd-border)",
              borderTopColor: "var(--bd-primary)",
              margin: "0 auto 16px",
            }}
          />
          <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 6 }}>Uploading…</div>
          <div className="mono faint" style={{ fontSize: 12 }}>
            {state.filename} · {state.sizeLabel}
          </div>
        </>
      )}

      {state.kind === "error" && (
        <>
          <div style={{ fontSize: 16, fontWeight: 600, color: "#934231", marginBottom: 6 }}>
            {ERROR_COPY[state.code]?.title ?? "Upload failed"}
          </div>
          <div className="muted" style={{ lineHeight: 1.5, maxWidth: 360, margin: "0 auto 12px" }}>
            {ERROR_COPY[state.code]?.body ?? state.message}
          </div>
          <div className="mono faint" style={{ fontSize: 11, marginBottom: 16 }}>
            {state.filename}
            {state.sizeLabel ? ` · ${state.sizeLabel}` : ""}
            {` · error: ${state.code}`}
          </div>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => {
              onClearError?.();
              inputRef.current?.click();
            }}
          >
            Choose another file
          </button>
        </>
      )}

      {state.kind === "success" && (
        <>
          <div style={{ fontSize: 16, fontWeight: 600, color: "#2f6640", marginBottom: 6 }}>
            Upload complete
          </div>
          <div className="muted" style={{ marginBottom: 8 }}>
            {state.title || state.filename} is ready to decode.
          </div>
          <div className="mono faint" style={{ fontSize: 11 }}>
            {state.filename}
          </div>
        </>
      )}
    </div>
  );
}

export function describeFile(file: File): { filename: string; sizeLabel: string } {
  return { filename: file.name, sizeLabel: formatBytes(file.size) };
}
