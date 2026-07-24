import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { SourcePreview, type SourcePreviewState } from "../components/SourcePreview";
import { ProvenanceLegend } from "../components/ProvenanceLegend";
import { SpineCanvas1a } from "../components/spine/SpineCanvas1a";
import { SpineThreaded1b } from "../components/spine/SpineThreaded1b";
import { getChapterSource, getChapterSpine, listChapters } from "../services/api";
import type { ArgumentSpine, ChapterSummary, LanguageMode, SourceBlock } from "../types/api";
import { ApiError } from "../types/api";

function useIsMobile(breakpoint = 720): boolean {
  const [mobile, setMobile] = useState(
    typeof window !== "undefined" ? window.innerWidth <= breakpoint : false,
  );
  useEffect(() => {
    const onResize = () => setMobile(window.innerWidth <= breakpoint);
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, [breakpoint]);
  return mobile;
}

export function SpinePage() {
  const { bookId = "", chapterId = "" } = useParams();
  const navigate = useNavigate();
  const mobile = useIsMobile();

  const [spine, setSpine] = useState<ArgumentSpine | null>(null);
  const [chapters, setChapters] = useState<ChapterSummary[]>([]);
  const [lang, setLang] = useState<LanguageMode>("en");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<{ code: string; message: string } | null>(null);
  const [preview, setPreview] = useState<SourcePreviewState>({ status: "closed" });
  const [activeBlockId, setActiveBlockId] = useState<string | null>(null);
  const [sourceCache, setSourceCache] = useState<SourceBlock[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setSpine(null);
      setLoadError(null);
      setSelectedId(null);
      setExpandedId(null);
      setSourceCache(null);
      try {
        const [sp, ch] = await Promise.all([
          getChapterSpine(bookId, chapterId),
          listChapters(bookId),
        ]);
        if (cancelled) return;
        setSpine(sp);
        setChapters(ch.chapters);
        const first = [...sp.nodes].sort((a, b) => a.order - b.order)[0];
        setSelectedId(first?.id ?? null);
        setExpandedId(first?.id ?? null);
      } catch (err) {
        if (cancelled) return;
        if (err instanceof ApiError) {
          setLoadError({ code: err.code, message: err.message });
        } else {
          setLoadError({
            code: "load_failed",
            message: err instanceof Error ? err.message : "Failed to load spine",
          });
        }
        try {
          const ch = await listChapters(bookId);
          if (!cancelled) setChapters(ch.chapters);
        } catch {
          /* ignore */
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [bookId, chapterId]);

  const orderedNodes = useMemo(
    () => (spine ? [...spine.nodes].sort((a, b) => a.order - b.order) : []),
    [spine],
  );

  const chapterIndex = chapters.findIndex((c) => c.chapter_id === chapterId);
  const chapter = chapters[chapterIndex];
  const prev = chapterIndex > 0 ? chapters[chapterIndex - 1] : null;
  const next =
    chapterIndex >= 0 && chapterIndex < chapters.length - 1 ? chapters[chapterIndex + 1] : null;

  const openSources = useCallback(
    async (ids: string[]) => {
      if (ids.length === 0) return;
      setPreview({ status: "loading", blockIds: ids });
      setActiveBlockId(ids[0] ?? null);
      try {
        let blocks = sourceCache;
        if (!blocks) {
          const source = await getChapterSource(bookId, chapterId);
          blocks = source.source_blocks ?? [];
          setSourceCache(blocks);
        }
        const found = ids
          .map((id) => blocks!.find((b) => b.block_id === id))
          .filter((b): b is SourceBlock => Boolean(b));
        const missingIds = ids.filter((id) => !found.some((b) => b.block_id === id));
        if (found.length === 0) {
          setPreview({ status: "missing", blockIds: ids });
        } else {
          setPreview({ status: "ready", blocks: found, missingIds });
          setActiveBlockId(found[0]?.block_id ?? null);
        }
      } catch (err) {
        setPreview({
          status: "error",
          message: err instanceof ApiError ? err.message : "Could not load source blocks",
        });
      }
    },
    [bookId, chapterId, sourceCache],
  );

  const chrome = (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: 12,
        flexWrap: "wrap",
        marginBottom: 16,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap" }}>
        <Link to={`/books/${bookId}/map`} className="mono muted" style={{ fontSize: 12 }}>
          ← Book Map
        </Link>
        <span style={{ color: "var(--bd-border-strong)" }}>/</span>
        <div>
          <span className="mono faint" style={{ fontSize: 11 }}>
            {chapterId.toUpperCase()}
          </span>{" "}
          <span style={{ fontSize: 15, fontWeight: 600 }}>
            {chapter?.title || "Chapter"}
          </span>
        </div>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <div className="mono faint" style={{ fontSize: 11, display: "flex", alignItems: "center", gap: 8 }}>
          <button
            type="button"
            disabled={!prev}
            onClick={() => prev && navigate(`/books/${bookId}/chapters/${prev.chapter_id}`)}
            style={{ background: "none", border: 0, color: "inherit", padding: 0 }}
          >
            ‹
          </button>
          <span>
            ch {chapterIndex >= 0 ? chapterIndex + 1 : "?"} / {chapters.length || "?"}
          </span>
          <button
            type="button"
            disabled={!next}
            onClick={() => next && navigate(`/books/${bookId}/chapters/${next.chapter_id}`)}
            style={{ background: "none", border: 0, color: "inherit", padding: 0 }}
          >
            ›
          </button>
        </div>
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
            onClick={() => setLang("en")}
            style={{
              padding: "5px 11px",
              borderRadius: 5,
              border: 0,
              background: lang === "en" ? "var(--bd-primary)" : "transparent",
              color: lang === "en" ? "#fff" : "var(--bd-muted)",
              font: "600 11.5px var(--bd-font-sans)",
            }}
          >
            EN
          </button>
          <button
            type="button"
            onClick={() => setLang("hinglish")}
            style={{
              padding: "5px 11px",
              borderRadius: 5,
              border: 0,
              background: lang === "hinglish" ? "var(--bd-primary)" : "transparent",
              color: lang === "hinglish" ? "#fff" : "var(--bd-muted)",
              font: "500 11.5px var(--bd-font-sans)",
            }}
          >
            हिं
          </button>
        </div>
      </div>
    </div>
  );

  if (loadError) {
    const notReady =
      loadError.code === "spine_not_ready" || loadError.code === "chapter_not_ready";
    return (
      <div className="page">
        {chrome}
        <div className="surface" style={{ padding: "48px 28px", textAlign: "center" }}>
          <div className="eyebrow" style={{ marginBottom: 10 }}>
            Chapter not ready
          </div>
          <h1 style={{ fontSize: 22, fontWeight: 600, margin: "0 0 10px" }}>
            {notReady ? "Spine isn’t available yet" : "Couldn’t open this spine"}
          </h1>
          <p className="muted" style={{ maxWidth: 360, margin: "0 auto 18px", lineHeight: 1.5 }}>
            {loadError.message}
          </p>
          <Link to={`/books/${bookId}/map`} className="mono muted" style={{ fontSize: 13 }}>
            ← back to Book Map
          </Link>
        </div>
      </div>
    );
  }

  if (!spine) {
    return (
      <div className="page">
        {chrome}
        <div className="surface anim-pulse" style={{ height: 320, background: "var(--bd-surface-2)" }} />
      </div>
    );
  }

  return (
    <div className="page" style={{ maxWidth: 1200 }}>
      {chrome}
      <div style={{ marginBottom: 14 }}>
        <ProvenanceLegend />
      </div>

      {mobile ? (
        <SpineThreaded1b
          nodes={orderedNodes}
          expandedId={expandedId}
          lang={lang}
          onToggle={(id) => setExpandedId((cur) => (cur === id ? null : id))}
          onOpenSources={openSources}
        />
      ) : (
        <SpineCanvas1a
          nodes={orderedNodes}
          selectedId={selectedId}
          lang={lang}
          onSelect={setSelectedId}
          onOpenSources={openSources}
        />
      )}

      <SourcePreview
        state={preview}
        activeBlockId={activeBlockId}
        onSelectBlock={setActiveBlockId}
        onClose={() => setPreview({ status: "closed" })}
      />
    </div>
  );
}
