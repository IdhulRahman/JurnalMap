/**
 * Per-feature LLM output language persisted in localStorage.
 * Each feature has its own key, defaulting to "id" (Bahasa Indonesia).
 *
 * Features:
 *   - summary: Ringkasan (Panel Kanan)
 *   - ask: Tanya Pustaka
 *   - matrix: derived from summary — not stored independently
 *
 * Check & Fix: no language toggle — feedback follows input text language.
 */
export const LANG_STORAGE_PREFIX = "jurnalmap.lang.";

export function getFeatureLanguage(feature, fallback = "id") {
  try {
    const v = localStorage.getItem(LANG_STORAGE_PREFIX + feature);
    return v === "en" || v === "id" ? v : fallback;
  } catch {
    return fallback;
  }
}

export function setFeatureLanguage(feature, lang) {
  try {
    localStorage.setItem(LANG_STORAGE_PREFIX + feature, lang);
  } catch {
    /* noop */
  }
}
