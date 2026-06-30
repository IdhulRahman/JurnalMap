import { useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Loader2, FileText } from "lucide-react";
import { api } from "@/services/api";

export default function FindSourceDialog({
  open,
  onOpenChange,
  projectId,
  text,
  onConfirm,
}) {
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    if (!open || !text) return;
    setResult(null);
    setErr("");
    setBusy(true);
    api
      .workspaceFindSource(projectId, text)
      .then((r) => setResult(r))
      .catch((e) => setErr(e?.response?.data?.detail || "Gagal mencari sumber."))
      .finally(() => setBusy(false));
  }, [open, text, projectId]);

  const accept = () => {
    if (result?.found && result.source) onConfirm?.(result.source);
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent data-testid="find-source-dialog" className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Cari Sumber Pendukung</DialogTitle>
        </DialogHeader>
        <div className="py-2">
          <div className="text-[10px] uppercase tracking-[0.2em] font-semibold text-[color:var(--jm-text-3)] mb-1">
            Klaim yang Anda tulis
          </div>
          <blockquote
            data-testid="find-source-claim"
            className="border-l-2 border-[color:var(--jm-text)] pl-3 font-reading text-sm text-[color:var(--jm-text-2)] mb-4"
          >
            {text || "(kosong)"}
          </blockquote>

          {busy ? (
            <div className="py-4 text-center text-sm text-[color:var(--jm-text-3)] font-ui">
              <Loader2 className="w-4 h-4 animate-spin mx-auto mb-2" /> Mencari di pustaka proyek…
            </div>
          ) : err ? (
            <div className="text-xs text-rose-700 dark:text-rose-300 font-ui">{err}</div>
          ) : result?.found && result.source ? (
            <div
              data-testid="find-source-result"
              className="rounded-md border border-[color:var(--jm-border)] bg-[color:var(--jm-reading)] p-3"
            >
              <div className="text-[10px] uppercase tracking-[0.2em] font-semibold text-[color:var(--jm-text-3)] mb-1 flex items-center gap-1">
                <FileText className="w-3 h-3" /> {result.source.document_title}
                {result.source.page ? <span>· hal. {result.source.page}</span> : null}
              </div>
              <div className="font-reading text-sm text-[color:var(--jm-text)] leading-relaxed">
                &ldquo;{result.source.quote}&rdquo;
              </div>
              <div className="mt-2 text-[10px] font-ui italic text-[color:var(--jm-text-3)]">
                Tambahkan sitasi dari paper ini ke akhir klaim?
              </div>
            </div>
          ) : (
            <div
              data-testid="find-source-empty"
              className="text-sm text-[color:var(--jm-text-2)] font-ui italic"
            >
              {result?.reason === "no-documents"
                ? "Tidak ada jurnal siap di proyek ini. Unggah PDF dulu."
                : "Tidak ditemukan sumber yang mendukung klaim ini di pustaka proyek."}
            </div>
          )}
        </div>
        <DialogFooter>
          <button
            onClick={() => onOpenChange(false)}
            className="px-3 py-1.5 rounded-md text-xs font-ui border border-[color:var(--jm-border)] hover:bg-[color:var(--jm-sidebar)]"
          >
            Batal
          </button>
          <button
            data-testid="find-source-accept"
            onClick={accept}
            disabled={!result?.found}
            className="px-3 py-1.5 rounded-md text-xs font-ui font-semibold bg-[color:var(--jm-text)] text-[color:var(--jm-bg)] hover:opacity-90 disabled:opacity-50"
          >
            Tambahkan
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
