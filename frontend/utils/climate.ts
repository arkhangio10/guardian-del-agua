/**
 * Client-side mirror of backend `layers/climate.project_under_el_nino`.
 * Used when an alert hasn't been re-run through /predict (so no scenario
 * was persisted) but we still want to surface the climate context.
 */
export function projectUnderElNino(base: any, climate: any): any {
  if (!base || !climate) return null;
  const sev = Math.max(0, Math.min(1, Number(climate?.severity) || 0));
  const peopleMult = 1.0 + sev * 0.6;
  const recoveryMult = 1.0 + sev * 0.4;
  const fishBoostAbs = sev * 25.0;
  const econMult = 1.0 + sev * 0.5;

  return {
    people_affected_7d: Math.max(0, Math.round((base?.people_affected_7d || 0) * peopleMult)),
    people_affected_30d: Math.max(0, Math.round((base?.people_affected_30d || 0) * peopleMult)),
    fish_dieoff_30d_pct: Math.max(
      0,
      Math.min(100, (base?.fish_dieoff_30d_pct || 0) + fishBoostAbs)
    ),
    recovery_days: Math.max(1, Math.round((base?.recovery_days || 0) * recoveryMult)),
    drinking_water_sources_at_risk: Math.round(
      (base?.drinking_water_sources_at_risk || 0) * (1.0 + sev * 0.3)
    ),
    economic_damage_usd: Math.round((base?.economic_damage_usd || 0) * econMult),
    _scenario: climate?.el_nino_costero ? "el_nino_costero" : "el_nino_active",
    _climate_severity: sev,
    _multipliers: {
      people: Math.round(peopleMult * 100) / 100,
      recovery: Math.round(recoveryMult * 100) / 100,
      fish_boost_pp: Math.round(fishBoostAbs * 10) / 10,
      economic: Math.round(econMult * 100) / 100,
    },
    _method:
      "Escenario separado computado client-side desde la predicción base × factores derivados de severidad climática. Mismo modelo que backend/layers/climate.project_under_el_nino.",
    _client_side: true,
  };
}
