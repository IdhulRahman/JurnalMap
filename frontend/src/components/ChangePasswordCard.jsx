import { useState } from "react";
import { Loader2, KeyRound, ShieldCheck } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/services/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import PasswordStrength from "@/components/PasswordStrength";
import { evaluatePassword } from "@/lib/passwordPolicy";

export default function ChangePasswordCard() {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);

  const { valid } = evaluatePassword(next);
  const canSubmit = current.length > 0 && valid && confirm === next && next !== current && !busy;

  const submit = async (e) => {
    e.preventDefault();
    if (!canSubmit) {
      if (!current) toast.error("Isi kata sandi saat ini");
      else if (next === current) toast.error("Kata sandi baru harus berbeda dari yang lama");
      else if (!valid) toast.error("Kata sandi baru belum memenuhi kebijakan");
      else if (confirm !== next) toast.error("Konfirmasi kata sandi tidak cocok");
      return;
    }
    setBusy(true);
    try {
      await api.changePassword(current, next);
      toast.success("Kata sandi berhasil diubah");
      setCurrent("");
      setNext("");
      setConfirm("");
    } catch (err) {
      const detail = err?.response?.data?.detail;
      if (Array.isArray(detail)) toast.error(detail[0]?.msg || "Gagal mengubah kata sandi");
      else if (typeof detail === "string") toast.error(detail);
      else toast.error("Gagal mengubah kata sandi");
    } finally {
      setBusy(false);
    }
  };

  return (
    <section
      data-testid="settings-changepwd-section"
      className="rounded-xl border border-[color:var(--jm-border)] bg-[color:var(--jm-surface)] p-6 mb-6"
    >
      <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.22em] font-semibold text-[color:var(--jm-text-3)] mb-1">
        <ShieldCheck className="w-3.5 h-3.5" />
        Ganti Kata Sandi
      </div>
      <p className="text-xs text-[color:var(--jm-text-2)] font-ui mb-4">
        Diperlukan kata sandi saat ini untuk konfirmasi. Kata sandi baru harus memenuhi kebijakan keamanan.
      </p>

      <form onSubmit={submit} className="space-y-4">
        <div>
          <label className="text-[11px] uppercase tracking-[0.18em] font-semibold text-[color:var(--jm-text-3)]">
            Kata sandi saat ini
          </label>
          <Input
            data-testid="changepwd-current-input"
            type="password"
            autoComplete="current-password"
            value={current}
            onChange={(e) => setCurrent(e.target.value)}
            className="mt-1"
            disabled={busy}
          />
        </div>
        <div>
          <label className="text-[11px] uppercase tracking-[0.18em] font-semibold text-[color:var(--jm-text-3)]">
            Kata sandi baru
          </label>
          <Input
            data-testid="changepwd-new-input"
            type="password"
            autoComplete="new-password"
            value={next}
            onChange={(e) => setNext(e.target.value)}
            className="mt-1"
            disabled={busy}
          />
          <PasswordStrength password={next} testId="changepwd-strength" />
        </div>
        <div>
          <label className="text-[11px] uppercase tracking-[0.18em] font-semibold text-[color:var(--jm-text-3)]">
            Konfirmasi kata sandi baru
          </label>
          <Input
            data-testid="changepwd-confirm-input"
            type="password"
            autoComplete="new-password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            className="mt-1"
            disabled={busy}
          />
          {confirm && confirm !== next && (
            <div className="mt-1 text-[11px] text-rose-600">Konfirmasi tidak cocok.</div>
          )}
        </div>

        <div className="flex justify-end">
          <Button
            data-testid="changepwd-submit"
            type="submit"
            disabled={!canSubmit}
            className="bg-[color:var(--jm-text)] text-[color:var(--jm-bg)] hover:opacity-90 gap-2 disabled:opacity-60"
          >
            {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <KeyRound className="w-4 h-4" />}
            Ubah kata sandi
          </Button>
        </div>
      </form>
    </section>
  );
}
