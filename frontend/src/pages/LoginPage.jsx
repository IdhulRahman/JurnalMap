import { useEffect, useMemo, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { Layers, Loader2, LogIn, Lock, AlertCircle } from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "@/store/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export default function LoginPage() {
  const nav = useNavigate();
  const loc = useLocation();
  const { token, login } = useAuth();
  const from = loc.state?.from || "/";

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [remainingAttempts, setRemainingAttempts] = useState(null);
  const [lockUntil, setLockUntil] = useState(0); // epoch seconds
  const [now, setNow] = useState(Date.now() / 1000);

  // 1-second ticker for lockout countdown
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now() / 1000), 1000);
    return () => clearInterval(t);
  }, []);

  const secondsLeft = Math.max(0, Math.ceil(lockUntil - now));
  const isLocked = secondsLeft > 0;

  useEffect(() => {
    if (token) nav(from, { replace: true });
  }, [token, from, nav]);

  const errorMessage = useMemo(() => {
    if (isLocked) {
      return `Akun terkunci sementara. Coba lagi dalam ${secondsLeft} detik, atau gunakan Lupa Kata Sandi.`;
    }
    if (remainingAttempts != null) {
      return `Kata sandi salah. Sisa percobaan: ${remainingAttempts}.`;
    }
    return null;
  }, [isLocked, secondsLeft, remainingAttempts]);

  const submit = async (e) => {
    e.preventDefault();
    if (isLocked) return;
    if (!username.trim() || !password) {
      toast.error("Isi nama pengguna dan kata sandi");
      return;
    }
    setBusy(true);
    try {
      await login(username.trim(), password);
      toast.success("Selamat datang!");
      nav(from, { replace: true });
    } catch (err) {
      const detail = err?.response?.data?.detail;
      if (detail && typeof detail === "object") {
        if (detail.locked && detail.remaining_seconds != null) {
          setLockUntil(Date.now() / 1000 + detail.remaining_seconds);
          setRemainingAttempts(null);
          toast.error(`Terlalu banyak percobaan. Menunggu ${detail.remaining_seconds}s.`);
        } else if (detail.remaining_attempts != null) {
          setRemainingAttempts(detail.remaining_attempts);
          toast.error(detail.message || "Kata sandi salah");
        } else {
          toast.error(detail.message || "Login gagal");
        }
      } else {
        toast.error(typeof detail === "string" ? detail : "Login gagal");
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-[color:var(--jm-bg)] px-4">
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
          data-testid="login-form"
          onSubmit={submit}
          className="rounded-2xl border border-[color:var(--jm-border)] bg-[color:var(--jm-surface)] p-8 shadow-sm"
        >
          <h1 className="font-display text-2xl font-semibold text-[color:var(--jm-text)] mb-1">
            Masuk
          </h1>
          <p className="text-sm text-[color:var(--jm-text-2)] font-ui mb-6">
            Masuk ke akun JurnalMap Anda.
          </p>

          <div className="space-y-4">
            <div>
              <label className="text-[11px] uppercase tracking-[0.18em] font-semibold text-[color:var(--jm-text-3)]">
                Nama pengguna
              </label>
              <Input
                data-testid="login-username-input"
                autoFocus
                autoComplete="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="admin"
                className="mt-1"
                disabled={busy || isLocked}
              />
            </div>
            <div>
              <label className="text-[11px] uppercase tracking-[0.18em] font-semibold text-[color:var(--jm-text-3)]">
                Kata sandi
              </label>
              <Input
                data-testid="login-password-input"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="mt-1"
                disabled={busy || isLocked}
              />
            </div>
          </div>

          {errorMessage && (
            <div
              data-testid="login-error"
              className="mt-4 flex items-start gap-2 rounded-md border border-rose-200 bg-rose-50 dark:bg-rose-950/40 dark:border-rose-900 px-3 py-2 text-sm text-rose-700 dark:text-rose-300"
            >
              {isLocked ? <Lock className="w-4 h-4 mt-0.5 shrink-0" /> : <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />}
              <span>{errorMessage}</span>
            </div>
          )}

          <Button
            data-testid="login-submit"
            type="submit"
            disabled={busy || isLocked}
            className="mt-6 w-full bg-[color:var(--jm-text)] text-[color:var(--jm-bg)] hover:opacity-90 gap-2"
          >
            {busy ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <LogIn className="w-4 h-4" />
            )}
            {isLocked ? `Tunggu ${secondsLeft}s…` : "Masuk"}
          </Button>

          <div className="mt-4 flex items-center justify-between text-xs font-ui">
            <Link
              data-testid="login-forgot-link"
              to="/forgot-password"
              className="text-[color:var(--jm-text-2)] hover:text-[color:var(--jm-text)] underline"
            >
              Lupa kata sandi?
            </Link>
            <Link
              data-testid="login-register-link"
              to="/register"
              className="text-[color:var(--jm-text)] font-semibold hover:underline"
            >
              Buat akun baru
            </Link>
          </div>
        </form>
      </div>
    </div>
  );
}
