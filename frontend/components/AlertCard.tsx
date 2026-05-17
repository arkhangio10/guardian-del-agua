"use client";
import { useTranslations } from "next-intl";

const TYPE_META: Record<string, { tKey: string; dot: string; bar: string; bg: string }> = {
  hydrocarbon: {
    tKey: "hydrocarbon_short",
    dot: "bg-red-500",
    bar: "bg-gradient-to-b from-red-500 to-red-600",
    bg: "hover:bg-red-500/5",
  },
  turbidity: {
    tKey: "turbidity_short",
    dot: "bg-orange-400",
    bar: "bg-gradient-to-b from-orange-400 to-orange-500",
    bg: "hover:bg-orange-500/5",
  },
  algal_bloom: {
    tKey: "algal_bloom_short",
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
  const tAlert = useTranslations("alert");
  const tContam = useTranslations("contamination");

  const meta = TYPE_META[alert.contamination_type];
  const label = meta ? tContam(meta.tKey as any) : alert.contamination_type;
  const dot = meta?.dot ?? "bg-slate-500";
  const bar = meta?.bar ?? "bg-slate-500";
  const bg = meta?.bg ?? "hover:bg-slate-500/5";

  return (
    <div
      className={`relative pl-3 pr-3 py-3 cursor-pointer transition-all border-b border-slate-800/60 group ${bg} ${
        selected ? "bg-slate-800/40" : ""
      }`}
      onClick={onSelect}
    >
      <div
        className={`absolute left-0 top-2 bottom-2 w-[3px] rounded-r-full ${bar} ${
          selected ? "opacity-100 shadow-glow-red" : "opacity-60 group-hover:opacity-100"
        } transition-opacity`}
      />

      <div className="flex items-start gap-2 ml-1">
        <span className={`mt-1.5 w-2 h-2 rounded-full flex-shrink-0 ${dot}`} />
        <div className="min-w-0 flex-1">
          <p className="font-medium text-sm text-slate-100 truncate">
            {alert.attribution?.operator_name ?? tAlert("detecting")}
          </p>
          <div className="flex items-center gap-2 mt-0.5">
            <span className="text-[11px] text-slate-400">{label}</span>
            <span className="w-1 h-1 rounded-full bg-slate-600" />
            <span className="text-[11px] text-teal-300 font-medium">
              {(alert.confidence * 100).toFixed(0)}%
            </span>
          </div>
          <p className="text-[10px] text-slate-500 mt-0.5">
            {alert.detected_at ? new Date(alert.detected_at).toLocaleDateString() : "—"}
          </p>
          {alert.predictions && (
            <p className="text-[11px] text-red-300/90 mt-1.5 font-medium">
              {tAlert("affected_30d_long", {
                count: alert.predictions.people_affected_30d?.toLocaleString() ?? "—",
              })}
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
        {tAlert("view_dossier_short")} →
      </button>
    </div>
  );
}
