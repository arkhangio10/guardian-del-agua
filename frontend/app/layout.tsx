import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Guardián del Agua — Evidencia probatoria ambiental",
  description: "Primer audit trail probatorio para denuncias ambientales en la Amazonía peruana. Sentinel-2 + Claude + Ley peruana, listo para OEFA en menos de 25 horas.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es">
      <body className="min-h-screen bg-slate-900 text-slate-100 flex flex-col">
        <nav className="border-b border-slate-700 bg-slate-800 px-6 py-3 flex items-center gap-6 flex-wrap">
          <a href="/" className="text-lg font-bold text-teal-400">
            Guardián del Agua
          </a>
          <span className="hidden md:inline text-xs text-slate-500 italic">
            Esto ya no es denuncia. Es prueba.
          </span>
          <a href="/" className="text-sm text-slate-300 hover:text-white">Dossiers</a>
          <a href="/leaderboard" className="text-sm text-slate-300 hover:text-white">Operadores</a>
          <a href="/pricing" className="text-sm text-slate-300 hover:text-white">Acceso</a>
          <a href="/independence" className="text-sm text-slate-300 hover:text-white">Independencia</a>
          <span className="ml-auto text-xs text-slate-500">hack@latam 2026 · MIT</span>
        </nav>
        <main className="flex-1">{children}</main>
        <footer className="border-t border-slate-700 bg-slate-800 px-6 py-3 text-xs text-slate-500 flex flex-wrap items-center gap-4">
          <span>Guardián del Agua — Evidencia probatoria grado-litigación para la Amazonía peruana.</span>
          <a href="/independence" className="text-teal-400 hover:underline">Compromiso de Independencia</a>
          <a href="/pricing" className="text-teal-400 hover:underline">Modelo de acceso</a>
          <span className="ml-auto">Código abierto · MIT</span>
        </footer>
      </body>
    </html>
  );
}
