import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Layers, Loader2, KeyRound } from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "@/store/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import PasswordStrength from "@/components/PasswordStrength";
import { evaluatePassword } from "@/lib/passwordPolicy";

export default function ForgotPasswordPage() {
  const nav = useNavigate();
  const { token, forgotPassword } = useAuth();

  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (token) nav("/", { replace: true });
  }, [token, nav]);

  const { valid } = evaluatePassword(newPassword);
  const emailValid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
  const canSubmit = username.trim().length >= 3 && emailValid && valid && confirm === newPassword && !busy;

  const submit = async (e) => {
    e.preventDefault();
    if (!canSubmit) {
      toast.error("Lengkapi semua kolom dengan benar");
      return;
    }
    setBusy(true);
    try {
      await forgotPassword({
        username: username.trim(),
        email: email.trim(),
        new_password: newPassword,
      });
      toast.success("Kata sandi berhasil diatur ulang!");
      nav("/", { replace: true });
    } catch (err) {
      const detail = err?.response?.data?.detail;
      if (Array.isArray(detail)) toast.error(detail[0]?.msg || "Gagal mengatur ulang");
      else if (typeof detail === "string") toast.error(detail);
      else toast.error("Gagal mengatur ulang kata sandi");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-[color:var(--jm-bg)] px-4 py-10">
      <div className="w-full max-w-md">
        <Link to="/" className="flex items-center justify-center gap-2.5 mb-8">
          <div className="w-9 h-9 rounded-md bg-[color:var(--jm-text)] flex items-center justify-center">
            <Layers className="w-4 h-4 text-[color:var(--jm-bg)]" strokeWidth={2.5} />
          </div>
          <div className="leading-tight text-left">
            <div className="font-display text-xl tracking-tight text-[color:var(--jm-text)] font-semibold">
              JurnalMap
            </div>
            <div className="text-[10px] uppercase tracking-[0.18em] text-[color:var(--jm-text-3)] font-medium">
              Evidence, not verdicts
            </div>
          </div>
        </Link>

        <form
          data-testid="forgot-form"
          onSubmit={submit}
          className="rounded-2xl border border-[color:var(--jm-border)] bg-[color:var(--jm-surface)] p-8 shadow-sm"
        >
          <h1 className="font-display text-2xl font-semibold text-[color:var(--jm-text)] mb-1">
            Lupa kata sandi
          </h1>
          <p className="text-sm text-[color:var(--jm-text-2)] font-ui mb-6">
            Verifikasi kepemilikan akun dengan nama pengguna + email yang terdaftar, lalu tetapkan kata sandi baru.
          </p>

          <div className="space-y-4">
            <div>
              <label className="text-[11px] uppercase tracking-[0.18em] font-semibold text-[color:var(--jm-text-3)]">
                Nama pengguna
              </label>
              <Input data-testid="forgot-username-input" value={username} onChange={(e) => setUsername(e.target.value)} className="mt-1" disabled={busy} />
            </div>
            <div>
              <label className="text-[11px] uppercase tracking-[0.18em] font-semibold text-[color:var(--jm-text-3)]">
                Email terdaftar
              </label>
              <Input data-testid="forgot-email-input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} className="mt-1" disabled={busy} />
            </div>
            <div>
              <label className="text-[11px] uppercase tracking-[0.18em] font-semibold text-[color:var(--jm-text-3)]">
                Kata sandi baru
              </label>
              <Input data-testid="forgot-newpwd-input" type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} className="mt-1" disabled={busy} />
              <PasswordStrength password={newPassword} testId="forgot-strength" />
            </div>
            <div>
              <label className="text-[11px] uppercase tracking-[0.18em] font-semibold text-[color:var(--jm-text-3)]">
                Konfirmasi kata sandi baru
              </label>
              <Input data-testid="forgot-confirm-input" type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} className="mt-1" disabled={busy} />
              {confirm && confirm !== newPassword && (
                <div className="mt-1 text-[11px] text-rose-600">Konfirmasi tidak cocok.</div>
              )}
            </div>
          </div>

          <Button
            data-testid="forgot-submit"
            type="submit"
            disabled={!canSubmit}
            className="mt-6 w-full bg-[color:var(--jm-text)] text-[color:var(--jm-bg)] hover:opacity-90 gap-2 disabled:opacity-60"
          >
            {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <KeyRound className="w-4 h-4" />}
            Atur ulang kata sandi
          </Button>

          <div className="mt-4 text-center text-xs font-ui text-[color:var(--jm-text-2)]">
            Ingat kata sandi Anda?{" "}
            <Link data-testid="forgot-back-login" to="/login" className="text-[color:var(--jm-text)] font-semibold hover:underline">
              Kembali ke Masuk
            </Link>
          </div>
        </form>
      </div>
    </div>
  );
}
