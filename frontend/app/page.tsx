"use client";
import dynamic from "next/dynamic";
import { useEffect, useMemo, useState } from "react";
import AlertCard from "@/components/AlertCard";
import AlertInspector from "@/components/AlertInspector";
import AlertDrawer from "@/components/AlertDrawer";

const Map = dynamic(() => import("@/components/Map"), { ssr: false });

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type Filter = "all" | "hydrocarbon" | "turbidity" | "algal_bloom";

const FILTERS: { key: Filter; label: string; dot: string }[] = [
  { key: "all", label: "Todos", dot: "bg-slate-300" },
  { key: "hydrocarbon", label: "Hidrocarburos", dot: "bg-red-500" },
  { key: "turbidity", label: "Turbidez", dot: "bg-orange-400" },
  { key: "algal_bloom", label: "Floración algal", dot: "bg-green-500" },
];

export default function HomePage() {
  const [alerts, setAlerts] = useState<any[]>([]);
  const [error, setError] = useState(false);
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [drawerId, setDrawerId] = useState<string | null>(null);
  const [filter, setFilter] = useState<Filter>("all");

  useEffect(() => {
    fetch(`${API}/detect/alerts?limit=20`)
      .then((r) => {
        if (!r.ok) throw new Error("fetch failed");
        return r.json();
      })
      .then((data) => setAlerts(Array.isArray(data) ? data : []))
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, []);

  const filteredAlerts = useMemo(
    () => (filter === "all" ? alerts : alerts.filter((a) => a.contamination_type === filter)),
    [alerts, filter]
  );

  const selectedAlert = useMemo(
    () => alerts.find((a) => a.alert_id === selectedId) ?? null,
    [alerts, selectedId]
  );

  const counts = useMemo(() => {
    const c = { hydrocarbon: 0, turbidity: 0, algal_bloom: 0 };
    for (const a of alerts) {
      if (a.contamination_type in c) (c as any)[a.contamination_type]++;
    }
    return c;
  }, [alerts]);

  return (
    <div className="relative flex flex-col h-full">
      {/* Compact hero */}
      <header className="relative px-6 py-4 border-b border-slate-800/60 glass-soft z-10">
        <div className="max-w-7xl mx-auto flex flex-wrap items-center gap-x-6 gap-y-2">
          <div className="min-w-0">
            <h1 className="text-lg md:text-xl font-bold text-slate-50 leading-tight">
              Audit trail probatorio ·{" "}
              <span className="text-gradient-teal">Amazonía peruana</span>
            </h1>
            <p className="text-xs text-slate-400 mt-0.5">
              Sentinel-2 + Claude + Ley peruana · listo para OEFA en menos de 25 horas
            </p>
          </div>
          <div className="ml-auto flex items-center gap-3 text-[11px]">
            <Pill color="bg-red-500" label={`${counts.hydrocarbon} hidrocarburos`} />
            <Pill color="bg-orange-400" label={`${counts.turbidity} turbidez`} />
            <Pill color="bg-green-500" label={`${counts.algal_bloom} algal`} />
          </div>
        </div>
      </header>

      <div className="flex flex-1 min-h-0">
        {/* Sidebar */}
        <aside className="w-[340px] glass-soft border-r border-slate-800/60 flex flex-col overflow-hidden flex-shrink-0">
          <div className="px-4 py-3 border-b border-slate-800/60 flex-shrink-0">
            <h2 className="font-semibold text-slate-200 text-sm">Dossiers probatorios</h2>
            <p className="text-[11px] text-slate-400 mt-0.5">
              {filteredAlerts.length} evidencia{filteredAlerts.length === 1 ? "" : "s"} técnica
              {filteredAlerts.length === 1 ? "" : "s"} · Cuatro Cuencas / Loreto
            </p>
          </div>

          {/* Filter pills */}
          <div className="px-3 py-2 flex flex-wrap gap-1 border-b border-slate-800/60 flex-shrink-0">
            {FILTERS.map((f) => (
              <button
                key={f.key}
                onClick={() => setFilter(f.key)}
                className={`flex items-center gap-1.5 px-2 py-1 rounded-full text-[11px] font-medium transition-colors ${
                  filter === f.key
                    ? "bg-teal-500/20 text-teal-200 ring-1 ring-teal-500/40"
                    : "bg-slate-800/40 text-slate-400 hover:text-slate-200"
                }`}
              >
                <span className={`w-1.5 h-1.5 rounded-full ${f.dot}`} />
                {f.label}
              </button>
            ))}
          </div>

          {/* Alert list */}
          <div className="flex-1 overflow-y-auto gda-scroll">
            {loading && (
              <div className="p-4 space-y-3">
                {[0, 1, 2].map((i) => (
                  <div key={i} className="h-16 bg-slate-800/40 rounded animate-pulse" />
                ))}
              </div>
            )}
            {!loading && error && (
              <div className="p-4 text-[11px] text-red-300 bg-red-950/20 border-y border-red-900/30">
                No se pudo conectar con el backend en{" "}
                <code className="font-mono text-red-200">{API}</code>.
              </div>
            )}
            {!loading && !error && filteredAlerts.length === 0 && (
              <p className="p-4 text-[11px] text-slate-500">
                Sin dossiers para este filtro. Ejecutar{" "}
                <code className="font-mono bg-slate-800/60 px-1 rounded">seed_demo.py</code> o{" "}
                <code className="font-mono bg-slate-800/60 px-1 rounded">POST /detect/run</code>.
              </p>
            )}
            {filteredAlerts.map((a) => (
              <AlertCard
                key={a.alert_id}
                alert={a}
                selected={selectedId === a.alert_id}
                onSelect={() => setSelectedId(a.alert_id)}
                onOpenDetail={() => setDrawerId(a.alert_id)}
              />
            ))}
          </div>

          {/* Footer chip */}
          <div className="px-4 py-2.5 border-t border-slate-800/60 text-[10px] text-slate-500 leading-relaxed flex-shrink-0">
            <span className="italic">Esto ya no es denuncia. Es prueba.</span>
          </div>
        </aside>

        {/* Map */}
        <div className="flex-1 relative">
          <Map alerts={filteredAlerts} selectedId={selectedId} onSelect={setSelectedId} />

          {/* Legend */}
          <div className="absolute bottom-4 left-4 glass rounded-xl px-3 py-2.5 text-[11px] space-y-1.5 z-20">
            <div className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold pb-1 border-b border-slate-700/40 mb-1">
              Tipo de contaminación
            </div>
            <LegendItem color="bg-red-500" label="Hidrocarburos" />
            <LegendItem color="bg-orange-400" label="Turbidez alta" />
            <LegendItem color="bg-green-500" label="Floración algal" />
          </div>

          {/* Floating inspector card */}
          {selectedAlert && (
            <AlertInspector
              key={selectedAlert.alert_id}
              alert={selectedAlert}
              apiBase={API}
              onClose={() => setSelectedId(null)}
              onOpenDrawer={() => setDrawerId(selectedAlert.alert_id)}
            />
          )}
        </div>
      </div>

      {/* Slide-in drawer */}
      <AlertDrawer alertId={drawerId} apiBase={API} onClose={() => setDrawerId(null)} />
    </div>
  );
}

function Pill({ color, label }: { color: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-slate-800/50 border border-slate-700/40 text-slate-300">
      <span className={`w-1.5 h-1.5 rounded-full ${color}`} />
      {label}
    </span>
  );
}

function LegendItem({ color, label }: { color: string; label: string }) {
  return (
    <div className="flex items-center gap-2 text-slate-300">
      <span className={`w-2.5 h-2.5 rounded-full ${color} ring-2 ring-white/20`} />
      {label}
    </div>
  );
}
