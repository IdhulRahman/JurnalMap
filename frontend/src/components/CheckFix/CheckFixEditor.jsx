import { useEffect, useRef } from "react";
import {
  Sparkles,
  Loader2,
  Download,
  ListChecks,
  CircleCheck,
  CircleAlert,
  CircleX,
  Eraser,
} from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
} from "@/components/ui/dropdown-menu";

export default function CheckFixEditor({
  text,
  setText,
  bibliography,
  setBibliography,
  running,
  result,
  onRun,
  onClear,
  onBadgeClick,
  onExportMarkdown,
  onExportText,
}) {
  const annotatedRef = useRef(null);

  // Wire up clicks on inline citation badges within the annotated result
  useEffect(() => {
    const node = annotatedRef.current;
    if (!node) return;
    const handler = (e) => {
      const t = e.target;
      if (t && t.classList && t.classList.contains("jm-citation-badge")) {
        const badgeId = t.getAttribute("data-badge-id");
        if (!badgeId) return;
        const badge = (result?.badges || []).find((b) => b.badge_id === badgeId);
        if (badge) onBadgeClick?.(badge);
      }
    };
    node.addEventListener("click", handler);
    return () => node.removeEventListener("click", handler);
  }, [result, onBadgeClick]);

  const wordCount = (text || "").trim().split(/\s+/).filter(Boolean).length;

  return (
    <section
      data-testid="checkfix-editor"
      className="rounded-xl border border-[color:var(--jm-border)] bg-[color:var(--jm-surface)] p-5"
    >
      {/* Input area */}
      <div className="space-y-3">
        <div>
          <label className="text-[10px] uppercase tracking-[0.22em] font-semibold text-[color:var(--jm-text-3)] mb-1 block">
            Tempelkan teks dari AI lain (ChatGPT / Claude / Gemini / dll.)
          </label>
          <textarea
            data-testid="checkfix-input-text"
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={10}
            placeholder="Tempelkan paragraf atau draf hasil AI di sini... Setiap unit (paragraf / item daftar) akan diverifikasi terhadap koleksi paper Anda."
            className="w-full px-3 py-2 rounded-md border border-[color:var(--jm-border)] focus:border-[color:var(--jm-text)] focus:outline-none font-reading text-[15px] leading-relaxed bg-[color:var(--jm-surface)] text-[color:var(--jm-text)] resize-y"
          />
          <div className="mt-1 text-[10px] uppercase tracking-[0.16em] font-semibold font-ui text-[color:var(--jm-text-3)]">
            {wordCount} kata
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-3">
          <div className="lg:col-span-7">
            <label className="text-[10px] uppercase tracking-[0.22em] font-semibold text-[color:var(--jm-text-3)] mb-1 block">
              Daftar Pustaka dari AI (opsional)
            </label>
            <textarea
              data-testid="checkfix-input-bibliography"
              value={bibliography}
              onChange={(e) => setBibliography(e.target.value)}
              rows={5}
              placeholder="Tempel daftar pustaka dari ChatGPT/Claude/Gemini di sini..."
              className="w-full px-3 py-2 rounded-md border border-[color:var(--jm-border)] focus:border-[color:var(--jm-text)] focus:outline-none font-ui text-xs leading-relaxed bg-[color:var(--jm-surface)] text-[color:var(--jm-text)] resize-y"
            />
          </div>
          <aside className="lg:col-span-5 rounded-md bg-[color:var(--jm-reading)] border border-[color:var(--jm-border)] p-3 text-[11px] font-ui leading-relaxed text-[color:var(--jm-text-2)]">
            <div className="text-[10px] uppercase tracking-[0.2em] font-semibold text-[color:var(--jm-text-3)] mb-1">
              Tips
            </div>
            <p>
              Gunakan prompt ini di AI Anda:
              <span className="block mt-1 italic">
                “Berikan daftar pustaka dari semua referensi yang Anda gunakan dalam format APA atau IEEE. Bungkus dalam satu blok teks.”
              </span>
            </p>
            <p className="mt-2">Lalu salin hasilnya ke kolom Daftar Pustaka. Daftar ini meningkatkan kepercayaan saat mencari sumber.</p>
          </aside>
        </div>

        <div className="flex items-center gap-2 pt-1">
          <button
            data-testid="checkfix-run-btn"
            onClick={onRun}
            disabled={running || !text.trim()}
            className="px-4 py-2 rounded-md text-sm font-ui font-semibold flex items-center gap-2 bg-[color:var(--jm-text)] text-[color:var(--jm-bg)] hover:opacity-90 disabled:opacity-50"
          >
            {running ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
            Periksa Sekarang
          </button>
          {result && (
            <>
              <button
                data-testid="checkfix-clear-btn"
                onClick={onClear}
                className="px-3 py-2 rounded-md text-xs font-ui font-semibold flex items-center gap-1.5 border border-[color:var(--jm-border)] hover:bg-[color:var(--jm-sidebar)]"
              >
                <Eraser className="w-3.5 h-3.5" /> Bersihkan
              </button>
              <span className="ml-auto" />
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <button
                    data-testid="checkfix-export-btn"
                    className="px-3 py-2 rounded-md text-xs font-ui font-semibold flex items-center gap-1.5 border border-[color:var(--jm-border)] hover:bg-[color:var(--jm-sidebar)]"
                  >
                    <Download className="w-3.5 h-3.5" /> Ekspor
                  </button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuItem data-testid="checkfix-export-md" onClick={onExportMarkdown}>
                    Markdown (.md)
                  </DropdownMenuItem>
                  <DropdownMenuItem data-testid="checkfix-export-txt" onClick={onExportText}>
                    Plain Text (.txt)
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </>
          )}
        </div>
      </div>

      {/* Summary + annotated result */}
      {result && (
        <div data-testid="checkfix-result" className="mt-6 pt-5 border-t border-[color:var(--jm-border)] space-y-4">
          <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.22em] font-semibold text-[color:var(--jm-text-3)]">
            <ListChecks className="w-3.5 h-3.5" /> Hasil Verifikasi
          </div>
          <div data-testid="checkfix-summary" className="flex flex-wrap gap-2 text-xs font-ui">
            <Stat icon={CircleCheck} colorClass="text-emerald-600" label="Didukung" value={result.summary.supported} />
            <Stat icon={CircleAlert} colorClass="text-amber-600" label="Mirip" value={result.summary.similar} />
            <Stat icon={CircleX} colorClass="text-rose-600" label="Tidak Didukung" value={result.summary.unsupported} />
            <div className="ml-auto self-center text-[11px] text-[color:var(--jm-text-3)]">
              Total: {result.summary.total} unit
            </div>
          </div>

          <div
            ref={annotatedRef}
            data-testid="checkfix-annotated"
            className="rounded-lg border border-[color:var(--jm-border)] bg-[color:var(--jm-surface)] p-4"
            dangerouslySetInnerHTML={{ __html: result.annotated_html }}
          />

          {/* Suggestions for unsupported units */}
          {result.units.some((u) => u.status === "unsupported" && (u.suggestions || []).length > 0) && (
            <div data-testid="checkfix-suggestions" className="space-y-2">
              <div className="text-[10px] uppercase tracking-[0.22em] font-semibold text-[color:var(--jm-text-3)]">
                Saran perbaikan untuk unit yang tidak didukung
              </div>
              {result.units
                .filter((u) => u.status === "unsupported" && (u.suggestions || []).length > 0)
                .map((u) => (
                  <div
                    key={u.unit_id}
                    data-testid={`checkfix-suggestion-${u.unit_id}`}
                    className="rounded-md border border-[color:var(--jm-border)] bg-[color:var(--jm-reading)] p-3"
                  >
                    <div className="text-xs font-ui italic text-[color:var(--jm-text-2)] mb-1">
                      “{u.text.slice(0, 140)}{u.text.length > 140 ? "…" : ""}”
                    </div>
                    <div className="text-[11px] text-[color:var(--jm-text-3)] font-ui mb-2">
                      Apakah maksud Anda merujuk ke salah satu sumber berikut?
                    </div>
                    <ul className="space-y-1.5">
                      {u.suggestions.map((s, si) => (
                        <li key={si} className="text-[12px] text-[color:var(--jm-text)] font-ui">
                          <strong>{s.document_title}</strong>
                          {s.page ? <span className="text-[color:var(--jm-text-3)]"> · hal. {s.page}</span> : null}
                          <div className="text-[12px] text-[color:var(--jm-text-2)] font-reading italic mt-0.5">
                            &ldquo;{s.quote}&rdquo;
                          </div>
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
            </div>
          )}
        </div>
      )}
    </section>
  );
}

function Stat({ icon: Icon, colorClass, label, value }) {
  return (
    <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-[color:var(--jm-sidebar)]">
      <Icon className={`w-3.5 h-3.5 ${colorClass}`} />
      <span className="font-semibold text-[color:var(--jm-text)]">{value}</span>
      <span className="text-[10px] uppercase tracking-[0.18em] font-semibold text-[color:var(--jm-text-3)]">
        {label}
      </span>
    </div>
  );
}
