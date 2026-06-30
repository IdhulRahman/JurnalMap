import { useSettings } from "@/store/settings";
import { TRANSLATIONS, fmt } from "@/lib/i18n";

export function useT() {
  const { settings } = useSettings();
  const lang = settings?.ui_language === "en" ? "en" : "id";
  const dict = TRANSLATIONS[lang] || TRANSLATIONS.id;
  const t = (key, vars) => {
    const tpl = dict[key] || TRANSLATIONS.id[key] || key;
    return vars ? fmt(tpl, vars) : tpl;
  };
  return { t, lang };
}
