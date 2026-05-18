"use client";
import { useState } from "react";
import { useTranslations } from "next-intl";
import { readableConcession } from "@/utils/concession";
import { projectUnderElNino } from "@/utils/climate";

type PublishChannel = "federation" | "press";
type PublishStatus = "idle" | "sending" | "sent" | "error";

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

  // Climate context — the /state/at-alert endpoint returns { current, historical }.
  // For the narrative we use the historical state (what ENSO looked like when the
  // incident actually happened) and fall back to current if no historical match.
  const climate =
    alert.climate_state ??
    climateState?.historical ??
    climateState?.current ??
    climateState;
  const scenario = alert.el_nino_scenario ?? (climate?.label && pred ? projectUnderElNino(pred, climate) : null);
  const climateActive = climate?.severity > 0;

  // Publish-button state. Each channel has independent feedback so the user can
  // re-send one without resetting the other. Click opens a modal with the
  // recipient pre-filled to the demo default (overridable) and a preview of
  // what's about to be sent — no more stray SMS to the hardcoded number.
  const [pubStatus, setPubStatus] = useState<Record<PublishChannel, PublishStatus>>({
    federation: "idle",
    press: "idle",
  });
  const [pubMessage, setPubMessage] = useState<Record<PublishChannel, string>>({
    federation: "",
    press: "",
  });
  const [modalChannel, setModalChannel] = useState<PublishChannel | null>(null);

  const openPublishModal = (channel: PublishChannel) => {
    setModalChannel(channel);
  };

  const dispatchPublish = async (channel: PublishChannel, recipient: string) => {
    setModalChannel(null);
    setPubStatus((s) => ({ ...s, [channel]: "sending" }));
    setPubMessage((m) => ({ ...m, [channel]: "" }));

    // Federation flow uses rural-connectivity channels (SMS + WhatsApp) — same
    // phone number is used for both. Press flow uses email. Server-side
    // `channels` query restricts which transports actually fire.
    const channelsParam = channel === "federation" ? "sms,whatsapp" : "email";
    const body =
      channel === "federation"
        ? { sms_recipients: [recipient], whatsapp_recipients: [recipient] }
        : { email_recipients: [recipient] };

    try {
      const resp = await fetch(
        `${apiBase}/publish/${alert.alert_id}?channels=${channelsParam}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        }
      );
      if (!resp.ok) {
        const errText = await resp.text();
        throw new Error(`HTTP ${resp.status}: ${errText.slice(0, 120)}`);
      }
      const data = await resp.json();
      const summary = summarizePublishResult(channel, data, recipient);
      setPubStatus((s) => ({ ...s, [channel]: "sent" }));
      setPubMessage((m) => ({ ...m, [channel]: summary }));
    } catch (e: any) {
      setPubStatus((s) => ({ ...s, [channel]: "error" }));
      setPubMessage((m) => ({ ...m, [channel]: e?.message ?? "Error" }));
    }
  };

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
              <SecondaryAction
                icon="📨"
                label={t("what_to_do.share_federation")}
                onClick={() => openPublishModal("federation")}
                status={pubStatus.federation}
                message={pubMessage.federation}
              />
              <SecondaryAction
                icon="📰"
                label={t("what_to_do.share_press")}
                onClick={() => openPublishModal("press")}
                status={pubStatus.press}
                message={pubMessage.press}
              />
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

      {modalChannel && (
        <PublishModal
          channel={modalChannel}
          alert={alert}
          onCancel={() => setModalChannel(null)}
          onSend={(recipient) => dispatchPublish(modalChannel, recipient)}
        />
      )}
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

function SecondaryAction({
  icon,
  label,
  onClick,
  status = "idle",
  message = "",
}: {
  icon: string;
  label: string;
  onClick?: () => void;
  status?: PublishStatus;
  message?: string;
}) {
  const disabled = status === "sending";
  const statusCls =
    status === "sent"
      ? "bg-emerald-900/30 border-emerald-700/50 text-emerald-200"
      : status === "error"
      ? "bg-rose-900/30 border-rose-700/50 text-rose-200"
      : status === "sending"
      ? "bg-slate-800/80 border-slate-600/60 text-slate-300"
      : "bg-slate-800/60 hover:bg-slate-700/80 border-slate-700/40 text-slate-200";
  const statusIcon =
    status === "sent" ? "✓" : status === "error" ? "⚠" : status === "sending" ? "…" : icon;
  return (
    <div className="flex flex-col gap-1">
      <button
        type="button"
        onClick={onClick}
        disabled={disabled}
        className={`flex items-center justify-center gap-2 px-3 py-2.5 rounded-lg border text-sm transition-colors disabled:opacity-70 disabled:cursor-wait ${statusCls}`}
      >
        <span aria-hidden>{statusIcon}</span>
        {label}
      </button>
      {message && (
        <p
          className={`text-[11px] leading-tight px-1 ${
            status === "error" ? "text-rose-300" : "text-emerald-300"
          }`}
        >
          {message}
        </p>
      )}
    </div>
  );
}

function summarizePublishResult(
  channel: PublishChannel,
  data: any,
  recipient: string
): string {
  const n = data?.notifications ?? {};
  if (channel === "federation") {
    const smsOk = (n.sms ?? []).filter((r: any) => r.sent).length;
    const smsTot = (n.sms ?? []).length;
    const waOk = (n.whatsapp ?? []).filter((r: any) => r.sent).length;
    const waTot = (n.whatsapp ?? []).length;
    if (smsTot + waTot === 0) {
      return "Backend OK pero Zavu no configurado (ZAVU_API_KEY)";
    }
    return `SMS ${smsOk}/${smsTot} · WA ${waOk}/${waTot} → ${maskPhone(recipient)}`;
  }
  if (!n.email) return "Backend OK pero Resend no configurado (RESEND_API_KEY)";
  return `Email enviado → ${recipient}`;
}

function maskPhone(phone: string): string {
  // Keep country code + last 3 digits, mask middle: +51 *** 528
  const clean = phone.replace(/\s/g, "");
  if (clean.length <= 6) return clean;
  return `${clean.slice(0, 3)} *** ${clean.slice(-3)}`;
}

function isValidPhone(p: string): boolean {
  // E.164-ish: starts with + and 8-15 digits
  return /^\+\d{8,15}$/.test(p.replace(/\s/g, ""));
}

function isValidEmail(e: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(e.trim());
}

function PublishModal({
  channel,
  alert,
  onCancel,
  onSend,
}: {
  channel: PublishChannel;
  alert: any;
  onCancel: () => void;
  onSend: (recipient: string) => void;
}) {
  const isFederation = channel === "federation";
  const defaultRecipient = isFederation ? "+51961530528" : "arkhangio@gmail.com";
  const [recipient, setRecipient] = useState(defaultRecipient);
  const valid = isFederation ? isValidPhone(recipient) : isValidEmail(recipient);

  const operator = alert.attribution?.operator_name ?? "operador denunciado";
  const concession = alert.attribution?.concession_id ?? "";
  const priorSanctions = alert.attribution?.prior_sanctions ?? 0;
  const contamType = (alert.contamination_type ?? "contaminación").toUpperCase();
  const affected30d = alert.predictions?.people_affected_30d ?? 0;
  const fishDieoff = alert.predictions?.fish_dieoff_30d_pct ?? 0;
  const alertRef = (alert.alert_id ?? "").slice(0, 8);

  const preview = isFederation
    ? `*ALERTA AMBIENTAL — Guardián del Agua*

*Tipo:* ${contamType}
*Presunto responsable* (sujeto a verificación in situ):
  ${operator}
  Concesión: ${concession}
  Sanciones previas: ${priorSanctions}

*Proyección 30 días:*
• ${affected30d.toLocaleString()} personas potencialmente afectadas
• ${fishDieoff.toFixed(0)}% mortandad piscícola

_Indicios técnicos preliminares. Requiere verificación humana._

Ref: ${alertRef}`
    : `Asunto: Dossier preliminar: presunto responsable ${operator} — ${contamType}

Dossier técnico con cadena de custodia (SHA-256), atribución espacial, modelo XGBoost de impacto, e imagen Sentinel-2 verificable.

Documento PRELIMINAR sujeto a verificación in situ por OEFA.`;

  return (
    <div
      className="fixed inset-0 z-[200] bg-slate-950/85 backdrop-blur-sm flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      onClick={onCancel}
    >
      <div
        className="bg-slate-900 border border-slate-700/60 rounded-2xl max-w-lg w-full p-5 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between mb-3">
          <div>
            <h3 className="text-lg font-semibold text-slate-100">
              {isFederation ? "Enviar a federación" : "Enviar a periodista"}
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              {isFederation
                ? "Se enviará SMS + WhatsApp al número indicado"
                : "Se enviará email al destinatario indicado"}
            </p>
          </div>
          <button
            onClick={onCancel}
            aria-label="Cerrar"
            className="text-slate-500 hover:text-slate-200 text-xl leading-none px-2"
          >
            ×
          </button>
        </div>

        <label className="block mb-3">
          <span className="text-[11px] uppercase tracking-wider text-slate-400 font-semibold">
            {isFederation ? "Número (formato internacional)" : "Email"}
          </span>
          <input
            type={isFederation ? "tel" : "email"}
            value={recipient}
            onChange={(e) => setRecipient(e.target.value)}
            placeholder={isFederation ? "+51961530528" : "destinatario@ejemplo.org"}
            autoFocus
            className={`mt-1 w-full px-3 py-2 rounded-lg bg-slate-950 border text-slate-100 text-sm font-mono focus:outline-none focus:ring-1 ${
              valid
                ? "border-slate-700 focus:border-teal-500 focus:ring-teal-500/40"
                : "border-rose-700/60 focus:border-rose-500 focus:ring-rose-500/40"
            }`}
          />
          {!valid && recipient.length > 0 && (
            <span className="text-[11px] text-rose-300 mt-1 block">
              {isFederation
                ? "Formato esperado: +<código país><número>, p.ej. +51961530528"
                : "Email no válido"}
            </span>
          )}
        </label>

        <div className="mb-4">
          <div className="text-[11px] uppercase tracking-wider text-slate-400 font-semibold mb-1">
            Vista previa del mensaje
          </div>
          <pre className="text-[11px] text-slate-300 bg-slate-950/70 border border-slate-800 rounded-lg p-3 max-h-44 overflow-auto whitespace-pre-wrap font-sans">
            {preview}
          </pre>
        </div>

        <div className="flex gap-2 justify-end">
          <button
            onClick={onCancel}
            className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-sm font-semibold transition-colors"
          >
            Cancelar
          </button>
          <button
            onClick={() => onSend(recipient.trim())}
            disabled={!valid}
            className="px-4 py-2 rounded-lg bg-teal-600 hover:bg-teal-500 disabled:bg-slate-700 disabled:text-slate-500 disabled:cursor-not-allowed text-white text-sm font-semibold transition-colors"
          >
            Enviar
          </button>
        </div>
      </div>
    </div>
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
