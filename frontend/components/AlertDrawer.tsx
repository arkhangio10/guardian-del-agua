"use client";
import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import SatelliteLightbox from "./SatelliteLightbox";
import { bboxAreaKm2, bboxSidesKm } from "@/utils/bbox";
import { projectUnderElNino } from "@/utils/climate";

const TYPE_META: Record<string, { tKey: string; chip: string; dot: string }> = {
  hydrocarbon: {
    tKey: "hydrocarbon",
    chip: "bg-red-500/15 text-red-300 border-red-500/30",
    dot: "bg-red-500",
  },
  turbidity: {
    tKey: "turbidity",
    chip: "bg-orange-500/15 text-orange-300 border-orange-500/30",
    dot: "bg-orange-400",
  },
  algal_bloom: {
    tKey: "algal_bloom",
    chip: "bg-green-500/15 text-green-300 border-green-500/30",
    dot: "bg-green-500",
  },
};

interface Props {
  alertId: string | null;
  apiBase: string;
  onClose: () => void;
}

export default function AlertDrawer({ alertId, apiBase, onClose }: Props) {
  const t = useTranslations("drawer");
  const tAlert = useTranslations("alert");
  const tContam = useTranslations("contamination");

  const tLight = useTranslations("lightbox");

  const [alert, setAlert] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [imgError, setImgError] = useState(false);
  const [lightboxOpen, setLightboxOpen] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [denuncia, setDenuncia] = useState<any>(null);
  const [denunciaError, setDenunciaError] = useState<string | null>(null);
  const [climateState, setClimateState] = useState<any>(null);

  useEffect(() => {
    if (!alertId) return;
    setLoading(true);
    setAlert(null);
    setImgError(false);
    setDenuncia(null);
    setDenunciaError(null);

    fetch(`${apiBase}/detect/alerts/${alertId}`)
      .then((r) => {
        if (!r.ok) throw new Error("not found");
        return r.json();
      })
      .then(setAlert)
      .catch(() => setAlert(null))
      .finally(() => setLoading(false));

    // Always fetch current ENSO climate state — demo alerts seeded directly into
    // Firestore never went through /predict, so they don't have climate_state
    // persisted. Showing the climate context regardless makes the layer visible
    // and lets the user reason about projection even on historical alerts.
    fetch(`${apiBase}/climate/state`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => setClimateState(data))
      .catch(() => setClimateState(null));
  }, [alertId, apiBase]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    if (alertId) window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [alertId, onClose]);

  async function generateDenuncia() {
    if (!alertId) return;
    setGenerating(true);
    setDenunciaError(null);
    try {
      const resp = await fetch(`${apiBase}/act/denuncia/${alertId}`, { method: "POST" });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      setDenuncia(data);
    } catch (err: any) {
      setDenunciaError(err?.message ?? "error");
    } finally {
      setGenerating(false);
    }
  }

  if (!alertId) return null;

  const meta = alert ? TYPE_META[alert.contamination_type] : null;
  const typeLabel = meta ? tContam(meta.tKey as any) : alert?.contamination_type;
  const at = alert?.attribution;
  const pred = alert?.predictions;

  return (
    <>
      <div
        className="fixed inset-0 z-40 bg-slate-950/55 backdrop-blur-sm animate-fade-in"
        onClick={onClose}
      />

      <aside
        className="fixed top-0 right-0 bottom-0 z-50 w-full md:w-[640px] glass-strong shadow-2xl flex flex-col animate-slide-in-right"
        role="dialog"
        aria-modal="true"
      >
        <header className="px-6 py-4 border-b border-slate-700/40 flex items-center justify-between gap-4 flex-shrink-0">
          <div className="flex items-center gap-3 min-w-0">
            <span className="text-[10px] uppercase tracking-[0.18em] text-teal-300 font-mono">
              {t("label")}
            </span>
            {alert?.alert_id && (
              <code className="text-[10px] text-slate-500 font-mono truncate">
                #{alert.alert_id.slice(0, 8)}
              </code>
            )}
          </div>
          <button
            onClick={onClose}
            aria-label={t("close_aria")}
            className="w-8 h-8 rounded-full bg-slate-800/60 hover:bg-slate-700 text-slate-300 flex items-center justify-center transition-colors"
          >
            ✕
          </button>
        </header>

        <div className="flex-1 overflow-y-auto gda-scroll">
          {loading && (
            <div className="p-10 space-y-4">
              <div className="h-6 w-2/3 bg-slate-800/60 rounded animate-pulse" />
              <div className="h-48 bg-slate-800/40 rounded-xl animate-pulse" />
              <div className="grid grid-cols-2 gap-3">
                <div className="h-24 bg-slate-800/40 rounded-xl animate-pulse" />
                <div className="h-24 bg-slate-800/40 rounded-xl animate-pulse" />
              </div>
            </div>
          )}

          {!loading && !alert && (
            <div className="p-10 text-center">
              <p className="text-red-300">{t("loading_error")}</p>
              <p className="text-xs text-slate-500 mt-2">ID: {alertId}</p>
            </div>
          )}

          {!loading && alert && (
            <div className="p-6 space-y-5">
              {/* Hero: satellite image + operator */}
              <section className="relative rounded-2xl overflow-hidden border border-slate-700/40 bg-slate-900">
                <div
                  className="aspect-[16/10] relative group/img cursor-zoom-in"
                  onClick={() => {
                    if (!imgError) setLightboxOpen(true);
                  }}
                  role="button"
                  aria-label={tLight("open_lightbox")}
                >
                  {!imgError ? (
                    <img
                      src={`${apiBase}/detect/alerts/${alert.alert_id}/image`}
                      alt={tAlert("alt_satellite")}
                      className="w-full h-full object-cover transition-transform duration-500 group-hover/img:scale-105"
                      style={{ filter: "contrast(1.35) saturate(1.5) brightness(1.05)" }}
                      onError={() => setImgError(true)}
                    />
                  ) : (
                    <div className="absolute inset-0 flex items-center justify-center text-sm text-slate-500 italic">
                      {tAlert("image_unavailable")}
                    </div>
                  )}
                  <div className="absolute inset-0 bg-gradient-to-b from-slate-950/85 via-transparent to-slate-950/40 pointer-events-none" />
                  <div className="absolute inset-4 border border-teal-400/40 rounded-xl pointer-events-none" />
                  {/* Claude reasoning ribbon — top, narrow, glass */}
                  {(alert.description || (alert.contamination_type && tContam(`${alert.contamination_type}_note` as any))) && (
                    <div className="absolute top-4 left-4 right-4 md:right-auto md:max-w-[78%] flex items-start gap-2 px-3 py-2 rounded-lg glass-strong border border-teal-500/30 pointer-events-none shadow-glow-teal">
                      <span className="text-[10px] uppercase tracking-[0.18em] text-teal-300 font-semibold flex-shrink-0 mt-0.5">
                        {tAlert("claude_label")}
                      </span>
                      <p className="text-[11px] sm:text-[12px] text-slate-100 leading-snug">
                        {alert.description ?? tContam(`${alert.contamination_type}_note` as any)}
                      </p>
                    </div>
                  )}
                  {/* Click-to-expand hint — bottom-right, doesn't compete with chip below */}
                  {!imgError && (
                    <div className="absolute bottom-3 right-3 px-2.5 py-1 rounded-md bg-slate-950/75 backdrop-blur text-[10px] uppercase tracking-wider text-teal-200 opacity-0 group-hover/img:opacity-100 transition-opacity pointer-events-none border border-teal-500/30">
                      ⊕ {tLight("click_to_expand")}
                    </div>
                  )}
                </div>

                <div className="px-5 pb-5 -mt-14 relative">
                  {meta && typeLabel && (
                    <span
                      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${meta.chip}`}
                    >
                      <span className={`inline-block w-1.5 h-1.5 rounded-full ${meta.dot}`} />
                      {typeLabel}
                    </span>
                  )}
                  <h2 className="text-2xl font-bold text-slate-50 mt-2 leading-tight">
                    {at?.operator_name ?? tAlert("unknown_operator")}
                  </h2>
                  <p className="text-sm text-slate-400 mt-1">
                    {at?.concession_id ? `${tAlert("concession")} ${at.concession_id} · ` : ""}
                    {alert.detected_at
                      ? new Date(alert.detected_at).toLocaleDateString(undefined, {
                          year: "numeric",
                          month: "long",
                          day: "numeric",
                        })
                      : "—"}
                  </p>

                  <div className="mt-4 flex items-center gap-6">
                    <div>
                      <div className="text-3xl font-bold text-gradient-teal leading-none">
                        {(alert.confidence * 100).toFixed(0)}%
                      </div>
                      <div className="text-[10px] uppercase tracking-wider text-slate-500 mt-1">
                        {t("confidence_claude")}
                      </div>
                    </div>
                    <div className="h-10 w-px bg-slate-700" />
                    <div>
                      <div className="text-sm font-mono text-slate-300">
                        {alert.sentinel_image_id ?? "—"}
                      </div>
                      <div className="text-[10px] uppercase tracking-wider text-slate-500 mt-1">
                        Sentinel-2 L2A
                      </div>
                    </div>
                  </div>
                </div>
              </section>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <Panel title={t("operator_panel")} tone="default">
                  <Row label={t("company")} value={at?.operator_name} />
                  <Row label={t("osinergmin")} value={at?.osinergmin_id} />
                  <Row
                    label={tAlert("prior_sanctions")}
                    value={
                      at?.prior_sanctions != null ? (
                        <span className="text-red-300 font-bold">{at.prior_sanctions}</span>
                      ) : (
                        "—"
                      )
                    }
                  />
                  <Row label={t("legal_status")} value={at?.legal_status} />
                  <Row
                    label={t("parent_company")}
                    value={<span className="text-xs">{at?.parent_company}</span>}
                  />
                </Panel>

                <Panel title={t("evidence_panel")} tone="default">
                  <Row label={t("satellite")} value="Sentinel-2 L2A" />
                  <Row
                    label={t("image_id")}
                    value={<span className="text-[11px] font-mono">{alert.sentinel_image_id}</span>}
                  />
                  {(() => {
                    const area = bboxAreaKm2(alert.sentinel_bbox);
                    const sides = bboxSidesKm(alert.sentinel_bbox);
                    return (
                      <>
                        {area != null && (
                          <Row
                            label={tLight("area_analyzed")}
                            value={
                              <span className="text-slate-200">
                                {area.toLocaleString()} km²
                                {sides && (
                                  <span className="text-slate-500 text-[11px] ml-1.5">
                                    ({sides[0]}×{sides[1]} km)
                                  </span>
                                )}
                              </span>
                            }
                          />
                        )}
                      </>
                    );
                  })()}
                  <Row
                    label={t("bbox")}
                    value={
                      <span className="text-[11px] font-mono text-slate-400">
                        {alert.sentinel_bbox?.map((n: number) => n.toFixed(2)).join(", ")}
                      </span>
                    }
                  />
                </Panel>
              </div>

              {pred && (
                <Panel title={t("impact_panel")} tone="danger">
                  <div className="grid grid-cols-3 gap-2 mt-1">
                    <Stat label={t("stat_affected_7d")} value={pred.people_affected_7d?.toLocaleString()} />
                    <Stat
                      label={t("stat_affected_30d")}
                      value={pred.people_affected_30d?.toLocaleString()}
                      highlight
                    />
                    <Stat label={t("stat_fish_dieoff")} value={`${pred.fish_dieoff_30d_pct?.toFixed(0)}%`} />
                    <Stat label={t("stat_water_sources")} value={pred.drinking_water_sources_at_risk} />
                    <Stat
                      label={t("stat_recovery")}
                      value={t("stat_recovery_days", { days: pred.recovery_days })}
                    />
                    <Stat
                      label={t("stat_economic_damage")}
                      value={`$${pred.economic_damage_usd?.toLocaleString("en-US")}`}
                    />
                  </div>
                </Panel>
              )}

              {alert.spectral_evidence && (
                <SpectralPanel evidence={alert.spectral_evidence} />
              )}

              {(() => {
                const climate = alert.climate_state ?? climateState;
                if (!climate) return null;
                const scenario =
                  alert.el_nino_scenario ?? projectUnderElNino(pred, climate);
                return <ClimatePanel climate={climate} base={pred} scenario={scenario} />;
              })()}

              <Panel title={t("actions_panel")} tone="default">
                {!denuncia ? (
                  <div className="space-y-2">
                    <button
                      onClick={generateDenuncia}
                      disabled={generating || !at}
                      className="w-full font-bold px-6 py-3 rounded-lg text-sm transition-all flex items-center justify-center gap-2 hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed"
                      style={{
                        background: "linear-gradient(135deg, #14b8a6 0%, #06b6d4 100%)",
                        color: "#ffffff",
                        boxShadow: "0 4px 14px rgba(20, 184, 166, 0.45), inset 0 1px 0 rgba(255,255,255,0.2)",
                        textShadow: "0 1px 2px rgba(0, 0, 0, 0.3)",
                        border: "1px solid rgba(94, 234, 212, 0.6)",
                      }}
                    >
                      {generating ? t("generating") : t("generate_denuncia")}
                    </button>
                    {denunciaError && (
                      <p className="text-xs text-red-400">
                        ⚠ {t("denuncia_error", { message: denunciaError })}
                      </p>
                    )}
                    {!at && (
                      <p className="text-xs text-amber-400/80 italic">{t("no_attribution")}</p>
                    )}
                  </div>
                ) : (
                  <div className="space-y-3">
                    <p className="text-emerald-400 text-sm">
                      ✓{" "}
                      {t("denuncia_success", {
                        ms: denuncia.generated_in_ms,
                        bytes: denuncia.pdf_size_bytes,
                      })}
                    </p>
                    <a
                      href={`${apiBase}/act/denuncia/${alertId}/download`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-block bg-emerald-600 hover:bg-emerald-500 text-white font-semibold px-5 py-2.5 rounded-lg transition-colors"
                    >
                      ⬇ {t("denuncia_download")}
                    </a>
                    {denuncia.denuncia_preview && (
                      <pre className="text-slate-400 text-[11px] mt-2 whitespace-pre-wrap font-mono bg-slate-950/70 border border-slate-700/40 p-3 rounded-lg max-h-48 overflow-y-auto gda-scroll">
                        {denuncia.denuncia_preview}
                      </pre>
                    )}
                  </div>
                )}
              </Panel>

              <p className="text-[10px] text-slate-500 italic leading-relaxed border-t border-slate-700/40 pt-3">
                {t("legal_disclaimer")}
              </p>
            </div>
          )}
        </div>
      </aside>

      {lightboxOpen && alert && (
        <SatelliteLightbox
          alert={alert}
          apiBase={apiBase}
          onClose={() => setLightboxOpen(false)}
        />
      )}
    </>
  );
}

function Panel({
  title,
  tone,
  children,
}: {
  title: string;
  tone: "default" | "danger";
  children: React.ReactNode;
}) {
  const borderCls =
    tone === "danger" ? "border-red-900/40 bg-red-950/15" : "border-slate-700/40 bg-slate-900/40";
  const titleCls = tone === "danger" ? "text-red-300" : "text-slate-300";
  return (
    <section className={`rounded-xl border ${borderCls} p-4`}>
      <h3 className={`text-[10px] uppercase tracking-[0.18em] font-semibold ${titleCls} mb-3`}>
        {title}
      </h3>
      <dl className="space-y-2 text-sm">{children}</dl>
    </section>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex justify-between items-baseline gap-3">
      <dt className="text-slate-500 text-xs flex-shrink-0">{label}</dt>
      <dd className="text-slate-200 text-right">{value ?? "—"}</dd>
    </div>
  );
}

function Stat({
  label,
  value,
  highlight,
}: {
  label: string;
  value: React.ReactNode;
  highlight?: boolean;
}) {
  return (
    <div className="bg-slate-900/60 border border-slate-700/40 rounded-lg p-3">
      <div className={`text-lg font-bold ${highlight ? "text-red-300" : "text-slate-100"}`}>
        {value ?? "—"}
      </div>
      <div className="text-[10px] uppercase tracking-wider text-slate-500 mt-1">{label}</div>
    </div>
  );
}

function SpectralPanel({ evidence }: { evidence: any }) {
  const tSpec = useTranslations("spectral");
  const strength = Math.max(0, Math.min(1, Number(evidence?.evidence_strength) || 0));
  const pct = Math.round(strength * 100);
  const areaPct = Math.round((Number(evidence?.affected_area_pct) || 0) * 100);
  const mult = 0.7 + 0.6 * strength;

  const tone =
    strength >= 0.7
      ? { border: "border-red-700/50", bar: "from-red-400 to-red-600", text: "text-red-300" }
      : strength >= 0.4
      ? { border: "border-amber-700/50", bar: "from-amber-400 to-orange-500", text: "text-amber-300" }
      : { border: "border-slate-700/40", bar: "from-teal-400 to-cyan-500", text: "text-teal-300" };

  return (
    <section className={`rounded-xl border ${tone.border} bg-slate-900/40 p-4 space-y-3`}>
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-[10px] uppercase tracking-[0.18em] font-semibold text-slate-300">
          {tSpec("panel_title")}
        </h3>
        <span className="text-[10px] font-mono text-slate-500 uppercase tracking-wider">
          {evidence?._method_version ?? "v0"} · {evidence?.index_name ?? "—"}
        </span>
      </div>

      <div>
        <div className="flex items-baseline justify-between mb-1.5">
          <span className="text-xs text-slate-400">{tSpec("strength_label")}</span>
          <span className={`text-xl font-bold ${tone.text}`}>{pct}%</span>
        </div>
        <div className="h-2 rounded-full bg-slate-800 overflow-hidden">
          <div
            className={`h-full bg-gradient-to-r ${tone.bar} transition-all duration-700`}
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>

      <div className="grid grid-cols-3 gap-2 text-[11px]">
        <SpecCell label={tSpec("affected_area")} value={`${areaPct}%`} />
        <SpecCell
          label={tSpec("multiplier_applied")}
          value={`×${mult.toFixed(2)}`}
          accent={mult !== 1.0}
        />
        <SpecCell
          label={tSpec("temporal_window")}
          value={
            <span className="font-mono text-[10px]">
              {evidence?.before_date} → {evidence?.after_date}
            </span>
          }
        />
      </div>

      <p className="text-[10px] text-slate-500 italic leading-snug">
        {tSpec("provenance_prefix")}: {evidence?._method ?? "—"}
      </p>
    </section>
  );
}

function SpecCell({
  label,
  value,
  accent,
}: {
  label: string;
  value: React.ReactNode;
  accent?: boolean;
}) {
  return (
    <div className="bg-slate-950/40 border border-slate-700/30 rounded-md px-2 py-1.5">
      <div className="text-[9px] uppercase tracking-wider text-slate-500">{label}</div>
      <div className={`mt-0.5 text-sm font-bold ${accent ? "text-cyan-300" : "text-slate-200"}`}>
        {value}
      </div>
    </div>
  );
}

const CLIMATE_LABEL: Record<string, { label: string; emoji: string; tone: string }> = {
  neutral: { label: "ENSO neutral", emoji: "⚖", tone: "text-slate-300 border-slate-600/40 bg-slate-800/40" },
  la_nina_weak: { label: "La Niña débil", emoji: "❄", tone: "text-sky-300 border-sky-700/40 bg-sky-950/30" },
  la_nina_moderate: { label: "La Niña moderada", emoji: "❄", tone: "text-sky-200 border-sky-600/50 bg-sky-950/40" },
  la_nina_strong: { label: "La Niña fuerte", emoji: "❄", tone: "text-sky-100 border-sky-500/60 bg-sky-900/50" },
  el_nino_weak: { label: "El Niño débil", emoji: "🌡", tone: "text-amber-300 border-amber-700/40 bg-amber-950/30" },
  el_nino_moderate: { label: "El Niño moderado", emoji: "🌡", tone: "text-orange-300 border-orange-600/50 bg-orange-950/40" },
  el_nino_strong: { label: "El Niño fuerte", emoji: "🔥", tone: "text-red-300 border-red-600/50 bg-red-950/40" },
  el_nino_costero: { label: "El Niño Costero", emoji: "🌊", tone: "text-red-200 border-red-500/60 bg-red-900/50" },
};

function ClimatePanel({
  climate,
  base,
  scenario,
}: {
  climate: any;
  base: any;
  scenario: any;
}) {
  const tClim = useTranslations("climate");
  const labelKey = climate?.label ?? "neutral";
  const meta = CLIMATE_LABEL[labelKey] ?? CLIMATE_LABEL.neutral;
  const isCostero = climate?.el_nino_costero === true;
  const severity = Math.max(0, Math.min(1, Number(climate?.severity) || 0));
  const sevPct = Math.round(severity * 100);

  const showScenario = !!scenario && severity > 0;

  return (
    <section className={`rounded-xl border ${meta.tone} p-4 space-y-3`}>
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-2">
          <span className="text-lg" aria-hidden>
            {meta.emoji}
          </span>
          <h3 className="text-[10px] uppercase tracking-[0.18em] font-semibold">
            {tClim("panel_title")}
          </h3>
        </div>
        <span className="text-[10px] font-mono uppercase tracking-wider opacity-80">
          {climate?.observation_year} · Niño 3.4: {climate?.nino_3_4_anomaly_c?.toFixed(2)}°C
          {climate?.nino_1_2_anomaly_c != null && (
            <> · Niño 1+2: {climate.nino_1_2_anomaly_c.toFixed(2)}°C</>
          )}
        </span>
      </div>

      <div className="flex items-baseline justify-between gap-2 flex-wrap">
        <div>
          <div className="text-xl font-bold">{tClim(`labels.${labelKey}` as any) ?? meta.label}</div>
          {isCostero && (
            <p className="text-[11px] opacity-80 mt-0.5">{tClim("costero_explainer")}</p>
          )}
        </div>
        <div className="text-right">
          <div className="text-xs uppercase tracking-wider opacity-60">{tClim("severity")}</div>
          <div className="text-2xl font-bold leading-none mt-0.5">{sevPct}%</div>
        </div>
      </div>

      {showScenario && base && (
        <div className="pt-2 border-t border-current/20">
          <div className="text-[10px] uppercase tracking-[0.18em] font-semibold opacity-80 mb-2">
            {tClim("scenario_compare_title")}
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            <ScenarioCol
              title={tClim("base_label")}
              pred={base}
              accent={false}
            />
            <ScenarioCol
              title={isCostero ? "El Niño Costero" : tClim("nino_label")}
              pred={scenario}
              accent={true}
            />
          </div>
          {scenario?._method && (
            <p className="text-[10px] opacity-60 italic mt-2 leading-snug">
              {tClim("method_prefix")}: {scenario._method}
            </p>
          )}
        </div>
      )}

      {climate?.sources && (
        <div className="flex items-center gap-2 text-[10px] opacity-60 pt-2 border-t border-current/20">
          <span className="uppercase tracking-wider font-semibold">{tClim("sources")}:</span>
          {climate.sources.map((s: any, i: number) => (
            <a
              key={i}
              href={s.url}
              target="_blank"
              rel="noopener noreferrer"
              className="underline hover:opacity-100"
            >
              {s.name}
            </a>
          ))}
        </div>
      )}
    </section>
  );
}

function ScenarioCol({
  title,
  pred,
  accent,
}: {
  title: string;
  pred: any;
  accent: boolean;
}) {
  const bg = accent
    ? "bg-red-950/30 border-red-600/50"
    : "bg-slate-900/40 border-slate-700/40";
  return (
    <div className={`rounded-lg border ${bg} p-3 space-y-1.5`}>
      <div className={`text-[10px] uppercase tracking-[0.18em] font-semibold ${accent ? "text-red-200" : "text-slate-400"}`}>
        {title}
      </div>
      <div className="space-y-1 text-xs">
        <ScenarioRow label="Afectados 30d" value={pred?.people_affected_30d?.toLocaleString() ?? "—"} bold accent={accent} />
        <ScenarioRow label="Mortandad pisc." value={pred?.fish_dieoff_30d_pct != null ? `${Math.round(pred.fish_dieoff_30d_pct)}%` : "—"} />
        <ScenarioRow label="Recuperación" value={pred?.recovery_days != null ? `${pred.recovery_days} d` : "—"} />
        <ScenarioRow label="Daño USD" value={pred?.economic_damage_usd != null ? `$${pred.economic_damage_usd.toLocaleString("en-US")}` : "—"} />
      </div>
    </div>
  );
}

function ScenarioRow({
  label,
  value,
  bold,
  accent,
}: {
  label: string;
  value: React.ReactNode;
  bold?: boolean;
  accent?: boolean;
}) {
  return (
    <div className="flex items-baseline justify-between gap-2">
      <span className="text-[10px] text-slate-500 flex-shrink-0">{label}</span>
      <span className={`${bold ? "font-bold" : ""} ${accent && bold ? "text-red-200" : "text-slate-200"}`}>
        {value}
      </span>
    </div>
  );
}
