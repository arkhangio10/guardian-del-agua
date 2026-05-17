"use client";
import { useLocale, useTranslations } from "next-intl";
import { useRouter, usePathname } from "@/i18n/navigation";
import { useState, useRef, useEffect, useTransition } from "react";
import { routing, LOCALE_META, type Locale } from "@/i18n/routing";

export default function LanguageSwitcher() {
  const locale = useLocale() as Locale;
  const t = useTranslations("language");
  const router = useRouter();
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [, startTransition] = useTransition();
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    if (open) document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [open]);

  const current = LOCALE_META[locale];

  function switchTo(next: Locale) {
    if (next === locale) {
      setOpen(false);
      return;
    }
    setOpen(false);
    // next-intl's router.replace handles cookie + prefix automatically.
    // pathname here is already locale-stripped.
    startTransition(() => router.replace(pathname, { locale: next }));
  }

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        aria-label={t("switcher_aria")}
        aria-haspopup="menu"
        aria-expanded={open}
        className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-md bg-slate-800/40 hover:bg-slate-800/80 border border-slate-700/40 text-[11px] text-slate-200 transition-colors"
      >
        <span className="font-mono text-teal-300 tracking-wider">{current.flag}</span>
        <span className="hidden sm:inline">{current.native}</span>
        <svg className="w-3 h-3 text-slate-400" viewBox="0 0 12 12" fill="currentColor">
          <path d="M2 4l4 4 4-4" stroke="currentColor" strokeWidth="1.5" fill="none" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>

      {open && (
        <div
          role="menu"
          className="absolute right-0 top-full mt-1.5 w-52 glass-strong rounded-lg overflow-hidden z-50 animate-slide-in-card"
        >
          {routing.locales.map((l) => {
            const meta = LOCALE_META[l];
            const isActive = l === locale;
            return (
              <button
                key={l}
                onClick={() => switchTo(l)}
                role="menuitem"
                className={`w-full flex items-center gap-3 px-3 py-2.5 text-left text-sm transition-colors ${
                  isActive
                    ? "bg-teal-500/15 text-teal-200"
                    : "text-slate-200 hover:bg-slate-800/60"
                }`}
              >
                <span className="font-mono text-[10px] w-7 text-teal-300 tracking-wider">
                  {meta.flag}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="font-medium truncate">{meta.native}</div>
                  {meta.native !== meta.label && (
                    <div className="text-[10px] text-slate-500 truncate">{meta.label}</div>
                  )}
                </div>
                {isActive && (
                  <span className="text-teal-400 text-xs" aria-hidden>
                    ●
                  </span>
                )}
              </button>
            );
          })}
          <div className="px-3 py-2 text-[10px] text-slate-500 border-t border-slate-700/40 italic leading-snug">
            Kichwa amazónico en validación con FEDIQUEP / OPIKAFPE / FECONACO
          </div>
        </div>
      )}
    </div>
  );
}
