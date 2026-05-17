import type { Metadata } from "next";
import { NextIntlClientProvider, hasLocale } from "next-intl";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { notFound } from "next/navigation";
import { routing } from "@/i18n/routing";
import LanguageSwitcher from "@/components/LanguageSwitcher";
import TranslationBanner from "@/components/TranslationBanner";
import "../globals.css";

export function generateStaticParams() {
  return routing.locales.map((locale) => ({ locale }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "nav" });
  return {
    title: `${t("brand")} — ${t("tagline")}`,
    description:
      "Primer audit trail probatorio para denuncias ambientales en la Amazonía peruana. Sentinel-2 + Claude + Ley peruana, listo para OEFA en menos de 25 horas.",
  };
}

export default async function LocaleLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  if (!hasLocale(routing.locales, locale)) notFound();
  setRequestLocale(locale);

  const t = await getTranslations({ locale, namespace: "nav" });
  const tFooter = await getTranslations({ locale, namespace: "footer" });

  return (
    <html lang={locale}>
      <body className="h-screen overflow-hidden flex flex-col bg-[#050b14] text-slate-100">
        <NextIntlClientProvider>
          <nav className="h-14 flex-shrink-0 border-b border-slate-800/60 glass-soft px-6 flex items-center gap-5 z-30">
            <a href="/" className="flex items-center gap-2 group">
              <span className="relative inline-block w-2.5 h-2.5">
                <span className="absolute inset-0 bg-teal-400 rounded-full" />
                <span className="absolute inset-0 bg-teal-400 rounded-full animate-ping opacity-60" />
              </span>
              <span className="text-base font-bold text-gradient-teal tracking-tight">
                {t("brand")}
              </span>
            </a>
            <span className="hidden lg:inline text-[11px] text-slate-500 italic border-l border-slate-700/60 pl-4">
              {t("tagline")}
            </span>
            <div className="hidden md:flex items-center gap-1 ml-2">
              <NavLink href="/" label={t("dossiers")} />
              <NavLink href="/leaderboard" label={t("operators")} />
              <NavLink href="/pricing" label={t("access")} />
              <NavLink href="/independence" label={t("independence")} />
            </div>
            <div className="ml-auto flex items-center gap-3">
              <LanguageSwitcher />
              <span className="hidden sm:inline text-[10px] text-slate-500 font-mono tracking-wider">
                {t("stamp")}
              </span>
            </div>
          </nav>

          <TranslationBanner />

          <main className="flex-1 min-h-0 flex flex-col overflow-y-auto gda-scroll">
            {children}
          </main>

          <footer className="h-9 flex-shrink-0 border-t border-slate-800/60 glass-soft px-6 flex items-center gap-4 text-[10px] text-slate-500">
            <span className="hidden sm:inline">{tFooter("byline")}</span>
            <a
              href="/independence"
              className="text-teal-400 hover:text-teal-300 transition-colors"
            >
              {tFooter("independence")}
            </a>
            <a
              href="/pricing"
              className="text-teal-400 hover:text-teal-300 transition-colors"
            >
              {tFooter("access")}
            </a>
            <span className="ml-auto font-mono tracking-wider">{tFooter("license")}</span>
          </footer>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}

function NavLink({ href, label }: { href: string; label: string }) {
  return (
    <a
      href={href}
      className="px-3 py-1.5 text-xs text-slate-300 hover:text-white hover:bg-slate-800/60 rounded-md transition-colors"
    >
      {label}
    </a>
  );
}
