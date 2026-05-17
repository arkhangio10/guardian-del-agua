import { useRouter } from "next/navigation";

const TYPE_COLOR: Record<string, string> = {
  hydrocarbon: "border-l-red-500 bg-red-900/10",
  turbidity: "border-l-orange-400 bg-orange-900/10",
  algal_bloom: "border-l-green-500 bg-green-900/10",
};

const TYPE_DOT: Record<string, string> = {
  hydrocarbon: "bg-red-500",
  turbidity: "bg-orange-400",
  algal_bloom: "bg-green-500",
};

const TYPE_LABEL: Record<string, string> = {
  hydrocarbon: "Hidrocarburos",
  turbidity: "Turbidez",
  algal_bloom: "Floración Algal",
};

interface Props {
  alert: any;
  selected: boolean;
  onClick: () => void;
}

export default function AlertCard({ alert, selected, onClick }: Props) {
  const router = useRouter();
  const colorClass = TYPE_COLOR[alert.contamination_type] ?? "border-l-slate-500 bg-slate-800/50";
  const dotClass = TYPE_DOT[alert.contamination_type] ?? "bg-slate-500";

  return (
    <div
      className={`border-l-4 p-3 cursor-pointer transition-colors hover:bg-slate-700/40 ${colorClass} ${
        selected ? "ring-1 ring-teal-500/50" : ""
      }`}
      onClick={onClick}
    >
      <div className="flex items-start gap-2">
        <span className={`mt-1 w-2 h-2 rounded-full flex-shrink-0 ${dotClass}`} />
        <div className="min-w-0 flex-1">
          <p className="font-medium text-sm truncate">{alert.attribution?.operator_name ?? "Detectando..."}</p>
          <p className="text-xs text-slate-400 mt-0.5">{TYPE_LABEL[alert.contamination_type] ?? alert.contamination_type}</p>
          <p className="text-xs text-slate-500 mt-0.5">
            {new Date(alert.detected_at).toLocaleDateString("es-PE")} ·{" "}
            {(alert.confidence * 100).toFixed(0)}% confianza
          </p>
          {alert.predictions && (
            <p className="text-xs text-red-400 mt-1">
              {alert.predictions.people_affected_30d?.toLocaleString("es-PE")} personas afectadas
            </p>
          )}
        </div>
      </div>
      <button
        onClick={(e) => { e.stopPropagation(); router.push(`/alerts/${alert.alert_id}`); }}
        className="mt-2 text-xs text-teal-400 hover:text-teal-300 underline"
      >
        Ver detalles →
      </button>
    </div>
  );
}
