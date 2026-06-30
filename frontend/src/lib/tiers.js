import { CheckCircle2, AlertTriangle, XCircle } from "lucide-react";

export const TIER_META = {
  high: {
    label: "Bukti kuat",
    Icon: CheckCircle2,
    className: "tier-high",
    color: "#059669",
    overlay: "rgba(5, 150, 105, 0.18)",
    border: "#059669",
  },
  medium: {
    label: "Bukti parsial",
    Icon: AlertTriangle,
    className: "tier-medium",
    color: "#d97706",
    overlay: "rgba(217, 119, 6, 0.18)",
    border: "#d97706",
  },
  low: {
    label: "Bukti lemah",
    Icon: XCircle,
    className: "tier-low",
    color: "#dc2626",
    overlay: "rgba(220, 38, 38, 0.16)",
    border: "#dc2626",
  },
};

export const CATEGORY_LABEL = {
  objective: "Tujuan",
  method: "Metode",
  finding: "Temuan",
  limitation: "Keterbatasan",
};

export const FIELD_LABEL = {
  objective: "Tujuan",
  method: "Metode",
  sample: "Sampel",
  key_finding: "Temuan Utama",
  limitation: "Keterbatasan",
};
