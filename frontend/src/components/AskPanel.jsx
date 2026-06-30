import { useState } from "react";
import { Send, MessageSquareText, Loader2, FileSearch, Sparkles, PenLine } from "lucide-react";
import { api } from "@/services/api";
import { toast } from "sonner";
import EvidenceBadge from "@/components/EvidenceBadge";
import InsertToWorkspaceDialog from "@/components/Workspace/InsertToWorkspaceDialog";
import { useT } from "@/lib/useT";

export default function AskPanel({ projectId, docs }) {
  const { t } = useT();
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [history, setHistory] = useState([]); // [{q, answer, citations, overall_tier}]
  const [insertDialog, setInsertDialog] = useState({ open: false, payload: null });
  const ready = (docs || []).filter((d) => d.status === "ready");

  const ask = async () => {
    if (!q.trim()) return;
    if (ready.length === 0) {
      toast.error(t("ask.noReady"));
      return;
    }
    setBusy(true);
    try {
      const r = await api.ask(projectId, q.trim());
      setHistory((h) => [{ ...r }, ...h]);
      setQ("");
    } catch {
      toast.error("Failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <section
      data-testid="ask-section"
      className="rounded-xl bg-[color:var(--jm-surface)] border border-[color:var(--jm-border)] p-5"
    >
      <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.22em] font-semibold text-[color:var(--jm-text-3)] mb-3">
        <MessageSquareText className="w-3.5 h-3.5" /> {t("ask.title")}
      </div>
      <p className="text-sm text-[color:var(--jm-text-2)] font-ui mb-4">{t("ask.intro")}</p>

      <div className="flex gap-2">
        <input
          data-testid="ask-input"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && !busy && ask()}
          placeholder={t("ask.placeholder")}
          className="flex-1 px-4 py-3 rounded-lg border border-[color:var(--jm-border)] focus:border-[color:var(--jm-text)] focus:outline-none font-ui text-sm bg-[color:var(--jm-surface)] text-[color:var(--jm-text)]"
        />
        <button
          data-testid="ask-submit"
          onClick={ask}
          disabled={busy || !q.trim()}
          className="px-4 py-3 rounded-lg bg-[color:var(--jm-text)] text-[color:var(--jm-bg)] hover:opacity-90 flex items-center gap-2 disabled:opacity-50 font-ui text-sm font-semibold"
        >
          {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
          {t("ask.submit")}
        </button>
      </div>

      <div className="mt-6 space-y-5">
        {history.length === 0 && !busy && (
          <div className="rounded-lg border border-dashed border-[color:var(--jm-border)] p-8 text-center text-sm text-[color:var(--jm-text-3)] font-ui">
            {t("ask.empty")}
          </div>
        )}
        {history.map((item, i) => (
          <article
            key={i}
            data-testid={`ask-answer-${i}`}
            className="rounded-lg border border-[color:var(--jm-border)] bg-[color:var(--jm-reading)] p-5"
          >
            <div className="flex items-center flex-wrap gap-2 mb-2">
              <span className="text-[10px] uppercase tracking-[0.2em] font-semibold text-[color:var(--jm-text-3)]">
                {t("ask.question")}
              </span>
              <EvidenceBadge tier={item.overall_tier} label={`${t("ask.overall")}: ${item.overall_tier}`} />
              {(item.model_used || item.persona_used) && (
                <span
                  data-testid={`ask-attribution-${i}`}
                  className="inline-flex items-center gap-1.5 text-[10px] font-ui text-[color:var(--jm-text-3)]"
                >
                  <Sparkles className="w-3 h-3" />
                  <span className="uppercase tracking-[0.16em]">{t("ask.via")}</span>
                  {item.model_used && (
                    <span
                      data-testid={`ask-attribution-model-${i}`}
                      className="px-1.5 py-0.5 rounded bg-[color:var(--jm-sidebar)] text-[color:var(--jm-text-2)] font-semibold"
                    >
                      {item.model_used}
                    </span>
                  )}
                  {item.persona_used && (
                    <span
                      data-testid={`ask-attribution-persona-${i}`}
                      className="px-1.5 py-0.5 rounded bg-[color:var(--jm-sidebar)] text-[color:var(--jm-text-2)] font-semibold"
                    >
                      {item.persona_used}
                    </span>
                  )}
                </span>
              )}
            </div>
            <h4 className="font-display text-lg font-semibold text-[color:var(--jm-text)] leading-tight mb-3">
              {item.question}
            </h4>
            <p className="font-reading text-[15px] leading-relaxed text-[color:var(--jm-text)] whitespace-pre-wrap">
              {item.answer}
            </p>
            {item.citations.length > 0 && (
              <div className="mt-4 pt-4 border-t border-[color:var(--jm-border)]">
                <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.2em] font-semibold text-[color:var(--jm-text-3)] mb-2">
                  <FileSearch className="w-3 h-3" /> {t("ask.sources")}
                </div>
                <ul className="space-y-2">
                  {item.citations.map((c, ci) => (
                    <li
                      key={ci}
                      data-testid={`citation-${i}-${ci}`}
                      className="rounded border border-[color:var(--jm-border)] bg-[color:var(--jm-surface)] p-2.5 flex items-start gap-3"
                    >
                      <EvidenceBadge tier={c.tier} compact testId={`cite-tier-${i}-${ci}`} />
                      <div className="flex-1 min-w-0">
                        <div className="text-xs font-semibold text-[color:var(--jm-text)] truncate font-ui">
                          {c.document_title} <span className="text-[color:var(--jm-text-3)] font-normal">· hal. {c.page}</span>
                        </div>
                        <div className="text-[12.5px] leading-snug font-reading text-[color:var(--jm-text-2)] mt-0.5 line-clamp-2">
                          &ldquo;{c.excerpt}&rdquo;
                        </div>
                        <button
                          data-testid={`ask-insert-ws-${i}-${ci}`}
                          onClick={() =>
                            setInsertDialog({
                              open: true,
                              payload: {
                                document_id: c.document_id,
                                sentence_id: c.sentence_id,
                                quote: c.excerpt,
                                page: c.page,
                              },
                            })
                          }
                          className="mt-1.5 inline-flex items-center gap-1 text-[10px] uppercase tracking-[0.16em] font-semibold font-ui text-[color:var(--jm-text-2)] hover:text-[color:var(--jm-text)]"
                        >
                          <PenLine className="w-3 h-3" /> Sisipkan ke Workspace
                        </button>
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </article>
        ))}
      </div>
      <InsertToWorkspaceDialog
        open={insertDialog.open}
        onOpenChange={(o) => setInsertDialog((s) => ({ ...s, open: o }))}
        projectId={projectId}
        payload={insertDialog.payload}
      />
    </section>
  );
}
