import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Plus, Trash2, BookOpen, ArrowRight, FileText } from "lucide-react";
import { api } from "@/services/api";
import { toast } from "sonner";
import Header from "@/components/Header";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

export default function ProjectsPage() {
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [desc, setDesc] = useState("");

  const load = async () => {
    setLoading(true);
    try {
      const r = await api.listProjects();
      setProjects(r);
    } catch (e) {
      toast.error("Gagal memuat proyek");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const create = async () => {
    if (!name.trim()) return toast.error("Nama proyek wajib diisi");
    try {
      await api.createProject({ name, description: desc });
      toast.success("Proyek dibuat");
      setOpen(false);
      setName("");
      setDesc("");
      load();
    } catch (e) {
      toast.error("Gagal membuat proyek");
    }
  };

  const del = async (id) => {
    if (!window.confirm("Hapus proyek ini beserta semua jurnal di dalamnya?")) return;
    try {
      await api.deleteProject(id);
      toast.success("Proyek dihapus");
      load();
    } catch {
      toast.error("Gagal menghapus");
    }
  };

  return (
    <div className="min-h-screen">
      <Header
        rightSlot={
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
              <Button
                data-testid="new-project-btn"
                className="bg-[color:var(--jm-text)] text-white hover:bg-[#343a40] gap-2"
              >
                <Plus className="w-4 h-4" /> Proyek Baru
              </Button>
            </DialogTrigger>
            <DialogContent data-testid="new-project-dialog">
              <DialogHeader>
                <DialogTitle className="font-display text-2xl">
                  Buat Proyek
                </DialogTitle>
              </DialogHeader>
              <div className="space-y-3 pt-2">
                <div>
                  <label className="text-[11px] uppercase tracking-[0.18em] font-semibold text-[color:var(--jm-text-3)]">
                    Nama
                  </label>
                  <Input
                    data-testid="project-name-input"
                    autoFocus
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="Misal: Tinjauan Pustaka Pembelajaran Mesin Pendidikan"
                    className="mt-1"
                  />
                </div>
                <div>
                  <label className="text-[11px] uppercase tracking-[0.18em] font-semibold text-[color:var(--jm-text-3)]">
                    Deskripsi (opsional)
                  </label>
                  <Textarea
                    data-testid="project-desc-input"
                    value={desc}
                    onChange={(e) => setDesc(e.target.value)}
                    rows={3}
                    className="mt-1"
                  />
                </div>
              </div>
              <DialogFooter>
                <Button
                  data-testid="create-project-confirm"
                  onClick={create}
                  className="bg-[color:var(--jm-text)] text-white hover:bg-[#343a40]"
                >
                  Buat
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        }
      />

      <main className="mx-auto max-w-[1600px] px-6 py-12">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 mb-12">
          <div className="lg:col-span-7">
            <div className="text-[11px] uppercase tracking-[0.25em] font-semibold text-[color:var(--jm-text-3)] mb-4">
              v1.0 — Verifikasi Bukti Bertingkat
            </div>
            <h1
              data-testid="home-heading"
              className="font-display text-4xl sm:text-5xl lg:text-6xl tracking-[-0.02em] font-semibold text-[color:var(--jm-text)] leading-[1.02]"
            >
              Baca, verifikasi, dan bandingkan jurnal —
              <span className="text-[color:var(--jm-text-3)]"> tanpa</span>
              <span className="italic font-display"> kompromi</span>
              <span className="text-[color:var(--jm-text-3)]"> pada bukti.</span>
            </h1>
            <p className="mt-6 text-base text-[color:var(--jm-text-2)] max-w-xl leading-relaxed font-ui">
              JurnalMap menemukan bukti, bukan menilai kebenaran. Membandingkan,
              bukan memutuskan. Menunjukkan perbedaan, bukan menyimpulkan siapa
              yang salah.
            </p>
          </div>
          <div className="lg:col-span-5 hidden lg:flex items-end">
            <div className="w-full p-6 rounded-2xl bg-white border border-[color:var(--jm-border)] surface-grain">
              <div className="font-display font-semibold text-lg text-[color:var(--jm-text)] mb-3">
                Lima Pilar
              </div>
              <ul className="space-y-2 text-sm text-[color:var(--jm-text-2)] font-ui">
                <li className="flex gap-3"><span className="text-[color:var(--jm-text-3)] font-mono w-5">01</span><span>Panel Ganda + Pelacak Bukti Bertingkat</span></li>
                <li className="flex gap-3"><span className="text-[color:var(--jm-text-3)] font-mono w-5">02</span><span>Deteksi Outlier dalam Proyek</span></li>
                <li className="flex gap-3"><span className="text-[color:var(--jm-text-3)] font-mono w-5">03</span><span>Matriks Perbandingan Multi-Jurnal</span></li>
                <li className="flex gap-3"><span className="text-[color:var(--jm-text-3)] font-mono w-5">04</span><span>Tanya Pustaka Lintas Dokumen</span></li>
                <li className="flex gap-3"><span className="text-[color:var(--jm-text-3)] font-mono w-5">05</span><span>Manajemen Proyek</span></li>
              </ul>
            </div>
          </div>
        </div>

        <div className="flex items-baseline justify-between mb-6 border-t border-[color:var(--jm-border)] pt-8">
          <h2 className="font-display text-2xl sm:text-3xl tracking-tight font-semibold text-[color:var(--jm-text)]">
            Proyek Anda
          </h2>
          <div className="text-[11px] uppercase tracking-[0.2em] font-semibold text-[color:var(--jm-text-3)]">
            {projects.length} proyek
          </div>
        </div>

        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {[1,2,3].map((i) => (
              <div key={i} className="h-48 rounded-xl bg-white border border-[color:var(--jm-border)] animate-pulse" />
            ))}
          </div>
        ) : projects.length === 0 ? (
          <div
            data-testid="empty-projects"
            className="rounded-2xl border-2 border-dashed border-[color:var(--jm-border)] p-16 text-center bg-white"
          >
            <div className="w-14 h-14 rounded-full bg-[color:var(--jm-sidebar)] mx-auto flex items-center justify-center mb-4">
              <BookOpen className="w-6 h-6 text-[color:var(--jm-text-2)]" />
            </div>
            <div className="font-display text-xl font-semibold text-[color:var(--jm-text)] mb-2">
              Belum ada proyek
            </div>
            <p className="text-sm text-[color:var(--jm-text-2)] mb-6 font-ui">
              Mulai dengan membuat proyek tinjauan pustaka pertama Anda.
            </p>
            <Button
              data-testid="empty-create-btn"
              onClick={() => setOpen(true)}
              className="bg-[color:var(--jm-text)] text-white hover:bg-[#343a40] gap-2"
            >
              <Plus className="w-4 h-4" /> Buat proyek pertama
            </Button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {projects.map((p) => (
              <div
                key={p.id}
                data-testid={`project-card-${p.id}`}
                className="group relative p-6 rounded-xl border border-[color:var(--jm-border)] bg-white hover:-translate-y-0.5 hover:shadow-lg hover:border-[color:var(--jm-border-2)] transition-all"
              >
                <button
                  data-testid={`delete-project-${p.id}`}
                  onClick={() => del(p.id)}
                  className="absolute top-4 right-4 opacity-0 group-hover:opacity-100 transition-opacity p-1.5 rounded hover:bg-[color:var(--jm-sidebar)]"
                  aria-label="Hapus proyek"
                >
                  <Trash2 className="w-4 h-4 text-[color:var(--jm-text-3)]" />
                </button>
                <Link to={`/project/${p.id}`} className="block">
                  <div className="font-display text-xl font-semibold text-[color:var(--jm-text)] leading-tight pr-8 mb-2">
                    {p.name}
                  </div>
                  {p.description && (
                    <p className="text-sm text-[color:var(--jm-text-2)] line-clamp-2 font-ui mb-6">
                      {p.description}
                    </p>
                  )}
                  <div className="flex items-center justify-between text-xs text-[color:var(--jm-text-3)] font-ui pt-4 border-t border-[color:var(--jm-border)]">
                    <span className="flex items-center gap-1.5">
                      <FileText className="w-3.5 h-3.5" /> {p.document_count} jurnal
                    </span>
                    <span className="inline-flex items-center gap-1 text-[color:var(--jm-text)] font-medium opacity-0 group-hover:opacity-100 transition-opacity">
                      Buka <ArrowRight className="w-3.5 h-3.5" />
                    </span>
                  </div>
                </Link>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
