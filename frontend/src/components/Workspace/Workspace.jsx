import { useEffect, useRef, useState, useCallback } from "react";
import { toast } from "sonner";
import { Loader2, FileWarning } from "lucide-react";
import { api } from "@/services/api";
import OutlineSetup from "./OutlineSetup";
import OutlineSidebar from "./OutlineSidebar";
import SynthesisEditor from "./SynthesisEditor";
import ReferenceManager from "./ReferenceManager";
import EvidenceDetector from "./EvidenceDetector";
import FindSourceDialog from "./FindSourceDialog";
import {
  htmlToMarkdown,
  htmlToPlainText,
  download,
  extractBadgesFromHTML,
} from "./workspaceUtils";

export default function Workspace({ projectId, docs }) {
  const [outline, setOutline] = useState(null);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false); // outline-edit mode
  const [activeSubId, setActiveSubId] = useState(null);
  const [contents, setContents] = useState({}); // {subId: {content, badges, references_used, plain_paragraphs}}
  const [generating, setGenerating] = useState(false);
  const [activeBadge, setActiveBadge] = useState(null);
  const [saveStatus, setSaveStatus] = useState({}); // {subId: "saved"|"dirty"|"saving"}
  const [formatChangedWarning, setFormatChangedWarning] = useState(false);
  const [allowSubsub, setAllowSubsub] = useState(false);
  const [findSourceDialog, setFindSourceDialog] = useState({ open: false, text: "" });

  const saveTimerRef = useRef(null);
  const lastSavedRef = useRef({});

  // Load outline + all contents on mount / project change
  useEffect(() => {
    let abort = false;
    setLoading(true);
    setActiveSubId(null);
    setActiveBadge(null);
    setContents({});
    Promise.all([
      api.getOutline(projectId),
      api.workspaceListContents(projectId),
    ])
      .then(([ol, list]) => {
        if (abort) return;
        if (ol && ol.exists) {
          setOutline(ol);
          const flat = [];
          for (const ch of ol.chapters || [])
            for (const sc of ch.subchapters || []) flat.push(sc.id);
          if (flat.length) setActiveSubId(flat[0]);
          const m = {};
          for (const item of list.items || []) {
            m[item.subchapter_id] = item;
          }
          setContents(m);
          lastSavedRef.current = Object.fromEntries(
            Object.entries(m).map(([k, v]) => [k, v.content || ""])
          );
          setEditing(false);
        } else {
          setOutline(null);
          setEditing(true);
        }
      })
      .catch(() => {
        if (!abort) toast.error("Gagal memuat outline");
      })
      .finally(() => !abort && setLoading(false));
    return () => {
      abort = true;
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    };
  }, [projectId]);

  // Cross-tab insert listener (Sisipkan ke Workspace)
  useEffect(() => {
    const handler = async (e) => {
      const detail = e.detail || {};
      if (detail.projectId !== projectId) return;
      const { subchapterId, document_id, sentence_id, quote, page } = detail;
      // Ask backend to compute label per current format
      try {
        const res = await api.workspaceInsertBadge(projectId, {
          subchapter_id: subchapterId,
          document_id,
          sentence_id,
          quote,
          page,
        });
        const badge = res.badge;
        // Switch active sub then insert
        setActiveSubId(subchapterId);
        setTimeout(() => insertBadgeIntoEditor(subchapterId, badge), 30);
        toast.success("Lencana sitasi disisipkan");
      } catch (err) {
        toast.error("Gagal menyisipkan sitasi");
      }
    };
    window.addEventListener("jm:workspace-insert", handler);
    return () => window.removeEventListener("jm:workspace-insert", handler);
  }, [projectId]);

  const insertBadgeIntoEditor = (subId, badge) => {
    // Mutate contents state to append badge into existing HTML
    setContents((m) => {
      const cur = m[subId] || { content: "", badges: [], references_used: [] };
      const html = cur.content || "";
      const append = ` <span class="jm-citation-badge" contenteditable="false" data-badge-id="${badge.badge_id}" data-document-id="${badge.document_id}" data-sentence-id="${badge.sentence_id || ""}" data-page="${badge.page ?? ""}">${escapeHtml(badge.label)}</span> `;
      let newHtml;
      if (html && html.trim()) {
        // append into last <p> if possible
        if (/<\/p>\s*$/i.test(html)) {
          newHtml = html.replace(/<\/p>\s*$/i, `${append}</p>`);
        } else {
          newHtml = html + append;
        }
      } else {
        newHtml = `<p>${append}</p>`;
      }
      const allBadges = [...(cur.badges || []), badge];
      const refsUsed = [...(cur.references_used || [])];
      if (!refsUsed.find((r) => r.document_id === badge.document_id)) {
        refsUsed.push({
          document_id: badge.document_id,
          title: badge.document_title,
          authors: badge.authors,
          year: badge.year,
        });
      }
      const next = {
        ...cur,
        content: newHtml,
        badges: allBadges,
        references_used: refsUsed,
      };
      // mark dirty and schedule save
      scheduleSave(subId, next);
      return { ...m, [subId]: next };
    });
    setSaveStatus((s) => ({ ...s, [subId]: "dirty" }));
  };

  const onChangeContent = (subId, { html, badges }) => {
    setContents((m) => {
      const cur = m[subId] || {};
      // Recompute references_used from current badges in DOM
      const refsMap = {};
      for (const b of badges) {
        if (!b.document_id) continue;
        if (!refsMap[b.document_id]) {
          refsMap[b.document_id] = {
            document_id: b.document_id,
            title: b.document_title,
            authors: b.authors,
            year: b.year,
          };
        }
      }
      const next = {
        ...cur,
        content: html,
        badges,
        references_used: Object.values(refsMap),
      };
      scheduleSave(subId, next);
      return { ...m, [subId]: next };
    });
    setSaveStatus((s) => ({ ...s, [subId]: "dirty" }));
  };

  const scheduleSave = (subId, payload) => {
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    saveTimerRef.current = setTimeout(() => {
      doSave(subId, payload);
    }, 1500); // idle debounce + 30s safety net below
  };

  const doSave = async (subId, payload) => {
    if (!subId) return;
    setSaveStatus((s) => ({ ...s, [subId]: "saving" }));
    try {
      await api.workspaceSaveContent(projectId, subId, {
        content: payload.content || "",
        badges: payload.badges || [],
        references_used: payload.references_used || [],
        plain_paragraphs: payload.plain_paragraphs || [],
      });
      lastSavedRef.current[subId] = payload.content || "";
      setSaveStatus((s) => ({ ...s, [subId]: "saved" }));
    } catch (e) {
      setSaveStatus((s) => ({ ...s, [subId]: "dirty" }));
    }
  };

  // Auto-save safety net every 30s for any dirty sub
  useEffect(() => {
    const id = setInterval(() => {
      const dirty = Object.entries(saveStatus).filter(([, v]) => v === "dirty");
      for (const [subId] of dirty) {
        const payload = contents[subId];
        if (payload) doSave(subId, payload);
      }
    }, 30000);
    return () => clearInterval(id);
  }, [saveStatus, contents]);

  const onGenerate = async ({ regenerate }) => {
    if (!activeSubId) return;
    setGenerating(true);
    try {
      const res = await api.workspaceGenerate(projectId, {
        subchapter_id: activeSubId,
        allow_subsubchapter: allowSubsub,
      });
      const next = {
        content: res.content || "",
        badges: res.badges || [],
        references_used: res.references_used || [],
        plain_paragraphs: [],
      };
      setContents((m) => ({ ...m, [activeSubId]: next }));
      lastSavedRef.current[activeSubId] = next.content;
      setSaveStatus((s) => ({ ...s, [activeSubId]: "saved" }));
      setFormatChangedWarning(false);
      toast.success(regenerate ? "Sub-bab di-generate ulang" : "Sub-bab dibuat");
    } catch (e) {
      const msg = e?.response?.data?.detail;
      toast.error(msg || "Gagal generate sub-bab");
    } finally {
      setGenerating(false);
    }
  };

  const onChangeFormat = async (newFmt) => {
    if (!outline || outline.citation_format === newFmt) return;
    try {
      const saved = await api.saveOutline(projectId, {
        title: outline.title,
        chapters: outline.chapters,
        citation_format: newFmt,
      });
      setOutline(saved);
      setFormatChangedWarning(true);
      toast.message(
        "Format sitasi diubah. Klik 'Generate Ulang' di sub-bab untuk menerapkan format baru."
      );
    } catch {
      toast.error("Gagal mengubah format sitasi");
    }
  };

  const activeContent = activeSubId ? contents[activeSubId] : null;
  const activeChapter =
    outline?.chapters?.find((c) =>
      (c.subchapters || []).some((s) => s.id === activeSubId)
    ) || null;
  const activeSub = activeChapter?.subchapters?.find((s) => s.id === activeSubId);

  const onExport = (fmt) => {
    if (!outline) return;
    // Build a combined document from all subchapters in outline order
    const lines = [];
    lines.push(fmt === "md" ? `# ${outline.title}\n` : outline.title + "\n");
    for (const ch of outline.chapters || []) {
      lines.push(fmt === "md" ? `## ${ch.title}\n` : `\n${ch.title}\n`);
      for (const sc of ch.subchapters || []) {
        lines.push(fmt === "md" ? `### ${sc.title}\n` : `\n${sc.title}\n`);
        const c = contents[sc.id];
        if (c?.content) {
          if (fmt === "md") lines.push(htmlToMarkdown(c.content));
          else lines.push(htmlToPlainText(c.content));
        } else {
          lines.push(
            fmt === "md" ? "_(belum ditulis)_\n\n" : "(belum ditulis)\n\n"
          );
        }
      }
    }
    const ext = fmt === "md" ? "md" : "txt";
    const mime = fmt === "md" ? "text/markdown" : "text/plain";
    download(
      `workspace-${outline.title.replace(/[^a-z0-9_-]+/gi, "_").slice(0, 40) || "draft"}-${Date.now()}.${ext}`,
      lines.join("\n"),
      mime
    );
  };

  if (loading) {
    return (
      <div
        data-testid="workspace-loading"
        className="p-10 text-center text-sm text-[color:var(--jm-text-3)] font-ui"
      >
        <Loader2 className="w-5 h-5 animate-spin mx-auto mb-2" /> Memuat workspace…
      </div>
    );
  }

  if (editing || !outline) {
    return (
      <OutlineSetup
        projectId={projectId}
        initial={outline}
        onSaved={(ol) => {
          setOutline(ol);
          setEditing(false);
          const first = ol.chapters?.[0]?.subchapters?.[0]?.id;
          if (first) setActiveSubId(first);
        }}
      />
    );
  }

  const readyDocsCount = (docs || []).filter((d) => d.status === "ready").length;

  return (
    <div data-testid="workspace-root" className="grid grid-cols-1 lg:grid-cols-12 gap-4">
      <div className="lg:col-span-3">
        <OutlineSidebar
          outline={outline}
          activeSubId={activeSubId}
          onSelect={(id) => {
            setActiveSubId(id);
            setActiveBadge(null);
          }}
          onEditOutline={() => setEditing(true)}
        />
      </div>
      <div className="lg:col-span-6">
        {readyDocsCount === 0 && (
          <div
            data-testid="workspace-no-docs"
            className="mb-3 flex items-start gap-2 p-3 rounded-md border border-amber-200 bg-amber-50 text-amber-800 text-xs font-ui"
          >
            <FileWarning className="w-4 h-4 shrink-0 mt-0.5" />
            <span>
              Tidak ada jurnal siap di proyek ini. Unggah PDF di tab Baca terlebih dahulu agar AI bisa merangkai bukti.
            </span>
          </div>
        )}
        <SynthesisEditor
          subchapter={activeSub}
          chapter={activeChapter}
          paperTitle={outline.title}
          initialContent={activeContent?.content || ""}
          initialBadges={activeContent?.badges || []}
          generating={generating}
          saveStatus={saveStatus[activeSubId]}
          allowSubsub={allowSubsub}
          onToggleSubsub={setAllowSubsub}
          onFindSource={(text) => setFindSourceDialog({ open: true, text })}
          onGenerate={onGenerate}
          onChange={(payload) => onChangeContent(activeSubId, payload)}
          onBadgeClick={(b) => setActiveBadge(b)}
          onExportMarkdown={() => onExport("md")}
          onExportText={() => onExport("txt")}
        />
      </div>
      <div className="lg:col-span-3 space-y-4">
        <ReferenceManager
          citationFormat={outline.citation_format}
          onChangeFormat={onChangeFormat}
          formatChangedWarning={formatChangedWarning}
          badges={activeContent?.badges || []}
          onSelectBadge={(b) => setActiveBadge(b)}
          activeBadgeId={activeBadge?.badge_id}
        />
        <EvidenceDetector projectId={projectId} badge={activeBadge} />
      </div>
      <FindSourceDialog
        open={findSourceDialog.open}
        onOpenChange={(o) => setFindSourceDialog((s) => ({ ...s, open: o }))}
        projectId={projectId}
        text={findSourceDialog.text}
        onConfirm={async (source) => {
          // Convert source -> badge via insert-badge endpoint to compute label
          try {
            const res = await api.workspaceInsertBadge(projectId, {
              subchapter_id: activeSubId,
              document_id: source.document_id,
              sentence_id: source.sentence_id,
              quote: source.quote,
              page: source.page,
            });
            insertBadgeIntoEditor(activeSubId, res.badge);
            toast.success("Sitasi disisipkan dari sumber yang ditemukan");
          } catch {
            toast.error("Gagal menyisipkan sitasi");
          }
        }}
      />
    </div>
  );
}

function escapeHtml(s) {
  return String(s || "")
    .replace(/&/g, "&amp;")
    .replace(/"/g, "&quot;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}
