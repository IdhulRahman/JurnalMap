import { Link, useLocation } from "react-router-dom";
import { Layers, Library } from "lucide-react";

export default function Header({ rightSlot = null }) {
  const loc = useLocation();
  const onProject = loc.pathname.startsWith("/project");
  return (
    <header
      data-testid="app-header"
      className="h-16 border-b border-[color:var(--jm-border)] bg-white/95 backdrop-blur-md sticky top-0 z-30"
    >
      <div className="mx-auto h-full max-w-[1600px] px-6 flex items-center justify-between">
        <Link
          to="/"
          data-testid="header-home-link"
          className="flex items-center gap-2.5 group"
        >
          <div className="w-8 h-8 rounded-md bg-[color:var(--jm-text)] flex items-center justify-center group-hover:rotate-3 transition-transform">
            <Layers className="w-4 h-4 text-white" strokeWidth={2.5} />
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
              <span className="font-ui">Pustaka Penelitian Pribadi</span>
            </div>
          )}
          {rightSlot}
        </div>
      </div>
    </header>
  );
}
