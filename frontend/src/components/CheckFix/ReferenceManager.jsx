import { BookMarked } from "lucide-react";

export default function ReferenceManager({ badges, onSelectBadge, activeBadgeId }) {
  const byDoc = {};
  for (const b of badges || []) {
    const k = b.document_id || "unknown";
    if (!byDoc[k]) byDoc[k] = { meta: b, items: [] };
    byDoc[k].items.push(b);
  }
  const refs = Object.values(byDoc);

  return (
    <section
      data-testid="checkfix-reference-manager"
      className="rounded-xl border border-[color:var(--jm-border)] bg-[color:var(--jm-surface)] p-4"
    >
      <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.22em] font-semibold text-[color:var(--jm-text-3)] mb-3">
        <BookMarked className="w-3.5 h-3.5" /> Daftar Pustaka Aktif
      </div>
      {refs.length === 0 ? (
        <div className="text-xs text-[color:var(--jm-text-3)] font-ui italic">
          Belum ada referensi. Jalankan “Periksa Sekarang” untuk mengaitkan klaim ke paper.
        </div>
      ) : (
        <ul data-testid="checkfix-ref-list" className="space-y-2">
          {refs.map((r) => (
            <li
              key={r.meta.document_id}
              className="rounded-md border border-[color:var(--jm-border)] p-2.5"
            >
              <div className="font-ui text-xs font-semibold text-[color:var(--jm-text)]">
                {r.meta.document_title}
                {r.meta.year ? <span className="text-[color:var(--jm-text-3)] font-normal"> · {r.meta.year}</span> : null}
              </div>
              <div className="mt-1 flex flex-wrap gap-1.5">
                {r.items.map((b) => (
                  <button
                    key={b.badge_id}
                    data-testid={`checkfix-ref-badge-${b.badge_id}`}
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
