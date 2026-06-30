import { useEffect, useState } from "react";
import { toast } from "sonner";
import { FileWarning } from "lucide-react";
import { api } from "@/services/api";
import CheckFixEditor from "./CheckFixEditor";
import ReferenceManager from "./ReferenceManager";
import EvidenceDetector from "./EvidenceDetector";
import "./checkfix.css";

function download(filename, content, mime) {
  const blob = new Blob([content], { type: mime || "text/plain" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function renderMarkdown(result, sourceText) {
  if (!result) return sourceText || "";
  const lines = ["# Check & Fix — Hasil Verifikasi\n"];
  lines.push(`**Ringkasan:** ${result.summary.supported} didukung, ${result.summary.similar} mirip, ${result.summary.unsupported} tidak didukung (total ${result.summary.total} unit).\n`);
  for (const u of result.units) {
    const tag = u.status === "supported" ? "\ud83d\udfe2" : u.status === "similar" ? "\ud83d\udfe1" : "\ud83d\udd34";
    const cite = u.badge ? ` ${u.badge.label}` : "";
    if (u.kind === "list_item") lines.push(`- ${tag} ${u.text}${cite}`);
    else lines.push(`${tag} ${u.text}${cite}\n`);
  }
  if ((result.references_used || []).length) {
    lines.push("\n## Referensi yang Digunakan\n");
    result.references_used.forEach((r, i) => {
      lines.push(`${i + 1}. ${r.title}${r.authors ? ` — ${r.authors}` : ""}${r.year ? ` (${r.year})` : ""}`);
    });
  }
  return lines.join("\n") + "\n";
}

function renderPlain(result, sourceText) {
  if (!result) return sourceText || "";
  const lines = ["CHECK & FIX — HASIL VERIFIKASI", ""];
  lines.push(`Ringkasan: ${result.summary.supported} didukung, ${result.summary.similar} mirip, ${result.summary.unsupported} tidak didukung (total ${result.summary.total} unit).`);
  lines.push("");
  for (const u of result.units) {
    const tag = u.status === "supported" ? "[OK]" : u.status === "similar" ? "[~]" : "[X]";
    const cite = u.badge ? ` ${u.badge.label}` : "";
    lines.push(`${tag} ${u.text}${cite}`);
  }
  if ((result.references_used || []).length) {
    lines.push("");
    lines.push("Referensi yang Digunakan:");
    result.references_used.forEach((r, i) => {
      lines.push(`  ${i + 1}. ${r.title}${r.authors ? ` - ${r.authors}` : ""}${r.year ? ` (${r.year})` : ""}`);
    });
  }
  return lines.join("\n") + "\n";
}

export default function CheckFix({ projectId, docs }) {
  const [text, setText] = useState("");
  const [bibliography, setBibliography] = useState("");
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState(null);
  const [activeBadge, setActiveBadge] = useState(null);

  const readyDocs = (docs || []).filter((d) => d.status === "ready");

  // Load last check on mount
  useEffect(() => {
    let abort = false;
    api
      .getLastCheck(projectId)
      .then((r) => {
        if (abort || !r || !r.exists) return;
        setText(r.text || "");
        setBibliography(r.bibliography || "");
        setResult({
          units: r.units || [],
          summary: r.summary || { total: 0, supported: 0, similar: 0, unsupported: 0 },
          annotated_html: r.annotated_html || "",
          badges: r.badges || [],
          references_used: r.references_used || [],
        });
      })
      .catch(() => {});
    return () => { abort = true; };
  }, [projectId]);

  const onRun = async () => {
    if (!text.trim()) {
      toast.error("Tempelkan teks yang ingin diperiksa");
      return;
    }
    if (readyDocs.length === 0) {
      toast.error("Tidak ada jurnal siap. Unggah PDF di tab Pustaka terlebih dahulu.");
      return;
    }
    setRunning(true);
    setActiveBadge(null);
    try {
      const r = await api.runCheck(projectId, {
        text,
        bibliography,
        citation_format: "ieee",
      });
      setResult(r);
      const sup = r.summary?.supported || 0;
      const sim = r.summary?.similar || 0;
      const uns = r.summary?.unsupported || 0;
      toast.success(`Selesai: ${sup} · ${sim} · ${uns} (didukung · mirip · tidak)`);
    } catch (e) {
      const detail = e?.response?.data?.detail;
      toast.error(detail || "Gagal memeriksa teks");
    } finally {
      setRunning(false);
    }
  };

  const onClear = () => {
    if (!window.confirm("Bersihkan hasil dan input?")) return;
    setText("");
    setBibliography("");
    setResult(null);
    setActiveBadge(null);
  };

  const onExportMarkdown = () => {
    const name = `check-fix-${Date.now()}.md`;
    download(name, renderMarkdown(result, text), "text/markdown");
  };
  const onExportText = () => {
    const name = `check-fix-${Date.now()}.txt`;
    download(name, renderPlain(result, text), "text/plain");
  };

  return (
    <div data-testid="checkfix-root" className="grid grid-cols-1 lg:grid-cols-12 gap-4">
      <div className="lg:col-span-8 space-y-3">
        {readyDocs.length === 0 && (
          <div
            data-testid="checkfix-no-docs"
            className="flex items-start gap-2 p-3 rounded-md border border-amber-200 bg-amber-50 text-amber-800 text-xs font-ui"
          >
            <FileWarning className="w-4 h-4 shrink-0 mt-0.5" />
            <span>
              Tidak ada jurnal siap di proyek ini. Unggah PDF di tab Pustaka terlebih dahulu agar pemeriksaan bisa mencari sumber.
            </span>
          </div>
        )}
        <CheckFixEditor
          text={text}
          setText={setText}
          bibliography={bibliography}
          setBibliography={setBibliography}
          running={running}
          result={result}
          onRun={onRun}
          onClear={onClear}
          onBadgeClick={(b) => setActiveBadge(b)}
          onExportMarkdown={onExportMarkdown}
          onExportText={onExportText}
        />
      </div>
      <div className="lg:col-span-4 space-y-4">
        <ReferenceManager
          badges={result?.badges || []}
          onSelectBadge={(b) => setActiveBadge(b)}
          activeBadgeId={activeBadge?.badge_id}
        />
        <EvidenceDetector projectId={projectId} badge={activeBadge} />
      </div>
    </div>
  );
}
