import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, Moon, Sun, Key, UserCircle2, Loader2, Save } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/services/api";
import { useSettings } from "@/store/settings";
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
  const [local, setLocal] = useState(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (settings) {
      setLocal({
        persona_id: settings.persona_id || "akademisi_ketat",
        persona_custom: settings.persona_custom || "",
        default_model: settings.default_model,
        gemini_key: "",
        openai_key: "",
        anthropic_key: "",
      });
    }
  }, [settings]);

  if (!settings || !local) {
    return (
      <div className="min-h-screen">
        <Header />
        <div className="p-16 text-center text-[color:var(--jm-text-3)] font-ui">Memuat…</div>
      </div>
    );
  }

  const save = async (patch) => {
    setSaving(true);
    try {
      await update(patch);
      toast.success("Tersimpan");
      await reload();
    } catch {
      toast.error("Gagal menyimpan");
    } finally {
      setSaving(false);
    }
  };

  const saveAll = async () => {
    const patch = {
      persona_id: local.persona_id,
      persona_custom: local.persona_custom,
      default_model: local.default_model,
    };
    // only send keys if user typed new value (not empty masked)
    if (local.gemini_key) patch.gemini_key = local.gemini_key;
    if (local.openai_key) patch.openai_key = local.openai_key;
    if (local.anthropic_key) patch.anthropic_key = local.anthropic_key;
    await save(patch);
    setLocal((s) => ({ ...s, gemini_key: "", openai_key: "", anthropic_key: "" }));
  };

  const clearKey = async (which) => {
    await save({ [which]: "" });
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
          <ArrowLeft className="w-3.5 h-3.5" /> Kembali
        </button>

        <h1
          data-testid="settings-heading"
          className="font-display text-4xl sm:text-5xl tracking-tight font-semibold text-[color:var(--jm-text)] mb-2"
        >
          Pengaturan
        </h1>
        <p className="text-sm text-[color:var(--jm-text-2)] font-ui mb-10">
          Konfigurasi tema, kunci API, dan persona AI untuk seluruh pustaka Anda.
        </p>

        {/* Theme */}
        <section
          data-testid="settings-theme-section"
          className="rounded-xl border border-[color:var(--jm-border)] bg-[color:var(--jm-surface)] p-6 mb-6"
        >
          <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.22em] font-semibold text-[color:var(--jm-text-3)] mb-3">
            {settings.theme === "dark" ? <Moon className="w-3.5 h-3.5" /> : <Sun className="w-3.5 h-3.5" />}
            Tema Pencahayaan
          </div>
          <div className="flex items-center gap-2">
            <button
              data-testid="theme-light-btn"
              onClick={() => setTheme("light")}
              className={`px-4 py-2 rounded-md text-sm font-ui font-medium border transition-all flex items-center gap-2 ${
                settings.theme === "light"
                  ? "border-[color:var(--jm-text)] bg-[color:var(--jm-text)] text-white"
                  : "border-[color:var(--jm-border)] text-[color:var(--jm-text-2)] hover:border-[color:var(--jm-border-2)] bg-[color:var(--jm-surface)]"
              }`}
            >
              <Sun className="w-4 h-4" /> Terang
            </button>
            <button
              data-testid="theme-dark-btn"
              onClick={() => setTheme("dark")}
              className={`px-4 py-2 rounded-md text-sm font-ui font-medium border transition-all flex items-center gap-2 ${
                settings.theme === "dark"
                  ? "border-[color:var(--jm-text)] bg-[color:var(--jm-text)] text-white"
                  : "border-[color:var(--jm-border)] text-[color:var(--jm-text-2)] hover:border-[color:var(--jm-border-2)] bg-[color:var(--jm-surface)]"
              }`}
            >
              <Moon className="w-4 h-4" /> Gelap
            </button>
          </div>
        </section>

        {/* API Keys */}
        <section
          data-testid="settings-keys-section"
          className="rounded-xl border border-[color:var(--jm-border)] bg-[color:var(--jm-surface)] p-6 mb-6"
        >
          <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.22em] font-semibold text-[color:var(--jm-text-3)] mb-1">
            <Key className="w-3.5 h-3.5" /> Kunci API LLM
          </div>
          <p className="text-xs text-[color:var(--jm-text-2)] font-ui mb-4">
            Opsional. Jika kosong, JurnalMap memakai Emergent Universal LLM Key. Kunci yang Anda masukkan disimpan di server dan hanya digunakan untuk panggilan LLM Anda.
          </p>

          <KeyField
            label="Gemini API Key"
            testId="gemini-key"
            placeholder={settings.gemini_key_masked || "AIza... (Google AI Studio)"}
            value={local.gemini_key}
            onChange={(v) => setLocal((s) => ({ ...s, gemini_key: v }))}
            hasKey={settings.has_gemini_key}
            onClear={() => clearKey("gemini_key")}
          />
          <KeyField
            label="OpenAI API Key"
            testId="openai-key"
            placeholder={settings.openai_key_masked || "sk-... (platform.openai.com)"}
            value={local.openai_key}
            onChange={(v) => setLocal((s) => ({ ...s, openai_key: v }))}
            hasKey={settings.has_openai_key}
            onClear={() => clearKey("openai_key")}
          />
          <KeyField
            label="Anthropic API Key"
            testId="anthropic-key"
            placeholder={settings.anthropic_key_masked || "sk-ant-... (console.anthropic.com)"}
            value={local.anthropic_key}
            onChange={(v) => setLocal((s) => ({ ...s, anthropic_key: v }))}
            hasKey={settings.has_anthropic_key}
            onClear={() => clearKey("anthropic_key")}
            last
          />
        </section>

        {/* Persona */}
        <section
          data-testid="settings-persona-section"
          className="rounded-xl border border-[color:var(--jm-border)] bg-[color:var(--jm-surface)] p-6 mb-6"
        >
          <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.22em] font-semibold text-[color:var(--jm-text-3)] mb-3">
            <UserCircle2 className="w-3.5 h-3.5" /> Persona AI (System Prompt)
          </div>
          <Select
            value={local.persona_id}
            onValueChange={(v) => setLocal((s) => ({ ...s, persona_id: v }))}
          >
            <SelectTrigger
              data-testid="persona-select"
              className="bg-[color:var(--jm-surface)] border-[color:var(--jm-border)] text-[color:var(--jm-text)]"
            >
              <SelectValue placeholder="Pilih persona" />
            </SelectTrigger>
            <SelectContent>
              {settings.personas.map((p) => (
                <SelectItem
                  key={p.id}
                  data-testid={`persona-option-${p.id}`}
                  value={p.id}
                >
                  {p.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {local.persona_id === "custom" && (
            <div className="mt-3">
              <label className="text-[11px] uppercase tracking-[0.18em] font-semibold text-[color:var(--jm-text-3)]">
                Instruksi Khusus
              </label>
              <Textarea
                data-testid="persona-custom-input"
                value={local.persona_custom}
                onChange={(e) => setLocal((s) => ({ ...s, persona_custom: e.target.value }))}
                rows={4}
                placeholder="Tulis instruksi khusus untuk AI..."
                className="mt-1 bg-[color:var(--jm-surface)] border-[color:var(--jm-border)] text-[color:var(--jm-text)]"
              />
            </div>
          )}
        </section>

        {/* Default model */}
        <section
          data-testid="settings-model-section"
          className="rounded-xl border border-[color:var(--jm-border)] bg-[color:var(--jm-surface)] p-6 mb-6"
        >
          <div className="text-[11px] uppercase tracking-[0.22em] font-semibold text-[color:var(--jm-text-3)] mb-3">
            Model Default
          </div>
          <Select
            value={local.default_model}
            onValueChange={(v) => setLocal((s) => ({ ...s, default_model: v }))}
          >
            <SelectTrigger
              data-testid="default-model-select"
              className="bg-[color:var(--jm-surface)] border-[color:var(--jm-border)] text-[color:var(--jm-text)]"
            >
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {settings.available_models.map((m) => (
                <SelectItem
                  key={`${m.provider}-${m.id}-${m.label}`}
                  data-testid={`model-option-${m.id}`}
                  value={m.id}
                >
                  {m.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <p className="text-xs text-[color:var(--jm-text-3)] font-ui mt-2">
            Model ini dipakai untuk semua panggilan LLM (ringkasan, bukti, matriks, tanya pustaka).
          </p>
        </section>

        <div className="flex justify-end">
          <Button
            data-testid="settings-save-btn"
            onClick={saveAll}
            disabled={saving}
            className="bg-[color:var(--jm-text)] text-white hover:bg-[#343a40] gap-2"
          >
            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
            Simpan
          </Button>
        </div>
      </main>
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
            Hapus
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
