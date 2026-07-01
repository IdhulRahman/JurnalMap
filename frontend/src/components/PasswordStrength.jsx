import { evaluatePassword } from "@/lib/passwordPolicy";
import { Check, X } from "lucide-react";

export default function PasswordStrength({ password, testId = "pwd-strength" }) {
  const { results, strength, valid } = evaluatePassword(password || "");
  const width = `${Math.round(strength * 100)}%`;
  const color =
    strength >= 1 ? "bg-emerald-500" : strength >= 0.75 ? "bg-lime-500" : strength >= 0.5 ? "bg-amber-500" : "bg-rose-500";

  return (
    <div data-testid={testId} className="mt-2">
      <div className="w-full h-1.5 rounded-full bg-[color:var(--jm-sidebar)] overflow-hidden">
        <div className={`h-full transition-all ${color}`} style={{ width }} />
      </div>
      <ul className="mt-2 grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-1 text-xs font-ui">
        {results.map((r) => (
          <li
            key={r.id}
            data-testid={`${testId}-rule-${r.id}`}
            className={`flex items-center gap-1.5 ${r.ok ? "text-emerald-600" : "text-[color:var(--jm-text-3)]"}`}
          >
            {r.ok ? <Check className="w-3.5 h-3.5" /> : <X className="w-3.5 h-3.5" />}
            <span>{r.label}</span>
          </li>
        ))}
      </ul>
      {password && !valid && (
        <div className="mt-1 text-[11px] text-[color:var(--jm-text-3)]">
          Kata sandi belum memenuhi kebijakan keamanan.
        </div>
      )}
    </div>
  );
}
