// Helpers shared across Workspace components.

export const CITATION_FORMATS = [
  { id: "ieee", label: "IEEE", example: "[1]" },
  { id: "apa7", label: "APA 7", example: "(Smith, 2023)" },
  { id: "harvard", label: "Harvard", example: "(Smith, 2023)" },
];

export function newId() {
  if (typeof crypto !== "undefined" && crypto.randomUUID) return crypto.randomUUID();
  return "id-" + Math.random().toString(36).slice(2) + Date.now().toString(36);
}

export function badgeSpanHTML(badge) {
  const safeLabel = String(badge.label || "[?]")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
  return (
    `<span class="jm-citation-badge" contenteditable="false" ` +
    `data-badge-id="${escapeAttr(badge.badge_id)}" ` +
    `data-document-id="${escapeAttr(badge.document_id || "")}" ` +
    `data-sentence-id="${escapeAttr(badge.sentence_id || "")}" ` +
    `data-page="${escapeAttr(String(badge.page ?? ""))}">${safeLabel}</span>`
  );
}

export function escapeAttr(s) {
  return String(s || "")
    .replace(/&/g, "&amp;")
    .replace(/"/g, "&quot;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

// Convert HTML editor content to Markdown for export.
export function htmlToMarkdown(html) {
  if (!html) return "";
  // Parse via DOMParser for fidelity
  const doc = new DOMParser().parseFromString(`<div>${html}</div>`, "text/html");
  const root = doc.body.firstChild;
  return mdWalk(root).trim() + "\n";
}

function mdWalk(node) {
  if (!node) return "";
  let out = "";
  for (const ch of node.childNodes) {
    if (ch.nodeType === 3) {
      out += ch.textContent;
      continue;
    }
    if (ch.nodeType !== 1) continue;
    const tag = ch.tagName.toLowerCase();
    const inner = mdWalk(ch);
    if (tag === "p") out += inner + "\n\n";
    else if (tag === "br") out += "\n";
    else if (tag === "strong" || tag === "b") out += `**${inner}**`;
    else if (tag === "em" || tag === "i") out += `*${inner}*`;
    else if (tag === "h1") out += `\n# ${inner}\n\n`;
    else if (tag === "h2") out += `\n## ${inner}\n\n`;
    else if (tag === "h3") out += `\n### ${inner}\n\n`;
    else if (tag === "h4") out += `\n#### ${inner}\n\n`;
    else if (tag === "ul") out += inner + "\n";
    else if (tag === "ol") out += inner + "\n";
    else if (tag === "li") out += `- ${inner}\n`;
    else if (tag === "span" && ch.classList?.contains("jm-citation-badge")) {
      // Keep the citation marker text inline.
      out += ` ${ch.textContent}`;
    } else out += inner;
  }
  return out;
}

export function htmlToPlainText(html) {
  if (!html) return "";
  const tmp = document.createElement("div");
  tmp.innerHTML = html;
  // Convert <p> to newlines
  tmp.querySelectorAll("p").forEach((p) => {
    p.append("\n\n");
  });
  return (tmp.innerText || tmp.textContent || "").replace(/\n{3,}/g, "\n\n").trim() + "\n";
}

export function download(filename, content, mime) {
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

// Extract badge metadata array from rendered HTML
export function extractBadgesFromHTML(html, knownBadges = []) {
  const out = [];
  const tmp = document.createElement("div");
  tmp.innerHTML = html || "";
  const map = Object.fromEntries((knownBadges || []).map((b) => [b.badge_id, b]));
  tmp.querySelectorAll(".jm-citation-badge").forEach((el) => {
    const id = el.getAttribute("data-badge-id");
    if (!id) return;
    if (map[id]) {
      out.push(map[id]);
      return;
    }
    out.push({
      badge_id: id,
      label: el.textContent || "",
      document_id: el.getAttribute("data-document-id") || "",
      sentence_id: el.getAttribute("data-sentence-id") || "",
      page: el.getAttribute("data-page") || null,
      quote: "",
    });
  });
  return out;
}
