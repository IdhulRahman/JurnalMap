import { TIER_META } from "@/lib/tiers";

export default function EvidenceBadge({ tier, label, compact = false, testId }) {
  const meta = TIER_META[tier] || TIER_META.medium;
  const { Icon } = meta;
  return (
    <span
      data-testid={testId || `evidence-badge-${tier}`}
      className={`inline-flex items-center gap-1.5 px-2 py-[3px] rounded-full text-[11px] font-semibold ${meta.className} font-ui`}
      style={{ lineHeight: 1.2 }}
    >
      <Icon className="w-3 h-3" strokeWidth={2.5} />
      {!compact && (label || meta.label)}
    </span>
  );
}
