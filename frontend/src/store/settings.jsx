import React, { createContext, useContext, useEffect, useState } from "react";
import { api } from "@/services/api";
import { useAuth } from "@/store/auth";

const SettingsCtx = createContext(null);

const LOCAL_THEME_KEY = "jurnalmap.theme";

const DEFAULT_SETTINGS = {
  theme: "light",
  persona_id: "akademisi_ketat",
  persona_custom: "",
  default_model: "gemini-3-flash-preview",
  personas: [],
  available_models: [],
};

export function SettingsProvider({ children }) {
  const { token } = useAuth();
  const [settings, setSettings] = useState(null);
  const [loading, setLoading] = useState(true);

  const applyTheme = (theme) => {
    const root = document.documentElement;
    if (theme === "dark") root.classList.add("dark");
    else root.classList.remove("dark");
  };

  const reload = async () => {
    if (!token) {
      // No auth — fall back to defaults and skip network call
      const stored = localStorage.getItem(LOCAL_THEME_KEY);
      const s = { ...DEFAULT_SETTINGS, theme: stored === "dark" ? "dark" : "light" };
      setSettings(s);
      applyTheme(s.theme);
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const s = await api.getSettings();
      const stored = localStorage.getItem(LOCAL_THEME_KEY);
      if (stored && stored !== s.theme) s.theme = stored;
      setSettings(s);
      applyTheme(s.theme);
    } catch (e) {
      setSettings({ ...DEFAULT_SETTINGS });
      applyTheme("light");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const stored = localStorage.getItem(LOCAL_THEME_KEY);
    if (stored === "dark") applyTheme("dark");
    reload();
    // Re-fetch whenever token changes (login/logout)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  const setTheme = async (theme) => {
    localStorage.setItem(LOCAL_THEME_KEY, theme);
    applyTheme(theme);
    setSettings((s) => ({ ...(s || {}), theme }));
    if (!token) return;
    try {
      await api.updateSettings({ theme });
    } catch {
      /* ignore — theme persists locally */
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
