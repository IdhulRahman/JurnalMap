import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  ArrowLeft,
  Moon,
  Sun,
  Monitor,
  UserCircle2,
  Loader2,
  Save,
  Languages,
} from "lucide-react";
import { toast } from "sonner";
import { useSettings } from "@/store/settings";
import { useT } from "@/lib/useT";
import Header from "@/components/Header";
import ChangePasswordCard from "@/components/ChangePasswordCard";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

/**
 * Simplified Settings:
 *   - Appearance (Light / Dark / System)
 *   - UI Language (id / en)
 *   - AI Persona (uses server-side default; still editable)
 *   - Change password
 *
 * All LLM key / provider / model inputs are removed — models are supplied by
 * the administrator via environment variables. Per-feature output language is
 * chosen in each feature's own panel (Ringkas, Tanya), not here.
 */
export default function SettingsPage() {
  const nav = useNavigate();
  const { settings, setTheme, setUiLanguage, update, reload } = useSettings();
  const { t } = useT();
  const [local, setLocal] = useState(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (settings) {
      setLocal({
        theme: settings.theme || "system",
        ui_language: settings.ui_language || "id",
        persona_id: settings.persona_id || "akademisi_ketat",
        persona_custom: settings.persona_custom || "",
      });
    }
  }, [settings]);

  if (!settings || !local) {
    return (
      <div className="min-h-screen">
        <Header />
        <div className="p-16 text-center text-[color:var(--jm-text-3)] font-ui">{t("common.loading")}</div>
      </div>
    );
  }

  const savePersona = async () => {
    setSaving(true);
    try {
      await update({
        persona_id: local.persona_id,
        persona_custom: local.persona_custom,
      });
      toast.success(t("settings.saved"));
      await reload();
    } catch {
      toast.error("Save failed");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="min-h-screen bg-[color:var(--jm-bg)]">
      <Header />
      <main className="mx-auto max-w-3xl px-6 py-10">
        <button
          data-testid="settings-back"
          onClick={() => nav(-1)}
          className="flex items-center gap-1.5 text-xs uppercase tracking-[0.2em] font-semibold text-[color:var(--jm-text-3)] hover:text-[color:var(--jm-text)] transition-colors mb-4"
        >
          <ArrowLeft className="w-3.5 h-3.5" /> {t("common.back")}
        </button>

        <h1
          data-testid="settings-heading"
          className="font-display text-4xl sm:text-5xl tracking-tight font-semibold text-[color:var(--jm-text)] mb-2"
        >
          {t("settings.title")}
        </h1>
        <p className="text-sm text-[color:var(--jm-text-2)] font-ui mb-10">{t("settings.sub")}</p>

        {/* Theme */}
        <Section
          testId="settings-theme-section"
          icon={local.theme === "dark" ? Moon : local.theme === "system" ? Monitor : Sun}
          title={t("settings.theme")}
          hint={t("settings.theme.sub")}
        >
          <div className="flex items-center gap-2 flex-wrap">
            <Pill
              testId="theme-light-btn"
              active={local.theme === "light"}
              icon={Sun}
              label={t("settings.theme.light")}
              onClick={() => {
                setLocal((s) => ({ ...s, theme: "light" }));
                setTheme("light");
              }}
            />
            <Pill
              testId="theme-dark-btn"
              active={local.theme === "dark"}
              icon={Moon}
              label={t("settings.theme.dark")}
              onClick={() => {
                setLocal((s) => ({ ...s, theme: "dark" }));
                setTheme("dark");
              }}
            />
            <Pill
              testId="theme-system-btn"
              active={local.theme === "system"}
              icon={Monitor}
              label={t("settings.theme.system")}
              onClick={() => {
                setLocal((s) => ({ ...s, theme: "system" }));
                setTheme("system");
              }}
            />
          </div>
        </Section>

        {/* UI language */}
        <Section testId="settings-uilang-section" icon={Languages} title={t("settings.uiLang")} hint={t("settings.uiLang.hint")}>
          <div className="flex items-center gap-2">
            <Pill
              testId="uilang-id-btn"
              active={local.ui_language === "id"}
              label="Bahasa Indonesia"
              onClick={() => {
                setLocal((s) => ({ ...s, ui_language: "id" }));
                setUiLanguage("id");
              }}
            />
            <Pill
              testId="uilang-en-btn"
              active={local.ui_language === "en"}
              label="English"
              onClick={() => {
                setLocal((s) => ({ ...s, ui_language: "en" }));
                setUiLanguage("en");
              }}
            />
          </div>
        </Section>

        {/* Persona */}
        <Section testId="settings-persona-section" icon={UserCircle2} title={t("settings.persona")}>
          <Select value={local.persona_id} onValueChange={(v) => setLocal((s) => ({ ...s, persona_id: v }))}>
            <SelectTrigger data-testid="persona-select"
                           className="bg-[color:var(--jm-surface)] border-[color:var(--jm-border)] text-[color:var(--jm-text)]">
              <SelectValue placeholder="Pilih persona" />
            </SelectTrigger>
            <SelectContent>
              {settings.personas?.map((p) => (
                <SelectItem key={p.id} data-testid={`persona-option-${p.id}`} value={p.id}>{p.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          {local.persona_id === "custom" && (
            <div className="mt-3">
              <label className="text-[11px] uppercase tracking-[0.18em] font-semibold text-[color:var(--jm-text-3)]">
                {t("settings.persona.custom")}
              </label>
              <Textarea data-testid="persona-custom-input" value={local.persona_custom}
                        onChange={(e) => setLocal((s) => ({ ...s, persona_custom: e.target.value }))}
                        rows={4} placeholder={t("settings.persona.placeholder")}
                        className="mt-1 bg-[color:var(--jm-surface)] border-[color:var(--jm-border)] text-[color:var(--jm-text)]" />
            </div>
          )}
          <div className="mt-3 flex justify-end">
            <Button data-testid="settings-save-btn" onClick={savePersona} disabled={saving}
                    className="bg-[color:var(--jm-text)] text-[color:var(--jm-bg)] hover:opacity-90 gap-2">
              {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
              {t("settings.save")}
            </Button>
          </div>
        </Section>

        {/* Admin-provided models info (read-only) */}
        <Section testId="settings-model-info-section" title={t("settings.model")} hint="Disediakan oleh administrator.">
          <ul data-testid="admin-model-list" className="space-y-1.5">
            {(settings.available_models || []).map((m) => (
              <li key={`${m.provider}-${m.id}`} className="text-sm font-ui text-[color:var(--jm-text-2)] flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-[color:var(--jm-accent)]" />
                <span className="font-mono">{m.id}</span>
                <span className="text-[10px] uppercase tracking-[0.18em] text-[color:var(--jm-text-3)]">
                  {m.provider}
                </span>
              </li>
            ))}
            {(!settings.available_models || settings.available_models.length === 0) && (
              <li className="text-sm text-[color:var(--jm-text-3)] font-ui">
                Tidak ada model yang dikonfigurasi.
              </li>
            )}
          </ul>
        </Section>

        {/* Security: Change Password */}
        <div className="mt-10">
          <ChangePasswordCard />
        </div>
      </main>
    </div>
  );
}

function Section({ testId, icon: Icon, title, hint, children }) {
  return (
    <section
      data-testid={testId}
      className="rounded-xl border border-[color:var(--jm-border)] bg-[color:var(--jm-surface)] p-6 mb-6"
    >
      <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.22em] font-semibold text-[color:var(--jm-text-3)] mb-1">
        {Icon ? <Icon className="w-3.5 h-3.5" /> : null}
        {title}
      </div>
      {hint && <p className="text-xs text-[color:var(--jm-text-2)] font-ui mb-3">{hint}</p>}
      <div className={hint ? "" : "mt-3"}>{children}</div>
    </section>
  );
}

function Pill({ testId, active, icon: Icon, label, onClick }) {
  return (
    <button
      data-testid={testId}
      onClick={onClick}
      className={`px-4 py-2 rounded-md text-sm font-ui font-medium border transition-all flex items-center gap-2 ${
        active
          ? "border-[color:var(--jm-text)] bg-[color:var(--jm-text)] text-[color:var(--jm-bg)]"
          : "border-[color:var(--jm-border)] text-[color:var(--jm-text-2)] hover:border-[color:var(--jm-border-2)] bg-[color:var(--jm-surface)]"
      }`}
    >
      {Icon ? <Icon className="w-4 h-4" /> : null}
      {label}
    </button>
  );
}
