import { useCallback, useState } from "react";
import { UploadCloud, FileText, Loader2 } from "lucide-react";

export default function UploadDropzone({ onUpload, busy = false }) {
  const [drag, setDrag] = useState(false);
  const [hover, setHover] = useState(false);

  const onDrop = useCallback(
    (e) => {
      e.preventDefault();
      setDrag(false);
      const file = e.dataTransfer?.files?.[0];
      if (file && file.type === "application/pdf") onUpload(file);
    },
    [onUpload],
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
        ${drag ? "border-[color:var(--jm-text)] bg-[color:var(--jm-sidebar)]" : hover ? "border-[color:var(--jm-border-2)] bg-white" : "border-[color:var(--jm-border)] bg-white"}
        ${busy ? "opacity-60 pointer-events-none" : ""}
      `}
    >
      <input
        data-testid="upload-input"
        type="file"
        accept="application/pdf"
        className="hidden"
        disabled={busy}
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) onUpload(file);
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
            {busy ? "Mengunggah…" : "Tarik PDF ke sini atau klik untuk memilih"}
          </div>
          <div className="text-xs text-[color:var(--jm-text-3)] mt-1 font-ui">
            Maks 1 file per unggahan • Diproses di latar belakang
          </div>
        </div>
        <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.2em] text-[color:var(--jm-text-3)] font-semibold">
          <FileText className="w-3 h-3" /> PDF
        </div>
      </div>
    </label>
  );
}
