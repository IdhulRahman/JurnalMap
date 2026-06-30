import { useState } from "react";
import { Grid3x3, Loader2, Quote, RefreshCw } from "lucide-react";
import { api } from "@/services/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { FIELD_LABEL } from "@/lib/tiers";

export default function MatrixView({ projectId, docs }) {
  const ready = (docs || []).filter((d) => d.status === "ready");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [activeCell, setActiveCell] = useState(null); // {rowIdx, field, excerpt, page}

  const generate = async (refresh = false) => {
    setLoading(true);
    setActiveCell(null);
    try {
      const r = await api.matrix(projectId, null, refresh);
      setData(r);
      if (refresh) toast.success("Matriks diperbarui dari LLM");
    } catch {
      toast.error("Gagal menyusun matriks");
    } finally {
      setLoading(false);
    }
  };

  return (
    <section
      data-testid="matrix-section"
      className="rounded-xl bg-white border border-[color:var(--jm-border)] p-5"
    >
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.22em] font-semibold text-[color:var(--jm-text-3)]">
          <Grid3x3 className="w-3.5 h-3.5" /> Matriks Perbandingan
        </div>
        <Button
          data-testid="matrix-generate"
          onClick={() => generate(false)}
          disabled={loading || ready.length === 0}
          className="bg-[color:var(--jm-text)] text-white hover:bg-[#343a40] gap-2"
        >
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Grid3x3 className="w-4 h-4" />}
          {data ? "Tampilkan lagi" : "Susun matriks"}
        </Button>
        {data && (
          <Button
            data-testid="matrix-refresh"
            onClick={() => generate(true)}
            disabled={loading}
            variant="outline"
            className="border-[color:var(--jm-border)] gap-2 ml-2"
            title="Hitung ulang dengan LLM (abaikan cache)"
          >
            <RefreshCw className="w-4 h-4" /> Hitung ulang
          </Button>
        )}
      </div>

      {!data ? (
        <div className="text-sm text-[color:var(--jm-text-3)] font-ui">
          {ready.length === 0
            ? "Belum ada jurnal yang siap. Unggah dan tunggu sampai status “Siap”."
            : `Tersedia ${ready.length} jurnal siap dibandingkan. Klik "Susun matriks" untuk membuat tabel struktur. Ini bukan penilaian kualitas, hanya pemetaan dimensi.`}
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
          <div className="lg:col-span-8 overflow-x-auto border border-[color:var(--jm-border)] rounded-lg">
            <table data-testid="matrix-table" className="w-full text-sm border-collapse">
              <thead>
                <tr className="bg-[color:var(--jm-sidebar)]">
                  <th className="text-left p-3 text-[10px] uppercase tracking-[0.18em] font-semibold text-[color:var(--jm-text-3)] sticky left-0 bg-[color:var(--jm-sidebar)] z-10 border-b border-r border-[color:var(--jm-border)]">
                    Jurnal
                  </th>
                  {data.fields.map((f) => (
                    <th
                      key={f}
                      className="text-left p-3 text-[10px] uppercase tracking-[0.18em] font-semibold text-[color:var(--jm-text-3)] border-b border-r border-[color:var(--jm-border)] min-w-[180px]"
                    >
                      {FIELD_LABEL[f] || f}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.rows.map((row, ri) => (
                  <tr key={row.document_id} className="hover:bg-[color:var(--jm-reading)]">
                    <td
                      data-testid={`matrix-row-title-${ri}`}
                      className="p-3 align-top font-display font-semibold text-[color:var(--jm-text)] text-[13px] sticky left-0 bg-white z-10 border-b border-r border-[color:var(--jm-border)]"
                    >
                      {row.title}
                    </td>
                    {data.fields.map((f) => {
                      const cell = row.cells.find((c) => c.field === f);
                      const value = cell?.value || "—";
                      const hasExcerpt = !!cell?.excerpt;
                      return (
                        <td
                          key={f}
                          data-testid={`matrix-cell-${ri}-${f}`}
                          className={`p-3 align-top border-b border-r border-[color:var(--jm-border)] font-ui text-[13px] text-[color:var(--jm-text-2)] ${hasExcerpt ? "cursor-pointer hover:bg-[color:var(--jm-sidebar)]" : ""}`}
                          onClick={() => hasExcerpt && setActiveCell({ rowIdx: ri, field: f, excerpt: cell.excerpt, page: cell.page, title: row.title, value })}
                        >
                          {value}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <aside
            data-testid="matrix-quote-sidebar"
            className="lg:col-span-4 rounded-lg bg-[color:var(--jm-reading)] border border-[color:var(--jm-border)] p-4"
          >
            <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.22em] font-semibold text-[color:var(--jm-text-3)] mb-3">
              <Quote className="w-3.5 h-3.5" /> Kutipan Sumber
            </div>
            {activeCell ? (
              <div>
                <div className="text-[10px] uppercase tracking-[0.18em] font-semibold text-[color:var(--jm-text-3)] mb-1">
                  {FIELD_LABEL[activeCell.field] || activeCell.field}
                </div>
                <div className="font-display text-base font-semibold text-[color:var(--jm-text)] mb-2 leading-tight">
                  {activeCell.title}
                </div>
                <div className="text-sm text-[color:var(--jm-text)] mb-2 font-ui">
                  Nilai: <span className="font-semibold">{activeCell.value}</span>
                </div>
                <blockquote className="border-l-2 border-[color:var(--jm-text)] pl-3 font-reading text-[14px] leading-relaxed text-[color:var(--jm-text-2)]">
                  &ldquo;{activeCell.excerpt}&rdquo;
                </blockquote>
                {activeCell.page ? (
                  <div className="mt-2 text-[10px] uppercase tracking-[0.18em] font-semibold text-[color:var(--jm-text-3)]">
                    Hal. {activeCell.page}
                  </div>
                ) : null}
              </div>
            ) : (
              <div className="text-sm text-[color:var(--jm-text-3)] font-ui italic">
                Klik sel di tabel untuk melihat kutipan sumbernya. Matriks menampilkan dimensi, bukan keputusan tentang kualitas.
              </div>
            )}
          </aside>
        </div>
      )}
    </section>
  );
}
