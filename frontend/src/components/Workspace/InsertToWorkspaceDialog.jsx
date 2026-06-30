import { useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogClose,
} from "@/components/ui/dialog";
import { Loader2 } from "lucide-react";
import { api } from "@/services/api";
import { toast } from "sonner";

export default function InsertToWorkspaceDialog({
  open,
  onOpenChange,
  projectId,
  payload, // {document_id, sentence_id, quote, page}
}) {
  const [outline, setOutline] = useState(null);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [selected, setSelected] = useState(null);

  useEffect(() => {
    if (!open || !projectId) return;
    setOutline(null);
    setSelected(null);
    setLoading(true);
    api
      .getOutline(projectId)
      .then((ol) => {
        setOutline(ol);
        const first = ol?.chapters?.[0]?.subchapters?.[0]?.id;
        if (first) setSelected(first);
      })
      .catch(() => toast.error("Gagal memuat outline"))
      .finally(() => setLoading(false));
  }, [open, projectId]);

  const exists = outline?.exists && (outline?.chapters || []).length > 0;

  const insert = () => {
    if (!selected) {
      toast.error("Pilih sub-bab tujuan");
      return;
    }
    setBusy(true);
    try {
      window.dispatchEvent(
        new CustomEvent("jm:workspace-insert", {
          detail: {
            projectId,
            subchapterId: selected,
            document_id: payload?.document_id,
            sentence_id: payload?.sentence_id,
            quote: payload?.quote,
            page: payload?.page,
          },
        })
      );
      onOpenChange(false);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent data-testid="workspace-insert-dialog" className="max-w-md">
        <DialogHeader>
          <DialogTitle>Sisipkan ke Workspace</DialogTitle>
        </DialogHeader>
        {loading ? (
          <div className="py-8 text-center text-sm text-[color:var(--jm-text-3)] font-ui">
            <Loader2 className="w-4 h-4 animate-spin mx-auto mb-2" /> Memuat outline…
          </div>
        ) : !exists ? (
          <div className="py-4 text-sm text-[color:var(--jm-text-2)] font-ui">
            Outline belum disusun. Buka tab Workspace dan susun Grand Outline terlebih dahulu.
          </div>
        ) : (
          <div className="space-y-3 max-h-[50vh] overflow-y-auto py-2">
            {(outline.chapters || []).map((ch) => (
              <div key={ch.id}>
                <div className="text-[10px] uppercase tracking-[0.2em] font-semibold text-[color:var(--jm-text-3)] mb-1">
                  {ch.title}
                </div>
                <ul className="space-y-1">
                  {(ch.subchapters || []).map((sc) => (
                    <li key={sc.id}>
                      <label
                        data-testid={`insert-sub-${sc.id}`}
                        className={`flex items-center gap-2 px-2.5 py-1.5 rounded-md text-xs font-ui cursor-pointer transition-colors ${
                          selected === sc.id
                            ? "bg-[color:var(--jm-text)] text-[color:var(--jm-bg)]"
                            : "hover:bg-[color:var(--jm-sidebar)]"
                        }`}
                      >
                        <input
                          type="radio"
                          name="insert-sub"
                          value={sc.id}
                          checked={selected === sc.id}
                          onChange={() => setSelected(sc.id)}
                          className="hidden"
                        />
                        {sc.title}
                      </label>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        )}
        <DialogFooter>
          <DialogClose asChild>
            <button className="px-3 py-1.5 rounded-md text-xs font-ui border border-[color:var(--jm-border)] hover:bg-[color:var(--jm-sidebar)]">
              Batal
            </button>
          </DialogClose>
          <button
            data-testid="insert-confirm"
            onClick={insert}
            disabled={busy || !selected || !exists}
            className="px-3 py-1.5 rounded-md text-xs font-ui font-semibold bg-[color:var(--jm-text)] text-[color:var(--jm-bg)] hover:opacity-90 disabled:opacity-50"
          >
            Sisipkan
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
