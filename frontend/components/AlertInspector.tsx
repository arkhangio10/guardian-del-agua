"use client";
import { useState } from "react";

const TYPE_META: Record<
  string,
  { label: string; dot: string; ring: string; chip: string; claudeNote: string }
> = {
  hydrocarbon: {
    label: "Hidrocarburos",
    dot: "bg-red-500",
    ring: "ring-red-500/40",
    chip: "bg-red-500/15 text-red-300 border-red-500/30",
    claudeNote:
      "Claude detectó manchas oscuras con brillo iridiscente en superficie — patrón consistente con derrame de petróleo.",
  },
  turbidity: {
    label: "Turbidez alta",
    dot: "bg-orange-400",
    ring: "ring-orange-400/40",
    chip: "bg-orange-500/15 text-orange-300 border-orange-500/30",
    claudeNote:
      "Claude identificó coloración marrón-rojiza atípica en el cauce — sedimentos en suspensión sobre el agua.",
  },
  algal_bloom: {
    label: "Floración algal",
    dot: "bg-green-500",
    ring: "ring-green-500/40",
    chip: "bg-green-500/15 text-green-300 border-green-500/30",
    claudeNote:
      "Claude detectó manchas verdes brillantes — pico de clorofila típico de eutrofización.",
  },
};

interface Props {
  alert: any;
  apiBase: string;
  onClose: () => void;
  onOpenDrawer: () => void;
}

export default function AlertInspector({ alert, apiBase, onClose, onOpenDrawer }: Props) {
  const [imgError, setImgError] = useState(false);
  const meta = TYPE_META[alert.contamination_type] ?? {
    label: alert.contamination_type,
    dot: "bg-slate-400",
    ring: "ring-slate-400/40",
    chip: "bg-slate-500/15 text-slate-300 border-slate-500/30",
  };

  const at = alert.attribution;
  const detectedAt = alert.detected_at ? new Date(alert.detected_at).toLocaleDateString("es-PE") : "—";

  return (
    <div
      className="absolute top-4 right-4 z-30 w-[340px] glass rounded-2xl shadow-glow-teal overflow-hidden animate-slide-in-card"
      onClick={(e) => e.stopPropagation()}
    >
      {/* Satellite image */}
      <div className="relative h-[200px] bg-slate-900 overflow-hidden">
        {!imgError ? (
          <img
            src={`${apiBase}/detect/alerts/${alert.alert_id}/image`}
            alt="Vista satelital del área"
            className="w-full h-full object-cover"
            onError={() => setImgError(true)}
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-xs text-slate-500 italic">
            Imagen satelital no disponible
          </div>
        )}
        {/* Gradient overlay */}
        <div className="absolute inset-0 bg-gradient-to-t from-slate-950/95 via-slate-950/30 to-transparent pointer-events-none" />
        {/* Crosshair frame */}
        <div className="absolute inset-3 border border-teal-400/40 rounded-lg pointer-events-none">
          <CrossCorner pos="tl" />
          <CrossCorner pos="tr" />
          <CrossCorner pos="bl" />
          <CrossCorner pos="br" />
        </div>
        {/* Top-left chip */}
        <div className="absolute top-3 left-3 flex items-center gap-2">
          <span
            className={`px-2 py-0.5 rounded-full text-[11px] font-medium border ${meta.chip}`}
          >
            <span className={`inline-block w-1.5 h-1.5 rounded-full ${meta.dot} mr-1.5 align-middle`} />
            {meta.label}
          </span>
        </div>
        {/* Close button */}
        <button
          onClick={onClose}
          className="absolute top-3 right-3 w-7 h-7 rounded-full bg-slate-950/60 hover:bg-slate-900/80 text-slate-300 flex items-center justify-center transition-colors backdrop-blur"
          aria-label="Cerrar"
        >
          ×
        </button>
        {/* Sentinel badge */}
        <div className="absolute bottom-2 left-3 text-[10px] uppercase tracking-wider text-teal-300/90 font-mono">
          Sentinel-2 L2A · {alert.sentinel_image_id ?? ""}
        </div>
      </div>

      {/* Body */}
      <div className="p-4 space-y-3">
        {/* Claude analysis caption */}
        <div className="flex items-start gap-2 -mt-1 mb-1 px-2.5 py-2 rounded-lg bg-teal-500/10 border border-teal-500/25">
          <span className="text-teal-300 text-[11px] font-semibold uppercase tracking-wider flex-shrink-0 mt-0.5">
            IA
          </span>
          <p className="text-[12px] text-slate-200 leading-snug">
            {alert.description ?? meta.claudeNote}
          </p>
        </div>

        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <h3 className="font-semibold text-slate-100 text-base leading-tight truncate">
              {at?.operator_name ?? "Operador desconocido"}
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              {at?.concession_id ? `Concesión ${at.concession_id} · ` : ""}
              {detectedAt}
            </p>
          </div>
          <div className="text-right flex-shrink-0">
            <div className="text-2xl font-bold text-gradient-teal leading-none">
              {(alert.confidence * 100).toFixed(0)}%
            </div>
            <div className="text-[10px] uppercase tracking-wider text-slate-500 mt-0.5">
              confianza
            </div>
          </div>
        </div>

        {/* Quick stats */}
        <div className="grid grid-cols-2 gap-2 text-xs">
          <Stat
            label="Sanciones previas"
            value={at?.prior_sanctions != null ? at.prior_sanctions.toLocaleString("es-PE") : "—"}
            tone="warn"
          />
          <Stat
            label="Afectados (30d)"
            value={
              alert.predictions?.people_affected_30d
                ? alert.predictions.people_affected_30d.toLocaleString("es-PE")
                : "—"
            }
            tone="danger"
          />
        </div>

        {/* CTA */}
        <button
          onClick={onOpenDrawer}
          className="w-full mt-1 bg-teal-400 hover:bg-teal-300 active:bg-teal-500 text-slate-950 font-bold py-3 rounded-lg text-sm transition-all shadow-lg shadow-teal-500/30 hover:shadow-teal-400/50 ring-1 ring-teal-300/50 flex items-center justify-center gap-2"
          style={{ textShadow: "none" }}
        >
          Ver dossier completo
          <span aria-hidden className="font-bold">→</span>
        </button>
      </div>
    </div>
  );
}

function Stat({ label, value, tone }: { label: string; value: React.ReactNode; tone: "warn" | "danger" }) {
  const valueCls = tone === "danger" ? "text-red-300" : "text-amber-300";
  return (
    <div className="bg-slate-900/60 border border-slate-700/40 rounded-lg px-3 py-2">
      <div className={`font-bold text-sm ${valueCls}`}>{value}</div>
      <div className="text-[10px] uppercase tracking-wider text-slate-500 mt-0.5">{label}</div>
    </div>
  );
}

function CrossCorner({ pos }: { pos: "tl" | "tr" | "bl" | "br" }) {
  const base = "absolute w-3 h-3 border-teal-300";
  const map: Record<string, string> = {
    tl: "top-0 left-0 border-t border-l rounded-tl-md",
    tr: "top-0 right-0 border-t border-r rounded-tr-md",
    bl: "bottom-0 left-0 border-b border-l rounded-bl-md",
    br: "bottom-0 right-0 border-b border-r rounded-br-md",
  };
  return <div className={`${base} ${map[pos]}`} />;
}
