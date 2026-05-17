"use client";
import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import AlertCard from "@/components/AlertCard";

const Map = dynamic(() => import("@/components/Map"), { ssr: false });

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function HomePage() {
  const [alerts, setAlerts] = useState<any[]>([]);
  const [error, setError] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${API}/detect/alerts?limit=20`)
      .then((r) => {
        if (!r.ok) throw new Error("fetch failed");
        return r.json();
      })
      .then(setAlerts)
      .catch(() => setError(true));
  }, []);

  return (
    <div className="flex flex-col">
      <header className="bg-slate-800 border-b border-slate-700 px-6 py-6">
        <div className="max-w-6xl mx-auto">
          <h1 className="text-2xl md:text-3xl font-bold text-teal-300">
            El primer audit trail probatorio para denuncias ambientales en la Amazonía peruana.
          </h1>
          <p className="mt-2 text-slate-300 text-sm md:text-base">
            Sentinel-2 + Claude + Ley peruana, en español jurídico, listo para OEFA en menos de 25 horas.
          </p>
          <p className="mt-3 italic text-teal-200 text-sm">
            Esto ya no es denuncia. Es prueba.
          </p>
        </div>
      </header>

      <div className="flex h-[calc(100vh-52px-160px)]">
      <aside className="w-80 bg-slate-800 border-r border-slate-700 flex flex-col overflow-hidden">
        <div className="p-4 border-b border-slate-700">
          <h2 className="font-semibold text-slate-200">Dossiers probatorios</h2>
          <p className="text-xs text-slate-400 mt-1">{alerts.length} evidencia(s) técnica(s) de contaminación</p>
        </div>
        <div className="flex-1 overflow-y-auto">
          {error && (
            <p className="p-4 text-xs text-red-400">No se pudo conectar con el servidor. Verificar que el backend está activo en {API}.</p>
          )}
          {!error && alerts.length === 0 && (
            <p className="p-4 text-xs text-slate-500">Sin dossiers. Ejecutar seed_demo.py o POST /detect/run para generar evidencias.</p>
          )}
          {alerts.map((a) => (
            <AlertCard
              key={a.alert_id}
              alert={a}
              selected={selected === a.alert_id}
              onClick={() => setSelected(a.alert_id)}
            />
          ))}
        </div>
      </aside>

      <div className="flex-1 relative">
        <Map alerts={alerts} selectedId={selected} onSelect={setSelected} />
        <div className="absolute bottom-4 left-4 bg-slate-800/90 rounded-lg p-3 text-xs space-y-1">
          <div className="flex items-center gap-2"><span className="w-3 h-3 rounded-full bg-red-500 inline-block" /> Hidrocarburos</div>
          <div className="flex items-center gap-2"><span className="w-3 h-3 rounded-full bg-orange-400 inline-block" /> Turbidez</div>
          <div className="flex items-center gap-2"><span className="w-3 h-3 rounded-full bg-green-500 inline-block" /> Floración Algal</div>
        </div>
      </div>
      </div>
    </div>
  );
}
