"use client";

const TYPE_META: Record<string, { label: string; dot: string; bar: string; bg: string }> = {
  hydrocarbon: {
    label: "Hidrocarburos",
    dot: "bg-red-500",
    bar: "bg-gradient-to-b from-red-500 to-red-600",
    bg: "hover:bg-red-500/5",
  },
  turbidity: {
    label: "Turbidez",
    dot: "bg-orange-400",
    bar: "bg-gradient-to-b from-orange-400 to-orange-500",
    bg: "hover:bg-orange-500/5",
  },
  algal_bloom: {
    label: "Floración algal",
    dot: "bg-green-500",
    bar: "bg-gradient-to-b from-green-500 to-green-600",
    bg: "hover:bg-green-500/5",
  },
};

interface Props {
  alert: any;
  selected: boolean;
  onSelect: () => void;
  onOpenDetail: () => void;
}

export default function AlertCard({ alert, selected, onSelect, onOpenDetail }: Props) {
  const meta = TYPE_META[alert.contamination_type] ?? {
    label: alert.contamination_type,
    dot: "bg-slate-500",
    bar: "bg-slate-500",
    bg: "hover:bg-slate-500/5",
  };

  return (
    <div
      className={`relative pl-3 pr-3 py-3 cursor-pointer transition-all border-b border-slate-800/60 group ${meta.bg} ${
        selected ? "bg-slate-800/40" : ""
      }`}
      onClick={onSelect}
    >
      {/* Severity bar */}
      <div
        className={`absolute left-0 top-2 bottom-2 w-[3px] rounded-r-full ${meta.bar} ${
          selected ? "opacity-100 shadow-glow-red" : "opacity-60 group-hover:opacity-100"
        } transition-opacity`}
      />

      <div className="flex items-start gap-2 ml-1">
        <span className={`mt-1.5 w-2 h-2 rounded-full flex-shrink-0 ${meta.dot}`} />
        <div className="min-w-0 flex-1">
          <p className="font-medium text-sm text-slate-100 truncate">
            {alert.attribution?.operator_name ?? "Detectando…"}
          </p>
          <div className="flex items-center gap-2 mt-0.5">
            <span className="text-[11px] text-slate-400">{meta.label}</span>
            <span className="w-1 h-1 rounded-full bg-slate-600" />
            <span className="text-[11px] text-teal-300 font-medium">
              {(alert.confidence * 100).toFixed(0)}%
            </span>
          </div>
          <p className="text-[10px] text-slate-500 mt-0.5">
            {alert.detected_at ? new Date(alert.detected_at).toLocaleDateString("es-PE") : "—"}
          </p>
          {alert.predictions && (
            <p className="text-[11px] text-red-300/90 mt-1.5 font-medium">
              {alert.predictions.people_affected_30d?.toLocaleString("es-PE")} afectados (30d)
            </p>
          )}
        </div>
      </div>

      <button
        onClick={(e) => {
          e.stopPropagation();
          onOpenDetail();
        }}
        className="mt-2 ml-3 text-[11px] text-teal-400 hover:text-teal-300 font-medium opacity-0 group-hover:opacity-100 transition-opacity"
      >
        Ver dossier →
      </button>
    </div>
  );
}
