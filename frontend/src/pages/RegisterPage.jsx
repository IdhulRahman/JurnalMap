import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Layers, Loader2, UserPlus } from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "@/store/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import PasswordStrength from "@/components/PasswordStrength";
import { evaluatePassword } from "@/lib/passwordPolicy";

export default function RegisterPage() {
  const nav = useNavigate();
  const { token, register } = useAuth();

  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (token) nav("/", { replace: true });
  }, [token, nav]);

  const { valid: pwValid } = evaluatePassword(password);
  const emailValid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
  const usernameValid = username.trim().length >= 3;
  const confirmValid = confirm.length > 0 && confirm === password;

  const canSubmit = usernameValid && emailValid && pwValid && confirmValid && !busy;

  const submit = async (e) => {
    e.preventDefault();
    if (!canSubmit) {
      if (!usernameValid) toast.error("Nama pengguna minimal 3 karakter");
      else if (!emailValid) toast.error("Format email tidak valid");
      else if (!pwValid) toast.error("Kata sandi belum memenuhi kebijakan");
      else if (!confirmValid) toast.error("Konfirmasi kata sandi tidak cocok");
      return;
    }
    setBusy(true);
    try {
      await register({ username: username.trim(), email: email.trim(), password });
      toast.success("Akun berhasil dibuat!");
      nav("/", { replace: true });
    } catch (err) {
      const detail = err?.response?.data?.detail;
      if (Array.isArray(detail)) {
        toast.error(detail[0]?.msg || "Registrasi gagal");
      } else if (typeof detail === "string") {
        toast.error(detail);
      } else {
        toast.error("Registrasi gagal");
      }
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
          data-testid="register-form"
          onSubmit={submit}
          className="rounded-2xl border border-[color:var(--jm-border)] bg-[color:var(--jm-surface)] p-8 shadow-sm"
        >
          <h1 className="font-display text-2xl font-semibold text-[color:var(--jm-text)] mb-1">
            Buat akun
          </h1>
          <p className="text-sm text-[color:var(--jm-text-2)] font-ui mb-6">
            Daftar untuk mulai membangun perpustakaan jurnal Anda.
          </p>

          <div className="space-y-4">
            <div>
              <label className="text-[11px] uppercase tracking-[0.18em] font-semibold text-[color:var(--jm-text-3)]">
                Nama pengguna
              </label>
              <Input
                data-testid="register-username-input"
                autoFocus
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="contoh: rina.suryani"
                className="mt-1"
                disabled={busy}
              />
              {!usernameValid && username.length > 0 && (
                <div className="mt-1 text-[11px] text-rose-600">Minimal 3 karakter.</div>
              )}
            </div>

            <div>
              <label className="text-[11px] uppercase tracking-[0.18em] font-semibold text-[color:var(--jm-text-3)]">
                Email
              </label>
              <Input
                data-testid="register-email-input"
                type="email"
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="nama@contoh.com"
                className="mt-1"
                disabled={busy}
              />
              {!emailValid && email.length > 0 && (
                <div className="mt-1 text-[11px] text-rose-600">Format email tidak valid.</div>
              )}
            </div>

            <div>
              <label className="text-[11px] uppercase tracking-[0.18em] font-semibold text-[color:var(--jm-text-3)]">
                Kata sandi
              </label>
              <Input
                data-testid="register-password-input"
                type="password"
                autoComplete="new-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="mt-1"
                disabled={busy}
              />
              <PasswordStrength password={password} testId="register-strength" />
            </div>

            <div>
              <label className="text-[11px] uppercase tracking-[0.18em] font-semibold text-[color:var(--jm-text-3)]">
                Konfirmasi kata sandi
              </label>
              <Input
                data-testid="register-confirm-input"
                type="password"
                autoComplete="new-password"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                placeholder="Ulangi kata sandi"
                className="mt-1"
                disabled={busy}
              />
              {confirm && !confirmValid && (
                <div className="mt-1 text-[11px] text-rose-600">Konfirmasi tidak cocok.</div>
              )}
            </div>
          </div>

          <Button
            data-testid="register-submit"
            type="submit"
            disabled={!canSubmit}
            className="mt-6 w-full bg-[color:var(--jm-text)] text-[color:var(--jm-bg)] hover:opacity-90 gap-2 disabled:opacity-60"
          >
            {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <UserPlus className="w-4 h-4" />}
            Buat akun
          </Button>

          <div className="mt-4 text-center text-xs font-ui text-[color:var(--jm-text-2)]">
            Sudah punya akun?{" "}
            <Link data-testid="register-login-link" to="/login" className="text-[color:var(--jm-text)] font-semibold hover:underline">
              Masuk
            </Link>
          </div>
        </form>
      </div>
    </div>
  );
}
