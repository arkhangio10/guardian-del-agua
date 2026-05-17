import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Guardián del Agua — Evidencia probatoria ambiental",
  description:
    "Primer audit trail probatorio para denuncias ambientales en la Amazonía peruana. Sentinel-2 + Claude + Ley peruana, listo para OEFA en menos de 25 horas.",
};

const NAV_LINKS = [
  { href: "/", label: "Dossiers" },
  { href: "/leaderboard", label: "Operadores" },
  { href: "/pricing", label: "Acceso" },
  { href: "/independence", label: "Independencia" },
];

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es">
      <body className="h-screen overflow-hidden flex flex-col bg-[#050b14] text-slate-100">
        <nav className="h-14 flex-shrink-0 border-b border-slate-800/60 glass-soft px-6 flex items-center gap-5 z-30">
          <a href="/" className="flex items-center gap-2 group">
            <span className="relative inline-block w-2.5 h-2.5">
              <span className="absolute inset-0 bg-teal-400 rounded-full" />
              <span className="absolute inset-0 bg-teal-400 rounded-full animate-ping opacity-60" />
            </span>
            <span className="text-base font-bold text-gradient-teal tracking-tight">
              Guardián del Agua
            </span>
          </a>
          <span className="hidden lg:inline text-[11px] text-slate-500 italic border-l border-slate-700/60 pl-4">
            Esto ya no es denuncia. Es prueba.
          </span>
          <div className="hidden md:flex items-center gap-1 ml-2">
            {NAV_LINKS.map((l) => (
              <a
                key={l.href}
                href={l.href}
                className="px-3 py-1.5 text-xs text-slate-300 hover:text-white hover:bg-slate-800/60 rounded-md transition-colors"
              >
                {l.label}
              </a>
            ))}
          </div>
          <span className="ml-auto text-[10px] text-slate-500 font-mono tracking-wider">
            hack@latam 2026 · MIT
          </span>
        </nav>

        <main className="flex-1 min-h-0 flex flex-col overflow-y-auto gda-scroll">{children}</main>

        <footer className="h-9 flex-shrink-0 border-t border-slate-800/60 glass-soft px-6 flex items-center gap-4 text-[10px] text-slate-500">
          <span className="hidden sm:inline">
            Evidencia probatoria grado-litigación para la Amazonía peruana
          </span>
          <a href="/independence" className="text-teal-400 hover:text-teal-300 transition-colors">
            Compromiso de Independencia
          </a>
          <a href="/pricing" className="text-teal-400 hover:text-teal-300 transition-colors">
            Modelo de acceso
          </a>
          <span className="ml-auto font-mono tracking-wider">Código abierto · MIT</span>
        </footer>
      </body>
    </html>
  );
}
