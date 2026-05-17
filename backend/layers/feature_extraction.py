"""
Tier 2.5 — Derive XGBoost input features from a Firestore alert document.

This module is the heart of the litigation-grade narrative. Previously, the
production predict.py hardcoded 6 of 7 features as constants (volume=800,
flow=1200, distance=15, ...) which means every hydrocarbon alert produced
essentially the same prediction.

This module derives each feature from the alert + attribution documents using
documented sources, and emits a `_provenance` dict that the ACT layer embeds in
the denuncia's chain-of-custody block.

Defensive contract:
  - NEVER raises. If a field is missing, falls back to DISTRICT_GEO["DEFAULT"]
    or to documented constants, and records that fact in `_provenance`.
  - Every returned feature has a corresponding provenance entry naming its
    source.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from layers._ml_geo import (  # noqa: E402
    DISTRICT_GEO,
    get_season,
    nearest_district,
)


CONTAMINATION_ENCODING = {"hydrocarbon": 0, "turbidity": 1, "algal_bloom": 2, "none": 3}
SEASON_ENCODING = {"dry": 0, "wet": 1}

# Volume scaling factor: how many barrels per (km2 of detection x unit confidence).
# Calibrated from FINE_TO_VOLUME bucketing: a typical detection area of ~3 km2
# at confidence 0.85 should yield ~255 barrels (matches OEFA's ~3rd bucket).
VOLUME_SCALING = 100.0

# Maximum area to use in the volume formula. A bbox larger than this is treated
# as a *search region* (the user-provided AOI for Sentinel Hub) rather than the
# actual contamination footprint. The Claude Vision detection in production
# already returns an `affected_area_pct` field, but the production Alert model
# does not persist it (TODO: lift this into the alert schema). Until then, we
# cap the effective area so that regional demo bboxes do not produce
# unrealistic "the whole region is contaminated" volumes.
EFFECTIVE_AREA_CAP_KM2 = 25.0


def _bbox_area_km2(bbox: list[float]) -> float:
    """
    Approximate area of a lon/lat bbox in km^2.

    This is correct enough at this latitude band (-2 to -5 degrees, where 1
    degree longitude ~ 111 km and 1 degree latitude ~ 111 km).
    """
    if not bbox or len(bbox) != 4:
        return 1.0
    lon_span = abs(bbox[2] - bbox[0]) * 111.0
    lat_span = abs(bbox[3] - bbox[1]) * 111.0
    return max(0.01, lon_span * lat_span)


def _bbox_centroid(bbox: list[float]) -> tuple[float, float]:
    if not bbox or len(bbox) != 4:
        return (-75.5, -4.0)  # fallback to mid-Loreto
    return ((bbox[0] + bbox[2]) / 2.0, (bbox[1] + bbox[3]) / 2.0)


def _parse_detected_at(value: Any) -> datetime | None:
    """Robust parsing of `detected_at` (Firestore can return datetime, str, or None)."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    # Firestore client sometimes returns a Timestamp object with a tzinfo
    if hasattr(value, "isoformat"):
        try:
            return datetime.fromisoformat(value.isoformat().replace("Z", "+00:00"))
        except Exception:
            return None
    return None


def features_from_alert(
    alert_doc: dict,
    attribution_doc: dict | None = None,
) -> dict:
    """
    Map a Firestore alert document to a feature dict for the XGBoost model.

    Args:
        alert_doc: alert document from Firestore. Expected keys:
            - contamination_type ("hydrocarbon" | "turbidity" | "algal_bloom")
            - sentinel_bbox ([lon_min, lat_min, lon_max, lat_max])
            - confidence (float in 0..1)
            - detected_at (datetime or ISO string)
        attribution_doc: optional dict from the ATTRIBUTE layer. May contain
            "distance_to_pipeline_km" (float).

    Returns:
        dict with keys:
            - "features": list[float] of length 7, in the order expected by predict_lib.FEATURES
            - "feature_names": list[str], same order
            - "_provenance": dict[feature_name -> {"value", "source"}], for the denuncia
            - "_derived_inputs": dict with the human-readable values (volume_barrels=355.0, ...)
    """
    attribution_doc = attribution_doc or {}
    provenance: dict[str, dict] = {}
    derived: dict[str, Any] = {}

    # --- contamination_type ---
    c_type_raw = str(alert_doc.get("contamination_type", "hydrocarbon")).lower()
    if c_type_raw not in CONTAMINATION_ENCODING:
        c_type_raw = "hydrocarbon"
        c_type_source = (
            f"fallback default 'hydrocarbon' — alert.contamination_type was missing or unrecognised"
        )
    else:
        c_type_source = (
            f"Capa DETECT (Claude Sonnet 4.5 sobre Sentinel-2 L2A): "
            f"contaminacion clasificada como '{c_type_raw}'"
        )
    derived["contamination_type"] = c_type_raw
    provenance["contamination_type"] = {"value": c_type_raw, "source": c_type_source}

    # --- bbox-derived geographic context ---
    bbox = alert_doc.get("sentinel_bbox") or alert_doc.get("bbox") or []
    if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
        area_km2 = _bbox_area_km2(list(bbox))
        lon_c, lat_c = _bbox_centroid(list(bbox))
        district = nearest_district(lon_c, lat_c)
        bbox_source = (
            f"Capa DETECT: bbox Sentinel-2 [{bbox[0]:.3f}, {bbox[1]:.3f}, "
            f"{bbox[2]:.3f}, {bbox[3]:.3f}], area={area_km2:.2f} km2, centroide="
            f"({lon_c:.3f}, {lat_c:.3f})"
        )
    else:
        area_km2 = 4.0   # ~2x2 km default detection
        lon_c, lat_c = (-75.5, -4.0)
        district = "DEFAULT"
        bbox_source = "fallback: alert.sentinel_bbox missing or malformed"

    geo = DISTRICT_GEO.get(district, DISTRICT_GEO["DEFAULT"])
    derived["bbox_area_km2"] = round(area_km2, 3)
    derived["district"] = district

    # --- volume_barrels ---
    confidence = float(alert_doc.get("confidence", 0.5))
    # Use affected_area_pct from Claude Vision detection if available, otherwise
    # cap area at EFFECTIVE_AREA_CAP_KM2 so that regional search bboxes do not
    # produce unrealistic "whole region contaminated" volumes.
    affected_pct = alert_doc.get("affected_area_pct")
    if affected_pct is not None and 0.0 <= float(affected_pct) <= 1.0:
        effective_area = area_km2 * float(affected_pct)
        area_note = f"area_km2={area_km2:.2f} x affected_area_pct={float(affected_pct):.2f}"
    elif area_km2 > EFFECTIVE_AREA_CAP_KM2:
        effective_area = EFFECTIVE_AREA_CAP_KM2
        area_note = (
            f"area_km2={area_km2:.2f} (regional search bbox, capped at "
            f"{EFFECTIVE_AREA_CAP_KM2} km2 since Claude Vision affected_area_pct "
            f"is not persisted on the alert)"
        )
    else:
        effective_area = area_km2
        area_note = f"area_km2={area_km2:.2f} (direct detection footprint)"

    volume = effective_area * confidence * VOLUME_SCALING
    volume = max(50.0, min(volume, 6000.0))  # physical clamp
    derived["volume_barrels"] = round(volume, 1)
    provenance["volume_barrels"] = {
        "value": round(volume, 1),
        "source": (
            f"derivado de la deteccion satelital: {area_note} x "
            f"confianza={confidence:.2f} x factor_escala={VOLUME_SCALING}. "
            f"Calibracion contra escala OEFA Res. 164-2013-OEFA/CD (UIT/barriles). "
            f"Bbox source: {bbox_source}"
        ),
    }

    # --- river_flow_m3s ---
    derived["river_flow_m3s"] = float(geo["flow"])
    provenance["river_flow_m3s"] = {
        "value": float(geo["flow"]),
        "source": (
            f"SENAMHI promedio estacional para rio {geo['river']} en distrito {district} "
            f"(centroide bbox -> nearest_district lookup)"
        ),
    }

    # --- distance_km ---
    if attribution_doc.get("distance_to_pipeline_km") is not None:
        distance = float(attribution_doc["distance_to_pipeline_km"])
        distance_source = (
            f"Capa ATTRIBUTE: distancia geoespacial calculada de centroide de deteccion "
            f"a poligono de operador atribuido ({attribution_doc.get('operator_name', 'desconocido')}, "
            f"{attribution_doc.get('concession_id', 'desconocida')})"
        )
    else:
        distance = float(geo["dist"])
        distance_source = (
            f"fallback: DISTRICT_GEO[{district}].dist = {geo['dist']} km "
            f"(promedio para el distrito; Capa ATTRIBUTE no proporciono distance_to_pipeline_km)"
        )
    derived["distance_km"] = round(distance, 2)
    provenance["distance_km"] = {"value": round(distance, 2), "source": distance_source}

    # --- pop_density_per_km2 ---
    derived["pop_density_per_km2"] = float(geo["density"])
    provenance["pop_density_per_km2"] = {
        "value": float(geo["density"]),
        "source": (
            f"INEI Censo Nacional 2017, distrito {district}: "
            f"densidad poblacional {geo['density']} hab/km2"
        ),
    }

    # --- biodiversity_index ---
    derived["biodiversity_index"] = float(geo["bio"])
    provenance["biodiversity_index"] = {
        "value": float(geo["bio"]),
        "source": (
            f"RAISG (Red Amazonica de Informacion Socioambiental Georreferenciada), "
            f"indice de biodiversidad para distrito {district}: {geo['bio']}"
        ),
    }

    # --- season ---
    dt = _parse_detected_at(alert_doc.get("detected_at"))
    if dt is not None:
        season = get_season(dt.month)
        season_source = (
            f"derivado de alert.detected_at (mes {dt.month}); "
            f"clasificacion estacional Amazonia peruana: "
            f"wet={{Ene-May,Nov-Dic}}, dry={{Jun-Oct}}"
        )
    else:
        season = "wet"
        season_source = "fallback: alert.detected_at missing or unparseable; defaulting to wet season"
    derived["season"] = season
    provenance["season"] = {"value": season, "source": season_source}

    # ----- Build the feature vector in the canonical order -----
    feature_names = [
        "contamination_type_enc",
        "volume_barrels",
        "river_flow_m3s",
        "distance_km",
        "pop_density_per_km2",
        "biodiversity_index",
        "season_enc",
    ]
    features = [
        float(CONTAMINATION_ENCODING.get(c_type_raw, 0)),
        float(derived["volume_barrels"]),
        float(derived["river_flow_m3s"]),
        float(derived["distance_km"]),
        float(derived["pop_density_per_km2"]),
        float(derived["biodiversity_index"]),
        float(SEASON_ENCODING.get(season, 1)),
    ]

    return {
        "features": features,
        "feature_names": feature_names,
        "_derived_inputs": derived,
        "_provenance": provenance,
    }
