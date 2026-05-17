from __future__ import annotations
from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, Field
from uuid import uuid4


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


class Attribution(BaseModel):
    operator_name: str
    concession_id: str
    osinergmin_id: str
    prior_sanctions: int
    legal_status: str
    parent_company: str


class ImpactPrediction(BaseModel):
    people_affected_7d: int
    people_affected_30d: int
    fish_dieoff_30d_pct: float
    recovery_days: int
    drinking_water_sources_at_risk: int
    economic_damage_usd: int


class Alert(BaseModel):
    alert_id: str = Field(default_factory=lambda: str(uuid4()))
    detected_at: datetime = Field(default_factory=_now_utc)
    contamination_type: Literal["hydrocarbon", "turbidity", "algal_bloom", "none"] = "none"
    confidence: float = 0.0
    sentinel_bbox: list[float] = Field(..., description="[lon_min, lat_min, lon_max, lat_max]")
    sentinel_image_id: str = ""
    satellite_image_url: str | None = None
    status: Literal[
        "pending_attribution", "attributed", "predicted", "act_generated", "published"
    ] = "pending_attribution"


class FullAlert(Alert):
    attribution: Attribution | None = None
    predictions: ImpactPrediction | None = None
    denuncia_pdf_url: str | None = None
    denuncia_text: str | None = None
