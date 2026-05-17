"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const TYPE_COLOR: Record<string, string> = {
  hydrocarbon: "bg-red-600",
  turbidity: "bg-orange-500",
  algal_bloom: "bg-green-600",
};

const TYPE_LABEL: Record<string, string> = {
  hydrocarbon: "Hidrocarburos",
  turbidity: "Turbidez alta",
  algal_bloom: "Floración Algal",
};

export default function AlertDetailPage() {
  const params = useParams();
  const alertId = params?.id as string;

  const [alert, setAlert] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [denuncia, setDenuncia] = useState<any>(null);

  useEffect(() => {
    fetch(`${API}/detect/alerts/${alertId}`)
      .then((r) => {
        if (!r.ok) throw new Error("not found");
        return r.json();
      })
      .then(setAlert)
      .catch(() => setAlert(null))
      .finally(() => setLoading(false));
  }, [alertId]);

  async function handleGenerateDenuncia() {
    setGenerating(true);
    try {
      const resp = await fetch(`${API}/act/denuncia/${alertId}`, { method: "POST" });
      const data = await resp.json();
      setDenuncia(data);
    } finally {
      setGenerating(false);
    }
  }

  if (loading) return <div className="p-8 text-slate-400">Cargando...</div>;
  if (!alert) return <div className="p-8 text-red-400">Alerta no encontrada: {alertId}</div>;

  const at = alert.attribution;
  const pred = alert.predictions;

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-6">
      {/* Header */}
      <div className="bg-slate-800 rounded-xl p-6 border border-slate-700">
        <div className="flex items-start justify-between">
          <div>
            <span className={`text-xs px-2 py-1 rounded-full text-white ${TYPE_COLOR[alert.contamination_type] ?? "bg-slate-600"}`}>
              {TYPE_LABEL[alert.contamination_type] ?? alert.contamination_type}
            </span>
            <h1 className="text-2xl font-bold mt-2">{at?.operator_name ?? "Operador desconocido"}</h1>
            <p className="text-slate-400 text-sm mt-1">
              Concesión {at?.concession_id} · Detectado: {new Date(alert.detected_at).toLocaleDateString("es-PE")}
            </p>
          </div>
          <div className="text-right">
            <div className="text-3xl font-bold text-teal-400">{(alert.confidence * 100).toFixed(0)}%</div>
            <div className="text-xs text-slate-400">confianza</div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        {/* Attribution */}
        <div className="bg-slate-800 rounded-xl p-5 border border-slate-700">
          <h2 className="font-semibold text-slate-300 mb-3 text-sm uppercase tracking-wide">Operador responsable</h2>
          <dl className="space-y-2 text-sm">
            <Row label="Empresa" value={at?.operator_name} />
            <Row label="OSINERGMIN" value={at?.osinergmin_id} />
            <Row label="Sanciones previas" value={<span className="text-red-400 font-bold">{at?.prior_sanctions}</span>} />
            <Row label="Estado legal" value={at?.legal_status} />
            <Row label="Empresa matriz" value={<span className="text-right text-xs">{at?.parent_company}</span>} />
          </dl>
        </div>

        {/* Satellite evidence */}
        <div className="bg-slate-800 rounded-xl p-5 border border-slate-700">
          <h2 className="font-semibold text-slate-300 mb-3 text-sm uppercase tracking-wide">Evidencia satelital</h2>
          <dl className="space-y-2 text-sm">
            <Row label="Satélite" value="Sentinel-2 L2A" />
            <Row label="ID imagen" value={<span className="text-xs font-mono">{alert.sentinel_image_id}</span>} />
            <Row label="Bbox (WGS84)" value={<span className="text-xs font-mono">{alert.sentinel_bbox?.join(", ")}</span>} />
          </dl>
        </div>
      </div>

      {/* Impact */}
      {pred && (
        <div className="bg-slate-800 rounded-xl p-5 border border-red-800/50">
          <h2 className="font-semibold text-red-400 mb-4 text-sm uppercase tracking-wide">Impacto proyectado</h2>
          <div className="grid grid-cols-3 gap-4">
            <Stat label="Personas afectadas (7d)" value={pred.people_affected_7d?.toLocaleString("es-PE")} />
            <Stat label="Personas afectadas (30d)" value={pred.people_affected_30d?.toLocaleString("es-PE")} highlight />
            <Stat label="Mortandad piscícola" value={`${pred.fish_dieoff_30d_pct?.toFixed(0)}%`} />
            <Stat label="Fuentes de agua en riesgo" value={pred.drinking_water_sources_at_risk} />
            <Stat label="Días de recuperación" value={pred.recovery_days} />
            <Stat label="Daño económico (USD)" value={`$${pred.economic_damage_usd?.toLocaleString("en-US")}`} />
          </div>
        </div>
      )}

      {/* Legal actions */}
      <div className="bg-slate-800 rounded-xl p-5 border border-slate-700">
        <h2 className="font-semibold mb-4 text-sm uppercase tracking-wide">Acciones legales</h2>
        {!denuncia ? (
          <button
            onClick={handleGenerateDenuncia}
            disabled={generating || !at}
            className="bg-teal-600 hover:bg-teal-500 disabled:opacity-50 text-white font-semibold px-6 py-3 rounded-lg transition-colors"
          >
            {generating ? "Generando denuncia..." : "Generar denuncia OEFA (PDF)"}
          </button>
        ) : (
          <div className="space-y-3">
            <p className="text-green-400 text-sm">Denuncia generada en {denuncia.generated_in_ms}ms · {denuncia.pdf_size_bytes} bytes</p>
            <a
              href={`${API}/act/denuncia/${alertId}/download`}
              target="_blank"
              className="inline-block bg-green-700 hover:bg-green-600 text-white font-semibold px-6 py-3 rounded-lg transition-colors"
            >
              Descargar PDF
            </a>
            <pre className="text-slate-400 text-xs mt-2 whitespace-pre-wrap font-mono bg-slate-900 p-3 rounded max-h-48 overflow-y-auto">
              {denuncia.denuncia_preview}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex justify-between items-baseline gap-2">
      <dt className="text-slate-400 flex-shrink-0">{label}</dt>
      <dd className="text-right">{value}</dd>
    </div>
  );
}

function Stat({ label, value, highlight }: { label: string; value: React.ReactNode; highlight?: boolean }) {
  return (
    <div className="bg-slate-700/50 rounded-lg p-3">
      <div className={`text-xl font-bold ${highlight ? "text-red-400" : "text-white"}`}>{value}</div>
      <div className="text-xs text-slate-400 mt-1">{label}</div>
    </div>
  );
}
