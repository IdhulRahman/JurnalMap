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
  Sparkles,
  Languages,
  Layers,
} from "lucide-react";
import EvidenceBadge from "@/components/EvidenceBadge";
import { CATEGORY_LABEL, TIER_META } from "@/lib/tiers";
import { useSettings } from "@/store/settings";
import { useT } from "@/lib/useT";
import { getFeatureLanguage, setFeatureLanguage } from "@/lib/featureLanguage";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";


const SECTION_LABEL_KEY = {
  abstract: "summary.section.abstract",
  objective: "summary.section.objective",
  method: "summary.section.method",
  results: "summary.section.results",
  conclusion: "summary.section.conclusion",
};
const SECTION_ORDER = ["abstract", "objective", "method", "results", "conclusion"];


export default function SummaryPanel({ docId, projectId, summary, claims, sections, modelUsed, personaUsed, onHighlight, onResummarized }) {
  const { settings } = useSettings();
  const { t } = useT();
  const [activeKey, setActiveKey] = useState(null); // "section:abstract" or "claim:<id>"
  const [busyKey, setBusyKey] = useState(null);
  const [evidenceByKey, setEvidenceByKey] = useState({});
  const [selectedModel, setSelectedModel] = useState(modelUsed || settings?.default_model || "");
  const [selectedLanguage, setSelectedLanguage] = useState(() => getFeatureLanguage("summary", "id"));
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
    setFeatureLanguage("summary", selectedLanguage);
    try {
      const r = await api.resummarize(docId, selectedModel, null, selectedLanguage);
      setEvidenceByKey({}); // claim ids changed
      setActiveKey(null);
      onHighlight([], null);
      toast.success("Ringkasan diperbarui");
      onResummarized?.(r);
    } catch (e) {
      const msg = e?.response?.data?.detail;
      if (e?.response?.status === 502 && msg) {
        toast.error(msg, { duration: 6000 });
      } else if (e?.response?.status === 409) {
        toast.error("Dokumen belum siap.");
      } else {
        toast.error("Gagal meringkas ulang");
      }
    } finally {
      setResummarizing(false);
    }
  };

  const hasSections = sections && SECTION_ORDER.some((k) => (sections[k] || "").trim());
  const isEmpty = !summary && !hasSections && (!claims || claims.length === 0);

  return (
    <div className="p-6 space-y-6">
      {/* Model picker + Language + Ringkas */}
      <section
        data-testid="summary-model-bar"
        className="pb-4 border-b border-[color:var(--jm-border)] space-y-2"
      >
        <div className="flex items-center gap-2 flex-wrap">
          <Cpu className="w-3.5 h-3.5 text-[color:var(--jm-text-3)]" />
          <span className="text-[10px] uppercase tracking-[0.22em] font-semibold text-[color:var(--jm-text-3)]">
            {t("summary.modelBar")}
          </span>
          <Select value={selectedModel} onValueChange={setSelectedModel}>
            <SelectTrigger
              data-testid="summary-model-select"
              className="h-8 text-xs bg-[color:var(--jm-surface)] border-[color:var(--jm-border)] text-[color:var(--jm-text)] flex-1 min-w-[140px]"
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

          <Languages className="w-3.5 h-3.5 text-[color:var(--jm-text-3)] ml-1" />
          <Select value={selectedLanguage} onValueChange={setSelectedLanguage}>
            <SelectTrigger
              data-testid="summary-lang-select"
              className="h-8 text-xs bg-[color:var(--jm-surface)] border-[color:var(--jm-border)] text-[color:var(--jm-text)] w-[128px]"
            >
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem data-testid="summary-lang-id" value="id">Bahasa Indonesia</SelectItem>
              <SelectItem data-testid="summary-lang-en" value="en">English</SelectItem>
            </SelectContent>
          </Select>

          <button
            data-testid="resummarize-btn"
            onClick={resummarize}
            disabled={resummarizing}
            className="px-3 py-1.5 rounded-md text-xs font-semibold font-ui flex items-center gap-1.5 bg-[color:var(--jm-text)] text-[color:var(--jm-bg)] hover:opacity-90 disabled:opacity-50"
            title="Ringkas dokumen dengan model & bahasa ini"
          >
            {resummarizing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}
            {isEmpty ? "Ringkas" : t("summary.resummarize")}
          </button>
        </div>
        {(modelUsed || personaUsed) && (
          <div
            data-testid="summary-attribution"
            className="flex items-center flex-wrap gap-1.5 text-[10px] font-ui text-[color:var(--jm-text-3)]"
          >
            <Sparkles className="w-3 h-3" />
            <span className="uppercase tracking-[0.16em]">{t("summary.attribution")}:</span>
            {modelUsed && (
              <span
                data-testid="attribution-model"
                className="px-1.5 py-0.5 rounded bg-[color:var(--jm-sidebar)] text-[color:var(--jm-text-2)] font-semibold"
              >
                {modelUsed}
              </span>
            )}
            {personaUsed && (
              <span
                data-testid="attribution-persona"
                className="px-1.5 py-0.5 rounded bg-[color:var(--jm-sidebar)] text-[color:var(--jm-text-2)] font-semibold"
              >
                {personaUsed}
              </span>
            )}
          </div>
        )}
      </section>

      {isEmpty && (
        <section
          data-testid="summary-placeholder"
          className="rounded-lg border-2 border-dashed border-[var(--jm-border-2)] bg-[var(--jm-surface)] p-8 text-center"
        >
          <BookOpenCheck className="w-8 h-8 mx-auto text-[color:var(--jm-text-3)] mb-3" />
          <p className="font-reading text-[15px] leading-relaxed text-[color:var(--jm-text-2)]">
            {t("summary.placeholder")}
          </p>
        </section>
      )}

      {!isEmpty && (
      <>
      {/* Overview */}
      <section>
        <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.22em] font-semibold text-[color:var(--jm-text-3)] mb-3">
          <BookOpenCheck className="w-3.5 h-3.5" /> {t("summary.overview")}
        </div>
        <p
          data-testid="document-summary"
          className="font-reading text-[15px] leading-relaxed text-[color:var(--jm-text)]"
        >
          {summary || t("summary.overview.empty")}
        </p>
        <div className="mt-3 text-[11px] text-[color:var(--jm-text-3)] font-ui italic">
          {t("summary.overview.note")}
        </div>
      </section>

      {/* Sections */}
      {sections && (
        <section>
          <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.22em] font-semibold text-[color:var(--jm-text-3)] mb-3">
            <Layers className="w-3.5 h-3.5" /> {t("summary.sections")}
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
                  className={`w-full text-left p-3.5 rounded-lg border-2 transition-all
                    ${active ? "border-[var(--jm-text)] bg-[var(--jm-reading)] shadow-sm" : "border-[var(--jm-border-2)] bg-[var(--jm-surface)] hover:border-[var(--jm-border)]"}`}
                >
                  <div className="flex items-start justify-between gap-2 mb-1.5">
                    <span className="text-[10px] uppercase tracking-[0.2em] font-semibold text-[color:var(--jm-text-3)]">
                      {t(SECTION_LABEL_KEY[k])}
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
                      <Loader2 className="w-3.5 h-3.5 animate-spin" /> {t("summary.searchingEvidence")}
                    </div>
                  )}
                  {active && busyKey !== key && items.length === 0 && (
                    <div className="mt-2 text-xs text-[color:var(--jm-text-3)] font-ui">
                      {t("summary.noEvidence")}
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
            <Quote className="w-3.5 h-3.5" /> {t("summary.claims")}
          </div>
          <div className="text-[10px] uppercase tracking-[0.2em] font-semibold text-[color:var(--jm-text-3)]">
            {t("summary.clickHint")}
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
                  className={`w-full text-left p-4 rounded-lg border-2 transition-all
                    ${active ? "border-[var(--jm-text)] bg-[var(--jm-reading)] shadow-sm" : "border-[var(--jm-border-2)] bg-[var(--jm-surface)] hover:border-[var(--jm-border)]"}`}
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
                    <div className="mt-3 pt-3 border-t-2 border-[var(--jm-border-2)] space-y-2">
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
                              className="rounded-md border-2 border-[var(--jm-border-2)] bg-[var(--jm-surface)] p-2.5"
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
          {t("summary.legend")}
        </div>
        <div className="flex flex-wrap gap-2">
          {["high", "medium", "low"].map((tier) => (
            <EvidenceBadge key={tier} tier={tier} label={t(`tier.${tier}`)} />
          ))}
        </div>
      </section>
      </>
      )}

      {projectId && null}
    </div>
  );
}
