import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  ArrowLeft,
  Moon,
  Sun,
  Key,
  UserCircle2,
  Loader2,
  Save,
  Languages,
  ServerCog,
  Globe,
} from "lucide-react";
import { toast } from "sonner";
import { useSettings } from "@/store/settings";
import { useT } from "@/lib/useT";
import Header from "@/components/Header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

export default function SettingsPage() {
  const nav = useNavigate();
  const { settings, setTheme, update, reload } = useSettings();
  const { t } = useT();
  const [local, setLocal] = useState(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (settings) {
      setLocal({
        persona_id: settings.persona_id || "akademisi_ketat",
        persona_custom: settings.persona_custom || "",
        output_language: settings.output_language || "en",
        ui_language: settings.ui_language || "id",
        default_model: settings.default_model,
        local_endpoint: settings.local_endpoint || "",
        local_model: settings.local_model || "",
        gemini_key: "",
        openai_key: "",
        anthropic_key: "",
        local_api_key: "",
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

  const save = async (patch) => {
    setSaving(true);
    try {
      await update(patch);
      toast.success(t("settings.saved"));
      await reload();
    } catch {
      toast.error("Save failed");
    } finally {
      setSaving(false);
    }
  };

  const saveAll = async () => {
    const patch = {
      persona_id: local.persona_id,
      persona_custom: local.persona_custom,
      output_language: local.output_language,
      ui_language: local.ui_language,
      default_model: local.default_model,
      local_endpoint: local.local_endpoint,
      local_model: local.local_model,
    };
    if (local.gemini_key) patch.gemini_key = local.gemini_key;
    if (local.openai_key) patch.openai_key = local.openai_key;
    if (local.anthropic_key) patch.anthropic_key = local.anthropic_key;
    if (local.local_api_key) patch.local_api_key = local.local_api_key;
    await save(patch);
    setLocal((s) => ({ ...s, gemini_key: "", openai_key: "", anthropic_key: "", local_api_key: "" }));
  };

  const clearKey = async (which) => save({ [which]: "" });

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
        <Section testId="settings-theme-section" icon={settings.theme === "dark" ? Moon : Sun} title={t("settings.theme")}>
          <div className="flex items-center gap-2">
            <Pill
              testId="theme-light-btn"
              active={settings.theme === "light"}
              icon={Sun}
              label={t("settings.theme.light")}
              onClick={() => setTheme("light")}
            />
            <Pill
              testId="theme-dark-btn"
              active={settings.theme === "dark"}
              icon={Moon}
              label={t("settings.theme.dark")}
              onClick={() => setTheme("dark")}
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
                save({ ui_language: "id" });
              }}
            />
            <Pill
              testId="uilang-en-btn"
              active={local.ui_language === "en"}
              label="English"
              onClick={() => {
                setLocal((s) => ({ ...s, ui_language: "en" }));
                save({ ui_language: "en" });
              }}
            />
          </div>
        </Section>

        {/* Output language */}
        <Section testId="settings-outlang-section" icon={Globe} title={t("settings.outLang")} hint={t("settings.outLang.hint")}>
          <div className="flex items-center gap-2">
            <Pill
              testId="outlang-en-btn"
              active={local.output_language === "en"}
              label="English"
              onClick={() => setLocal((s) => ({ ...s, output_language: "en" }))}
            />
            <Pill
              testId="outlang-id-btn"
              active={local.output_language === "id"}
              label="Bahasa Indonesia"
              onClick={() => setLocal((s) => ({ ...s, output_language: "id" }))}
            />
          </div>
        </Section>

        {/* API Keys */}
        <Section testId="settings-keys-section" icon={Key} title={t("settings.keys")} hint={t("settings.keys.hint")}>
          <KeyField label="Gemini API Key" testId="gemini-key" placeholder={settings.gemini_key_masked || "AIza..."}
                    value={local.gemini_key} onChange={(v) => setLocal((s) => ({ ...s, gemini_key: v }))}
                    hasKey={settings.has_gemini_key} onClear={() => clearKey("gemini_key")} />
          <KeyField label="OpenAI API Key" testId="openai-key" placeholder={settings.openai_key_masked || "sk-..."}
                    value={local.openai_key} onChange={(v) => setLocal((s) => ({ ...s, openai_key: v }))}
                    hasKey={settings.has_openai_key} onClear={() => clearKey("openai_key")} />
          <KeyField label="Anthropic API Key" testId="anthropic-key" placeholder={settings.anthropic_key_masked || "sk-ant-..."}
                    value={local.anthropic_key} onChange={(v) => setLocal((s) => ({ ...s, anthropic_key: v }))}
                    hasKey={settings.has_anthropic_key} onClear={() => clearKey("anthropic_key")} last />
        </Section>

        {/* Local model */}
        <Section testId="settings-local-section" icon={ServerCog} title={t("settings.local")} hint={t("settings.local.hint")}>
          <div className="space-y-3">
            <Labeled label={t("settings.local.endpoint")}>
              <Input data-testid="local-endpoint-input" value={local.local_endpoint}
                     onChange={(e) => setLocal((s) => ({ ...s, local_endpoint: e.target.value }))}
                     placeholder="http://localhost:11434/v1"
                     className="bg-[color:var(--jm-surface)] border-[color:var(--jm-border)] text-[color:var(--jm-text)]" />
            </Labeled>
            <Labeled label={t("settings.local.model")}>
              <Input data-testid="local-model-input" value={local.local_model}
                     onChange={(e) => setLocal((s) => ({ ...s, local_model: e.target.value }))}
                     placeholder="llama3.1:8b"
                     className="bg-[color:var(--jm-surface)] border-[color:var(--jm-border)] text-[color:var(--jm-text)]" />
            </Labeled>
            <Labeled label={t("settings.local.key")}>
              <Input data-testid="local-api-key-input" type="password" autoComplete="off" value={local.local_api_key}
                     onChange={(e) => setLocal((s) => ({ ...s, local_api_key: e.target.value }))}
                     placeholder="ollama"
                     className="bg-[color:var(--jm-surface)] border-[color:var(--jm-border)] text-[color:var(--jm-text)]" />
            </Labeled>
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
              {settings.personas.map((p) => (
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
        </Section>

        {/* Default model */}
        <Section testId="settings-model-section" title={t("settings.model")} hint={t("settings.model.hint")}>
          <Select value={local.default_model} onValueChange={(v) => setLocal((s) => ({ ...s, default_model: v }))}>
            <SelectTrigger data-testid="default-model-select"
                           className="bg-[color:var(--jm-surface)] border-[color:var(--jm-border)] text-[color:var(--jm-text)]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {settings.available_models.map((m) => (
                <SelectItem key={`${m.provider}-${m.id}-${m.label}`} data-testid={`model-option-${m.id}`} value={m.id}>
                  {m.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Section>

        <div className="flex justify-end">
          <Button data-testid="settings-save-btn" onClick={saveAll} disabled={saving}
                  className="bg-[color:var(--jm-text)] text-[color:var(--jm-bg)] hover:opacity-90 gap-2">
            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
            {t("settings.save")}
          </Button>
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

function Labeled({ label, children }) {
  return (
    <div>
      <label className="text-[11px] uppercase tracking-[0.18em] font-semibold text-[color:var(--jm-text-3)]">
        {label}
      </label>
      <div className="mt-1">{children}</div>
    </div>
  );
}

function KeyField({ label, testId, placeholder, value, onChange, hasKey, onClear, last = false }) {
  return (
    <div className={last ? "" : "mb-4"}>
      <div className="flex items-center justify-between mb-1">
        <label className="text-[11px] uppercase tracking-[0.18em] font-semibold text-[color:var(--jm-text-3)]">
          {label}
        </label>
        {hasKey && (
          <button
            data-testid={`${testId}-clear-btn`}
            onClick={onClear}
            className="text-[10px] uppercase tracking-[0.18em] font-semibold text-[color:var(--jm-low-fg)] hover:underline"
          >
            Hapus / Clear
          </button>
        )}
      </div>
      <Input
        data-testid={`${testId}-input`}
        type="password"
        autoComplete="off"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="bg-[color:var(--jm-surface)] border-[color:var(--jm-border)] text-[color:var(--jm-text)]"
      />
    </div>
  );
}
