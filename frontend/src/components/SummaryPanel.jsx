import { useEffect, useState } from "react";
import { api } from "@/services/api";
import { toast } from "sonner";
import {
  Loader2,
  ChevronRight,
  BookOpenCheck,
  Quote,
  RefreshCw,
  Cpu,
} from "lucide-react";
import EvidenceBadge from "@/components/EvidenceBadge";
import { CATEGORY_LABEL, TIER_META } from "@/lib/tiers";
import { useSettings } from "@/store/settings";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";


const SECTION_LABEL = {
  abstract: "Abstrak",
  objective: "Tujuan",
  method: "Metode",
  results: "Hasil",
  conclusion: "Kesimpulan",
};
const SECTION_ORDER = ["abstract", "objective", "method", "results", "conclusion"];


export default function SummaryPanel({ docId, summary, claims, sections, modelUsed, onHighlight, onResummarized }) {
  const { settings } = useSettings();
  const [activeKey, setActiveKey] = useState(null); // "section:abstract" or "claim:<id>"
  const [busyKey, setBusyKey] = useState(null);
  const [evidenceByKey, setEvidenceByKey] = useState({});
  const [selectedModel, setSelectedModel] = useState(modelUsed || settings?.default_model || "");
  const [resummarizing, setResummarizing] = useState(false);

  useEffect(() => {
    if (!selectedModel && settings?.default_model) setSelectedModel(settings.default_model);
    if (modelUsed) setSelectedModel(modelUsed);
  }, [modelUsed, settings?.default_model, selectedModel]);

  const fetchSectionEvidence = async (sectionKey, text) => {
    const key = `section:${sectionKey}`;
    if (activeKey === key) {
      setActiveKey(null);
      onHighlight([], null);
      return;
    }
    setActiveKey(key);
    setBusyKey(key);
    try {
      let payload = evidenceByKey[key];
      if (!payload) {
        payload = await api.evidenceForSection(docId, text);
        setEvidenceByKey((m) => ({ ...m, [key]: payload }));
      }
      const items = payload.items || [];
      onHighlight(items, items[0] ? { page: items[0].page, sentence_id: items[0].sentence_id } : null);
      if (items.length === 0) toast.info("Tidak ditemukan kalimat sumber untuk bagian ini.");
    } catch {
      toast.error("Gagal mengambil bukti");
      setActiveKey(null);
    } finally {
      setBusyKey(null);
    }
  };

  const fetchClaimEvidence = async (claim) => {
    const key = `claim:${claim.id}`;
    if (activeKey === key) {
      setActiveKey(null);
      onHighlight([], null);
      return;
    }
    setActiveKey(key);
    setBusyKey(key);
    try {
      let payload = evidenceByKey[key];
      if (!payload) {
        payload = await api.evidenceForClaim(claim.id);
        setEvidenceByKey((m) => ({ ...m, [key]: payload }));
      }
      const items = payload.items || [];
      onHighlight(items, items[0] ? { page: items[0].page, sentence_id: items[0].sentence_id } : null);
      if (items.length === 0) toast.info("Tidak ditemukan kalimat sumber untuk klaim ini.");
    } catch {
      toast.error("Gagal mengambil bukti");
      setActiveKey(null);
    } finally {
      setBusyKey(null);
    }
  };

  const resummarize = async () => {
    setResummarizing(true);
    try {
      const r = await api.resummarize(docId, selectedModel);
      setEvidenceByKey({}); // claim ids changed
      setActiveKey(null);
      onHighlight([], null);
      toast.success("Ringkasan diperbarui");
      onResummarized?.(r);
    } catch (e) {
      const msg = e?.response?.data?.detail;
      if (e?.response?.status === 502 && msg) {
        toast.error(msg, { duration: 6000 });
      } else {
        toast.error("Gagal meringkas ulang");
      }
    } finally {
      setResummarizing(false);
    }
  };

  const hasSections = sections && SECTION_ORDER.some((k) => (sections[k] || "").trim());

  if (!summary && !hasSections && (!claims || claims.length === 0)) {
    return (
      <div className="p-6 text-sm text-[color:var(--jm-text-3)] font-ui">
        Belum ada ringkasan untuk jurnal ini.
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Model picker + Ringkas Ulang */}
      <section
        data-testid="summary-model-bar"
        className="flex items-center gap-2 pb-4 border-b border-[color:var(--jm-border)]"
      >
        <Cpu className="w-3.5 h-3.5 text-[color:var(--jm-text-3)]" />
        <span className="text-[10px] uppercase tracking-[0.22em] font-semibold text-[color:var(--jm-text-3)]">
          Model
        </span>
        <Select value={selectedModel} onValueChange={setSelectedModel}>
          <SelectTrigger
            data-testid="summary-model-select"
            className="h-8 text-xs bg-[color:var(--jm-surface)] border-[color:var(--jm-border)] text-[color:var(--jm-text)] flex-1 min-w-0"
          >
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {(settings?.available_models || []).map((m) => (
              <SelectItem
                key={`${m.provider}-${m.id}-${m.label}`}
                data-testid={`summary-model-option-${m.id}`}
                value={m.id}
              >
                {m.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <button
          data-testid="resummarize-btn"
          onClick={resummarize}
          disabled={resummarizing}
          className="px-3 py-1.5 rounded-md text-xs font-semibold font-ui flex items-center gap-1.5 bg-[color:var(--jm-text)] text-[color:var(--jm-bg)] hover:opacity-90 disabled:opacity-50"
          title="Ringkas ulang dengan model ini"
        >
          {resummarizing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}
          Ringkas Ulang
        </button>
      </section>

      {/* Overview */}
      <section>
        <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.22em] font-semibold text-[color:var(--jm-text-3)] mb-3">
          <BookOpenCheck className="w-3.5 h-3.5" /> Ringkasan Jurnal Aktif
        </div>
        <p
          data-testid="document-summary"
          className="font-reading text-[15px] leading-relaxed text-[color:var(--jm-text)]"
        >
          {summary || "Ringkasan belum tersedia."}
        </p>
        <div className="mt-3 text-[11px] text-[color:var(--jm-text-3)] font-ui italic">
          JurnalMap meringkas dari teks jurnal ini saja — bukan gabungan banyak jurnal.
        </div>
      </section>

      {/* Sections */}
      {hasSections && (
        <section>
          <div className="text-[10px] uppercase tracking-[0.22em] font-semibold text-[color:var(--jm-text-3)] mb-3">
            Bagian-Bagian Jurnal
          </div>
          <div data-testid="summary-sections" className="space-y-2">
            {SECTION_ORDER.map((k) => {
              const text = (sections[k] || "").trim();
              if (!text) return null;
              const key = `section:${k}`;
              const active = activeKey === key;
              const ev = evidenceByKey[key];
              const items = ev?.items || [];
              return (
                <button
                  key={k}
                  data-testid={`section-card-${k}`}
                  onClick={() => fetchSectionEvidence(k, text)}
                  className={`w-full text-left p-3.5 rounded-lg border transition-all
                    ${active ? "border-[color:var(--jm-text)] bg-[color:var(--jm-reading)] shadow-sm" : "border-[color:var(--jm-border)] bg-[color:var(--jm-surface)] hover:border-[color:var(--jm-border-2)]"}`}
                >
                  <div className="flex items-start justify-between gap-2 mb-1.5">
                    <span className="text-[10px] uppercase tracking-[0.2em] font-semibold text-[color:var(--jm-text-3)]">
                      {SECTION_LABEL[k]}
                    </span>
                    <ChevronRight
                      className={`w-4 h-4 text-[color:var(--jm-text-3)] transition-transform shrink-0 ${active ? "rotate-90" : ""}`}
                    />
                  </div>
                  <p className="font-reading text-[14px] leading-snug text-[color:var(--jm-text)]">
                    {text}
                  </p>
                  {active && busyKey === key && (
                    <div className="mt-2 flex items-center gap-2 text-xs text-[color:var(--jm-text-3)] font-ui">
                      <Loader2 className="w-3.5 h-3.5 animate-spin" /> Mencari bukti…
                    </div>
                  )}
                  {active && busyKey !== key && items.length === 0 && (
                    <div className="mt-2 text-xs text-[color:var(--jm-text-3)] font-ui">
                      Tidak ditemukan kalimat sumber yang cocok.
                    </div>
                  )}
                </button>
              );
            })}
          </div>
        </section>
      )}

      {/* Claims */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.22em] font-semibold text-[color:var(--jm-text-3)]">
            <Quote className="w-3.5 h-3.5" /> Klaim Inti
          </div>
          <div className="text-[10px] uppercase tracking-[0.2em] font-semibold text-[color:var(--jm-text-3)]">
            klik untuk menyorot
          </div>
        </div>
        <ul data-testid="claim-list" className="space-y-3">
          {claims.map((claim) => {
            const key = `claim:${claim.id}`;
            const active = activeKey === key;
            const ev = evidenceByKey[key];
            const items = ev?.items || [];
            return (
              <li key={claim.id}>
                <button
                  data-testid={`claim-card-${claim.id}`}
                  onClick={() => fetchClaimEvidence(claim)}
                  className={`w-full text-left p-4 rounded-lg border transition-all
                    ${active ? "border-[color:var(--jm-text)] bg-[color:var(--jm-reading)] shadow-sm" : "border-[color:var(--jm-border)] bg-[color:var(--jm-surface)] hover:border-[color:var(--jm-border-2)]"}`}
                >
                  <div className="flex items-start justify-between gap-3 mb-2">
                    <span className="text-[10px] uppercase tracking-[0.18em] font-semibold text-[color:var(--jm-text-3)]">
                      {CATEGORY_LABEL[claim.category] || claim.category}
                    </span>
                    <ChevronRight
                      className={`w-4 h-4 text-[color:var(--jm-text-3)] transition-transform ${active ? "rotate-90" : ""}`}
                    />
                  </div>
                  <p className="font-reading text-[15px] leading-snug text-[color:var(--jm-text)]">
                    {claim.text}
                  </p>
                  {active && (
                    <div className="mt-3 pt-3 border-t border-[color:var(--jm-border)] space-y-2">
                      {busyKey === key ? (
                        <div className="flex items-center gap-2 text-xs text-[color:var(--jm-text-3)] font-ui">
                          <Loader2 className="w-3.5 h-3.5 animate-spin" /> Mencari bukti…
                        </div>
                      ) : items.length === 0 ? (
                        <div className="text-xs text-[color:var(--jm-text-3)] font-ui">
                          Tidak ditemukan kalimat sumber yang cocok.
                        </div>
                      ) : (
                        <div className="space-y-2">
                          {items.slice(0, 3).map((it, i) => (
                            <div
                              key={i}
                              data-testid={`evidence-item-${claim.id}-${i}`}
                              className="rounded-md border border-[color:var(--jm-border)] bg-[color:var(--jm-surface)] p-2.5"
                            >
                              <div className="flex items-center justify-between mb-1.5">
                                <EvidenceBadge tier={it.tier} />
                                <span className="text-[10px] uppercase tracking-[0.18em] font-semibold text-[color:var(--jm-text-3)]">
                                  Hal. {it.page}
                                </span>
                              </div>
                              <div
                                className="text-[12.5px] leading-snug font-reading text-[color:var(--jm-text-2)] line-clamp-3 cursor-pointer hover:text-[color:var(--jm-text)]"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  onHighlight(items, { page: it.page, sentence_id: it.sentence_id });
                                }}
                              >
                                &ldquo;{it.text}&rdquo;
                              </div>
                              {it.rationale && (
                                <div className="mt-1.5 text-[10px] font-ui italic text-[color:var(--jm-text-3)]">
                                  {it.rationale}
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </button>
              </li>
            );
          })}
        </ul>
      </section>

      <section className="pt-4 border-t border-[color:var(--jm-border)]">
        <div className="text-[10px] uppercase tracking-[0.22em] font-semibold text-[color:var(--jm-text-3)] mb-2">
          Legenda Bukti
        </div>
        <div className="flex flex-wrap gap-2">
          {["high", "medium", "low"].map((t) => (
            <EvidenceBadge key={t} tier={t} label={TIER_META[t].label} />
          ))}
        </div>
      </section>
    </div>
  );
}
