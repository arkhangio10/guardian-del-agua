"""
Layer 7 — CLIMATE: ENSO / El Niño Costero state for impact scenario modeling.

Fetches:
- NOAA ONI (Oceanic Niño Index, Niño 3.4 region, global-scale ENSO)
- NOAA ERSST Niño 1+2 (specifically the Peruvian coast — proxy for
  El Niño Costero, the local phenomenon that drives Amazon flooding
  via Andean snowmelt + atmospheric river coupling)

Both data sources are NOAA CPC public text files, refreshed monthly,
no auth required. Cached in memory for 6h to be a good citizen.

The output is used by:
- /predict to compute a SECOND scenario ("under_el_nino") alongside
  the base XGBoost prediction. Never silently modifies the base.
- The dossier UI to show the current ENSO state as context.

Categorical state ladder (from coolest to warmest):
  La Niña Strong | La Niña Moderate | La Niña Weak | Neutral |
  El Niño Weak | El Niño Moderate | El Niño Strong | El Niño Costero
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, HTTPException

router = APIRouter()

NOAA_ONI_URL = "https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt"
NOAA_NINO_ERSST_URL = "https://www.cpc.ncep.noaa.gov/data/indices/ersst5.nino.mth.91-20.ascii"

_cache: dict = {"data": None, "expires_at": datetime.now(timezone.utc)}
_CACHE_TTL = timedelta(hours=6)


# ENSO category thresholds (degrees C anomaly).
def _classify_oni(anom: float) -> str:
    if anom <= -1.5:
        return "la_nina_strong"
    if anom <= -1.0:
        return "la_nina_moderate"
    if anom <= -0.5:
        return "la_nina_weak"
    if anom < 0.5:
        return "neutral"
    if anom < 1.0:
        return "el_nino_weak"
    if anom < 1.5:
        return "el_nino_moderate"
    return "el_nino_strong"


def _classify_costero(anom_12: float, anom_34: float) -> bool:
    """
    El Niño Costero: warming concentrated in Niño 1+2 (Peruvian coast)
    while Niño 3.4 (global ENSO) remains near-neutral or cooler. This is
    the pattern that produced devastating Amazon floods in 2017 and 2023.
    Threshold per ENFEN: Niño 1+2 anomaly ≥ +0.4 C for ≥3 months while
    Niño 3.4 < +0.5 C. We use the single-month proxy since this is a
    real-time snapshot, not a multi-month average.
    """
    return anom_12 >= 0.4 and anom_34 < 0.5


def _parse_oni_ascii(text: str) -> dict | None:
    """
    Parse NOAA ONI ascii. Format:
        SEAS  YR   TOTAL ANOM
        DJF   1950  ...   -1.5
        JFM   1950  ...   -1.4
        ...
    Returns the most recent row.
    """
    rows: list[tuple[str, int, float, float]] = []
    for line in text.splitlines():
        m = re.match(r"\s*([A-Z]{3})\s+(\d{4})\s+([-\d.]+)\s+([-\d.]+)\s*$", line)
        if m:
            seas, yr, total, anom = m.groups()
            rows.append((seas, int(yr), float(total), float(anom)))
    if not rows:
        return None
    seas, yr, total, anom = rows[-1]
    return {"season": seas, "year": yr, "sst_c": total, "anomaly_c": anom}


def _parse_nino_regions_ascii(text: str) -> dict | None:
    """
    Parse NOAA ERSST monthly Niño regions ascii. Format includes columns
    for Niño 1+2, 3, 4, 3.4 SST and anomalies. We pick the most recent row.

    Header looks like:
        YR  MON  NINO1+2 ANOM NINO3 ANOM NINO4 ANOM NINO3.4 ANOM
    """
    rows = []
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 10:
            continue
        try:
            yr = int(parts[0])
            mon = int(parts[1])
            nino12_sst = float(parts[2])
            nino12_anom = float(parts[3])
            nino34_sst = float(parts[8])
            nino34_anom = float(parts[9])
            rows.append({
                "year": yr,
                "month": mon,
                "nino12_sst": nino12_sst,
                "nino12_anom": nino12_anom,
                "nino34_sst": nino34_sst,
                "nino34_anom": nino34_anom,
            })
        except (ValueError, IndexError):
            continue
    if not rows:
        return None
    return rows[-1]


async def fetch_climate_state() -> dict:
    """Fetch + parse + classify. Cached 6h."""
    if _cache["data"] and datetime.now(timezone.utc) < _cache["expires_at"]:
        return _cache["data"]

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            oni_resp = await client.get(NOAA_ONI_URL)
            oni_resp.raise_for_status()
            oni = _parse_oni_ascii(oni_resp.text)
        except Exception as exc:
            print(f"[WARN] NOAA ONI fetch failed: {exc}", flush=True)
            oni = None

        try:
            nino_resp = await client.get(NOAA_NINO_ERSST_URL)
            nino_resp.raise_for_status()
            nino = _parse_nino_regions_ascii(nino_resp.text)
        except Exception as exc:
            print(f"[WARN] NOAA Niño regions fetch failed: {exc}", flush=True)
            nino = None

    anom_34 = (oni["anomaly_c"] if oni else (nino["nino34_anom"] if nino else 0.0))
    anom_12 = (nino["nino12_anom"] if nino else None)

    enso_category = _classify_oni(anom_34)
    costero = bool(anom_12 is not None and _classify_costero(anom_12, anom_34))

    # If costero pattern detected, that label trumps the global ENSO label for
    # the Peruvian-context narrative.
    label = "el_nino_costero" if costero else enso_category

    # Severity 0..1 for use as a scenario weight by /predict.
    # Costero gets a higher weight because rainfall on the Peruvian coast +
    # Andean snowmelt cause faster Amazon-tributary discharge.
    severity_map = {
        "neutral": 0.0,
        "la_nina_weak": 0.05,
        "la_nina_moderate": 0.10,
        "la_nina_strong": 0.15,
        "el_nino_weak": 0.20,
        "el_nino_moderate": 0.40,
        "el_nino_strong": 0.65,
    }
    severity = 0.80 if costero else severity_map.get(enso_category, 0.0)

    data = {
        "label": label,
        "enso_category": enso_category,
        "el_nino_costero": costero,
        "severity": round(severity, 2),
        "nino_3_4_anomaly_c": round(anom_34, 2),
        "nino_1_2_anomaly_c": round(anom_12, 2) if anom_12 is not None else None,
        "season": (oni or {}).get("season"),
        "observation_year": (oni or {}).get("year") or (nino or {}).get("year"),
        "observation_month": (nino or {}).get("month"),
        "sources": [
            {"name": "NOAA ONI (Niño 3.4)", "url": NOAA_ONI_URL},
            {"name": "NOAA ERSST monthly Niño regions", "url": NOAA_NINO_ERSST_URL},
        ],
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }
    _cache["data"] = data
    _cache["expires_at"] = datetime.now(timezone.utc) + _CACHE_TTL
    return data


def project_under_el_nino(base: dict, climate: dict) -> dict:
    """
    Build a SEPARATE 'under_el_nino' scenario from a base ImpactPrediction dict.
    This is NOT applied to the base. It is shown side-by-side in the UI so the
    user sees the climate dependency explicitly, not as hidden math.

    The multipliers are documented:
    - people_affected_*: scale with severity × 0.6  (higher river flow disperses
      contaminants further downstream → more communities exposed)
    - fish_dieoff: scale sub-linearly, max +25% absolute
    - recovery_days: scale with severity × 0.4 (saturated soils + flood pulses
      delay natural recovery)
    """
    sev = float(climate.get("severity", 0.0))
    people_mult = 1.0 + sev * 0.6
    recovery_mult = 1.0 + sev * 0.4
    fish_boost_abs = sev * 25.0  # absolute % points to add, capped at 100 total

    return {
        "people_affected_7d": max(0, int(round(float(base.get("people_affected_7d", 0)) * people_mult))),
        "people_affected_30d": max(0, int(round(float(base.get("people_affected_30d", 0)) * people_mult))),
        "fish_dieoff_30d_pct": max(0.0, min(100.0, float(base.get("fish_dieoff_30d_pct", 0.0)) + fish_boost_abs)),
        "recovery_days": max(1, int(round(float(base.get("recovery_days", 0)) * recovery_mult))),
        "drinking_water_sources_at_risk": int(round(float(base.get("drinking_water_sources_at_risk", 0)) * (1.0 + sev * 0.3))),
        "economic_damage_usd": int(round(float(base.get("economic_damage_usd", 0)) * (1.0 + sev * 0.5))),
        "_scenario": "el_nino_costero" if climate.get("el_nino_costero") else "el_nino_active",
        "_climate_severity": sev,
        "_multipliers": {
            "people": round(people_mult, 2),
            "recovery": round(recovery_mult, 2),
            "fish_boost_pp": round(fish_boost_abs, 1),
            "economic": round(1.0 + sev * 0.5, 2),
        },
        "_method": (
            "Separate scenario: base prediction is multiplied by climate-derived factors. "
            "people × (1 + sev × 0.6), recovery × (1 + sev × 0.4), fish + (sev × 25)pp."
        ),
    }


@router.get("/state")
async def get_climate_state():
    """Return current ENSO / El Niño Costero state from NOAA CPC."""
    try:
        return await fetch_climate_state()
    except Exception as exc:
        raise HTTPException(502, f"Climate fetch failed: {exc}")
