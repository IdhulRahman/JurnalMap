/* Export the matrix to Markdown or CSV strings, then trigger a download. */

function csvEscape(v) {
  const s = (v ?? "").toString();
  if (/[",\n]/.test(s)) return `"${s.replace(/"/g, '""')}"`;
  return s;
}

function fieldLabel(field, labelMap) {
  return labelMap[field] || field;
}

export function matrixToMarkdown(data, labelMap = {}, methodLabel = "") {
  const fields = data.fields || [];
  const header = ["Journal", ...fields.map((f) => fieldLabel(f, labelMap))];
  const lines = [];
  if (methodLabel) lines.push(`# Matrix — ${methodLabel}`, "");
  lines.push(`| ${header.join(" | ")} |`);
  lines.push(`| ${header.map(() => "---").join(" | ")} |`);
  for (const row of data.rows || []) {
    const cells = [row.title, ...fields.map((f) => {
      const c = row.cells.find((x) => x.field === f);
      return ((c?.value || "—").replace(/\|/g, "\\|")).replace(/\n/g, " ");
    })];
    lines.push(`| ${cells.join(" | ")} |`);
  }
  // sources section
  const sources = [];
  for (const row of data.rows || []) {
    for (const c of row.cells || []) {
      if (c.excerpt) sources.push(`- **${row.title}** — _${fieldLabel(c.field, labelMap)}_${c.page ? ` (p.${c.page})` : ""}: “${c.excerpt}”`);
    }
  }
  if (sources.length) {
    lines.push("", "## Source quotes", "", ...sources);
  }
  return lines.join("\n");
}

export function matrixToCsv(data, labelMap = {}) {
  const fields = data.fields || [];
  const header = ["journal", ...fields, ...fields.map((f) => `${f}__excerpt`), ...fields.map((f) => `${f}__page`)];
  const lines = [header.map((h) => fieldLabel(h, labelMap)).map(csvEscape).join(",")];
  for (const row of data.rows || []) {
    const map = Object.fromEntries((row.cells || []).map((c) => [c.field, c]));
    const out = [row.title];
    for (const f of fields) out.push(map[f]?.value || "");
    for (const f of fields) out.push(map[f]?.excerpt || "");
    for (const f of fields) out.push(map[f]?.page ?? "");
    lines.push(out.map(csvEscape).join(","));
  }
  return lines.join("\n");
}

export function download(filename, content, mime = "text/plain") {
  const blob = new Blob([content], { type: `${mime};charset=utf-8` });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
