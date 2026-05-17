import { defineRouting } from "next-intl/routing";

export const routing = defineRouting({
  locales: ["es", "en", "qu"] as const,
  defaultLocale: "es",
  localePrefix: "as-needed",
});

export type Locale = (typeof routing.locales)[number];

export const LOCALE_META: Record<Locale, { label: string; flag: string; native: string }> = {
  es: { label: "Español", flag: "ES", native: "Español" },
  en: { label: "English", flag: "EN", native: "English" },
  qu: { label: "Kichwa amazónico", flag: "QU", native: "Runa shimi" },
};
