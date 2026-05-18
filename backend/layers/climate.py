"""
Layer 7 — CLIMATE: ENSO / El Niño Costero state for impact scenario modeling.

Fetches:
- NOAA ONI (Oceanic Niño Index, Niño 3.4 region, global-scale ENSO,
  3-month running mean)
- NOAA ERSST Niño 1+2 (specifically the Peruvian coast — proxy for
  El Niño Costero, the local phenomenon that drives Amazon flooding
  via Andean snowmelt + atmospheric river coupling)

Both data sources are NOAA CPC public text files, refreshed monthly,
no auth required. The full history is parsed once and cached 6h to enable:
- current state
- state at any historical alert date
- 3-month rolling average for the official ENFEN El Niño Costero declaration
- last-3-months trend (rising / falling / stable)

The output is consumed by:
- /predict to compute a SECOND scenario alongside the base XGBoost prediction
- The dossier UI to show context + temporal comparison

Categorical state ladder (cool → warm):
  la_nina_strong | la_nina_moderate | la_nina_weak | neutral |
  el_nino_weak | el_nino_moderate | el_nino_strong | el_nino_costero
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException

router = APIRouter()

NOAA_ONI_URL = "https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt"
NOAA_NINO_ERSST_URL = "https://www.cpc.ncep.noaa.gov/data/indices/ersst5.nino.mth.91-20.ascii"
NOAA_FORECAST_URL = "https://cpc.ncep.noaa.gov/products/analysis_monitoring/enso/roni/probabilities.php"
NOAA_DIAGNOSTIC_URL = "https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso_advisory/ensodisc.shtml"
IRI_PLUME_URL = "https://iri.columbia.edu/our-expertise/climate/forecasts/enso/current/"

_cache: dict = {
    "oni_rows": None,         # list[dict]
    "nino_rows": None,        # list[dict]
    "current": None,
    "expires_at": datetime.now(timezone.utc),
}
_CACHE_TTL = timedelta(hours=6)

# Season code → center month (1-12). NOAA assigns ONI to the middle month.
SEASON_TO_CENTER_MONTH = {
    "DJF": 1, "JFM": 2, "FMA": 3, "MAM": 4, "AMJ": 5, "MJJ": 6,
    "JJA": 7, "JAS": 8, "ASO": 9, "SON": 10, "OND": 11, "NDJ": 12,
}
MONTH_TO_SEASON = {v: k for k, v in SEASON_TO_CENTER_MONTH.items()}


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


def _classify_costero_3mo(avg_anom_12: float | None, avg_anom_34: float | None) -> bool:
    """
    Official ENFEN-style El Niño Costero declaration: 3-month average of
    Niño 1+2 anomaly ≥ +0.4 °C while Niño 3.4 stays below +0.5 °C.
    """
    if avg_anom_12 is None or avg_anom_34 is None:
        return False
    return avg_anom_12 >= 0.4 and avg_anom_34 < 0.5


SEVERITY_MAP = {
    "neutral": 0.0,
    "la_nina_weak": 0.05,
    "la_nina_moderate": 0.10,
    "la_nina_strong": 0.15,
    "el_nino_weak": 0.20,
    "el_nino_moderate": 0.40,
    "el_nino_strong": 0.65,
}
COSTERO_SEVERITY = 0.80


# ---------- Parsers ----------

def _parse_oni_ascii(text: str) -> list[dict]:
    rows: list[dict] = []
    for line in text.splitlines():
        m = re.match(r"\s*([A-Z]{3})\s+(\d{4})\s+([-\d.]+)\s+([-\d.]+)\s*$", line)
        if not m:
            continue
        seas, yr, total, anom = m.groups()
        rows.append({
            "season": seas,
            "year": int(yr),
            "month": SEASON_TO_CENTER_MONTH.get(seas, 0),
            "sst_c": float(total),
            "anomaly_c": float(anom),
        })
    return rows


def _parse_nino_regions_ascii(text: str) -> list[dict]:
    rows: list[dict] = []
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 10:
            continue
        try:
            yr = int(parts[0])
            mon = int(parts[1])
            rows.append({
                "year": yr,
                "month": mon,
                "nino12_sst": float(parts[2]),
                "nino12_anom": float(parts[3]),
                "nino34_sst": float(parts[8]),
                "nino34_anom": float(parts[9]),
            })
        except (ValueError, IndexError):
            continue
    return rows


# ---------- Lookups + analysis ----------

def _oni_at(rows: list[dict], year: int, month: int) -> dict | None:
    """Find ONI row whose center month matches (year, month)."""
    for r in rows:
        if r["year"] == year and r["month"] == month:
            return r
    # Fall back to closest preceding row.
    candidates = [r for r in rows if (r["year"], r["month"]) <= (year, month)]
    return candidates[-1] if candidates else None


def _nino_at(rows: list[dict], year: int, month: int) -> dict | None:
    for r in rows:
        if r["year"] == year and r["month"] == month:
            return r
    candidates = [r for r in rows if (r["year"], r["month"]) <= (year, month)]
    return candidates[-1] if candidates else None


def _nino_window(rows: list[dict], year: int, month: int, n: int = 3) -> list[dict]:
    """Return last n ERSST monthly rows ending at (year, month) inclusive."""
    target_idx = None
    for i, r in enumerate(rows):
        if r["year"] == year and r["month"] == month:
            target_idx = i
            break
    if target_idx is None:
        # Fall back to closest preceding
        for i, r in enumerate(rows):
            if (r["year"], r["month"]) <= (year, month):
                target_idx = i
        if target_idx is None:
            return []
    start = max(0, target_idx - n + 1)
    return rows[start:target_idx + 1]


def _trend(rows: list[dict], key: str) -> dict:
    """Compute the slope of the last 3 anomalies. Returns direction + delta."""
    if len(rows) < 2:
        return {"direction": "stable", "delta_c": 0.0}
    first = rows[0][key]
    last = rows[-1][key]
    delta = last - first
    if delta >= 0.2:
        direction = "rising"
    elif delta <= -0.2:
        direction = "falling"
    else:
        direction = "stable"
    return {"direction": direction, "delta_c": round(delta, 2)}


def _build_state(
    oni_row: dict | None,
    nino_row: dict | None,
    nino_window_rows: list[dict],
    oni_window_rows: list[dict],
    label_hint: str | None = None,
) -> dict:
    anom_34 = oni_row["anomaly_c"] if oni_row else (nino_row["nino34_anom"] if nino_row else 0.0)
    anom_12 = nino_row["nino12_anom"] if nino_row else None
    enso_category = _classify_oni(anom_34)

    avg_12 = (
        sum(r["nino12_anom"] for r in nino_window_rows) / len(nino_window_rows)
        if nino_window_rows else None
    )
    avg_34 = (
        sum(r["nino34_anom"] for r in nino_window_rows) / len(nino_window_rows)
        if nino_window_rows else None
    )
    costero_3mo = _classify_costero_3mo(avg_12, avg_34)

    label = label_hint or ("el_nino_costero" if costero_3mo else enso_category)
    severity = COSTERO_SEVERITY if label == "el_nino_costero" else SEVERITY_MAP.get(enso_category, 0.0)

    trend_12 = _trend(nino_window_rows, "nino12_anom") if nino_window_rows else None
    trend_34 = _trend(oni_window_rows, "anomaly_c") if oni_window_rows else None

    return {
        "label": label,
        "enso_category": enso_category,
        "el_nino_costero": label == "el_nino_costero",
        "severity": round(severity, 2),
        "nino_3_4_anomaly_c": round(anom_34, 2),
        "nino_1_2_anomaly_c": round(anom_12, 2) if anom_12 is not None else None,
        "season": (oni_row or {}).get("season"),
        "observation_year": (oni_row or {}).get("year") or (nino_row or {}).get("year"),
        "observation_month": (nino_row or {}).get("month"),
        "three_month_average": {
            "nino_3_4_avg_c": round(avg_34, 2) if avg_34 is not None else None,
            "nino_1_2_avg_c": round(avg_12, 2) if avg_12 is not None else None,
            "costero_declared": costero_3mo,
            "window_months": len(nino_window_rows),
        },
        "trend": {
            "nino_3_4": trend_34,
            "nino_1_2": trend_12,
        },
    }


# ---------- Fetchers ----------

async def _ensure_cache_fresh():
    if (
        _cache["oni_rows"] is not None
        and _cache["nino_rows"] is not None
        and datetime.now(timezone.utc) < _cache["expires_at"]
    ):
        return

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            oni_resp = await client.get(NOAA_ONI_URL)
            oni_resp.raise_for_status()
            _cache["oni_rows"] = _parse_oni_ascii(oni_resp.text)
        except Exception as exc:
            print(f"[WARN] NOAA ONI fetch failed: {exc}", flush=True)
            _cache["oni_rows"] = _cache["oni_rows"] or []

        try:
            nino_resp = await client.get(NOAA_NINO_ERSST_URL)
            nino_resp.raise_for_status()
            _cache["nino_rows"] = _parse_nino_regions_ascii(nino_resp.text)
        except Exception as exc:
            print(f"[WARN] NOAA Niño regions fetch failed: {exc}", flush=True)
            _cache["nino_rows"] = _cache["nino_rows"] or []

    _cache["expires_at"] = datetime.now(timezone.utc) + _CACHE_TTL


async def fetch_climate_state(reference_date: str | None = None) -> dict:
    """
    Resolve ENSO climate state for `reference_date` (YYYY-MM-DD).
    Defaults to the most recent month available — i.e. the "current" state.
    """
    await _ensure_cache_fresh()
    oni_rows = _cache["oni_rows"] or []
    nino_rows = _cache["nino_rows"] or []

    if reference_date:
        try:
            dt = datetime.strptime(reference_date[:10], "%Y-%m-%d")
            ref_year, ref_month = dt.year, dt.month
        except Exception:
            ref_year, ref_month = None, None
    else:
        ref_year, ref_month = None, None

    if ref_year is None or ref_month is None:
        # Most-recent rows.
        nino_row = nino_rows[-1] if nino_rows else None
        oni_row = oni_rows[-1] if oni_rows else None
        if nino_row:
            ref_year, ref_month = nino_row["year"], nino_row["month"]
    else:
        nino_row = _nino_at(nino_rows, ref_year, ref_month)
        oni_row = _oni_at(oni_rows, ref_year, ref_month)

    if nino_row:
        nino_window = _nino_window(nino_rows, nino_row["year"], nino_row["month"], n=3)
    else:
        nino_window = nino_rows[-3:]

    if oni_row:
        # Pick last 3 ONI rows up to and including this one.
        idx = oni_rows.index(oni_row) if oni_row in oni_rows else len(oni_rows) - 1
        oni_window = oni_rows[max(0, idx - 2): idx + 1]
    else:
        oni_window = oni_rows[-3:]

    state = _build_state(oni_row, nino_row, nino_window, oni_window)
    state["reference_date"] = (
        reference_date[:10] if reference_date else (
            f"{nino_row['year']:04d}-{nino_row['month']:02d}-01" if nino_row else None
        )
    )
    state["is_historical"] = bool(reference_date)
    state["sources"] = [
        {"name": "NOAA ONI (Niño 3.4)", "url": NOAA_ONI_URL},
        {"name": "NOAA ERSST Niño regions", "url": NOAA_NINO_ERSST_URL},
        {"name": "NOAA CPC ENSO Diagnostic Discussion", "url": NOAA_DIAGNOSTIC_URL},
        {"name": "NOAA CPC ENSO probabilities", "url": NOAA_FORECAST_URL},
        {"name": "IRI ENSO Prediction Plume", "url": IRI_PLUME_URL},
    ]
    state["fetched_at"] = datetime.now(timezone.utc).isoformat()
    return state


def project_under_el_nino(base: dict, climate: dict) -> dict:
    """
    Separate "under El Niño" scenario — never modifies the base prediction.
    Multipliers documented in _method for chain-of-custody.
    """
    sev = float(climate.get("severity", 0.0))
    people_mult = 1.0 + sev * 0.6
    recovery_mult = 1.0 + sev * 0.4
    fish_boost_abs = sev * 25.0

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
async def get_climate_state(reference_date: str | None = None):
    """
    Return ENSO / El Niño Costero state.

    Query params:
    - reference_date (YYYY-MM-DD, optional): if provided, returns the historical
      state at that date. Otherwise returns the most recent available state
      ("current"). When an alert is involved, the frontend can ALSO call this
      with the alert's detected_at to show "ENSO was X when the incident occurred,
      vs Y today" comparisons.
    """
    try:
        return await fetch_climate_state(reference_date)
    except Exception as exc:
        raise HTTPException(502, f"Climate fetch failed: {exc}")


@router.get("/state/at-alert/{alert_id}")
async def get_climate_state_at_alert(alert_id: str):
    """
    Return both the historical state at the alert's incident date AND the
    current state, so the UI can show "then vs now".
    """
    from db import get_db
    db = get_db()
    doc = db.collection("alerts").document(alert_id).get()
    if not doc.exists:
        raise HTTPException(404, f"Alert {alert_id} not found")
    data = doc.to_dict()
    incident_date = (data.get("detected_at") or "")[:10] or None

    current = await fetch_climate_state()
    historical = await fetch_climate_state(incident_date) if incident_date else None

    return {
        "alert_id": alert_id,
        "incident_date": incident_date,
        "current": current,
        "historical": historical,
    }
