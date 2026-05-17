"""Layer 3 — PREDICT: XGBoost downstream impact prediction."""
from __future__ import annotations
from pathlib import Path

import joblib
import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from models.alert import ImpactPrediction

router = APIRouter()

ML_DIR = Path(__file__).parent.parent / "ml"
_model = None


def get_model():
    global _model
    if _model is None:
        model_path = ML_DIR / "impact_model.pkl"
        if not model_path.exists():
            raise FileNotFoundError("impact_model.pkl not found. Run ml/train.py first.")
        _model = joblib.load(str(model_path))
    return _model


CONTAMINATION_ENCODING = {"hydrocarbon": 0, "turbidity": 1, "algal_bloom": 2, "none": 3}
SEASON_ENCODING = {"dry": 0, "wet": 1}


def build_feature_vector(
    contamination_type: str,
    volume_barrels: float,
    river_flow_m3s: float,
    distance_km: float,
    pop_density: float,
    biodiversity_index: float,
    season: str,
) -> list[float]:
    return [
        CONTAMINATION_ENCODING.get(contamination_type, 0),
        volume_barrels,
        river_flow_m3s,
        distance_km,
        pop_density,
        biodiversity_index,
        SEASON_ENCODING.get(season, 1),
    ]


def estimate_water_sources(bbox: list[float]) -> int:
    # Estimate based on bbox area — 1 source per ~25 km² in Loreto basin
    lon_span = abs(bbox[2] - bbox[0]) * 111
    lat_span = abs(bbox[3] - bbox[1]) * 111
    area_km2 = lon_span * lat_span
    return max(1, int(area_km2 / 25))


def estimate_economic_damage(people_30d: int, fish_dieoff_pct: float, recovery_days: int) -> int:
    # Simple: $200/person/month subsistence impact + $5K per recovery day (remediation)
    subsistence = people_30d * 200
    remediation = recovery_days * 5000
    return subsistence + remediation


@router.post("/{alert_id}")
async def predict_impact_endpoint(alert_id: str):
    """Run XGBoost impact prediction on attributed alert and update Firestore."""
    from db import get_db
    db = get_db()

    doc = db.collection("alerts").document(alert_id).get()
    if not doc.exists:
        raise HTTPException(404, f"Alert {alert_id} not found")

    data = doc.to_dict()
    attribution = data.get("attribution")
    if not attribution:
        raise HTTPException(400, "Alert must be attributed before prediction")

    contamination_type = data.get("contamination_type", "hydrocarbon")
    bbox = data.get("sentinel_bbox", [-76.0, -4.0, -75.0, -3.0])

    # Default river conditions for NorPeruano / Loreto
    X = build_feature_vector(
        contamination_type=contamination_type,
        volume_barrels=800.0,
        river_flow_m3s=1200.0,
        distance_km=15.0,
        pop_density=8.5,
        biodiversity_index=0.82,
        season="wet",
    )

    try:
        model = get_model()
        preds = model.predict([X])[0]
        people_7d = max(0, int(preds[0]))
        people_30d = max(0, int(preds[1]))
        fish_pct = max(0.0, min(100.0, float(preds[2])))
        recovery = max(1, int(preds[3]))
    except FileNotFoundError:
        # Fallback to heuristic estimates for demo if model not trained yet
        people_7d = 400
        people_30d = 1200
        fish_pct = 80.0
        recovery = 180

    prediction = ImpactPrediction(
        people_affected_7d=people_7d,
        people_affected_30d=people_30d,
        fish_dieoff_30d_pct=fish_pct,
        recovery_days=recovery,
        drinking_water_sources_at_risk=estimate_water_sources(bbox),
        economic_damage_usd=estimate_economic_damage(people_30d, fish_pct, recovery),
    )

    db.collection("alerts").document(alert_id).update({
        "predictions": prediction.model_dump(),
        "status": "predicted",
    })

    return prediction.model_dump()
