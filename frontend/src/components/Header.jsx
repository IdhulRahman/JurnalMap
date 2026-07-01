import { Link, useLocation, useNavigate } from "react-router-dom";
import { Layers, Library, Settings as SettingsIcon, LogOut, UserCircle2 } from "lucide-react";
import { toast } from "sonner";
import { useSettings } from "@/store/settings";
import { useAuth } from "@/store/auth";
import { useT } from "@/lib/useT";

export default function Header({ rightSlot = null }) {
  const loc = useLocation();
  const nav = useNavigate();
  const onProject = loc.pathname.startsWith("/project");
  const { settings } = useSettings();
  const { user, logout } = useAuth();
  const { t } = useT();
  const _theme = settings?.theme || "light";

  const onLogout = () => {
    logout();
    toast.success("Anda telah keluar");
    nav("/login", { replace: true });
  };

  return (
    <header
      data-testid="app-header"
      className="h-16 border-b border-[color:var(--jm-border)] bg-[color:var(--jm-surface)]/95 backdrop-blur-md sticky top-0 z-30"
    >
      <div className="mx-auto h-full max-w-[1600px] px-6 flex items-center justify-between">
        <Link
          to="/"
          data-testid="header-home-link"
          className="flex items-center gap-2.5 group"
        >
          <div className="w-8 h-8 rounded-md bg-[color:var(--jm-text)] flex items-center justify-center group-hover:rotate-3 transition-transform">
            <Layers className="w-4 h-4 text-[color:var(--jm-bg)]" strokeWidth={2.5} />
          </div>
          <div className="leading-tight">
            <div className="font-display text-[18px] tracking-tight text-[color:var(--jm-text)] font-semibold">
              JurnalMap
            </div>
            <div className="text-[10px] uppercase tracking-[0.18em] text-[color:var(--jm-text-3)] font-medium">
              Evidence, not verdicts
            </div>
          </div>
        </Link>
        <div className="flex items-center gap-3">
          {!onProject && (
            <div className="hidden md:flex items-center gap-2 text-xs text-[color:var(--jm-text-2)]">
              <Library className="w-3.5 h-3.5" />
              <span className="font-ui">{t("header.tagline")}</span>
            </div>
          )}
          {rightSlot}
          {user && (
            <div
              data-testid="header-user-badge"
              className="hidden sm:flex items-center gap-1.5 px-2.5 py-1.5 rounded-md border border-[color:var(--jm-border)] text-xs font-ui text-[color:var(--jm-text-2)]"
              title={user.email || user.username}
            >
              <UserCircle2 className="w-3.5 h-3.5" />
              <span className="font-semibold text-[color:var(--jm-text)]">{user.username}</span>
              {user.is_admin && (
                <span className="text-[9px] uppercase tracking-widest ml-1 px-1.5 py-0.5 rounded bg-[color:var(--jm-text)] text-[color:var(--jm-bg)]">
                  admin
                </span>
              )}
            </div>
          )}
          <Link
            to="/settings"
            data-testid="header-settings-link"
            title={t("header.settings")}
            className="w-9 h-9 rounded-md flex items-center justify-center border border-[color:var(--jm-border)] text-[color:var(--jm-text-2)] hover:bg-[color:var(--jm-sidebar)] hover:text-[color:var(--jm-text)] transition-colors"
          >
            <SettingsIcon className="w-4 h-4" />
          </Link>
          {user && (
            <button
              onClick={onLogout}
              data-testid="header-logout-btn"
              title="Keluar"
              className="w-9 h-9 rounded-md flex items-center justify-center border border-[color:var(--jm-border)] text-[color:var(--jm-text-2)] hover:bg-[color:var(--jm-sidebar)] hover:text-[color:var(--jm-text)] transition-colors"
            >
              <LogOut className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>
    </header>
  );
}
