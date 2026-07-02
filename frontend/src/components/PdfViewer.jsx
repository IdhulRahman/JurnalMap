import { useEffect, useRef, useState, useCallback } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";
import { ZoomIn, ZoomOut, ChevronLeft, ChevronRight } from "lucide-react";
import { TIER_META } from "@/lib/tiers";

// Use pdf.js worker from unpkg CDN to bypass Windows MIME type issues with .mjs in local dev server
pdfjs.GlobalWorkerOptions.workerSrc = `https://unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

/**
 * PdfViewer renders a PDF and a canvas overlay of highlight rectangles.
 * Props:
 *   - fileUrl: full URL to the PDF
 *   - highlights: array of { sentence_id, page, x0,y0,x1,y1, page_width, page_height, tier }
 *   - jumpTo: { page, sentence_id } trigger
 */
export default function PdfViewer({ fileUrl, highlights = [], jumpTo = null }) {
  const [numPages, setNumPages] = useState(null);
  const [pageNum, setPageNum] = useState(1);
  const [scale, setScale] = useState(1.2);
  const [containerWidth, setContainerWidth] = useState(720);
  const containerRef = useRef(null);
  const pageWrapRef = useRef(null);

  useEffect(() => {
    if (!containerRef.current) return;
    const el = containerRef.current;
    const ro = new ResizeObserver(() => {
      setContainerWidth(el.clientWidth - 24);
    });
    ro.observe(el);
    setContainerWidth(el.clientWidth - 24);
    return () => ro.disconnect();
  }, []);

  // Jump to a page when requested
  useEffect(() => {
    if (jumpTo && jumpTo.page) {
      setPageNum(jumpTo.page);
      // scroll handled below after page renders
    }
  }, [jumpTo]);

  const onDocLoad = useCallback(({ numPages }) => {
    setNumPages(numPages);
  }, []);

  const pageHighlights = highlights.filter((h) => h.page === pageNum);

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-2 px-4 py-2.5 border-b border-[color:var(--jm-border)] bg-[color:var(--jm-surface)]">
        <button
          data-testid="pdf-prev-page"
          className="p-1.5 rounded hover:bg-[color:var(--jm-sidebar)] disabled:opacity-40"
          disabled={pageNum <= 1}
          onClick={() => setPageNum((p) => Math.max(1, p - 1))}
        >
          <ChevronLeft className="w-4 h-4" />
        </button>
        <div className="text-xs font-ui font-medium text-[color:var(--jm-text-2)] min-w-[80px] text-center">
          Hal. {pageNum} / {numPages || "—"}
        </div>
        <button
          data-testid="pdf-next-page"
          className="p-1.5 rounded hover:bg-[color:var(--jm-sidebar)] disabled:opacity-40"
          disabled={numPages ? pageNum >= numPages : true}
          onClick={() => setPageNum((p) => Math.min(numPages || p, p + 1))}
        >
          <ChevronRight className="w-4 h-4" />
        </button>
        <div className="w-px h-5 bg-[color:var(--jm-border)] mx-1" />
        <button
          data-testid="pdf-zoom-out"
          className="p-1.5 rounded hover:bg-[color:var(--jm-sidebar)]"
          onClick={() => setScale((s) => Math.max(0.6, s - 0.15))}
        >
          <ZoomOut className="w-4 h-4" />
        </button>
        <div className="text-xs font-ui font-medium text-[color:var(--jm-text-2)] min-w-[42px] text-center">
          {Math.round(scale * 100)}%
        </div>
        <button
          data-testid="pdf-zoom-in"
          className="p-1.5 rounded hover:bg-[color:var(--jm-sidebar)]"
          onClick={() => setScale((s) => Math.min(2.5, s + 0.15))}
        >
          <ZoomIn className="w-4 h-4" />
        </button>
        <div className="ml-auto flex items-center gap-2 text-[10px] uppercase tracking-[0.18em] font-semibold text-[color:var(--jm-text-3)]">
          {pageHighlights.length > 0
            ? `${pageHighlights.length} sorotan di halaman ini`
            : "Tidak ada sorotan aktif"}
        </div>
      </div>

      <div
        ref={containerRef}
        data-testid="pdf-canvas-wrap"
        className="flex-1 overflow-auto p-3 bg-[color:var(--jm-reading)]"
      >
        <Document
          file={{
            url: fileUrl,
            httpHeaders: {
              Authorization: `Bearer ${localStorage.getItem("jurnalmap.token")}`
            }
          }}
          onLoadSuccess={onDocLoad}
          loading={<div className="text-center p-12 text-[color:var(--jm-text-3)] font-ui">Memuat PDF…</div>}
          error={<div className="text-center p-12 text-[color:var(--jm-low-fg)] font-ui">Gagal memuat PDF.</div>}
        >
          <div ref={pageWrapRef} className="jm-page-wrap" style={{ width: "fit-content" }}>
            <Page
              key={pageNum}
              pageNumber={pageNum}
              width={Math.min(containerWidth, 900) * scale}
              renderAnnotationLayer={false}
              renderTextLayer={false}
              onRenderSuccess={() => {
                // attach overlay rectangles after render
              }}
            />
            {/* Overlay */}
            <HighlightOverlay
              highlights={pageHighlights}
              renderedWidth={Math.min(containerWidth, 900) * scale}
            />
          </div>
        </Document>
      </div>
    </div>
  );
}

function HighlightOverlay({ highlights, renderedWidth }) {
  // We need page native width to compute scale. All highlights for a page share page_width/page_height.
  const ref = useRef(null);
  if (!highlights.length) return null;
  const sample = highlights[0];
  const scaleX = renderedWidth / sample.page_width;
  const scaleY = scaleX; // assume uniform scaling (react-pdf preserves aspect)

  return (
    <div
      ref={ref}
      className="absolute inset-0 pointer-events-none"
      style={{ width: renderedWidth }}
    >
      {highlights.map((h, i) => {
        const meta = TIER_META[h.tier] || TIER_META.medium;
        const left = h.x0 * scaleX;
        const top = h.y0 * scaleY;
        const width = Math.max(2, (h.x1 - h.x0) * scaleX);
        const height = Math.max(8, (h.y1 - h.y0) * scaleY);
        return (
          <div
            key={`${h.sentence_id}-${i}`}
            data-testid={`highlight-${h.tier}`}
            className="absolute rounded-sm transition-all"
            style={{
              left,
              top,
              width,
              height,
              backgroundColor: meta.overlay,
              boxShadow: `inset 0 0 0 1.5px ${meta.border}`,
            }}
          />
        );
      })}
    </div>
  );
}
