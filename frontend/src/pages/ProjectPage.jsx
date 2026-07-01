import { useEffect, useState } from "react";
import { Link, useParams, useNavigate } from "react-router-dom";
import {
  ArrowLeft,
  BookOpen,
  GitCompare,
  MessageSquareText,
  Loader2,
  CheckCircle2,
  AlertCircle,
  Trash2,
  FileText,
  ShieldCheck,
  RotateCw,
  Clock,
} from "lucide-react";
import { api } from "@/services/api";
import { toast } from "sonner";
import Header from "@/components/Header";
import UploadDropzone from "@/components/UploadDropzone";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import NetworkGraph from "@/components/NetworkGraph";
import MatrixView from "@/components/MatrixView";
import AskPanel from "@/components/AskPanel";
import EditableTitle from "@/components/EditableTitle";
import CheckFix from "@/components/CheckFix/CheckFix";
import { useT } from "@/lib/useT";

export default function ProjectPage() {
  const { id } = useParams();
  const nav = useNavigate();
  const { t } = useT();
  const [project, setProject] = useState(null);
  const [docs, setDocs] = useState([]);
  const [busyUpload, setBusyUpload] = useState(false);
  const [tab, setTab] = useState("baca");

  const loadDocs = async () => {
    try {
      const list = await api.listDocuments(id);
      setDocs(list);
      return list;
    } catch {
      toast.error("Gagal memuat dokumen");
      return [];
    }
  };

  useEffect(() => {
    api.getProject(id).then(setProject).catch(() => toast.error("Proyek tidak ditemukan"));
    loadDocs();
  }, [id]);

  // Poll while any doc is queued OR processing
  useEffect(() => {
    const active = docs.some((d) => d.status === "processing" || d.status === "queued");
    if (!active) return;
    const t = setInterval(loadDocs, 2500);
    return () => clearInterval(t);
  }, [docs.map((d) => `${d.id}:${d.status}`).join(",")]);

  const onUpload = async (files) => {
    // Backwards compat: allow single File
    const arr = Array.isArray(files) ? files : [files];
    if (!arr.length) return;
    setBusyUpload(true);
    try {
      await api.uploadDocuments(id, arr);
      toast.success(
        arr.length === 1
          ? "Diunggah — masuk ke antrean pemrosesan"
          : `${arr.length} file diunggah — masuk ke antrean`,
      );
      await loadDocs();
    } catch (e) {
      const detail = e?.response?.data?.detail;
      toast.error(typeof detail === "string" ? detail : "Unggah gagal");
    } finally {
      setBusyUpload(false);
    }
  };

  const retryDoc = async (docId) => {
    try {
      await api.retryDocument(docId);
      toast.success("Diantrekan ulang");
      loadDocs();
    } catch (e) {
      const detail = e?.response?.data?.detail;
      toast.error(typeof detail === "string" ? detail : "Gagal mengantre ulang");
    }
  };

  const removeDoc = async (docId) => {
    if (!window.confirm("Hapus dokumen ini?")) return;
    try {
      await api.deleteDocument(docId);
      toast.success("Dokumen dihapus");
      loadDocs();
    } catch {
      toast.error("Gagal menghapus");
    }
  };

  if (!project) {
    return (
      <div className="min-h-screen">
        <Header />
        <div className="p-16 text-center text-[color:var(--jm-text-3)] font-ui">Memuat…</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      <Header />
      <div className="border-b border-[color:var(--jm-border)] bg-white">
        <div className="mx-auto max-w-[1600px] px-6 py-6">
          <button
            data-testid="back-to-projects"
            onClick={() => nav("/")}
            className="flex items-center gap-1.5 text-xs uppercase tracking-[0.2em] font-semibold text-[color:var(--jm-text-3)] hover:text-[color:var(--jm-text)] transition-colors mb-3"
          >
            <ArrowLeft className="w-3.5 h-3.5" /> {t("project.back")}
          </button>
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <h1
                data-testid="project-title"
                className="font-display text-3xl sm:text-4xl font-semibold tracking-tight text-[color:var(--jm-text)]"
              >
                {project.name}
              </h1>
              {project.description && (
                <p className="mt-2 text-sm text-[color:var(--jm-text-2)] max-w-3xl font-ui">
                  {project.description}
                </p>
              )}
            </div>
            <div className="text-[11px] uppercase tracking-[0.2em] font-semibold text-[color:var(--jm-text-3)]">
              {t("project.journalsCount", { n: docs.length })}
            </div>
          </div>
        </div>
      </div>

      <main className="mx-auto max-w-[1600px] px-6 py-8">
        <Tabs value={tab} onValueChange={setTab} className="w-full">
          <TabsList
            data-testid="project-tabs"
            className="bg-[color:var(--jm-surface)] border border-[color:var(--jm-border)] p-1 rounded-lg h-auto"
          >
            <TabsTrigger
              data-testid="tab-baca"
              value="baca"
              className="data-[state=active]:bg-[color:var(--jm-text)] data-[state=active]:text-[color:var(--jm-bg)] px-4 py-2 gap-2"
            >
              <BookOpen className="w-4 h-4" /> Pustaka
            </TabsTrigger>
            <TabsTrigger
              data-testid="tab-bandingkan"
              value="bandingkan"
              className="data-[state=active]:bg-[color:var(--jm-text)] data-[state=active]:text-[color:var(--jm-bg)] px-4 py-2 gap-2"
            >
              <GitCompare className="w-4 h-4" /> Matriks
            </TabsTrigger>
            <TabsTrigger
              data-testid="tab-tanya"
              value="tanya"
              className="data-[state=active]:bg-[color:var(--jm-text)] data-[state=active]:text-[color:var(--jm-bg)] px-4 py-2 gap-2"
            >
              <MessageSquareText className="w-4 h-4" /> {t("tab.ask")}
            </TabsTrigger>
            <TabsTrigger
              data-testid="tab-check-fix"
              value="check-fix"
              className="data-[state=active]:bg-[color:var(--jm-text)] data-[state=active]:text-[color:var(--jm-bg)] px-4 py-2 gap-2"
            >
              <ShieldCheck className="w-4 h-4" /> Check & Fix
            </TabsTrigger>
          </TabsList>

          <TabsContent value="baca" className="mt-6">
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
              <section className="lg:col-span-5">
                <h3 className="text-[11px] uppercase tracking-[0.2em] font-semibold text-[color:var(--jm-text-3)] mb-3">
                  {t("project.add")}
                </h3>
                <UploadDropzone onUpload={onUpload} busy={busyUpload} />
              </section>

              <section className="lg:col-span-7">
                <h3 className="text-[11px] uppercase tracking-[0.2em] font-semibold text-[color:var(--jm-text-3)] mb-3">
                  {t("project.list")}
                </h3>
                {docs.length === 0 ? (
                  <div className="rounded-xl border border-[color:var(--jm-border)] bg-[color:var(--jm-surface)] p-10 text-center text-sm text-[color:var(--jm-text-2)] font-ui">
                    {t("project.empty")}
                  </div>
                ) : (
                  <ul data-testid="documents-list" className="space-y-3">
                    {docs.map((d) => (
                      <li
                        key={d.id}
                        data-testid={`doc-row-${d.id}`}
                        className="rounded-xl border border-[color:var(--jm-border)] bg-[color:var(--jm-surface)] p-4 flex items-center gap-4 hover:border-[color:var(--jm-border-2)] transition-colors"
                      >
                        <div className="w-10 h-10 rounded-md bg-[color:var(--jm-sidebar)] flex items-center justify-center shrink-0">
                          <FileText className="w-5 h-5 text-[color:var(--jm-text-2)]" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <EditableTitle
                            documentId={d.id}
                            value={d.title || d.filename}
                            variant="row"
                            testIdPrefix={`edit-title-${d.id}`}
                            className="font-ui font-semibold text-sm text-[color:var(--jm-text)]"
                            inputClass="text-sm"
                            onSaved={(newTitle) => {
                              setDocs((arr) => arr.map((x) => x.id === d.id ? { ...x, title: newTitle } : x));
                            }}
                          />
                          <div className="text-xs text-[color:var(--jm-text-3)] font-ui mt-0.5">
                            {d.filename} • {d.page_count > 0 ? `${d.page_count} hlm` : "—"}
                          </div>
                          {d.quality && d.status === "ready" && (
                            <QualityIndicator quality={d.quality} testId={`doc-quality-${d.id}`} />
                          )}
                        </div>
                        <StatusPill status={d.status} error={d.error} pos={d.queue_position} total={countActive(docs)} t={t} />
                        {d.status === "ready" ? (
                          <Link
                            data-testid={`open-doc-${d.id}`}
                            to={`/project/${id}/doc/${d.id}`}
                            className="text-xs font-semibold text-[color:var(--jm-bg)] bg-[color:var(--jm-text)] hover:opacity-90 px-3 py-2 rounded-md transition-colors"
                          >
                            {t("common.open")}
                          </Link>
                        ) : null}
                        {d.status === "failed" ? (
                          <button
                            data-testid={`retry-doc-${d.id}`}
                            onClick={() => retryDoc(d.id)}
                            className="text-xs font-semibold text-[color:var(--jm-bg)] bg-[color:var(--jm-accent)] hover:opacity-90 px-3 py-2 rounded-md transition-colors flex items-center gap-1.5"
                            title="Antrekan ulang file ini"
                          >
                            <RotateCw className="w-3.5 h-3.5" /> {t("status.retry")}
                          </button>
                        ) : null}
                        <button
                          data-testid={`delete-doc-${d.id}`}
                          onClick={() => removeDoc(d.id)}
                          className="p-2 rounded hover:bg-[color:var(--jm-sidebar)]"
                          aria-label={t("common.delete")}
                        >
                          <Trash2 className="w-4 h-4 text-[color:var(--jm-text-3)]" />
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </section>
            </div>
            {(docs || []).filter((d) => d.status === "ready").length >= 2 && (
              <div className="mt-6">
                <NetworkGraph projectId={id} docs={docs} />
              </div>
            )}
          </TabsContent>

          <TabsContent value="bandingkan" className="mt-6">
            <MatrixView projectId={id} docs={docs} />
          </TabsContent>

          <TabsContent value="tanya" className="mt-6">
            <AskPanel projectId={id} docs={docs} />
          </TabsContent>

          <TabsContent value="check-fix" className="mt-6">
            <CheckFix projectId={id} docs={docs} />
          </TabsContent>
        </Tabs>
      </main>
    </div>
  );
}

function countActive(docs) {
  return (docs || []).filter((d) => d.status === "processing" || d.status === "queued").length;
}

function StatusPill({ status, error, pos, total, t }) {
  if (status === "processing") {
    return (
      <span
        data-testid="status-processing"
        className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold bg-[color:var(--jm-sidebar)] text-[color:var(--jm-text-2)] font-ui"
      >
        <Loader2 className="w-3 h-3 animate-spin" />
        {total > 1 && typeof pos === "number"
          ? t("status.processingNow", { pos: 1, total })
          : t("status.processing")}
      </span>
    );
  }
  if (status === "queued") {
    return (
      <span
        data-testid="status-queued"
        className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold bg-[color:var(--jm-sidebar)] text-[color:var(--jm-text-2)] font-ui"
      >
        <Clock className="w-3 h-3" />
        {typeof pos === "number" && total > 1
          ? t("status.queuePos", { pos, total })
          : t("status.queued")}
      </span>
    );
  }
  if (status === "ready") {
    return (
      <span
        data-testid="status-ready"
        className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold tier-high font-ui"
      >
        <CheckCircle2 className="w-3 h-3" /> {t("status.ready")}
      </span>
    );
  }
  return (
    <span
      data-testid="status-failed"
      title={error || ""}
      className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold tier-low font-ui"
    >
      <AlertCircle className="w-3 h-3" /> {t("status.failed")}
    </span>
  );
}

function QualityIndicator({ quality, testId }) {
  if (!quality || typeof quality.score !== "number") return null;
  const score = Math.max(0, Math.min(100, quality.score));
  const label = quality.label || (score >= 80 ? "good" : score >= 50 ? "fair" : "poor");
  const colorBar =
    label === "good" ? "bg-emerald-500" : label === "fair" ? "bg-amber-500" : "bg-rose-500";
  const colorText =
    label === "good"
      ? "text-emerald-700 dark:text-emerald-300"
      : label === "fair"
      ? "text-amber-700 dark:text-amber-300"
      : "text-rose-700 dark:text-rose-300";
  const labelId = label === "good" ? "Baik" : label === "fair" ? "Cukup" : "Buruk";
  return (
    <div data-testid={testId} className="mt-1.5 flex items-center gap-2 text-[10px] font-ui">
      <span className="uppercase tracking-[0.18em] font-semibold text-[color:var(--jm-text-3)]">
        Kualitas
      </span>
      <div className="w-24 h-1.5 rounded-full bg-[color:var(--jm-sidebar)] overflow-hidden">
        <div
          className={`h-full ${colorBar}`}
          style={{ width: `${score}%` }}
        />
      </div>
      <span className={`font-semibold ${colorText}`}>
        {score}% · {labelId}
      </span>
      {(quality.tables_count != null || quality.figures_count != null) && (
        <span className="text-[color:var(--jm-text-3)]">
          {quality.tables_count ? `· ${quality.tables_count} tbl` : ""}
          {quality.figures_count ? ` · ${quality.figures_count} gbr` : ""}
        </span>
      )}
      {label === "poor" && (
        <span
          data-testid={`${testId}-warning`}
          className="text-[color:var(--jm-low-fg)]"
          title="Beberapa halaman mungkin tidak terbaca."
        >
          ⚠
        </span>
      )}
    </div>
  );
}
