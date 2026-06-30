import { useState } from "react";
import { api } from "@/services/api";
import { toast } from "sonner";
import { Loader2, ChevronRight, BookOpenCheck, Quote } from "lucide-react";
import EvidenceBadge from "@/components/EvidenceBadge";
import { CATEGORY_LABEL, TIER_META } from "@/lib/tiers";

export default function SummaryPanel({ summary, claims, onHighlight }) {
  const [activeClaimId, setActiveClaimId] = useState(null);
  const [busyClaimId, setBusyClaimId] = useState(null);
  const [evidenceByClaim, setEvidenceByClaim] = useState({}); // claimId -> {items, claim_text}

  const onClickClaim = async (claim) => {
    if (activeClaimId === claim.id) {
      // toggle off
      setActiveClaimId(null);
      onHighlight([], null);
      return;
    }
    setActiveClaimId(claim.id);
    setBusyClaimId(claim.id);
    try {
      let payload = evidenceByClaim[claim.id];
      if (!payload) {
        payload = await api.evidenceForClaim(claim.id);
        setEvidenceByClaim((m) => ({ ...m, [claim.id]: payload }));
      }
      const items = payload.items || [];
      onHighlight(items, items[0] ? { page: items[0].page, sentence_id: items[0].sentence_id } : null);
      if (items.length === 0) toast.info("Tidak ditemukan kalimat sumber untuk klaim ini.");
    } catch (e) {
      toast.error("Gagal mengambil bukti");
      setActiveClaimId(null);
    } finally {
      setBusyClaimId(null);
    }
  };

  if (!summary && (!claims || claims.length === 0)) {
    return (
      <div className="p-6 text-sm text-[color:var(--jm-text-3)] font-ui">
        Belum ada ringkasan untuk jurnal ini.
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
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
            const active = activeClaimId === claim.id;
            const ev = evidenceByClaim[claim.id];
            const items = ev?.items || [];
            return (
              <li key={claim.id}>
                <button
                  data-testid={`claim-card-${claim.id}`}
                  onClick={() => onClickClaim(claim)}
                  className={`w-full text-left p-4 rounded-lg border transition-all
                    ${active ? "border-[color:var(--jm-text)] bg-[color:var(--jm-reading)] shadow-sm" : "border-[color:var(--jm-border)] bg-white hover:border-[color:var(--jm-border-2)]"}
                  `}
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
                      {busyClaimId === claim.id ? (
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
                              className="rounded-md border border-[color:var(--jm-border)] bg-white p-2.5"
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
                                “{it.text}”
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
