import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, Loader2 } from "lucide-react";
import { api } from "@/services/api";
import { toast } from "sonner";
import Header from "@/components/Header";
import PdfViewer from "@/components/PdfViewer";
import SummaryPanel from "@/components/SummaryPanel";
import EditableTitle from "@/components/EditableTitle";
import { useT } from "@/lib/useT";

export default function DocumentReader() {
  const { projectId, docId } = useParams();
  const { t } = useT();
  const [summary, setSummary] = useState(null);
  const [highlights, setHighlights] = useState([]);
  const [jumpTo, setJumpTo] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api
      .getSummary(docId)
      .then((d) => {
        setSummary(d);
        setLoading(false);
      })
      .catch(() => {
        toast.error("Gagal memuat dokumen");
        setLoading(false);
      });
  }, [docId]);

  return (
    <div className="h-screen flex flex-col">
      <Header />
      <div className="border-b border-[color:var(--jm-border)] bg-white">
        <div className="mx-auto max-w-[1600px] px-6 py-3 flex items-center gap-4">
          <Link
            data-testid="back-to-project"
            to={`/project/${projectId}`}
            className="flex items-center gap-1.5 text-xs uppercase tracking-[0.2em] font-semibold text-[color:var(--jm-text-3)] hover:text-[color:var(--jm-text)] transition-colors"
          >
            <ArrowLeft className="w-3.5 h-3.5" /> {t("reader.back")}
          </Link>
          <div className="w-px h-5 bg-[color:var(--jm-border)]" />
          <div className="flex-1 min-w-0">
            <EditableTitle
              documentId={docId}
              value={summary?.title || summary?.filename || "—"}
              variant="title"
              testIdPrefix="reader-title"
              className="font-display font-semibold text-base text-[color:var(--jm-text)]"
              inputClass="font-display text-base font-semibold"
              onSaved={(newTitle) => setSummary((s) => (s ? { ...s, title: newTitle } : s))}
            />
          </div>
        </div>
      </div>

      <div className="flex-1 grid grid-cols-1 lg:grid-cols-12 overflow-hidden">
        <section
          data-testid="left-pdf-panel"
          className="lg:col-span-7 border-r border-[color:var(--jm-border)] overflow-hidden h-[calc(100vh-64px-49px)]"
        >
          {loading || !summary ? (
            <div className="flex items-center justify-center h-full text-[color:var(--jm-text-3)] font-ui">
              <Loader2 className="w-4 h-4 animate-spin mr-2" /> Memuat…
            </div>
          ) : (
            <PdfViewer
              fileUrl={api.pdfUrl(docId)}
              highlights={highlights}
              jumpTo={jumpTo}
            />
          )}
        </section>

        <aside
          data-testid="right-summary-panel"
          className="lg:col-span-5 bg-white overflow-y-auto h-[calc(100vh-64px-49px)]"
        >
          {loading || !summary ? (
            <div className="p-6 text-sm text-[color:var(--jm-text-3)] font-ui">Memuat ringkasan…</div>
          ) : (
            <SummaryPanel
              docId={docId}
              summary={summary.summary}
              sections={summary.sections || {}}
              modelUsed={summary.model_used}
              personaUsed={summary.persona_used}
              claims={summary.claims || []}
              onHighlight={(items, jump) => {
                setHighlights(items);
                if (jump) setJumpTo(jump);
              }}
              onResummarized={() => {
                api.getSummary(docId).then(setSummary).catch(() => {});
              }}
            />
          )}
        </aside>
      </div>
    </div>
  );
}
