"use client";
import { useEffect, useState } from "react";
import Leaderboard from "@/components/Leaderboard";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type SortKey = "total_spills" | "fines_paid" | "open_sanctions";

export default function LeaderboardPage() {
  const [data, setData] = useState<any[]>([]);
  const [sortKey, setSortKey] = useState<SortKey>("total_spills");
  const [error, setError] = useState(false);

  useEffect(() => {
    fetch(`${API}/leaderboard`)
      .then((r) => {
        if (!r.ok) throw new Error("fetch failed");
        return r.json();
      })
      .then(setData)
      .catch(() => setError(true));
  }, []);

  const sortedData = [...data].sort((a, b) => {
    const va = a[sortKey];
    const vb = b[sortKey];
    const na = typeof va === "number" ? va : -1;
    const nb = typeof vb === "number" ? vb : -1;
    return nb - na;
  });

  return (
    <div className="max-w-6xl mx-auto p-6">
      <div className="mb-6">
        <p className="text-xs uppercase tracking-wider text-teal-400">Audit trail probatorio</p>
        <h1 className="text-2xl md:text-3xl font-bold mt-1">
          Operadores con derrames documentados — Amazonía peruana
        </h1>
        <p className="text-slate-300 text-sm mt-2 max-w-3xl">
          Operadores con mayor número de derrames documentados en la Amazonía peruana
          <strong className="text-slate-100"> 1997-2023</strong>. Datos: OEFA, OSINERGMIN,
          Oxfam y Mongabay Latam.{" "}
          <span className="text-slate-400">
            Total verificado: <strong className="text-red-400">831 derrames</strong> en Amazonía /
            <strong className="text-red-400"> 1,462</strong> a nivel nacional.
          </span>
        </p>
      </div>

      <div className="flex flex-wrap gap-2 mb-4">
        <span className="text-sm text-slate-400 self-center">Ordenar por:</span>
        {[
          { key: "total_spills" as const, label: "N° derrames" },
          { key: "fines_paid" as const, label: "Multas pagadas" },
          { key: "open_sanctions" as const, label: "Sanciones abiertas" },
        ].map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setSortKey(key)}
            className={`px-3 py-1 text-sm rounded-full transition-colors ${
              sortKey === key
                ? "bg-teal-600 text-white"
                : "bg-slate-700 text-slate-300 hover:bg-slate-600"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {error && (
        <p className="text-red-400 text-sm mb-4">
          No se pudo cargar el ranking. Verificar que el backend está activo y que seed_demo.py fue ejecutado.
        </p>
      )}
      {!error && data.length === 0 && (
        <p className="text-slate-500 text-sm mb-4">
          Sin datos. Ejecutar{" "}
          <code className="font-mono bg-slate-800 px-1 rounded">python backend/seed_demo.py</code>{" "}
          para poblar el ranking.
        </p>
      )}

      <Leaderboard data={sortedData} />

      <div className="text-xs text-slate-500 mt-4 space-y-2">
        <p>
          <strong>Fuentes verificables:</strong> OEFA — registros de fiscalización 2014-2023 ·
          OSINERGMIN — sanciones a operadores de hidrocarburos · Oxfam Internacional —
          informe "La Sombra del Petróleo" (2019) · Mongabay Latam — investigaciones de
          derrames Loreto · El Comercio — base de datos Oleoducto Norperuano.
        </p>
        <p>
          <strong>Lenguaje:</strong> los derrames son hechos documentados; la atribución de
          responsabilidad individual es <em>presunta, sujeta a verificación in situ</em> por
          la autoridad competente. Marcadas "Datos en validación" donde el dato individual
          por operador aún no haya sido cotejado con OEFA pre-publicación.
        </p>
      </div>
    </div>
  );
}
