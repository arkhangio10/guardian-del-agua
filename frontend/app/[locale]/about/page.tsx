export const metadata = {
  title: "Acerca de — Guardián del Agua",
  description: "Plataforma de evidencia probatoria grado-litigación para denuncias ambientales en la Amazonía peruana.",
};

export default function AboutPage() {
  return (
    <div className="max-w-3xl mx-auto px-6 py-10 space-y-8 text-slate-200">
      <header>
        <h1 className="text-3xl font-bold text-teal-300">
          Acerca de Guardián del Agua
        </h1>
        <p className="mt-2 italic text-teal-200">Esto ya no es denuncia. Es prueba.</p>
      </header>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold text-slate-100">¿Qué es?</h2>
        <p>
          Guardián del Agua es la primera plataforma de evidencia probatoria grado-litigación
          para denuncias ambientales en la Amazonía peruana. Combina audit trail satelital
          (Sentinel-2), análisis con Claude, polígonos de concesión OSINERGMIN/OEFA, y
          fundamentos legales citables de la Ley General del Ambiente (Ley 28611), para
          producir dossiers probatorios con cadena de custodia técnica reproducible.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold text-slate-100">¿Por qué evidencia y no monitoreo?</h2>
        <p>
          El espacio de monitoreo satelital ya está atendido: MAAP, Geobosques, Cerulean,
          Rainforest Alert, Kayrros. Lo que falta — y lo que las federaciones indígenas,
          NGOs de litigación, y reguladores nos han pedido — no es <em>detectar</em>: es
          presentar evidencia técnica admisible que sobreviva a una impugnación procesal.
        </p>
        <p>
          Por eso Guardián del Agua usa lenguaje "presunto responsable, sujeto a verificación
          in situ", incluye bloque de cadena de custodia técnica en cada PDF, y exige
          revisión humana antes de cualquier presentación legal.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold text-slate-100">Cómo funciona — 5 capas</h2>
        <ol className="list-decimal pl-5 space-y-2 text-sm">
          <li><strong>DETECT</strong> — Sentinel-2 L2A + Claude Sonnet 4.5 (vision): clasifica firma espectral de contaminación.</li>
          <li><strong>ATTRIBUTE</strong> — Intersección espacial contra polígonos de concesión: identifica al presunto responsable.</li>
          <li><strong>PREDICT</strong> — XGBoost entrenado en 698 registros reales OEFA/RUIAS: proyecta impacto humano y ecológico.</li>
          <li><strong>ACT</strong> — Context7 RAG sobre corpus de derecho ambiental peruano + Claude Haiku: redacta denuncia con base legal citada.</li>
          <li><strong>PUBLISH</strong> — Zavu (SMS/WhatsApp) + Resend (email) entregan a federaciones, periodistas y NGOs de litigación.</li>
        </ol>
      </section>

      <section className="space-y-3 border-l-4 border-teal-500 pl-4 bg-slate-800/40 py-3">
        <h2 className="text-lg font-semibold text-slate-100">Compromisos no negociables</h2>
        <ul className="list-disc pl-5 space-y-1 text-sm">
          <li>Código abierto bajo licencia MIT, en perpetuidad.</li>
          <li>Nunca aceptamos financiamiento de operadores de hidrocarburos o minería.</li>
          <li>Soberanía de datos para las federaciones indígenas.</li>
          <li>Verificación humana obligatoria antes de cualquier presentación legal.</li>
          <li>Consejo Asesor con mayoría indígena para cambios metodológicos.</li>
        </ul>
        <p className="text-xs text-slate-400 mt-2">
          Ver <a href="/independence" className="text-teal-400 hover:underline">Compromiso de Independencia</a> completo.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold text-slate-100">Quién paga, quién no paga</h2>
        <p className="text-sm">
          Federaciones indígenas y periodistas independientes: gratis para siempre.
          NGOs de litigación y reguladores: financian el sostenimiento del Tier Comunitario.
          Operadores extractivos: <strong>no vendemos</strong>.
        </p>
        <p className="text-xs text-slate-400">
          Ver <a href="/pricing" className="text-teal-400 hover:underline">modelo de acceso</a>.
        </p>
      </section>

      <footer className="text-xs text-slate-500 pt-6 border-t border-slate-700">
        Construido para hack@latam 2026. Código en{" "}
        <a href="https://github.com/" className="text-teal-400 hover:underline">GitHub</a>.
        Licencia MIT.
      </footer>
    </div>
  );
}
