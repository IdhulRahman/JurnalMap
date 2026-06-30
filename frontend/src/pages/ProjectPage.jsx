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
} from "lucide-react";
import { api } from "@/services/api";
import { toast } from "sonner";
import Header from "@/components/Header";
import UploadDropzone from "@/components/UploadDropzone";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import OutlierMap from "@/components/OutlierMap";
import MatrixView from "@/components/MatrixView";
import AskPanel from "@/components/AskPanel";

export default function ProjectPage() {
  const { id } = useParams();
  const nav = useNavigate();
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

  // Poll processing docs
  useEffect(() => {
    const processing = docs.some((d) => d.status === "processing");
    if (!processing) return;
    const t = setInterval(loadDocs, 3000);
    return () => clearInterval(t);
  }, [docs.map((d) => `${d.id}:${d.status}`).join(",")]); // eslint-disable-line react-hooks/exhaustive-deps

  const onUpload = async (file) => {
    setBusyUpload(true);
    try {
      await api.uploadDocument(id, file);
      toast.success("Unggahan dimulai — pemrosesan berjalan di latar belakang");
      await loadDocs();
    } catch (e) {
      toast.error("Unggah gagal");
    } finally {
      setBusyUpload(false);
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
            <ArrowLeft className="w-3.5 h-3.5" /> Semua Proyek
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
              {docs.length} jurnal dalam proyek ini
            </div>
          </div>
        </div>
      </div>

      <main className="mx-auto max-w-[1600px] px-6 py-8">
        <Tabs value={tab} onValueChange={setTab} className="w-full">
          <TabsList
            data-testid="project-tabs"
            className="bg-white border border-[color:var(--jm-border)] p-1 rounded-lg h-auto"
          >
            <TabsTrigger
              data-testid="tab-baca"
              value="baca"
              className="data-[state=active]:bg-[color:var(--jm-text)] data-[state=active]:text-white px-4 py-2 gap-2"
            >
              <BookOpen className="w-4 h-4" /> Baca
            </TabsTrigger>
            <TabsTrigger
              data-testid="tab-bandingkan"
              value="bandingkan"
              className="data-[state=active]:bg-[color:var(--jm-text)] data-[state=active]:text-white px-4 py-2 gap-2"
            >
              <GitCompare className="w-4 h-4" /> Bandingkan
            </TabsTrigger>
            <TabsTrigger
              data-testid="tab-tanya"
              value="tanya"
              className="data-[state=active]:bg-[color:var(--jm-text)] data-[state=active]:text-white px-4 py-2 gap-2"
            >
              <MessageSquareText className="w-4 h-4" /> Tanya Pustaka
            </TabsTrigger>
          </TabsList>

          <TabsContent value="baca" className="mt-6">
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
              <section className="lg:col-span-5">
                <h3 className="text-[11px] uppercase tracking-[0.2em] font-semibold text-[color:var(--jm-text-3)] mb-3">
                  Tambah Jurnal
                </h3>
                <UploadDropzone onUpload={onUpload} busy={busyUpload} />
              </section>

              <section className="lg:col-span-7">
                <h3 className="text-[11px] uppercase tracking-[0.2em] font-semibold text-[color:var(--jm-text-3)] mb-3">
                  Jurnal dalam Proyek
                </h3>
                {docs.length === 0 ? (
                  <div className="rounded-xl border border-[color:var(--jm-border)] bg-white p-10 text-center text-sm text-[color:var(--jm-text-2)] font-ui">
                    Unggah PDF pertama Anda untuk mulai membaca dengan pelacak bukti.
                  </div>
                ) : (
                  <ul data-testid="documents-list" className="space-y-3">
                    {docs.map((d) => (
                      <li
                        key={d.id}
                        data-testid={`doc-row-${d.id}`}
                        className="rounded-xl border border-[color:var(--jm-border)] bg-white p-4 flex items-center gap-4 hover:border-[color:var(--jm-border-2)] transition-colors"
                      >
                        <div className="w-10 h-10 rounded-md bg-[color:var(--jm-sidebar)] flex items-center justify-center shrink-0">
                          <FileText className="w-5 h-5 text-[color:var(--jm-text-2)]" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="font-ui font-semibold text-sm text-[color:var(--jm-text)] truncate">
                            {d.title || d.filename}
                          </div>
                          <div className="text-xs text-[color:var(--jm-text-3)] font-ui mt-0.5">
                            {d.filename} • {d.page_count > 0 ? `${d.page_count} hlm` : "—"}
                          </div>
                        </div>
                        <StatusPill status={d.status} error={d.error} />
                        {d.status === "ready" ? (
                          <Link
                            data-testid={`open-doc-${d.id}`}
                            to={`/project/${id}/doc/${d.id}`}
                            className="text-xs font-semibold text-white bg-[color:var(--jm-text)] hover:bg-[#343a40] px-3 py-2 rounded-md transition-colors"
                          >
                            Buka
                          </Link>
                        ) : null}
                        <button
                          data-testid={`delete-doc-${d.id}`}
                          onClick={() => removeDoc(d.id)}
                          className="p-2 rounded hover:bg-[color:var(--jm-sidebar)]"
                          aria-label="Hapus"
                        >
                          <Trash2 className="w-4 h-4 text-[color:var(--jm-text-3)]" />
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </section>
            </div>
          </TabsContent>

          <TabsContent value="bandingkan" className="mt-6">
            <OutlierMap projectId={id} docs={docs} />
            <div className="h-6" />
            <MatrixView projectId={id} docs={docs} />
          </TabsContent>

          <TabsContent value="tanya" className="mt-6">
            <AskPanel projectId={id} docs={docs} />
          </TabsContent>
        </Tabs>
      </main>
    </div>
  );
}

function StatusPill({ status, error }) {
  if (status === "processing") {
    return (
      <span
        data-testid="status-processing"
        className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold bg-[color:var(--jm-sidebar)] text-[color:var(--jm-text-2)] font-ui"
      >
        <Loader2 className="w-3 h-3 animate-spin" /> Memproses
      </span>
    );
  }
  if (status === "ready") {
    return (
      <span
        data-testid="status-ready"
        className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold tier-high font-ui"
      >
        <CheckCircle2 className="w-3 h-3" /> Siap
      </span>
    );
  }
  return (
    <span
      data-testid="status-failed"
      title={error || ""}
      className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold tier-low font-ui"
    >
      <AlertCircle className="w-3 h-3" /> Gagal
    </span>
  );
}
