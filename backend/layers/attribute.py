"""Layer 2 — ATTRIBUTE: Spatial intersection maps alert bbox to a named legal operator."""
from __future__ import annotations
from pathlib import Path

import geopandas as gpd
from fastapi import APIRouter, HTTPException
from shapely.geometry import box

from models.alert import Attribution

router = APIRouter()

_concessions: gpd.GeoDataFrame | None = None
DATA_DIR = Path(__file__).parent.parent / "data"


def load_concessions() -> gpd.GeoDataFrame:
    global _concessions
    if _concessions is not None:
        return _concessions

    geojson_path = DATA_DIR / "norperuana.geojson"
    if not geojson_path.exists():
        raise FileNotFoundError(f"Concession data not found: {geojson_path}")

    _concessions = gpd.read_file(str(geojson_path)).to_crs("EPSG:4326")
    return _concessions


def attribute_alert(bbox: list[float]) -> Attribution | None:
    concessions = load_concessions()
    alert_poly = box(*bbox)

    hits = concessions[concessions.geometry.intersects(alert_poly)].copy()
    if hits.empty:
        return None

    # Project to UTM zone 18S (EPSG:32718) for correct area calculation in metres²
    hits_proj = hits.to_crs("EPSG:32718")
    alert_poly_proj = gpd.GeoDataFrame(geometry=[alert_poly], crs="EPSG:4326").to_crs("EPSG:32718").geometry.iloc[0]
    hits["overlap"] = hits_proj.geometry.intersection(alert_poly_proj).area

    # Pipeline right-of-way contamination is unambiguous: operator owns the narrow corridor.
    # Multiply pipeline overlap scores so pipeline operators win over large-area concessions
    # when the detection falls within the right-of-way — legally, the pipeline operator
    # bears direct liability for their infrastructure (Ley 26221 Art. 8, OEFA reglamento).
    PIPELINE_MULTIPLIER = 8.0
    pipeline_mask = hits.get("feature_type", "concession") == "pipeline"
    hits.loc[pipeline_mask, "overlap"] *= PIPELINE_MULTIPLIER

    best = hits.loc[hits["overlap"].idxmax()]

    return Attribution(
        operator_name=str(best.get("operator_name", "Unknown")),
        concession_id=str(best.get("concession_id", "")),
        osinergmin_id=str(best.get("osinergmin_id", "")),
        prior_sanctions=int(best.get("prior_sanctions", 0)),
        legal_status=str(best.get("legal_status", "active")),
        parent_company=str(best.get("parent_company", "")),
    )


@router.post("/{alert_id}")
async def attribute_alert_endpoint(alert_id: str):
    """Intersect stored alert bbox with concession polygons and update Firestore."""
    from db import get_db
    db = get_db()

    doc = db.collection("alerts").document(alert_id).get()
    if not doc.exists:
        raise HTTPException(404, f"Alert {alert_id} not found")

    data = doc.to_dict()
    bbox = data.get("sentinel_bbox")
    if not bbox:
        raise HTTPException(400, "Alert has no bbox")

    attribution = attribute_alert(bbox)
    if attribution is None:
        raise HTTPException(404, "No concession found for alert bbox")

    db.collection("alerts").document(alert_id).update({
        "attribution": attribution.model_dump(),
        "status": "attributed",
    })

    return attribution.model_dump()
