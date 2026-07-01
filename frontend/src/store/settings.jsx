import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import { api } from "@/services/api";
import { useAuth } from "@/store/auth";

const SettingsCtx = createContext(null);

const LOCAL_THEME_KEY = "jurnalmap.theme";        // "light" | "dark" | "system"
const LOCAL_UI_LANG_KEY = "jurnalmap.ui_language"; // "id" | "en"

const DEFAULT_SETTINGS = {
  theme: "system",
  ui_language: "id",
  persona_id: "akademisi_ketat",
  persona_custom: "",
  default_model: "gemini-2.0-flash",
  personas: [],
  available_models: [],
};

function systemPrefersDark() {
  try {
    return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
  } catch {
    return false;
  }
}

function applyDomTheme(effective) {
  const root = document.documentElement;
  if (effective === "dark") root.classList.add("dark");
  else root.classList.remove("dark");
}

/**
 * theme: "light" | "dark" | "system"
 * effectiveTheme: "light" | "dark" (resolved for system)
 */
export function SettingsProvider({ children }) {
  const { token } = useAuth();
  const [settings, setSettings] = useState(null);
  const [loading, setLoading] = useState(true);
  const [effectiveTheme, setEffectiveTheme] = useState(() => {
    const stored = typeof window !== "undefined" ? localStorage.getItem(LOCAL_THEME_KEY) : null;
    if (stored === "dark") return "dark";
    if (stored === "light") return "light";
    return systemPrefersDark() ? "dark" : "light";
  });

  // Reactively apply theme when it changes
  const applyTheme = useCallback((mode) => {
    const effective = mode === "system" ? (systemPrefersDark() ? "dark" : "light") : mode;
    applyDomTheme(effective);
    setEffectiveTheme(effective);
  }, []);

  // Listen to OS theme changes when in "system" mode
  useEffect(() => {
    if (settings?.theme !== "system") return undefined;
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => applyTheme("system");
    mq.addEventListener?.("change", onChange);
    return () => mq.removeEventListener?.("change", onChange);
  }, [settings?.theme, applyTheme]);

  const reload = useCallback(async () => {
    // Local-first: theme and ui_language always come from localStorage.
    const storedTheme = localStorage.getItem(LOCAL_THEME_KEY);
    const theme = ["light", "dark", "system"].includes(storedTheme) ? storedTheme : "system";
    const storedUi = localStorage.getItem(LOCAL_UI_LANG_KEY);
    const uiLang = storedUi === "en" || storedUi === "id" ? storedUi : "id";

    if (!token) {
      const s = { ...DEFAULT_SETTINGS, theme, ui_language: uiLang };
      setSettings(s);
      applyTheme(theme);
      setLoading(false);
      return;
    }

    setLoading(true);
    try {
      const s = await api.getSettings();
      // Force local overrides for theme + ui_language (client-owned)
      s.theme = theme;
      s.ui_language = uiLang;
      // Merge server config (available_models etc.)
      try {
        const cfg = await api.getConfig();
        if (cfg?.available_models?.length) s.available_models = cfg.available_models;
        s.default_model = cfg?.default_model || s.default_model || "gemini-2.0-flash";
        s.embedding_backend = cfg?.embedding_model;
        s.embedding_enabled = cfg?.embedding_enabled;
        s.local_llm_enabled = cfg?.local_llm_enabled;
      } catch {
        /* ignore */
      }
      setSettings(s);
      applyTheme(theme);
    } catch {
      setSettings({ ...DEFAULT_SETTINGS, theme, ui_language: uiLang });
      applyTheme(theme);
    } finally {
      setLoading(false);
    }
  }, [token, applyTheme]);

  useEffect(() => {
    reload();
  }, [reload]);

  const setTheme = useCallback((mode) => {
    if (!["light", "dark", "system"].includes(mode)) return;
    localStorage.setItem(LOCAL_THEME_KEY, mode);
    setSettings((s) => ({ ...(s || DEFAULT_SETTINGS), theme: mode }));
    applyTheme(mode);
  }, [applyTheme]);

  const setUiLanguage = useCallback((lang) => {
    if (lang !== "id" && lang !== "en") return;
    localStorage.setItem(LOCAL_UI_LANG_KEY, lang);
    setSettings((s) => ({ ...(s || DEFAULT_SETTINGS), ui_language: lang }));
  }, []);

  const update = useCallback(async (patch) => {
    // Client-owned settings never hit the server
    const localPatch = {};
    if (patch.theme) {
      setTheme(patch.theme);
      // eslint-disable-next-line no-param-reassign
      delete patch.theme;
    }
    if (patch.ui_language) {
      setUiLanguage(patch.ui_language);
      // eslint-disable-next-line no-param-reassign
      delete patch.ui_language;
    }
    if (Object.keys(patch).length === 0) return settings;
    const s = await api.updateSettings(patch);
    s.theme = localStorage.getItem(LOCAL_THEME_KEY) || "system";
    s.ui_language = localStorage.getItem(LOCAL_UI_LANG_KEY) || "id";
    setSettings((cur) => ({ ...(cur || {}), ...s, ...localPatch }));
    return s;
  }, [setTheme, setUiLanguage, settings]);

  return (
    <SettingsCtx.Provider value={{ settings, loading, effectiveTheme, setTheme, setUiLanguage, update, reload }}>
      {children}
    </SettingsCtx.Provider>
  );
}

export function useSettings() {
  const ctx = useContext(SettingsCtx);
  if (!ctx) throw new Error("useSettings must be used within SettingsProvider");
  return ctx;
}
