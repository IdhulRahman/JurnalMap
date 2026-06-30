import { BookMarked, AlertTriangle } from "lucide-react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { CITATION_FORMATS } from "./workspaceUtils";

export default function ReferenceManager({
  citationFormat,
  onChangeFormat,
  formatChangedWarning,
  badges,
  onSelectBadge,
  activeBadgeId,
}) {
  // Group badges by document_id
  const byDoc = {};
  for (const b of badges || []) {
    const k = b.document_id || "unknown";
    if (!byDoc[k]) byDoc[k] = { meta: b, items: [] };
    byDoc[k].items.push(b);
  }
  const refs = Object.values(byDoc);

  const renderRefLabel = (b) => {
    if (citationFormat === "ieee") {
      return `${b.document_title || "Untitled"}`;
    }
    const parts = [];
    if (b.authors) parts.push(b.authors);
    if (b.year) parts.push(b.year);
    return `${b.document_title || "Untitled"}${parts.length ? ` — ${parts.join(", ")}` : ""}`;
  };

  return (
    <section
      data-testid="workspace-reference-manager"
      className="rounded-xl border border-[color:var(--jm-border)] bg-[color:var(--jm-surface)] p-4"
    >
      <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.22em] font-semibold text-[color:var(--jm-text-3)] mb-3">
        <BookMarked className="w-3.5 h-3.5" /> Daftar Pustaka Aktif
      </div>
      <div className="mb-3">
        <label className="text-[10px] uppercase tracking-[0.18em] font-semibold text-[color:var(--jm-text-3)] block mb-1">
          Format Sitasi
        </label>
        <Select value={citationFormat} onValueChange={onChangeFormat}>
          <SelectTrigger
            data-testid="workspace-cf-select"
            className="h-8 text-xs bg-[color:var(--jm-surface)] border-[color:var(--jm-border)] text-[color:var(--jm-text)]"
          >
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {CITATION_FORMATS.map((f) => (
              <SelectItem key={f.id} value={f.id}>
                {f.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {formatChangedWarning && (
          <div
            data-testid="workspace-cf-warning"
            className="mt-2 flex items-start gap-1.5 text-[11px] font-ui text-amber-700 dark:text-amber-400 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-md p-2"
          >
            <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
            <span>Format diubah. Generate ulang sub-bab untuk menerapkan format baru.</span>
          </div>
        )}
      </div>
      {refs.length === 0 ? (
        <div className="text-xs text-[color:var(--jm-text-3)] font-ui italic">
          Belum ada referensi yang digunakan.
        </div>
      ) : (
        <ul data-testid="workspace-ref-list" className="space-y-2">
          {refs.map((r) => (
            <li
              key={r.meta.document_id}
              className="rounded-md border border-[color:var(--jm-border)] p-2.5"
            >
              <div className="font-ui text-xs font-semibold text-[color:var(--jm-text)] truncate">
                {renderRefLabel(r.meta)}
              </div>
              <div className="mt-1 flex flex-wrap gap-1.5">
                {r.items.map((b) => (
                  <button
                    key={b.badge_id}
                    data-testid={`ref-badge-${b.badge_id}`}
                    onClick={() => onSelectBadge(b)}
                    className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold font-ui transition-colors ${
                      activeBadgeId === b.badge_id
                        ? "bg-[color:var(--jm-text)] text-[color:var(--jm-bg)]"
                        : "bg-[color:var(--jm-sidebar)] text-[color:var(--jm-text-2)] hover:bg-[color:var(--jm-reading)]"
                    }`}
                    title={b.quote || ""}
                  >
                    {b.label}
                  </button>
                ))}
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
