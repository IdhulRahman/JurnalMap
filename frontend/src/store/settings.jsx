import { createContext, useContext, useEffect, useState } from "react";
import { api } from "@/services/api";

const SettingsCtx = createContext(null);

const LOCAL_THEME_KEY = "jurnalmap.theme";

export function SettingsProvider({ children }) {
  const [settings, setSettings] = useState(null);
  const [loading, setLoading] = useState(true);

  const applyTheme = (theme) => {
    const root = document.documentElement;
    if (theme === "dark") root.classList.add("dark");
    else root.classList.remove("dark");
  };

  const reload = async () => {
    try {
      const s = await api.getSettings();
      // honor any pre-existing localStorage theme so dark stays dark on reload
      const stored = localStorage.getItem(LOCAL_THEME_KEY);
      if (stored && stored !== s.theme) s.theme = stored;
      setSettings(s);
      applyTheme(s.theme);
    } catch (e) {
      setSettings({
        theme: "light",
        persona_id: "akademisi_ketat",
        persona_custom: "",
        default_model: "gemini-3-flash-preview",
        personas: [],
        available_models: [],
      });
      applyTheme("light");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // optimistic theme from localStorage before fetch
    const stored = localStorage.getItem(LOCAL_THEME_KEY);
    if (stored === "dark") applyTheme("dark");
    reload();
  }, []);

  const setTheme = async (theme) => {
    localStorage.setItem(LOCAL_THEME_KEY, theme);
    applyTheme(theme);
    setSettings((s) => ({ ...(s || {}), theme }));
    try {
      await api.updateSettings({ theme });
    } catch {
      /* ignore — theme is persisted locally too */
    }
  };

  const update = async (patch) => {
    const s = await api.updateSettings(patch);
    if (patch.theme) {
      localStorage.setItem(LOCAL_THEME_KEY, patch.theme);
      applyTheme(patch.theme);
    }
    setSettings(s);
    return s;
  };

  return (
    <SettingsCtx.Provider value={{ settings, loading, setTheme, update, reload }}>
      {children}
    </SettingsCtx.Provider>
  );
}

export function useSettings() {
  const ctx = useContext(SettingsCtx);
  if (!ctx) throw new Error("useSettings must be used within SettingsProvider");
  return ctx;
}
