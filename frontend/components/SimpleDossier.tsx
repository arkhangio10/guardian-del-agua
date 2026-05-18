"use client";
import { useTranslations } from "next-intl";
import { readableConcession } from "@/utils/concession";
import { projectUnderElNino } from "@/utils/climate";

interface Props {
  alert: any;
  apiBase: string;
  climateState: any | null;
  onOpenImage: () => void;
  onGenerateDenuncia: () => void;
  generating: boolean;
  denuncia: any | null;
  denunciaError: string | null;
}

const TYPE_NAME: Record<string, { kind: string; emoji: string; plain: string }> = {
  hydrocarbon: {
    kind: "derrame de hidrocarburos",
    emoji: "🛢",
    plain: "manchas oscuras con brillo iridiscente — patrón típico de petróleo en agua",
  },
  turbidity: {
    kind: "contaminación por turbidez (sedimentos)",
    emoji: "🌫",
    plain: "coloración marrón-rojiza atípica en el cauce — sedimentos en suspensión",
  },
  algal_bloom: {
    kind: "floración algal anómala",
    emoji: "🦠",
    plain: "manchas verdes brillantes — pico de clorofila típico de eutrofización",
  },
};

export default function SimpleDossier({
  alert,
  apiBase,
  climateState,
  onOpenImage,
  onGenerateDenuncia,
  generating,
  denuncia,
  denunciaError,
}: Props) {
  const t = useTranslations("simple");
  const at = alert.attribution;
  const pred = alert.predictions;
  const concession = readableConcession(at?.concession_id);
  const typeMeta =
    TYPE_NAME[alert.contamination_type] ?? {
      kind: alert.contamination_type ?? "contaminación",
      emoji: "⚠",
      plain: "",
    };
  const detectedDate = alert.detected_at
    ? new Date(alert.detected_at).toLocaleDateString("es-PE", {
        year: "numeric",
        month: "long",
        day: "numeric",
      })
    : "—";
  const confidence = Math.round((alert.confidence || 0) * 100);

  // Climate context — uses persisted or freshly-fetched ENSO state.
  const climate = alert.climate_state ?? climateState;
  const scenario = alert.el_nino_scenario ?? (climate && pred ? projectUnderElNino(pred, climate) : null);
  const climateActive = climate && climate.severity > 0;

  return (
    <div className="space-y-5">
      {/* Hero with image preview */}
      <section
        className="relative rounded-2xl overflow-hidden border border-slate-700/40 bg-slate-900 cursor-zoom-in group"
        onClick={onOpenImage}
        role="button"
        aria-label={t("open_image")}
      >
        <div className="aspect-[16/9] relative">
          <img
            src={`${apiBase}/detect/alerts/${alert.alert_id}/image`}
            alt={t("alt_image")}
            className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-105"
            style={{ filter: "contrast(1.35) saturate(1.5) brightness(1.05)" }}
          />
          <div className="absolute inset-0 bg-gradient-to-t from-slate-950 via-slate-950/30 to-transparent" />
          <div className="absolute bottom-4 left-4 right-4 flex items-end justify-between gap-3">
            <div>
              <div className="text-2xl sm:text-3xl font-bold text-white leading-tight flex items-center gap-2">
                <span aria-hidden>{typeMeta.emoji}</span>
                {typeMeta.kind.charAt(0).toUpperCase() + typeMeta.kind.slice(1)}
              </div>
              <div className="text-sm text-slate-200 mt-1">
                {detectedDate}
                {concession.region ? ` · ${concession.region}` : ""}
              </div>
            </div>
            <div className="px-3 py-1 rounded-md bg-slate-950/70 backdrop-blur text-[10px] uppercase tracking-wider text-teal-200 opacity-0 group-hover:opacity-100 transition-opacity border border-teal-500/30 hidden sm:block">
              ⊕ {t("expand_image")}
            </div>
          </div>
        </div>
      </section>

      {/* 1. Qué pasa */}
      <NarrativeBlock icon="📍" title={t("what_happens.title")}>
        <p>
          {t.rich("what_happens.body", {
            kind: typeMeta.kind,
            concession: concession.name,
            operator: at?.operator_name ?? t("unknown_operator"),
            date: detectedDate,
            strong: (chunks) => <strong className="text-slate-50">{chunks}</strong>,
          })}
        </p>
        {concession.river && (
          <p className="text-slate-400 text-sm mt-2">
            {t("what_happens.river_label")}: <strong className="text-slate-200">{concession.river}</strong>
          </p>
        )}
      </NarrativeBlock>

      {/* 2. A quién afecta */}
      {pred ? (
        <NarrativeBlock icon="👥" title={t("who_affected.title")} tone="warn">
          <p>
            {t.rich("who_affected.body", {
              count_30d: pred.people_affected_30d?.toLocaleString("es-PE") ?? "—",
              count_7d: pred.people_affected_7d?.toLocaleString("es-PE") ?? "—",
              strong: (chunks) => <strong className="text-red-300">{chunks}</strong>,
            })}
          </p>
          <ul className="mt-3 space-y-1.5 text-sm">
            {pred.drinking_water_sources_at_risk > 0 && (
              <li className="flex items-start gap-2">
                <span className="text-red-400 mt-0.5">💧</span>
                <span>
                  {t("who_affected.water_sources", { n: pred.drinking_water_sources_at_risk })}
                </span>
              </li>
            )}
            {pred.fish_dieoff_30d_pct > 0 && (
              <li className="flex items-start gap-2">
                <span className="text-red-400 mt-0.5">🐟</span>
                <span>
                  {t("who_affected.fish", { pct: Math.round(pred.fish_dieoff_30d_pct) })}
                </span>
              </li>
            )}
            {pred.economic_damage_usd > 0 && (
              <li className="flex items-start gap-2">
                <span className="text-red-400 mt-0.5">💰</span>
                <span>
                  {t("who_affected.economic", {
                    usd: pred.economic_damage_usd.toLocaleString("en-US"),
                  })}
                </span>
              </li>
            )}
          </ul>
        </NarrativeBlock>
      ) : (
        <NarrativeBlock icon="👥" title={t("who_affected.title")}>
          <p className="text-slate-400 italic text-sm">{t("who_affected.no_data")}</p>
        </NarrativeBlock>
      )}

      {/* 3. Por qué es grave */}
      <NarrativeBlock icon="⚠️" title={t("why_serious.title")} tone="warn">
        <ul className="space-y-2 text-sm">
          {at?.prior_sanctions != null && at.prior_sanctions > 0 && (
            <li className="flex items-start gap-2">
              <span className="text-amber-400 mt-0.5">▸</span>
              <span>
                {t.rich("why_serious.prior_sanctions", {
                  operator: at.operator_name,
                  count: at.prior_sanctions,
                  strong: (chunks) => <strong className="text-red-300">{chunks}</strong>,
                })}
              </span>
            </li>
          )}
          {climateActive && scenario && pred && (
            <li className="flex items-start gap-2">
              <span className="text-amber-400 mt-0.5">▸</span>
              <span>
                {t.rich("why_serious.el_nino", {
                  state: climateLabel(climate.label),
                  base: pred.people_affected_30d?.toLocaleString("es-PE") ?? "—",
                  worst: scenario.people_affected_30d?.toLocaleString("es-PE") ?? "—",
                  mult: Math.round((1 + (climate.severity || 0) * 0.6) * 100) / 100,
                  strong: (chunks) => <strong className="text-red-300">{chunks}</strong>,
                })}
              </span>
            </li>
          )}
          {pred?.recovery_days && (
            <li className="flex items-start gap-2">
              <span className="text-amber-400 mt-0.5">▸</span>
              <span>
                {t.rich("why_serious.recovery", {
                  days: pred.recovery_days,
                  months: Math.round(pred.recovery_days / 30),
                  strong: (chunks) => <strong className="text-amber-200">{chunks}</strong>,
                })}
              </span>
            </li>
          )}
          {at?.legal_status && (
            <li className="flex items-start gap-2">
              <span className="text-amber-400 mt-0.5">▸</span>
              <span>
                {t.rich(`why_serious.legal_status.${at.legal_status}` as any, {
                  operator: at.operator_name,
                  strong: (chunks) => <strong className="text-slate-100">{chunks}</strong>,
                }) ?? at.legal_status}
              </span>
            </li>
          )}
        </ul>
      </NarrativeBlock>

      {/* 4. Cómo lo sabemos */}
      <NarrativeBlock icon="📊" title={t("how_we_know.title")}>
        <p>
          {t.rich("how_we_know.satellite", {
            date: detectedDate,
            strong: (chunks) => <strong className="text-slate-100">{chunks}</strong>,
          })}
        </p>
        <p className="mt-2">
          {t.rich("how_we_know.ai", {
            pattern: typeMeta.plain,
            confidence,
            strong: (chunks) => <strong className="text-teal-300">{chunks}</strong>,
          })}
        </p>
        <button
          onClick={onOpenImage}
          className="mt-3 text-sm text-teal-300 hover:text-teal-200 font-semibold inline-flex items-center gap-1.5 underline-offset-2 hover:underline"
        >
          👁 {t("how_we_know.see_image")}
        </button>
      </NarrativeBlock>

      {/* 5. Qué se puede hacer */}
      <NarrativeBlock icon="🎯" title={t("what_to_do.title")} tone="action">
        {!denuncia ? (
          <div className="space-y-3">
            <p className="text-sm">{t("what_to_do.description")}</p>
            <button
              onClick={onGenerateDenuncia}
              disabled={generating || !at}
              className="w-full font-bold px-6 py-3.5 rounded-lg transition-all hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed"
              style={{
                background: "linear-gradient(135deg, #14b8a6 0%, #06b6d4 100%)",
                color: "#ffffff",
                boxShadow: "0 4px 14px rgba(20, 184, 166, 0.45), inset 0 1px 0 rgba(255,255,255,0.2)",
                textShadow: "0 1px 2px rgba(0, 0, 0, 0.3)",
                border: "1px solid rgba(94, 234, 212, 0.6)",
              }}
            >
              📄 {generating ? t("what_to_do.generating") : t("what_to_do.generate")}
            </button>
            {denunciaError && (
              <p className="text-xs text-red-400">⚠ {denunciaError}</p>
            )}
            {!at && (
              <p className="text-xs text-amber-300 italic">{t("what_to_do.no_attribution")}</p>
            )}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mt-2">
              <SecondaryAction icon="📨" label={t("what_to_do.share_federation")} />
              <SecondaryAction icon="📰" label={t("what_to_do.share_press")} />
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            <p className="text-emerald-300 text-sm font-semibold">
              ✓ {t("what_to_do.denuncia_ready")}
            </p>
            <a
              href={`${apiBase}/act/denuncia/${alert.alert_id}/download`}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 bg-emerald-600 hover:bg-emerald-500 text-white font-semibold px-5 py-3 rounded-lg transition-colors"
            >
              ⬇ {t("what_to_do.download_pdf")}
            </a>
          </div>
        )}
      </NarrativeBlock>

      {/* Bottom disclaimer */}
      <p className="text-[11px] text-slate-500 italic leading-relaxed pt-2 border-t border-slate-800/60">
        {t("disclaimer")}
      </p>
    </div>
  );
}

function NarrativeBlock({
  icon,
  title,
  tone,
  children,
}: {
  icon: string;
  title: string;
  tone?: "warn" | "action";
  children: React.ReactNode;
}) {
  const toneCls =
    tone === "warn"
      ? "border-amber-700/40 bg-amber-950/10"
      : tone === "action"
      ? "border-teal-600/40 bg-teal-950/15"
      : "border-slate-700/40 bg-slate-900/40";
  return (
    <section className={`rounded-2xl border ${toneCls} p-4 sm:p-5`}>
      <h3 className="flex items-center gap-2 text-sm font-bold text-slate-100 mb-3">
        <span className="text-xl leading-none" aria-hidden>
          {icon}
        </span>
        {title}
      </h3>
      <div className="text-slate-200 text-[14px] leading-relaxed">{children}</div>
    </section>
  );
}

function SecondaryAction({ icon, label }: { icon: string; label: string }) {
  return (
    <button
      type="button"
      className="flex items-center justify-center gap-2 px-3 py-2.5 rounded-lg bg-slate-800/60 hover:bg-slate-700/80 border border-slate-700/40 text-sm text-slate-200 transition-colors"
    >
      <span aria-hidden>{icon}</span>
      {label}
    </button>
  );
}

function climateLabel(label: string): string {
  return {
    el_nino_costero: "El Niño Costero",
    el_nino_strong: "El Niño fuerte",
    el_nino_moderate: "El Niño moderado",
    el_nino_weak: "El Niño débil",
    la_nina_weak: "La Niña débil",
    la_nina_moderate: "La Niña moderada",
    la_nina_strong: "La Niña fuerte",
    neutral: "Neutral",
  }[label] ?? label;
}
