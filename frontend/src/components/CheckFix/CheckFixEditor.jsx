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
      className="rounded-xl border-2 border-[var(--jm-border-2)] bg-[var(--jm-surface)] p-5"
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
            className="w-full px-3 py-2 rounded-md border-2 border-[var(--jm-border-2)] focus:border-[var(--jm-text)] focus:outline-none font-reading text-[15px] leading-relaxed bg-[var(--jm-surface)] text-[color:var(--jm-text)] resize-y"
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
              className="w-full px-3 py-2 rounded-md border-2 border-[var(--jm-border-2)] focus:border-[var(--jm-text)] focus:outline-none font-ui text-xs leading-relaxed bg-[var(--jm-surface)] text-[color:var(--jm-text)] resize-y"
            />
          </div>
          <aside className="lg:col-span-5 rounded-md bg-[color:var(--jm-reading)] border-2 border-[var(--jm-border-2)] p-3 text-[11px] font-ui leading-relaxed text-[color:var(--jm-text-2)]">
            <div className="text-[10px] uppercase tracking-[0.2em] font-semibold text-[color:var(--jm-text-3)] mb-1">
              Tips
            </div>
            <p>
              Gunakan prompt ini di AI Anda:
              <span className="block mt-1 italic">
                "Berikan daftar pustaka dari semua referensi yang Anda gunakan dalam format APA atau IEEE. Bungkus dalam satu blok teks."
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
            className="px-4 py-2 rounded-md text-sm font-ui font-semibold flex items-center gap-2 bg-[var(--jm-focus)] text-white hover:opacity-90 disabled:opacity-50"
          >
            {running ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
            Periksa Sekarang
          </button>
          {result && (
            <>
              <button
                data-testid="checkfix-clear-btn"
                onClick={onClear}
                className="px-3 py-2 rounded-md text-xs font-ui font-semibold flex items-center gap-1.5 border-2 border-[var(--jm-border-2)] hover:bg-[color:var(--jm-sidebar)]"
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

      {/* ======================================================
          Result area — clean stats banner + highlighted text
         ====================================================== */}
      {result && (
        <div data-testid="checkfix-result" className="mt-6 pt-5 border-t border-[color:var(--jm-border)] space-y-5">

          {/* ── Stats banner ── */}
          <div
            data-testid="checkfix-summary"
            className="rounded-xl border border-[color:var(--jm-border)] bg-[color:var(--jm-sidebar)] px-5 py-4"
          >
            <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.22em] font-semibold text-[color:var(--jm-text-3)] mb-4">
              <ListChecks className="w-3.5 h-3.5" />
              Hasil Verifikasi
            </div>
            <div className="grid grid-cols-3 divide-x divide-[color:var(--jm-border)]">
              <StatBig
                icon={CircleCheck}
                colorClass="text-emerald-600 dark:text-emerald-400"
                bgClass="bg-emerald-50 dark:bg-emerald-900/20"
                label="Didukung"
                value={result.summary.supported}
                testId="checkfix-stat-supported"
              />
              <StatBig
                icon={CircleAlert}
                colorClass="text-amber-600 dark:text-amber-400"
                bgClass="bg-amber-50 dark:bg-amber-900/20"
                label="Mirip"
                value={result.summary.similar}
                testId="checkfix-stat-similar"
              />
              <StatBig
                icon={CircleX}
                colorClass="text-rose-600 dark:text-rose-400"
                bgClass="bg-rose-50 dark:bg-rose-900/20"
                label="Tidak Didukung"
                value={result.summary.unsupported}
                testId="checkfix-stat-unsupported"
              />
            </div>
            <div className="mt-3 text-[11px] text-[color:var(--jm-text-3)] font-ui text-right">
              Total {result.summary.total} unit diperiksa
            </div>
          </div>

          {/* ── Legend ── */}
          <div className="flex flex-wrap items-center gap-4 text-[11px] font-ui text-[color:var(--jm-text-3)]">
            <span className="flex items-center gap-1.5">
              <span className="inline-block w-3 h-3 rounded-sm bg-emerald-500/20 border-l-2 border-emerald-500" />
              Didukung — bukti kuat di paper
            </span>
            <span className="flex items-center gap-1.5">
              <span className="inline-block w-3 h-3 rounded-sm bg-amber-400/20 border-l-2 border-amber-400" />
              Mirip — ada kecocokan parsial
            </span>
            <span className="flex items-center gap-1.5">
              <span className="inline-block w-3 h-3 rounded-sm bg-rose-500/20 border-l-2 border-rose-500" />
              Tidak Didukung — tidak ditemukan
            </span>
          </div>

          {/* ── Annotated text ── */}
          <div
            ref={annotatedRef}
            data-testid="checkfix-annotated"
            className="cf-units rounded-xl border border-[color:var(--jm-border)] bg-[color:var(--jm-surface)] p-5 leading-relaxed"
            dangerouslySetInnerHTML={{ __html: result.annotated_html }}
          />

          {/* ── Suggestions for unsupported units ── */}
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
                      "{u.text.slice(0, 140)}{u.text.length > 140 ? "…" : ""}"
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

/* ── Stat tile — big number version ── */
function StatBig({ icon: Icon, colorClass, bgClass, label, value, testId }) {
  return (
    <div data-testid={testId} className="flex flex-col items-center gap-1 px-4 py-1 first:rounded-l-lg last:rounded-r-lg">
      <div className={`w-9 h-9 rounded-full flex items-center justify-center mb-1 ${bgClass}`}>
        <Icon className={`w-5 h-5 ${colorClass}`} />
      </div>
      <span className={`text-3xl font-bold font-display tracking-tight ${colorClass}`}>{value}</span>
      <span className="text-[10px] uppercase tracking-[0.18em] font-semibold text-[color:var(--jm-text-3)] text-center leading-tight">
        {label}
      </span>
    </div>
  );
}
