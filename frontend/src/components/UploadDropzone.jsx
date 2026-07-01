import { useCallback, useState } from "react";
import { UploadCloud, FileText, Loader2 } from "lucide-react";
import { useT } from "@/lib/useT";

const MAX_FILES = 5;

/**
 * Upload dropzone that accepts up to 5 PDF files.
 * Calls `onUpload(files: File[])` with the accepted files.
 */
export default function UploadDropzone({ onUpload, busy = false, maxFiles = MAX_FILES }) {
  const { t } = useT();
  const [drag, setDrag] = useState(false);
  const [hover, setHover] = useState(false);

  const accept = useCallback(
    (fileList) => {
      const arr = Array.from(fileList || []);
      const pdfs = arr.filter((f) => f && (f.type === "application/pdf" || f.name?.toLowerCase().endsWith(".pdf")));
      if (pdfs.length === 0) return;
      const selected = pdfs.slice(0, maxFiles);
      onUpload(selected);
    },
    [onUpload, maxFiles],
  );

  const onDrop = useCallback(
    (e) => {
      e.preventDefault();
      setDrag(false);
      accept(e.dataTransfer?.files);
    },
    [accept],
  );

  return (
    <label
      data-testid="upload-dropzone"
      onDragOver={(e) => {
        e.preventDefault();
        setDrag(true);
      }}
      onDragLeave={() => setDrag(false)}
      onDrop={onDrop}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      className={`block border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all
        ${drag ? "border-[var(--jm-text)] bg-[var(--jm-sidebar)]" : hover ? "border-[var(--jm-border-2)] bg-[var(--jm-surface)]" : "border-[var(--jm-border-2)] bg-[var(--jm-surface)]"}
        ${busy ? "opacity-60 pointer-events-none" : ""}
      `}
    >
      <input
        data-testid="upload-input"
        type="file"
        accept="application/pdf"
        multiple
        className="hidden"
        disabled={busy}
        onChange={(e) => {
          accept(e.target.files);
          // reset so the same file selected again triggers change
          e.target.value = "";
        }}
      />
      <div className="flex flex-col items-center gap-3">
        {busy ? (
          <Loader2 className="w-10 h-10 text-[color:var(--jm-text-2)] animate-spin" />
        ) : (
          <div className="w-12 h-12 rounded-lg bg-[color:var(--jm-sidebar)] flex items-center justify-center">
            <UploadCloud className="w-6 h-6 text-[color:var(--jm-text)]" />
          </div>
        )}
        <div>
          <div className="font-ui text-sm font-semibold text-[color:var(--jm-text)]">
            {busy ? t("upload.busy") : t("upload.drop")}
          </div>
          <div className="text-xs text-[color:var(--jm-text-3)] mt-1 font-ui">
            Maks {maxFiles} file per unggahan • Diproses di latar belakang
          </div>
        </div>
        <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.2em] text-[color:var(--jm-text-3)] font-semibold">
          <FileText className="w-3 h-3" /> PDF
        </div>
      </div>
    </label>
  );
}
