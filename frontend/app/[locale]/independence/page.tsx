export const metadata = {
  title: "Compromiso de Independencia — Guardián del Agua",
  description: "Compromiso público vinculante: cero conflicto de interés con industria extractiva, código abierto en perpetuidad, soberanía de datos indígena.",
};

export default function IndependencePage() {
  return (
    <div className="max-w-3xl mx-auto px-6 py-10 space-y-8 text-slate-200">
      <header className="border-b border-teal-700 pb-4">
        <p className="text-xs uppercase tracking-wider text-teal-400">Documento público vinculante</p>
        <h1 className="text-3xl font-bold text-teal-300 mt-1">
          Compromiso de Independencia
        </h1>
        <p className="mt-2 text-sm text-slate-400">
          Vinculante para fundadores y obligatorio para cualquier estructura legal futura
          (fundación, asociación civil, sociedad anónima).
        </p>
      </header>

      <p className="text-slate-300">
        Guardián del Agua se compromete públicamente a:
      </p>

      <Pledge
        n={1}
        title="Conflicto de interés cero con la industria extractiva"
      >
        <p>
          NUNCA aceptaremos financiamiento, donaciones, contratos de servicio,
          asociaciones comerciales, ni cualquier otro flujo económico proveniente de:
        </p>
        <ul className="list-disc pl-5 mt-2 space-y-1 text-sm text-slate-300">
          <li>Empresas concesionarias de hidrocarburos operando en territorio peruano</li>
          <li>Sus subsidiarias, filiales o vehículos corporativos</li>
          <li>Sus matrices o sociedades controladoras</li>
          <li>Cualquier persona jurídica con participación accionaria en operaciones de extracción de hidrocarburos o minería en territorio peruano</li>
          <li>Fondos de inversión cuya cartera mayoritaria esté concentrada en industria extractiva</li>
        </ul>
        <p className="text-sm text-slate-400 mt-2">
          Esta prohibición se extiende a contribuciones in-kind (servicios técnicos gratuitos, infraestructura cloud subsidiada, etc.).
        </p>
      </Pledge>

      <Pledge n={2} title="Código abierto en perpetuidad">
        <p>
          El código fuente estará disponible bajo licencia MIT (componentes técnicos)
          y AGPL-3.0 (componentes de publicación de evidencia), sin restricciones
          temporales ni geográficas.
        </p>
        <p className="text-sm text-slate-400 mt-2">
          Cualquier persona puede auditar la metodología, reproducir resultados sobre
          nuevas regiones, o hacer fork del proyecto para uso independiente.
          Obligación irrevocable, heredada por cualquier estructura legal sucesora.
        </p>
      </Pledge>

      <Pledge n={3} title="Soberanía de datos para las federaciones indígenas">
        <p>
          Las organizaciones de base son <strong>propietarias</strong> de los datos
          georreferenciados a sus territorios. Guardián del Agua opera como
          infraestructura técnica, no como autoridad sobre esos datos.
        </p>
        <ul className="list-disc pl-5 mt-2 space-y-1 text-sm text-slate-300">
          <li>Las federaciones pueden solicitar la eliminación de registros vinculados a sus territorios.</li>
          <li>Las federaciones pueden vetar la publicación de evidencia que las afecte.</li>
          <li>Intercambios con terceros requieren consentimiento previo, libre e informado (FPIC).</li>
        </ul>
      </Pledge>

      <Pledge n={4} title="Verificación humana antes de presentación legal">
        <p>
          Ningún documento generado por Guardián del Agua puede ser presentado ante
          OEFA, el Poder Judicial, o cualquier autoridad sin la revisión y firma
          explícita de un representante legal autorizado.
        </p>
        <p className="text-sm text-slate-400 mt-2">
          Esta obligación está implementada técnicamente: los PDFs incluyen un sello
          "DOCUMENTO PRELIMINAR — REQUIERE VERIFICACIÓN HUMANA Y FIRMA DE REPRESENTANTE
          LEGAL ANTES DE PRESENTACIÓN".
        </p>
      </Pledge>

      <Pledge n={5} title="Consejo Asesor con mayoría indígena">
        <p>
          Cualquier cambio metodológico sustantivo (algoritmo de atribución, umbrales
          de confianza, ampliación a nuevas regiones, cambio de licencia, modificación
          a este Compromiso) requiere aprobación de un Consejo Asesor con:
        </p>
        <ul className="list-disc pl-5 mt-2 space-y-1 text-sm text-slate-300">
          <li><strong>Mínimo 51%</strong> de representantes de federaciones amazónicas o comunidades nativas afectadas.</li>
          <li>Representantes técnicos sin afiliación a industria extractiva.</li>
          <li>Representantes legales especializados en derecho ambiental peruano.</li>
        </ul>
        <p className="text-sm text-slate-400 mt-2">
          Sesiona mínimo una vez por año. Publica actas en el repositorio público.
        </p>
      </Pledge>

      <Pledge n={6} title="Transparencia financiera">
        <p>Guardián del Agua publica anualmente:</p>
        <ul className="list-disc pl-5 mt-2 space-y-1 text-sm text-slate-300">
          <li>Estados financieros auditados</li>
          <li>Lista completa de fuentes de financiamiento (con montos y condiciones)</li>
          <li>Compensación del equipo</li>
          <li>Asignación de presupuesto por área</li>
        </ul>
      </Pledge>

      <section className="bg-red-900/30 border border-red-800 rounded-lg p-5 space-y-2">
        <h2 className="text-base font-semibold text-red-300">Aplicación y verificación</h2>
        <p className="text-sm text-slate-200">
          Cualquier persona puede reportar una posible violación de este Compromiso al
          correo público del proyecto. Las violaciones confirmadas resultan en:
        </p>
        <ul className="list-disc pl-5 text-sm text-slate-300 space-y-1">
          <li>Publicación inmediata del incidente en el repositorio público</li>
          <li>Convocatoria extraordinaria al Consejo Asesor</li>
          <li>En caso de violación dolosa: disolución de la estructura legal infractora, con activos transferidos a organización sucesora que respete este Compromiso</li>
        </ul>
      </section>

      <footer className="border-t border-slate-700 pt-6 text-xs text-slate-500 space-y-1">
        <p><strong>Estado:</strong> Borrador — pendiente firma humana de fundadores antes de merge legal.</p>
        <p><strong>Versión:</strong> 1.0 (hack@latam 2026)</p>
        <p>
          Fuente:{" "}
          <a href="https://github.com/" className="text-teal-400 hover:underline">
            INDEPENDENCE_PLEDGE.md
          </a>{" "}
          en el repositorio público.
        </p>
      </footer>
    </div>
  );
}

function Pledge({ n, title, children }: { n: number; title: string; children: React.ReactNode }) {
  return (
    <section className="border-l-4 border-teal-500 pl-5 py-2">
      <h2 className="text-lg font-semibold text-slate-100">
        <span className="text-teal-400 mr-2">{n}.</span>{title}
      </h2>
      <div className="mt-2 text-slate-300 text-sm leading-relaxed">{children}</div>
    </section>
  );
}
