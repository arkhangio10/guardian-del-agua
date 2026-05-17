"use client";

interface Entry {
  rank?: number;
  operator_name: string;
  asset_label?: string;
  total_spills: number;
  spills_period?: string;
  fines_paid?: number | null;
  fines_imposed?: number | null;
  open_sanctions?: number | null;
  legal_status: string;
  source?: string;
  total_volume_barrels?: number;
}

const STATUS_LABELS: Record<string, { label: string; cls: string }> = {
  active: { label: "Activo", cls: "bg-red-900/50 text-red-300" },
  in_liquidation: { label: "En liquidación", cls: "bg-yellow-900/50 text-yellow-300" },
  divested: { label: "Desvinculado", cls: "bg-yellow-900/50 text-yellow-300" },
  settled: { label: "Acuerdo", cls: "bg-green-900/50 text-green-300" },
};

function formatFines(paid: number | null | undefined, imposed: number | null | undefined) {
  if (paid == null && imposed == null) {
    return <span className="text-slate-500 italic text-xs">Datos en validación</span>;
  }
  if (paid != null && imposed != null) {
    return (
      <span>
        <span className="font-bold text-orange-300">{paid}</span>
        <span className="text-slate-500"> / {imposed}</span>
      </span>
    );
  }
  return <span className="text-slate-500 italic text-xs">Parcial</span>;
}

export default function Leaderboard({ data }: { data: Entry[] }) {
  return (
    <div className="bg-slate-800 rounded-xl border border-slate-700 overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-slate-700/50 text-left text-xs text-slate-400 uppercase tracking-wide">
            <th className="px-4 py-3">#</th>
            <th className="px-4 py-3">Operador / activo</th>
            <th className="px-4 py-3 text-right">Derrames</th>
            <th className="px-4 py-3">Período</th>
            <th className="px-4 py-3 text-right">Multas pagadas / impuestas</th>
            <th className="px-4 py-3 text-right">Sanciones abiertas</th>
            <th className="px-4 py-3">Estado</th>
            <th className="px-4 py-3">Fuente</th>
          </tr>
        </thead>
        <tbody>
          {data.map((row, i) => {
            const status =
              STATUS_LABELS[row.legal_status] ?? {
                label: row.legal_status,
                cls: "bg-slate-700 text-slate-300",
              };
            return (
              <tr
                key={`${row.operator_name}-${i}`}
                className="border-t border-slate-700 hover:bg-slate-700/30 transition-colors align-top"
              >
                <td className="px-4 py-3 font-bold text-slate-400">{row.rank ?? i + 1}</td>
                <td className="px-4 py-3">
                  <div className="font-semibold">{row.operator_name}</div>
                  {row.asset_label && (
                    <div className="text-xs text-slate-400 mt-0.5">{row.asset_label}</div>
                  )}
                </td>
                <td className="px-4 py-3 text-right font-bold text-red-400">
                  {row.total_spills.toLocaleString("es-PE")}
                </td>
                <td className="px-4 py-3 text-xs text-slate-400">{row.spills_period ?? "—"}</td>
                <td className="px-4 py-3 text-right">
                  {formatFines(row.fines_paid, row.fines_imposed)}
                </td>
                <td className="px-4 py-3 text-right">
                  {row.open_sanctions == null ? (
                    <span className="text-slate-500 italic text-xs">En validación</span>
                  ) : row.open_sanctions > 0 ? (
                    <span className="text-yellow-400 font-bold">{row.open_sanctions}</span>
                  ) : (
                    <span className="text-slate-500">0</span>
                  )}
                </td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-1 rounded-full text-xs ${status.cls}`}>
                    {status.label}
                  </span>
                </td>
                <td className="px-4 py-3 text-xs text-slate-400 max-w-[14rem]">
                  {row.source ?? "—"}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
