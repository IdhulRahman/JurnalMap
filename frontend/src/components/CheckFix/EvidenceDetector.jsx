import { useEffect, useState } from "react";
import { Link as LinkIcon, Loader2, Search, FileText } from "lucide-react";
import { api } from "@/services/api";
import { Link } from "react-router-dom";

export default function EvidenceDetector({ projectId, badge }) {
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    let abort = false;
    setData(null);
    setErr("");
    if (!badge) return;
    setData({
      text: badge.quote || "",
      page: badge.page,
      document_title: badge.document_title,
      document_id: badge.document_id,
      sentence_id: badge.sentence_id,
    });
    if (badge.document_id && badge.sentence_id) {
      setBusy(true);
      api
        .getSentenceDetail(badge.document_id, badge.sentence_id)
        .then((d) => { if (!abort) setData(d); })
        .catch(() => { if (!abort) setErr("Tidak dapat memuat detail kalimat."); })
        .finally(() => !abort && setBusy(false));
    }
    return () => { abort = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [badge?.badge_id]);

  return (
    <section
      data-testid="checkfix-evidence-detector"
      className="rounded-xl border border-[color:var(--jm-border)] bg-[color:var(--jm-reading)] p-4 min-h-[200px]"
    >
      <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.22em] font-semibold text-[color:var(--jm-text-3)] mb-3">
        <Search className="w-3.5 h-3.5" /> Detektor Bukti
      </div>
      {!badge ? (
        <div className="text-xs text-[color:var(--jm-text-3)] font-ui italic space-y-3">
          <div>Klik lencana sitasi pada hasil verifikasi untuk melihat kalimat sumber.</div>
          <div className="pt-2 text-[11px] text-rose-500 font-semibold border-t border-[color:var(--jm-border)]">
            Tidak ditemukan bukti di koleksi paper.
          </div>
        </div>
      ) : (
        <div className="space-y-3">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-semibold bg-[color:var(--jm-text)] text-[color:var(--jm-bg)] font-ui">
              {badge.label}
            </span>
            {busy && <Loader2 className="w-3.5 h-3.5 animate-spin text-[color:var(--jm-text-3)]" />}
          </div>
          <div className="text-[10px] uppercase tracking-[0.18em] font-semibold text-[color:var(--jm-text-3)] flex items-center gap-1">
            <FileText className="w-3 h-3" />
            <span data-testid="checkfix-evidence-doc-title">{data?.document_title || badge.document_title || ""}</span>
            {(data?.page || badge.page) ? <span>· hal. {data?.page || badge.page}</span> : null}
          </div>
          
          <blockquote
            data-testid="checkfix-evidence-quote"
            className="border-l-2 border-[color:var(--jm-text)] pl-3 font-reading text-sm leading-relaxed text-[color:var(--jm-text)]"
          >
            &ldquo;{data?.text || badge.quote || "(kutipan tidak tersedia)"}&rdquo;
          </blockquote>

          {badge.status === "similar" && (
            <div className="text-[11.5px] text-amber-700 dark:text-amber-400 font-ui italic bg-amber-500/10 p-2.5 rounded-md border-l-2 border-amber-500 leading-normal">
              Klaim ini merupakan rangkaian dari beberapa sumber dengan tambahan inferensi AI.
            </div>
          )}

          {err && (
            <div className="text-[11px] text-[color:var(--jm-text-3)] italic font-ui">{err}</div>
          )}
          {data?.document_id && (
            <Link
              data-testid="checkfix-evidence-open-baca"
              to={`/project/${projectId}/doc/${data.document_id}`}
              className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs font-semibold font-ui bg-[color:var(--jm-text)] text-[color:var(--jm-bg)] hover:opacity-90 mt-1"
            >
              <LinkIcon className="w-3 h-3" /> Buka di Tab Baca
            </Link>
          )}
        </div>
      )}
    </section>
  );
}
