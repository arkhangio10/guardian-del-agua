"use client";
import { useLocale, useMessages } from "next-intl";
import { useState } from "react";

interface MetaShape {
  status?: string;
  language_native_name?: string;
  target_federations?: string[];
  translation_notice_es?: string;
  translation_notice_en?: string;
  completion_pct?: number;
}

export default function TranslationBanner() {
  const locale = useLocale();
  const messages = useMessages() as { _meta?: MetaShape };
  const [dismissed, setDismissed] = useState(false);

  const meta = messages?._meta;
  if (!meta || meta.status !== "pending_translation" || dismissed) return null;

  const notice =
    locale === "en" ? meta.translation_notice_en : meta.translation_notice_es;
  const fedList = meta.target_federations?.join(" · ") ?? "";

  return (
    <div className="relative bg-gradient-to-r from-amber-900/40 via-amber-800/30 to-transparent border-b border-amber-700/30 px-6 py-2 flex items-start gap-3 z-20">
      <span className="text-amber-300 text-lg leading-none mt-0.5" aria-hidden>
        ⚠
      </span>
      <div className="flex-1 min-w-0">
        <div className="text-[11px] uppercase tracking-wider text-amber-300 font-semibold">
          {meta.language_native_name ?? "Traducción pendiente"}
          {meta.completion_pct != null && (
            <span className="ml-2 text-amber-200/70 font-mono normal-case tracking-normal">
              · {meta.completion_pct}% traducido
            </span>
          )}
        </div>
        <p className="text-[12px] text-amber-100/90 mt-0.5 leading-snug">{notice}</p>
        {fedList && (
          <p className="text-[10px] text-amber-200/60 mt-1 font-mono">
            Federaciones objetivo: {fedList}
          </p>
        )}
      </div>
      <button
        onClick={() => setDismissed(true)}
        aria-label="Cerrar aviso"
        className="text-amber-300/70 hover:text-amber-200 text-sm leading-none flex-shrink-0 mt-0.5"
      >
        ×
      </button>
    </div>
  );
}
