"use client";
import { useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type RoleType = "federacion" | "periodista" | "abogado" | "investigador";

const ROLES: { id: RoleType; label: string; sub: string; icon: string }[] = [
  {
    id: "federacion",
    label: "Federación indígena",
    sub: "Representante con FPIC firmado",
    icon: "🌿",
  },
  {
    id: "periodista",
    label: "Periodista",
    sub: "Medio verificado o independiente",
    icon: "📰",
  },
  {
    id: "abogado",
    label: "Abogado ambiental",
    sub: "Litigación o defensoría",
    icon: "⚖️",
  },
  {
    id: "investigador",
    label: "Investigador",
    sub: "Académico o centro de investigación",
    icon: "🔬",
  },
];

const CUENCAS = [
  "Pastaza",
  "Tigre",
  "Corrientes",
  "Marañón",
  "Napo",
  "Ucayali",
  "Madre de Dios",
  "Otra / No aplica",
];

interface State {
  status: "idle" | "submitting" | "success" | "error";
  requestId?: string;
  message?: string;
  error?: string;
}

export default function AccessRequestForm() {
  const [role, setRole] = useState<RoleType>("federacion");
  const [nombre, setNombre] = useState("");
  const [organizacion, setOrganizacion] = useState("");
  const [telefono, setTelefono] = useState("");
  const [email, setEmail] = useState("");
  const [cuenca, setCuenca] = useState("");
  const [state, setState] = useState<State>({ status: "idle" });

  const orgPlaceholder: Record<RoleType, string> = {
    federacion: "Ej: FECONACO, AIDESEP, ORPIO, CORPI-SL…",
    periodista: "Ej: Mongabay Latam, Ojo Público, Diario La Región…",
    abogado: "Ej: IDL, SPDA, EarthRights, estudio jurídico…",
    investigador: "Ej: PUCP, UNMSM, IIAP, centro de investigación…",
  };

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (state.status === "submitting") return;
    setState({ status: "submitting" });

    try {
      const resp = await fetch(`${API_BASE}/access/request`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          nombre: nombre.trim(),
          role_type: role,
          organizacion: organizacion.trim(),
          telefono: telefono.trim(),
          email: email.trim(),
          cuenca: cuenca || null,
        }),
      });
      if (!resp.ok) {
        const errBody = await resp.text();
        throw new Error(`HTTP ${resp.status}: ${errBody.slice(0, 200)}`);
      }
      const data = await resp.json();
      setState({
        status: "success",
        requestId: data.request_id,
        message: data.message,
      });
    } catch (err: any) {
      setState({
        status: "error",
        error: err?.message ?? "Error enviando la solicitud",
      });
    }
  }

  function reset() {
    setNombre("");
    setOrganizacion("");
    setTelefono("");
    setEmail("");
    setCuenca("");
    setRole("federacion");
    setState({ status: "idle" });
  }

  if (state.status === "success") {
    return (
      <section className="rounded-2xl border border-teal-500/40 bg-teal-950/30 p-8 backdrop-blur">
        <div className="flex items-center gap-3 mb-4">
          <span className="text-2xl">✓</span>
          <h2 className="text-2xl font-bold text-teal-200">Solicitud recibida</h2>
        </div>
        <p className="text-slate-200 mb-4">{state.message}</p>
        <div className="bg-slate-950/60 border border-slate-700/50 rounded-lg p-4 mb-4">
          <p className="text-[11px] uppercase tracking-wider text-slate-500 mb-1">
            Tu número de solicitud
          </p>
          <code className="text-teal-300 font-mono text-lg">{state.requestId}</code>
        </div>
        <p className="text-xs text-slate-400 leading-relaxed">
          Guardalo: te llegará un email cuando el equipo apruebe tu acceso. Si sos
          representante de federación, te contactaremos para el proceso FPIC formal
          antes de habilitarte el tier comunitario.
        </p>
        <button
          onClick={reset}
          className="mt-5 text-sm text-teal-400 hover:text-teal-300 underline underline-offset-4"
        >
          Enviar otra solicitud
        </button>
      </section>
    );
  }

  return (
    <section className="rounded-2xl border border-slate-700/50 bg-slate-900/40 backdrop-blur p-6 md:p-8">
      <div className="mb-6">
        <p className="text-xs uppercase tracking-[0.18em] text-teal-400 font-mono mb-2">
          Solicitar acceso
        </p>
        <h2 className="text-2xl md:text-3xl font-bold text-slate-100 leading-tight">
          Registrá tu organización
        </h2>
        <p className="text-slate-300 mt-2 max-w-2xl">
          Si representás una <strong className="text-teal-200">federación indígena</strong>,
          sos <strong className="text-teal-200">periodista</strong>,{" "}
          <strong className="text-teal-200">abogado ambiental</strong> o{" "}
          <strong className="text-teal-200">investigador</strong>, completá este formulario.
          Te contactamos en 48-72h.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-5">
        {/* Role type — radio pills */}
        <div>
          <label className="block text-xs uppercase tracking-wider text-slate-400 mb-2">
            ¿Qué tipo de organización representás?
          </label>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            {ROLES.map((r) => (
              <button
                key={r.id}
                type="button"
                onClick={() => setRole(r.id)}
                className={`text-left px-3 py-3 rounded-lg border transition-all ${
                  role === r.id
                    ? "border-teal-400 bg-teal-500/10 ring-1 ring-teal-300/40"
                    : "border-slate-700 bg-slate-800/40 hover:border-slate-500"
                }`}
              >
                <div className="text-lg mb-1">{r.icon}</div>
                <div
                  className={`text-sm font-semibold ${
                    role === r.id ? "text-teal-200" : "text-slate-200"
                  }`}
                >
                  {r.label}
                </div>
                <div className="text-[11px] text-slate-400 mt-0.5">{r.sub}</div>
              </button>
            ))}
          </div>
        </div>

        {/* Nombre + Organizacion */}
        <div className="grid md:grid-cols-2 gap-4">
          <Field
            label="Nombre completo"
            value={nombre}
            onChange={setNombre}
            placeholder="Ej: María López"
            required
          />
          <Field
            label={
              role === "federacion"
                ? "Federación / comunidad"
                : role === "periodista"
                ? "Medio"
                : role === "abogado"
                ? "Estudio / NGO"
                : "Centro de investigación"
            }
            value={organizacion}
            onChange={setOrganizacion}
            placeholder={orgPlaceholder[role]}
            required
          />
        </div>

        {/* Telefono + Email */}
        <div className="grid md:grid-cols-2 gap-4">
          <Field
            label="Teléfono"
            value={telefono}
            onChange={setTelefono}
            placeholder="+51 9XX XXX XXX"
            type="tel"
            required
          />
          <Field
            label="Email"
            value={email}
            onChange={setEmail}
            placeholder="contacto@org.pe"
            type="email"
            required
          />
        </div>

        {/* Cuenca dropdown */}
        <div>
          <label className="block text-xs uppercase tracking-wider text-slate-400 mb-2">
            Cuenca / territorio de jurisdicción{" "}
            <span className="normal-case lowercase text-slate-500">(opcional)</span>
          </label>
          <select
            value={cuenca}
            onChange={(e) => setCuenca(e.target.value)}
            className="w-full bg-slate-800/60 border border-slate-700 rounded-lg px-4 py-2.5 text-slate-200 focus:border-teal-400 focus:outline-none focus:ring-1 focus:ring-teal-400/40"
          >
            <option value="">— Seleccionar cuenca —</option>
            {CUENCAS.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </div>

        {/* FPIC notice for federacion */}
        {role === "federacion" && (
          <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 px-4 py-3 text-xs text-amber-200/90 leading-relaxed">
            <strong className="text-amber-300">Nota FPIC.</strong> Para tier
            Comunitario activamos el flujo de Consentimiento Previo, Libre e Informado
            con la asamblea de la federación antes de habilitar acceso. No publicamos
            evidencia que afecte territorio sin tu consentimiento explícito.
          </div>
        )}

        {state.status === "error" && (
          <div className="rounded-lg border border-red-500/40 bg-red-950/30 px-4 py-3 text-sm text-red-200">
            ⚠ {state.error}
          </div>
        )}

        <button
          type="submit"
          disabled={state.status === "submitting"}
          className="w-full md:w-auto bg-teal-400 hover:bg-teal-300 active:bg-teal-500 disabled:opacity-60 disabled:cursor-not-allowed text-slate-950 font-bold px-6 py-3 rounded-lg transition-all shadow-lg shadow-teal-500/30 ring-1 ring-teal-300/50"
        >
          {state.status === "submitting" ? "Enviando…" : "Enviar solicitud →"}
        </button>

        <p className="text-[11px] text-slate-500 leading-relaxed">
          Al enviar este formulario aceptás los términos del{" "}
          <a href="/independence" className="text-teal-400 hover:underline">
            Compromiso de Independencia
          </a>
          . Tus datos se usan únicamente para procesar la solicitud de acceso y nunca
          se comparten con la industria extractiva.
        </p>
      </form>
    </section>
  );
}

function Field({
  label,
  value,
  onChange,
  placeholder,
  type = "text",
  required,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  type?: string;
  required?: boolean;
}) {
  return (
    <div>
      <label className="block text-xs uppercase tracking-wider text-slate-400 mb-2">
        {label} {required && <span className="text-teal-400">*</span>}
      </label>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        required={required}
        className="w-full bg-slate-800/60 border border-slate-700 rounded-lg px-4 py-2.5 text-slate-200 placeholder:text-slate-500 focus:border-teal-400 focus:outline-none focus:ring-1 focus:ring-teal-400/40"
      />
    </div>
  );
}
