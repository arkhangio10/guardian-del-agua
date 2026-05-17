"use client";
import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";

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

  const [alert, setAlert] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [imgError, setImgError] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [denuncia, setDenuncia] = useState<any>(null);
  const [denunciaError, setDenunciaError] = useState<string | null>(null);

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
                <div className="aspect-[16/10] relative">
                  {!imgError ? (
                    <img
                      src={`${apiBase}/detect/alerts/${alert.alert_id}/image`}
                      alt={tAlert("alt_satellite")}
                      className="w-full h-full object-cover"
                      style={{ filter: "contrast(1.35) saturate(1.5) brightness(1.05)" }}
                      onError={() => setImgError(true)}
                    />
                  ) : (
                    <div className="absolute inset-0 flex items-center justify-center text-sm text-slate-500 italic">
                      {tAlert("image_unavailable")}
                    </div>
                  )}
                  <div className="absolute inset-0 bg-gradient-to-t from-slate-950 via-slate-950/40 to-transparent pointer-events-none" />
                  <div className="absolute inset-4 border border-teal-400/50 rounded-xl pointer-events-none" />
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
