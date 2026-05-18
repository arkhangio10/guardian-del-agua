/**
 * Maps cryptic concession IDs to human-readable names + the river basin
 * they sit on. Used by the Modo Simple narrative so users don't have to
 * decode "ONP-Tramo-I" or "Lote-192".
 */
const CONCESSION_NAMES: Record<string, { name: string; river: string; region: string }> = {
  "ONP-Tramo-I": {
    name: "Oleoducto Norperuano · Tramo I",
    river: "Marañón / Pastaza",
    region: "Cuatro Cuencas, Loreto",
  },
  "ONP-Tramo-II": {
    name: "Oleoducto Norperuano · Tramo II",
    river: "Marañón",
    region: "Loreto",
  },
  "Lote-192": {
    name: "Lote 192 (ex-1AB)",
    river: "Pastaza / Corrientes",
    region: "Cuatro Cuencas, Loreto",
  },
  "Lote-8": {
    name: "Lote 8",
    river: "Corrientes",
    region: "Loreto",
  },
  "Lote-95": {
    name: "Lote 95",
    river: "Marañón",
    region: "Loreto",
  },
  "Lote-67": {
    name: "Lote 67",
    river: "Tigre",
    region: "Loreto",
  },
};

export function readableConcession(concessionId: string | undefined | null): {
  name: string;
  river: string | null;
  region: string | null;
} {
  if (!concessionId) return { name: "concesión no identificada", river: null, region: null };
  const meta = CONCESSION_NAMES[concessionId];
  if (meta) return { name: meta.name, river: meta.river, region: meta.region };
  return { name: concessionId, river: null, region: null };
}
