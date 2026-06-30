import { ChevronRight, Settings2 } from "lucide-react";

export default function OutlineSidebar({ outline, activeSubId, onSelect, onEditOutline }) {
  if (!outline) return null;
  return (
    <aside
      data-testid="workspace-outline-sidebar"
      className="rounded-xl border border-[color:var(--jm-border)] bg-[color:var(--jm-surface)] p-4 h-fit sticky top-4"
    >
      <div className="flex items-start justify-between gap-2 mb-3">
        <div className="min-w-0">
          <div className="text-[10px] uppercase tracking-[0.22em] font-semibold text-[color:var(--jm-text-3)]">
            Outline
          </div>
          <div
            data-testid="workspace-paper-title"
            className="font-display text-sm font-semibold text-[color:var(--jm-text)] truncate mt-0.5"
            title={outline.title}
          >
            {outline.title || "Untitled"}
          </div>
        </div>
        <button
          data-testid="workspace-edit-outline"
          onClick={onEditOutline}
          className="p-1.5 rounded hover:bg-[color:var(--jm-sidebar)] shrink-0"
          title="Ubah outline"
        >
          <Settings2 className="w-3.5 h-3.5 text-[color:var(--jm-text-3)]" />
        </button>
      </div>
      <ul className="space-y-2.5">
        {(outline.chapters || []).map((ch) => (
          <li key={ch.id}>
            <div className="text-[11px] uppercase tracking-[0.18em] font-semibold text-[color:var(--jm-text-2)] mb-1.5">
              {ch.title}
            </div>
            <ul className="space-y-0.5">
              {(ch.subchapters || []).map((sc) => {
                const active = sc.id === activeSubId;
                return (
                  <li key={sc.id}>
                    <button
                      data-testid={`workspace-sub-${sc.id}`}
                      onClick={() => onSelect(sc.id)}
                      className={`w-full text-left px-2.5 py-1.5 rounded-md text-xs font-ui flex items-center gap-1.5 transition-colors ${
                        active
                          ? "bg-[color:var(--jm-text)] text-[color:var(--jm-bg)] font-semibold"
                          : "text-[color:var(--jm-text)] hover:bg-[color:var(--jm-sidebar)]"
                      }`}
                    >
                      <ChevronRight className={`w-3 h-3 shrink-0 ${active ? "" : "opacity-50"}`} />
                      <span className="truncate">{sc.title}</span>
                    </button>
                  </li>
                );
              })}
            </ul>
          </li>
        ))}
      </ul>
    </aside>
  );
}
