import { useState } from "react";
import { Plus, Trash2, Save, ListTree } from "lucide-react";
import { CITATION_FORMATS, newId } from "./workspaceUtils";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { toast } from "sonner";
import { api } from "@/services/api";
import { Loader2 } from "lucide-react";

export default function OutlineSetup({ projectId, initial, onSaved }) {
  const [title, setTitle] = useState(initial?.title || "");
  const [format, setFormat] = useState(initial?.citation_format || "ieee");
  const [chapters, setChapters] = useState(
    initial?.chapters?.length
      ? initial.chapters
      : [
          {
            id: newId(),
            title: "Bab 1: Pendahuluan",
            subchapters: [
              { id: newId(), title: "1.1 Latar Belakang" },
              { id: newId(), title: "1.2 Rumusan Masalah" },
            ],
          },
        ]
  );
  const [busy, setBusy] = useState(false);

  const addChapter = () =>
    setChapters((arr) => [
      ...arr,
      { id: newId(), title: `Bab ${arr.length + 1}`, subchapters: [] },
    ]);
  const removeChapter = (idx) =>
    setChapters((arr) => arr.filter((_, i) => i !== idx));
  const updateChapterTitle = (idx, value) =>
    setChapters((arr) => arr.map((c, i) => (i === idx ? { ...c, title: value } : c)));
  const addSub = (cIdx) =>
    setChapters((arr) =>
      arr.map((c, i) =>
        i === cIdx
          ? {
              ...c,
              subchapters: [
                ...c.subchapters,
                {
                  id: newId(),
                  title: `${i + 1}.${c.subchapters.length + 1} Sub-bab baru`,
                },
              ],
            }
          : c
      )
    );
  const removeSub = (cIdx, sIdx) =>
    setChapters((arr) =>
      arr.map((c, i) =>
        i === cIdx ? { ...c, subchapters: c.subchapters.filter((_, j) => j !== sIdx) } : c
      )
    );
  const updateSubTitle = (cIdx, sIdx, value) =>
    setChapters((arr) =>
      arr.map((c, i) =>
        i === cIdx
          ? {
              ...c,
              subchapters: c.subchapters.map((s, j) =>
                j === sIdx ? { ...s, title: value } : s
              ),
            }
          : c
      )
    );

  const save = async () => {
    if (!title.trim()) {
      toast.error("Judul makalah wajib diisi");
      return;
    }
    if (chapters.length === 0) {
      toast.error("Tambahkan minimal satu bab");
      return;
    }
    setBusy(true);
    try {
      const saved = await api.saveOutline(projectId, {
        title: title.trim(),
        chapters,
        citation_format: format,
      });
      toast.success("Outline tersimpan");
      onSaved?.(saved);
    } catch (e) {
      toast.error("Gagal menyimpan outline");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      data-testid="workspace-outline-setup"
      className="max-w-3xl mx-auto rounded-xl border border-[color:var(--jm-border)] bg-[color:var(--jm-surface)] p-6 space-y-5"
    >
      <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.22em] font-semibold text-[color:var(--jm-text-3)]">
        <ListTree className="w-3.5 h-3.5" /> Grand Outline
      </div>

      <div>
        <label className="text-[10px] uppercase tracking-[0.2em] font-semibold text-[color:var(--jm-text-3)] mb-1 block">
          Judul Makalah
        </label>
        <input
          data-testid="outline-title-input"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Contoh: Dampak Media Sosial terhadap Kesehatan Mental Mahasiswa"
          className="w-full px-3 py-2 rounded-md border border-[color:var(--jm-border)] focus:border-[color:var(--jm-text)] focus:outline-none font-ui text-sm bg-[color:var(--jm-surface)] text-[color:var(--jm-text)]"
        />
      </div>

      <div>
        <label className="text-[10px] uppercase tracking-[0.2em] font-semibold text-[color:var(--jm-text-3)] mb-1 block">
          Format Sitasi
        </label>
        <Select value={format} onValueChange={setFormat}>
          <SelectTrigger data-testid="outline-citation-select" className="h-9 text-xs bg-[color:var(--jm-surface)] border-[color:var(--jm-border)] text-[color:var(--jm-text)]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {CITATION_FORMATS.map((f) => (
              <SelectItem key={f.id} data-testid={`outline-cf-${f.id}`} value={f.id}>
                {f.label} — contoh {f.example}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-[10px] uppercase tracking-[0.2em] font-semibold text-[color:var(--jm-text-3)]">
            Struktur Bab
          </span>
          <button
            data-testid="outline-add-chapter"
            onClick={addChapter}
            className="px-2.5 py-1 rounded-md text-xs font-ui font-semibold flex items-center gap-1 bg-[color:var(--jm-sidebar)] text-[color:var(--jm-text-2)] hover:bg-[color:var(--jm-reading)]"
          >
            <Plus className="w-3.5 h-3.5" /> Tambah Bab
          </button>
        </div>
        <ul className="space-y-3">
          {chapters.map((ch, ci) => (
            <li
              key={ch.id}
              data-testid={`outline-chapter-${ci}`}
              className="rounded-lg border border-[color:var(--jm-border)] p-3 space-y-2"
            >
              <div className="flex items-center gap-2">
                <input
                  data-testid={`outline-chapter-title-${ci}`}
                  value={ch.title}
                  onChange={(e) => updateChapterTitle(ci, e.target.value)}
                  className="flex-1 px-2 py-1.5 rounded-md border border-[color:var(--jm-border)] focus:border-[color:var(--jm-text)] focus:outline-none font-ui text-sm bg-[color:var(--jm-surface)] text-[color:var(--jm-text)]"
                />
                <button
                  data-testid={`outline-remove-chapter-${ci}`}
                  onClick={() => removeChapter(ci)}
                  className="p-1.5 rounded hover:bg-[color:var(--jm-sidebar)]"
                  title="Hapus bab"
                >
                  <Trash2 className="w-3.5 h-3.5 text-[color:var(--jm-text-3)]" />
                </button>
              </div>
              <ul className="space-y-1.5 pl-4 border-l border-[color:var(--jm-border)]">
                {ch.subchapters.map((sc, si) => (
                  <li key={sc.id} className="flex items-center gap-2">
                    <input
                      data-testid={`outline-sub-title-${ci}-${si}`}
                      value={sc.title}
                      onChange={(e) => updateSubTitle(ci, si, e.target.value)}
                      className="flex-1 px-2 py-1 rounded-md border border-[color:var(--jm-border)] focus:border-[color:var(--jm-text)] focus:outline-none font-ui text-xs bg-[color:var(--jm-surface)] text-[color:var(--jm-text)]"
                    />
                    <button
                      data-testid={`outline-remove-sub-${ci}-${si}`}
                      onClick={() => removeSub(ci, si)}
                      className="p-1 rounded hover:bg-[color:var(--jm-sidebar)]"
                    >
                      <Trash2 className="w-3 h-3 text-[color:var(--jm-text-3)]" />
                    </button>
                  </li>
                ))}
                <li>
                  <button
                    data-testid={`outline-add-sub-${ci}`}
                    onClick={() => addSub(ci)}
                    className="text-xs text-[color:var(--jm-text-2)] hover:text-[color:var(--jm-text)] font-ui flex items-center gap-1"
                  >
                    <Plus className="w-3 h-3" /> Tambah Sub-bab
                  </button>
                </li>
              </ul>
            </li>
          ))}
        </ul>
      </div>

      <div className="pt-3 border-t border-[color:var(--jm-border)] flex justify-end">
        <button
          data-testid="outline-save"
          onClick={save}
          disabled={busy}
          className="px-4 py-2 rounded-md text-sm font-ui font-semibold flex items-center gap-2 bg-[color:var(--jm-text)] text-[color:var(--jm-bg)] hover:opacity-90 disabled:opacity-50"
        >
          {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
          Simpan Outline
        </button>
      </div>
    </div>
  );
}
