import { useEffect, useState } from "react";
import { Grid3x3, Loader2, Quote, RefreshCw, FileDown, FileText, PenLine } from "lucide-react";
import { api } from "@/services/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import InsertToWorkspaceDialog from "@/components/Workspace/InsertToWorkspaceDialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useSettings } from "@/store/settings";
import { useT } from "@/lib/useT";
import { matrixToMarkdown, matrixToCsv, download } from "@/lib/exportMatrix";

// Translate field ids to localized labels. Falls back to id.
const FIELD_I18N = {
  objective: { id: "Tujuan", en: "Objective" },
  method: { id: "Metode", en: "Method" },
  sample: { id: "Sampel", en: "Sample" },
  key_finding: { id: "Temuan Utama", en: "Key finding" },
  limitation: { id: "Keterbatasan", en: "Limitation" },
  what_is_known: { id: "Yang Sudah Diketahui", en: "What is known" },
  gap_identified: { id: "Kesenjangan", en: "Gap identified" },
  why_unresolved: { id: "Mengapa Belum Terpecahkan", en: "Why unresolved" },
  opportunity: { id: "Peluang", en: "Opportunity" },
  study_design: { id: "Desain Studi", en: "Study design" },
  sampling: { id: "Sampling", en: "Sampling" },
  data_collection: { id: "Pengumpulan Data", en: "Data collection" },
  analysis_technique: { id: "Teknik Analisis", en: "Analysis technique" },
  validity: { id: "Validitas", en: "Validity" },
  features_supported: { id: "Fitur yang Didukung", en: "Features supported" },
  dataset: { id: "Dataset", en: "Dataset" },
  evaluation_metric: { id: "Metrik Evaluasi", en: "Evaluation metric" },
  performance: { id: "Performa", en: "Performance" },
  hypothesis: { id: "Hipotesis", en: "Hypothesis" },
  conditions: { id: "Kondisi", en: "Conditions" },
  controls: { id: "Kontrol", en: "Controls" },
  results: { id: "Hasil", en: "Results" },
  statistical_test: { id: "Uji Statistik", en: "Statistical test" },
};

export default function MatrixView({ projectId, docs }) {
  const ready = (docs || []).filter((d) => d.status === "ready");
  const { settings } = useSettings();
  const { t, lang } = useT();
  const [method, setMethod] = useState("default");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [activeCell, setActiveCell] = useState(null);
  const [insertDialog, setInsertDialog] = useState({ open: false, payload: null });

  const methods = settings?.matrix_methods || [
    { id: "default", label: "Default" },
    { id: "gap_analysis", label: "Gap Analysis Matrix" },
    { id: "method_comparison", label: "Method Comparison Matrix" },
    { id: "feature_comparison", label: "Feature Comparison Matrix" },
    { id: "experimental_comparison", label: "Experimental Comparison" },
  ];

  useEffect(() => {
    // changing method clears the visible table; user has to click to build
    setData(null);
    setActiveCell(null);
  }, [method]);

  const generate = async (refresh = false) => {
    setLoading(true);
    setActiveCell(null);
    try {
      const r = await api.matrix(projectId, null, refresh, method);
      setData(r);
      if (refresh) toast.success(t("matrix.refresh"));
    } catch (e) {
      const detail = e?.response?.data?.detail;
      toast.error(detail || "Matrix failed");
    } finally {
      setLoading(false);
    }
  };

  const labelMap = Object.fromEntries(Object.entries(FIELD_I18N).map(([k, v]) => [k, v[lang] || v.id]));
  const fieldLabel = (f) => labelMap[f] || f;
  const methodLabel = methods.find((m) => m.id === method)?.label || method;

  const onExportMd = () => {
    if (!data) return;
    download(`matriks-${method}-${Date.now()}.md`, matrixToMarkdown(data, labelMap, methodLabel), "text/markdown");
  };
  const onExportCsv = () => {
    if (!data) return;
    const suffixes = { excerpt: t("matrix.csv.excerpt"), page: t("matrix.csv.page") };
    download(`matriks-${method}-${Date.now()}.csv`, matrixToCsv(data, labelMap, suffixes), "text/csv");
  };

  return (
    <section
      data-testid="matrix-section"
      className="rounded-xl bg-[color:var(--jm-surface)] border border-[color:var(--jm-border)] p-5"
    >
      <div className="flex flex-wrap items-center gap-3 mb-4">
        <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.22em] font-semibold text-[color:var(--jm-text-3)]">
          <Grid3x3 className="w-3.5 h-3.5" /> {t("matrix.title")}
        </div>
        <div className="flex items-center gap-2 ml-auto">
          <div className="text-[10px] uppercase tracking-[0.2em] font-semibold text-[color:var(--jm-text-3)]">
            {t("matrix.method")}
          </div>
          <Select value={method} onValueChange={setMethod}>
            <SelectTrigger
              data-testid="matrix-method-select"
              className="h-9 text-xs bg-[color:var(--jm-surface)] border-[color:var(--jm-border)] text-[color:var(--jm-text)] min-w-[230px]"
            >
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {methods.map((m) => (
                <SelectItem key={m.id} data-testid={`matrix-method-option-${m.id}`} value={m.id}>
                  {m.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button
            data-testid="matrix-generate"
            onClick={() => generate(false)}
            disabled={loading || ready.length === 0}
            className="bg-[color:var(--jm-text)] text-[color:var(--jm-bg)] hover:opacity-90 gap-2"
          >
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Grid3x3 className="w-4 h-4" />}
            {data ? t("matrix.again") : t("matrix.generate")}
          </Button>
          {data && (
            <Button
              data-testid="matrix-refresh"
              onClick={() => generate(true)}
              disabled={loading}
              variant="outline"
              className="border-[color:var(--jm-border)] gap-2"
              title={t("matrix.refresh")}
            >
              <RefreshCw className="w-4 h-4" /> {t("matrix.refresh")}
            </Button>
          )}
        </div>
      </div>

      {!data ? (
        <div className="text-sm text-[color:var(--jm-text-3)] font-ui">
          {ready.length === 0 ? t("matrix.empty.noDocs") : `Tersedia ${ready.length} jurnal siap dibandingkan dengan metode "${methodLabel}". Klik tombol untuk menyusun matriks.`}
        </div>
      ) : (
        <>
          <div className="flex flex-wrap items-center gap-2 mb-3">
            <Button
              data-testid="matrix-export-md"
              variant="outline"
              size="sm"
              onClick={onExportMd}
              className="gap-2 border-[color:var(--jm-border)] text-[color:var(--jm-text-2)] hover:bg-[color:var(--jm-sidebar)]"
            >
              <FileText className="w-3.5 h-3.5" /> {t("matrix.exportMd")}
            </Button>
            <Button
              data-testid="matrix-export-csv"
              variant="outline"
              size="sm"
              onClick={onExportCsv}
              className="gap-2 border-[color:var(--jm-border)] text-[color:var(--jm-text-2)] hover:bg-[color:var(--jm-sidebar)]"
            >
              <FileDown className="w-3.5 h-3.5" /> {t("matrix.exportCsv")}
            </Button>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
            <div className="lg:col-span-8 overflow-x-auto border border-[color:var(--jm-border)] rounded-lg">
              <table data-testid="matrix-table" className="w-full text-sm border-collapse">
                <thead>
                  <tr className="bg-[color:var(--jm-sidebar)]">
                    <th className="text-left p-3 text-[10px] uppercase tracking-[0.18em] font-semibold text-[color:var(--jm-text-3)] sticky left-0 bg-[color:var(--jm-sidebar)] z-10 border-b border-r border-[color:var(--jm-border)]">
                      {t("matrix.col.journal")}
                    </th>
                    {data.fields.map((f) => (
                      <th
                        key={f}
                        className="text-left p-3 text-[10px] uppercase tracking-[0.18em] font-semibold text-[color:var(--jm-text-3)] border-b border-r border-[color:var(--jm-border)] min-w-[180px]"
                      >
                        {fieldLabel(f)}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {data.rows.map((row, ri) => (
                    <tr key={row.document_id} className="hover:bg-[color:var(--jm-reading)]">
                      <td
                        data-testid={`matrix-row-title-${ri}`}
                        className="p-3 align-top font-display font-semibold text-[color:var(--jm-text)] text-[13px] sticky left-0 bg-[color:var(--jm-surface)] z-10 border-b border-r border-[color:var(--jm-border)]"
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
                <Quote className="w-3.5 h-3.5" /> {t("matrix.quote")}
              </div>
              {activeCell ? (
                <div>
                  <div className="text-[10px] uppercase tracking-[0.18em] font-semibold text-[color:var(--jm-text-3)] mb-1">
                    {fieldLabel(activeCell.field)}
                  </div>
                  <div className="font-display text-base font-semibold text-[color:var(--jm-text)] mb-2 leading-tight">
                    {activeCell.title}
                  </div>
                  <div className="text-sm text-[color:var(--jm-text)] mb-2 font-ui">
                    {activeCell.value}
                  </div>
                  <blockquote className="border-l-2 border-[color:var(--jm-text)] pl-3 font-reading text-[14px] leading-relaxed text-[color:var(--jm-text-2)]">
                    &ldquo;{activeCell.excerpt}&rdquo;
                  </blockquote>
                  {activeCell.page ? (
                    <div className="mt-2 text-[10px] uppercase tracking-[0.18em] font-semibold text-[color:var(--jm-text-3)]">
                      Hal. {activeCell.page}
                    </div>
                  ) : null}
                  <button
                    data-testid="matrix-insert-ws"
                    onClick={() => {
                      const row = data.rows[activeCell.rowIdx];
                      setInsertDialog({
                        open: true,
                        payload: {
                          document_id: row?.document_id,
                          sentence_id: "",
                          quote: activeCell.excerpt || activeCell.value,
                          page: activeCell.page,
                        },
                      });
                    }}
                    className="mt-3 inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-[11px] font-semibold font-ui bg-[color:var(--jm-text)] text-[color:var(--jm-bg)] hover:opacity-90"
                  >
                    <PenLine className="w-3 h-3" /> Sisipkan ke Workspace
                  </button>
                </div>
              ) : (
                <div className="text-sm text-[color:var(--jm-text-3)] font-ui italic">
                  {t("matrix.quote.hint")}
                </div>
              )}
            </aside>
          </div>
        </>
      )}
      <InsertToWorkspaceDialog
        open={insertDialog.open}
        onOpenChange={(o) => setInsertDialog((s) => ({ ...s, open: o }))}
        projectId={projectId}
        payload={insertDialog.payload}
      />
    </section>
  );
}
