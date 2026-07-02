import { TIER_META } from "@/lib/tiers";

const TOOLTIPS = {
  high: "Teks dirangkai langsung dari kalimat di paper. Setiap klaim dapat ditelusuri ke sumber spesifik.",
  supported: "Teks dirangkai langsung dari kalimat di paper. Setiap klaim dapat ditelusuri ke sumber spesifik.",
  
  medium: "Teks berangkat dari paper, tapi AI menambahkan jembatan logis atau konteks dari pengetahuan umum. Verifikasi sebelum digunakan.",
  similar: "Teks berangkat dari paper, tapi AI menambahkan jembatan logis atau konteks dari pengetahuan umum. Verifikasi sebelum digunakan.",
  
  low: "Teks sepenuhnya hasil generasi AI. Tidak ada dasar di paper. Jangan digunakan sebagai rujukan akademik.",
  unsupported: "Teks sepenuhnya hasil generasi AI. Tidak ada dasar di paper. Jangan digunakan sebagai rujukan akademik.",
};

export default function EvidenceBadge({ tier, label, compact = false, testId }) {
  const meta = TIER_META[tier] || TIER_META.medium;
  const { Icon } = meta;
  const tooltipText = TOOLTIPS[tier] || "";
  
  return (
    <span
      data-testid={testId || `evidence-badge-${tier}`}
      title={tooltipText}
      className={`inline-flex items-center gap-1.5 px-2 py-[3px] rounded-full text-[11px] font-semibold ${meta.className} font-ui cursor-help`}
      style={{ lineHeight: 1.2 }}
    >
      <Icon className="w-3 h-3" strokeWidth={2.5} />
      {!compact && (label || meta.label)}
    </span>
  );
}

