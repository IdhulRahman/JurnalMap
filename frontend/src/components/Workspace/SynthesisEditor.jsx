import { useEffect, useRef, useState } from "react";
import {
  Sparkles,
  RefreshCw,
  Loader2,
  Download,
  Bold,
  Italic,
  Heading2,
  Heading3,
  List as ListIcon,
  CheckCircle2,
  CircleDot,
} from "lucide-react";
import { toast } from "sonner";
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
} from "@/components/ui/dropdown-menu";
import {
  badgeSpanHTML,
  extractBadgesFromHTML,
  htmlToMarkdown,
  htmlToPlainText,
  download,
} from "./workspaceUtils";
import "./workspace.css";

export default function SynthesisEditor({
  subchapter,
  chapter,
  paperTitle,
  initialContent,
  initialBadges,
  onGenerate,
  onChange,
  generating,
  onBadgeClick,
  saveStatus,
  onExportMarkdown,
  onExportText,
}) {
  const editorRef = useRef(null);
  const lastEmittedHtmlRef = useRef("");

  // Sync external content into editor when the subchapter changes
  useEffect(() => {
    if (!editorRef.current) return;
    const html = initialContent || "<p></p>";
    if (editorRef.current.innerHTML !== html) {
      editorRef.current.innerHTML = html;
      lastEmittedHtmlRef.current = html;
    }
  }, [subchapter?.id, initialContent]);

  const emitChange = () => {
    if (!editorRef.current) return;
    const html = editorRef.current.innerHTML;
    if (html === lastEmittedHtmlRef.current) return;
    lastEmittedHtmlRef.current = html;
    const badges = extractBadgesFromHTML(html, initialBadges || []);
    onChange?.({ html, badges });
  };

  const handleInput = () => {
    emitChange();
  };

  const handleClick = (e) => {
    const t = e.target;
    if (t && t.classList && t.classList.contains("jm-citation-badge")) {
      e.preventDefault();
      const badgeId = t.getAttribute("data-badge-id");
      const badges = extractBadgesFromHTML(editorRef.current.innerHTML, initialBadges || []);
      const b = badges.find((x) => x.badge_id === badgeId);
      if (b) onBadgeClick?.(b);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key !== "Backspace" && e.key !== "Delete") return;
    const sel = window.getSelection();
    if (!sel || sel.rangeCount === 0) return;
    const range = sel.getRangeAt(0);
    if (!range.collapsed) return;
    let badgeEl = null;
    if (e.key === "Backspace") {
      const node =
        range.startContainer.nodeType === 3
          ? range.startContainer
          : range.startContainer.childNodes[range.startOffset - 1] || null;
      if (range.startContainer.nodeType === 3 && range.startOffset === 0) {
        // at start of a text node — look at previous sibling
        let prev = range.startContainer.previousSibling;
        while (prev && prev.nodeType === 3 && (prev.textContent || "").length === 0)
          prev = prev.previousSibling;
        if (prev && prev.nodeType === 1 && prev.classList?.contains("jm-citation-badge")) {
          badgeEl = prev;
        }
      } else if (node && node.nodeType === 1 && node.classList?.contains("jm-citation-badge")) {
        badgeEl = node;
      }
    } else {
      const c = range.startContainer.childNodes[range.startOffset] || null;
      if (c && c.nodeType === 1 && c.classList?.contains("jm-citation-badge")) {
        badgeEl = c;
      }
    }
    if (badgeEl) {
      e.preventDefault();
      if (window.confirm("Lepas sitasi?")) {
        badgeEl.remove();
        emitChange();
      }
    }
  };

  const exec = (cmd, val = null) => {
    document.execCommand(cmd, false, val);
    emitChange();
  };

  // Public method: insert badge at the end of the editor content
  const insertBadge = (badge) => {
    if (!editorRef.current) return;
    editorRef.current.focus();
    const html = badgeSpanHTML(badge) + " ";
    // Insert at caret. If no selection inside, append to last <p>.
    const sel = window.getSelection();
    if (sel && sel.rangeCount && editorRef.current.contains(sel.anchorNode)) {
      document.execCommand("insertHTML", false, html);
    } else {
      const ps = editorRef.current.querySelectorAll("p");
      if (ps.length === 0) {
        editorRef.current.innerHTML = `<p>${html}</p>`;
      } else {
        ps[ps.length - 1].insertAdjacentHTML("beforeend", " " + html);
      }
    }
    emitChange();
  };

  // Expose insertBadge via ref pattern through onChange callback? Use imperative ref via window proxy on element.
  useEffect(() => {
    if (editorRef.current) editorRef.current._jmInsertBadge = insertBadge;
  });

  return (
    <section
      data-testid="workspace-synthesis-editor"
      className="rounded-xl border border-[color:var(--jm-border)] bg-[color:var(--jm-surface)] p-4 flex flex-col min-h-[60vh]"
    >
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="min-w-0">
          <div className="text-[10px] uppercase tracking-[0.22em] font-semibold text-[color:var(--jm-text-3)]">
            {paperTitle}
          </div>
          <h2
            data-testid="workspace-active-sub-title"
            className="font-display text-xl sm:text-2xl font-semibold text-[color:var(--jm-text)] truncate mt-0.5"
          >
            {subchapter?.title || "Pilih sub-bab di sidebar"}
          </h2>
          {chapter?.title && (
            <div className="text-xs text-[color:var(--jm-text-3)] font-ui mt-0.5">
              {chapter.title}
            </div>
          )}
        </div>
        <div className="flex items-center gap-1.5">
          <SaveBadge status={saveStatus} />
        </div>
      </div>

      {subchapter && (
        <div
          data-testid="workspace-editor-toolbar"
          className="flex items-center flex-wrap gap-1 mb-3 pb-3 border-b border-[color:var(--jm-border)]"
        >
          <button
            onClick={() => exec("bold")}
            className="p-1.5 rounded hover:bg-[color:var(--jm-sidebar)]"
            title="Bold"
          >
            <Bold className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => exec("italic")}
            className="p-1.5 rounded hover:bg-[color:var(--jm-sidebar)]"
            title="Italic"
          >
            <Italic className="w-3.5 h-3.5" />
          </button>
          <span className="w-px h-4 bg-[color:var(--jm-border)] mx-1" />
          <button
            onClick={() => exec("formatBlock", "H2")}
            className="p-1.5 rounded hover:bg-[color:var(--jm-sidebar)]"
            title="Heading 2"
          >
            <Heading2 className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => exec("formatBlock", "H3")}
            className="p-1.5 rounded hover:bg-[color:var(--jm-sidebar)]"
            title="Heading 3"
          >
            <Heading3 className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => exec("insertUnorderedList")}
            className="p-1.5 rounded hover:bg-[color:var(--jm-sidebar)]"
            title="Bullet list"
          >
            <ListIcon className="w-3.5 h-3.5" />
          </button>
          <span className="w-px h-4 bg-[color:var(--jm-border)] mx-1" />
          <button
            data-testid="workspace-generate-btn"
            onClick={() => onGenerate?.({ regenerate: false })}
            disabled={generating}
            className="px-3 py-1.5 rounded-md text-xs font-ui font-semibold flex items-center gap-1.5 bg-[color:var(--jm-text)] text-[color:var(--jm-bg)] hover:opacity-90 disabled:opacity-50"
          >
            {generating ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Sparkles className="w-3.5 h-3.5" />
            )}
            {initialContent ? "Generate Ulang" : "Generate"}
          </button>
          {initialContent && (
            <button
              data-testid="workspace-regen-btn"
              onClick={() => onGenerate?.({ regenerate: true })}
              disabled={generating}
              className="px-2.5 py-1.5 rounded-md text-xs font-ui font-semibold flex items-center gap-1 bg-[color:var(--jm-sidebar)] text-[color:var(--jm-text-2)] hover:bg-[color:var(--jm-reading)] disabled:opacity-50"
              title="Tulis ulang sub-bab dari awal"
            >
              <RefreshCw className="w-3 h-3" /> Tulis ulang
            </button>
          )}
          <span className="ml-auto" />
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button
                data-testid="workspace-export-btn"
                className="px-2.5 py-1.5 rounded-md text-xs font-ui font-semibold flex items-center gap-1 border border-[color:var(--jm-border)] hover:bg-[color:var(--jm-sidebar)]"
              >
                <Download className="w-3.5 h-3.5" /> Ekspor
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem data-testid="workspace-export-md" onClick={onExportMarkdown}>
                Markdown (.md)
              </DropdownMenuItem>
              <DropdownMenuItem data-testid="workspace-export-txt" onClick={onExportText}>
                Plain Text (.txt)
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      )}

      {!subchapter ? (
        <div className="flex-1 flex items-center justify-center text-sm text-[color:var(--jm-text-3)] font-ui italic">
          Pilih sub-bab dari sidebar untuk mulai menulis.
        </div>
      ) : (
        <div
          ref={editorRef}
          data-testid="workspace-editor"
          contentEditable
          suppressContentEditableWarning
          onInput={handleInput}
          onClick={handleClick}
          onKeyDown={handleKeyDown}
          spellCheck={true}
          className="jm-workspace-editor flex-1 outline-none font-reading text-[15px] leading-relaxed text-[color:var(--jm-text)]"
        />
      )}
    </section>
  );
}

function SaveBadge({ status }) {
  if (!status) return null;
  if (status === "saving") {
    return (
      <span
        data-testid="workspace-save-status"
        className="inline-flex items-center gap-1 text-[11px] font-ui text-[color:var(--jm-text-3)]"
      >
        <Loader2 className="w-3 h-3 animate-spin" /> Menyimpan…
      </span>
    );
  }
  if (status === "saved") {
    return (
      <span
        data-testid="workspace-save-status"
        className="inline-flex items-center gap-1 text-[11px] font-ui text-emerald-600"
      >
        <CheckCircle2 className="w-3 h-3" /> Tersimpan
      </span>
    );
  }
  if (status === "dirty") {
    return (
      <span
        data-testid="workspace-save-status"
        className="inline-flex items-center gap-1 text-[11px] font-ui text-amber-600"
      >
        <CircleDot className="w-3 h-3" /> Belum tersimpan
      </span>
    );
  }
  return null;
}
