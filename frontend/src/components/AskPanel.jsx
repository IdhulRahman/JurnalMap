import { useState, useEffect, useRef } from "react";
import { Send, MessageSquareText, Loader2, FileSearch, Sparkles } from "lucide-react";
import { api } from "@/services/api";
import { toast } from "sonner";
import EvidenceBadge from "@/components/EvidenceBadge";
import { useT } from "@/lib/useT";

export default function AskPanel({ projectId, docs, globalModel, globalLanguage }) {
  const { t } = useT();
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  
  // Chat history format: [{ role: "user" | "assistant", content: string, citations: [], overall_tier: "high" | "medium" | "low", model_used: string }]
  const [history, setHistory] = useState([]);
  const ready = (docs || []).filter((d) => d.status === "ready");
  
  const scrollRef = useRef(null);

  // Auto-scroll to the bottom of the chat list on new messages
  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [history, busy]);

  const ask = async () => {
    const questionText = q.trim();
    if (!questionText) return;
    if (ready.length === 0) {
      toast.error(t("ask.noReady"));
      return;
    }
    
    setBusy(true);
    setQ(""); // Clear input immediately
    
    // Add user message to history immediately for a fluid chat experience
    const newUserMsg = { role: "user", content: questionText };
    setHistory((prev) => [...prev, newUserMsg]);
    
    // Filter history to send simple {role, content} list to backend context
    const historyPayload = history.map((h) => ({
      role: h.role,
      content: h.content,
    }));
    
    try {
      const r = await api.ask(projectId, questionText, globalLanguage, globalModel, historyPayload);
      
      const newAiMsg = {
        role: "assistant",
        content: r.answer || "Tidak ada jawaban yang dapat disusun.",
        citations: r.citations || [],
        overall_tier: r.overall_tier || "low",
        model_used: r.model_used,
        persona_used: r.persona_used,
      };
      
      setHistory((prev) => [...prev, newAiMsg]);
    } catch (e) {
      const errorMsg = e?.response?.data?.detail || "Gagal mendapatkan jawaban.";
      toast.error(errorMsg);
      // Remove the last user message if it failed, or add an assistant error message
      setHistory((prev) => [
        ...prev,
        {
          role: "assistant",
          content: `Error: ${errorMsg}. Silakan coba lagi.`,
          citations: [],
          overall_tier: "low",
        },
      ]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section
      data-testid="ask-section"
      className="rounded-xl bg-[var(--jm-surface)] border-2 border-[var(--jm-border-2)] p-5"
    >
      <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.22em] font-semibold text-[color:var(--jm-text-3)] mb-3">
        <MessageSquareText className="w-3.5 h-3.5" /> {t("ask.title")}
      </div>
      <p className="text-sm text-[color:var(--jm-text-2)] font-ui mb-4">{t("ask.intro")}</p>

      {/* Chat Messages Log */}
      <div className="flex flex-col h-[500px] border border-[color:var(--jm-border)] rounded-lg bg-[color:var(--jm-reading)] overflow-hidden mb-4">
        <div className="flex-1 overflow-y-auto p-4 space-y-4 scrollbar-thin">
          {history.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-center p-6 text-sm text-[color:var(--jm-text-3)] italic font-ui space-y-2">
              <MessageSquareText className="w-8 h-8 opacity-40 mb-1" />
              <div>Belum ada obrolan. Ajukan pertanyaan lintas jurnal Anda di bawah.</div>
            </div>
          ) : (
            history.map((msg, index) => {
              const isUser = msg.role === "user";
              return (
                <div key={index} className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
                  <div
                    className={`max-w-[85%] rounded-2xl px-4 py-3.5 font-ui text-[13.5px] leading-relaxed shadow-sm ${
                      isUser
                        ? "bg-[var(--jm-focus)] text-white rounded-br-sm"
                        : "bg-[var(--jm-surface)] text-[color:var(--jm-text)] border border-[color:var(--jm-border)] rounded-bl-sm"
                    }`}
                  >
                    {!isUser && (
                      <div className="flex items-center flex-wrap gap-2 mb-2 pb-2 border-b border-[color:var(--jm-border)]">
                        <EvidenceBadge tier={msg.overall_tier} label={`${t("ask.overall")}: ${msg.overall_tier}`} />
                        {(msg.model_used || msg.persona_used) && (
                          <span className="inline-flex items-center gap-1 text-[10px] text-[color:var(--jm-text-3)] font-semibold uppercase bg-[color:var(--jm-sidebar)] px-1.5 py-0.5 rounded">
                            <Sparkles className="w-3 h-3 text-[color:var(--jm-text-3)]" />
                            {msg.model_used || "LLM"}
                          </span>
                        )}
                      </div>
                    )}
                    
                    <p className="whitespace-pre-wrap leading-relaxed">{msg.content}</p>
                    
                    {/* Collapsible references list inside AI response */}
                    {!isUser && msg.citations && msg.citations.length > 0 && (
                      <div className="mt-3.5 pt-3 border-t border-[color:var(--jm-border)]">
                        <div className="text-[10px] uppercase tracking-[0.18em] font-semibold text-[color:var(--jm-text-3)] mb-2 flex items-center gap-1">
                          <FileSearch className="w-3 h-3" /> {t("ask.sources")}
                        </div>
                        <ul className="space-y-2">
                          {msg.citations.map((c, ci) => (
                            <li
                              key={ci}
                              className="rounded border border-[color:var(--jm-border)] bg-[color:var(--jm-reading)] p-2 flex items-start gap-2.5"
                            >
                              <EvidenceBadge tier={c.tier} compact />
                              <div className="flex-1 min-w-0">
                                <div className="text-[11.5px] font-semibold text-[color:var(--jm-text)] truncate font-ui">
                                  {c.document_title} <span className="text-[color:var(--jm-text-3)] font-normal">· hal. {c.page}</span>
                                </div>
                                <div className="text-[11px] leading-snug font-reading text-[color:var(--jm-text-2)] mt-0.5 italic line-clamp-2">
                                  &ldquo;{c.excerpt}&rdquo;
                                </div>
                              </div>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                </div>
              );
            })
          )}
          {busy && (
            <div className="flex justify-start">
              <div className="bg-[var(--jm-surface)] text-[color:var(--jm-text-2)] border border-[color:var(--jm-border)] rounded-2xl rounded-bl-sm px-4 py-3 text-xs flex items-center gap-2">
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                <span>Mencari bukti & merumuskan jawaban…</span>
              </div>
            </div>
          )}
          <div ref={scrollRef} />
        </div>
      </div>

      {/* Input chat controls */}
      <div className="flex gap-2">
        <input
          data-testid="ask-input"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && !busy && ask()}
          placeholder="Tanyakan sesuatu tentang koleksi paper di proyek ini..."
          disabled={busy}
          className="flex-1 px-4 py-3 rounded-lg border-2 border-[var(--jm-border-2)] focus:border-[var(--jm-text)] focus:outline-none font-ui text-sm bg-[var(--jm-surface)] text-[color:var(--jm-text)] disabled:opacity-60"
        />
        <button
          data-testid="ask-submit"
          onClick={ask}
          disabled={busy || !q.trim() || ready.length === 0}
          className="px-5 py-3 rounded-lg bg-[var(--jm-focus)] text-white hover:opacity-90 flex items-center gap-2 disabled:opacity-50 font-ui text-sm font-semibold shrink-0 transition-opacity"
        >
          {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
          Tanya
        </button>
      </div>
    </section>
  );
}
