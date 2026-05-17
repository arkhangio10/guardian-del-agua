export const metadata = {
  title: "Modelo de acceso — Guardián del Agua",
  description: "Open-core: gratis para federaciones indígenas y periodistas; tarifas público-pagas sostienen el código abierto. Operadores extractivos: no vendemos.",
};

interface Tier {
  name: string;
  audience: string;
  price: string;
  bullets: string[];
  cta?: string;
  highlight?: boolean;
  forbidden?: boolean;
}

const TIERS: Tier[] = [
  {
    name: "Comunitario",
    audience: "Federaciones indígenas, comunidades nativas, periodistas independientes",
    price: "Gratis para siempre",
    bullets: [
      "Acceso completo a la plataforma de evidencia probatoria",
      "Dossiers PDF ilimitados con cadena de custodia técnica",
      "Alertas SMS/WhatsApp/email a representantes territoriales",
      "Soberanía total sobre datos de su territorio",
      "Soporte por correo y Discord comunitario",
    ],
    cta: "Solicitar acceso comunitario",
    highlight: true,
  },
  {
    name: "Investigación",
    audience: "Periodistas de medios establecidos · académicos · centros de investigación",
    price: "Gratis (con atribución)",
    bullets: [
      "Acceso al dashboard de evidencia",
      "Descarga de dossiers PDF",
      "Exportación de datasets para análisis (CSV/GeoJSON)",
      "Atribución requerida en publicaciones derivadas",
    ],
    cta: "Solicitar credencial de prensa/académica",
  },
  {
    name: "Evidence Pack",
    audience: "NGOs de litigación ambiental · estudios jurídicos especializados",
    price: "US$ 15,000 – 40,000 / año",
    bullets: [
      "Dossiers court-admissible con chain-of-custody verificable",
      "Hash criptográfico SHA-256 por evidencia",
      "Acompañamiento técnico para preparación de casos",
      "API privada para integración con sistemas internos",
      "SLA con respuesta < 24 horas",
    ],
    cta: "Conversar con el equipo",
  },
  {
    name: "Gobierno y Reguladores",
    audience: "OEFA · MINAM · defensorías regionales · fiscalías ambientales",
    price: "US$ 80,000 – 250,000 / año",
    bullets: [
      "Despliegue dedicado (on-prem o cloud privado)",
      "Cobertura geográfica configurable",
      "Integración con sistemas SINADA / OEFA",
      "Capacitación y transferencia metodológica",
      "Soporte 24/7 con SLA institucional",
    ],
    cta: "Solicitar propuesta",
  },
  {
    name: "Operadores extractivos",
    audience: "Empresas concesionarias de hidrocarburos, minería y sus filiales",
    price: "NO VENDEMOS",
    bullets: [
      "Política pública no negociable bajo el Compromiso de Independencia.",
      "Nunca aceptaremos financiamiento, contratos o asociaciones de la industria extractiva.",
      "Esta prohibición se extiende a contribuciones in-kind y se hereda por toda estructura legal sucesora.",
    ],
    forbidden: true,
  },
];

export default function PricingPage() {
  return (
    <div className="max-w-6xl mx-auto px-6 py-10 space-y-8 text-slate-200">
      <header className="space-y-2">
        <p className="text-xs uppercase tracking-wider text-teal-400">Modelo de acceso</p>
        <h1 className="text-3xl md:text-4xl font-bold text-teal-300">
          Open-core: gratis para quien lo necesita, pagado por quien puede.
        </h1>
        <p className="text-slate-300 max-w-3xl">
          Todos los ingresos de los tiers pagados sostienen el desarrollo del código
          abierto y la operación gratuita del <strong className="text-teal-200">Tier Comunitario</strong>.
        </p>
      </header>

      <div className="grid md:grid-cols-2 gap-5">
        {TIERS.map((t) => (
          <TierCard key={t.name} tier={t} />
        ))}
      </div>

      <section className="border-l-4 border-teal-500 pl-5 py-3 bg-slate-800/40 rounded-r-lg">
        <p className="text-sm text-slate-300">
          <strong className="text-teal-200">¿Por qué hacemos pricing público?</strong>{" "}
          Porque queremos que las federaciones indígenas, los periodistas, las NGOs y los
          reguladores puedan auditar el modelo de negocio. La transparencia financiera
          forma parte del{" "}
          <a href="/independence" className="text-teal-400 hover:underline">
            Compromiso de Independencia
          </a>
          .
        </p>
      </section>

      <footer className="text-xs text-slate-500 border-t border-slate-700 pt-4 space-y-1">
        <p>
          <strong>Benchmarks utilizados:</strong> Planet Labs ARR per customer ~US$200k ·
          Global Forest Watch Pro · Sylvera US$15M ARR · NGO procurement bands
          US$5k–150k. Rangos sujetos a ajuste según madurez del producto.
        </p>
        <p>
          <strong>Notas:</strong> Los tiers pagados están en validación durante hack@latam
          2026 con potenciales clientes pilotos (EarthRights, IDL, SPDA). Precios finales se
          publicarán al cerrar primer caso pagado.
        </p>
      </footer>
    </div>
  );
}

function TierCard({ tier }: { tier: Tier }) {
  const baseCls = "rounded-xl p-5 border flex flex-col";
  const cls = tier.forbidden
    ? `${baseCls} bg-red-950/40 border-red-800`
    : tier.highlight
    ? `${baseCls} bg-teal-950/40 border-teal-700`
    : `${baseCls} bg-slate-800 border-slate-700`;
  const priceCls = tier.forbidden
    ? "text-red-300"
    : tier.highlight
    ? "text-teal-300"
    : "text-slate-100";
  return (
    <div className={cls}>
      <div className="mb-3">
        <h2 className="text-xl font-bold text-slate-100">{tier.name}</h2>
        <p className="text-xs text-slate-400 mt-1">{tier.audience}</p>
      </div>
      <p className={`text-2xl font-bold mb-3 ${priceCls}`}>{tier.price}</p>
      <ul className="space-y-1.5 text-sm text-slate-300 flex-1">
        {tier.bullets.map((b, i) => (
          <li key={i} className="flex gap-2">
            <span className={tier.forbidden ? "text-red-400" : "text-teal-400"}>
              {tier.forbidden ? "✕" : "✓"}
            </span>
            <span>{b}</span>
          </li>
        ))}
      </ul>
      {tier.cta && (
        <button
          className={`mt-4 px-4 py-2 rounded-lg font-semibold text-sm transition-colors ${
            tier.highlight
              ? "bg-teal-500 hover:bg-teal-400 text-slate-900"
              : "bg-slate-700 hover:bg-slate-600 text-white"
          }`}
        >
          {tier.cta}
        </button>
      )}
    </div>
  );
}
