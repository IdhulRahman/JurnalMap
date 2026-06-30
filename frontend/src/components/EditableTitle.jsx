import { useEffect, useRef, useState } from "react";
import { Pencil, Check, X, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/services/api";
import { useT } from "@/lib/useT";

/**
 * Editable document title. Renders the title as text plus a small pencil button.
 * Clicking the pencil swaps in an inline input; ⏎ saves, Esc cancels.
 *
 * Props:
 *   documentId   – id of the doc
 *   value        – current title text
 *   onSaved(t)   – called with the saved title
 *   className    – wrapper class for the static text
 *   inputClass   – class applied to the inline input
 *   variant      – "title" (large) | "row" (small)
 *   testIdPrefix – data-testid prefix (default "edit-title")
 */
export default function EditableTitle({
  documentId,
  value,
  onSaved,
  className = "",
  inputClass = "",
  variant = "row",
  testIdPrefix = "edit-title",
}) {
  const { t } = useT();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value || "");
  const [saving, setSaving] = useState(false);
  const inputRef = useRef(null);

  useEffect(() => {
    if (!editing) setDraft(value || "");
  }, [value, editing]);

  useEffect(() => {
    if (editing && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [editing]);

  const save = async () => {
    const next = draft.trim();
    if (!next) {
      toast.error(t("title.empty"));
      return;
    }
    if (next === (value || "")) {
      setEditing(false);
      return;
    }
    setSaving(true);
    try {
      const updated = await api.updateDocumentTitle(documentId, next);
      toast.success(t("title.updated"));
      onSaved?.(updated.title);
      setEditing(false);
    } catch (e) {
      const detail = e?.response?.data?.detail;
      toast.error(detail || t("title.empty"));
    } finally {
      setSaving(false);
    }
  };

  const cancel = () => {
    setDraft(value || "");
    setEditing(false);
  };

  if (editing) {
    return (
      <div className="flex items-center gap-1.5 min-w-0 flex-1">
        <input
          ref={inputRef}
          data-testid={`${testIdPrefix}-input`}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") save();
            if (e.key === "Escape") cancel();
          }}
          placeholder={t("title.placeholder")}
          className={`flex-1 min-w-0 px-2 py-1 rounded border border-[color:var(--jm-text)] bg-[color:var(--jm-surface)] text-[color:var(--jm-text)] outline-none font-ui ${inputClass}`}
        />
        <button
          data-testid={`${testIdPrefix}-save`}
          onClick={save}
          disabled={saving}
          title={t("title.save")}
          className="p-1.5 rounded bg-[color:var(--jm-text)] text-[color:var(--jm-bg)] hover:opacity-90 disabled:opacity-50"
        >
          {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-3.5 h-3.5" />}
        </button>
        <button
          data-testid={`${testIdPrefix}-cancel`}
          onClick={cancel}
          disabled={saving}
          title={t("title.cancel")}
          className="p-1.5 rounded border border-[color:var(--jm-border)] hover:bg-[color:var(--jm-sidebar)]"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      </div>
    );
  }

  return (
    <div className={`flex items-center gap-1.5 min-w-0 group ${variant === "title" ? "" : "flex-1"}`}>
      <span data-testid={`${testIdPrefix}-value`} className={`truncate ${className}`} title={value || ""}>
        {value || "—"}
      </span>
      <button
        data-testid={`${testIdPrefix}-edit`}
        onClick={(e) => {
          e.preventDefault();
          e.stopPropagation();
          setEditing(true);
        }}
        title={t("title.edit")}
        className="p-1 rounded text-[color:var(--jm-text-3)] hover:text-[color:var(--jm-text)] hover:bg-[color:var(--jm-sidebar)] opacity-0 group-hover:opacity-100 transition-opacity"
      >
        <Pencil className="w-3.5 h-3.5" />
      </button>
    </div>
  );
}
