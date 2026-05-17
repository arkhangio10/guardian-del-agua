"""Layer 1 — DETECT: Sentinel-2 imagery + Claude Vision contamination classification."""
from __future__ import annotations
import base64
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import anthropic
import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from config import settings
from models.alert import Alert

router = APIRouter()

SENTINEL_AUTH_URL = (
    "https://services.sentinel-hub.com/auth/realms/main/protocol/openid-connect/token"
)
SENTINEL_PROCESS_URL = "https://services.sentinel-hub.com/api/v1/process"

EVALSCRIPT = """
//VERSION=3
function setup() {
  return {
    input: ["B04", "B03", "B02", "B08"],
    output: { bands: 4, sampleType: "UINT8" }
  };
}
function evaluatePixel(s) {
  return [s.B04 * 3.5 * 255, s.B03 * 3.5 * 255, s.B02 * 3.5 * 255, s.B08 * 3.5 * 255];
}
"""

_sentinel_token: dict = {"token": None, "expires_at": datetime.now(timezone.utc)}


async def get_sentinel_token() -> str:
    global _sentinel_token
    if _sentinel_token["token"] and datetime.now(timezone.utc) < _sentinel_token["expires_at"]:
        return _sentinel_token["token"]

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            SENTINEL_AUTH_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": settings.sentinel_hub_client_id,
                "client_secret": settings.sentinel_hub_client_secret,
            },
        )
        resp.raise_for_status()
        data = resp.json()

    _sentinel_token["token"] = data["access_token"]
    _sentinel_token["expires_at"] = datetime.now(timezone.utc) + timedelta(seconds=data["expires_in"] - 60)
    return _sentinel_token["token"]


async def fetch_sentinel_image(bbox: list[float], date: str) -> bytes:
    token = await get_sentinel_token()
    # Sentinel-2 revisits every 5 days; Amazonia is heavily clouded.
    # Search ±15 days around the target date and let Sentinel Hub pick the least-cloudy pass.
    target_dt = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    date_from = (target_dt - timedelta(days=15)).strftime("%Y-%m-%dT00:00:00Z")
    date_to = (target_dt + timedelta(days=15)).strftime("%Y-%m-%dT23:59:59Z")

    payload = {
        "input": {
            "bounds": {
                "bbox": bbox,
                "properties": {"crs": "http://www.opengis.net/def/crs/EPSG/0/4326"},
            },
            "data": [
                {
                    "type": "sentinel-2-l2a",
                    "dataFilter": {
                        "timeRange": {"from": date_from, "to": date_to},
                        "maxCloudCoverage": 70,
                        "mosaickingOrder": "leastCC",
                    },
                }
            ],
        },
        "evalscript": EVALSCRIPT,
        "output": {
            "width": 512,
            "height": 512,
            "responses": [{"identifier": "default", "format": {"type": "image/png"}}],
        },
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            SENTINEL_PROCESS_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        resp.raise_for_status()
        return resp.content


async def analyze_with_claude(image_bytes: bytes) -> dict:
    b64 = base64.b64encode(image_bytes).decode()
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    response = await client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=512,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": b64,
                        },
                    },
                    {
                        "type": "text",
                        "text": (
                            "Analyze this Sentinel-2 multi-spectral image of the Peruvian Amazon river basin.\n"
                            "Identify contamination signatures:\n"
                            "- hydrocarbon: dark patches on water, rainbow/iridescent sheen, near-infrared anomaly\n"
                            "- turbidity: red-brown discoloration, sediment plume, unusual opacity\n"
                            "- algal_bloom: bright green patches, chlorophyll spike, surface bloom\n\n"
                            "Return ONLY valid JSON, no other text:\n"
                            '{"contamination_detected": true/false, '
                            '"type": "hydrocarbon|turbidity|algal_bloom|none", '
                            '"confidence": 0.0-1.0, '
                            '"description": "one sentence in Spanish", '
                            '"affected_area_pct": 0.0-1.0}'
                        ),
                    },
                ],
            }
        ],
    )

    text = response.content[0].text.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())


class DetectRequest(BaseModel):
    bbox: list[float]
    date: str


class DetectResponse(BaseModel):
    alert_id: str | None
    detected: bool
    confidence: float
    contamination_type: str
    description: str


@router.post("/run", response_model=DetectResponse)
async def run_detection(req: DetectRequest):
    """Fetch Sentinel-2 image for bbox+date, classify with Claude Vision, store alert."""
    if len(req.bbox) != 4:
        raise HTTPException(400, "bbox must have 4 values: [lon_min, lat_min, lon_max, lat_max]")

    try:
        image_bytes = await fetch_sentinel_image(req.bbox, req.date)
    except httpx.HTTPStatusError as e:
        raise HTTPException(502, f"Sentinel Hub error: {e.response.status_code}")

    result = await analyze_with_claude(image_bytes)

    if not result.get("contamination_detected") or result["confidence"] < settings.confidence_threshold:
        return DetectResponse(
            alert_id=None,
            detected=False,
            confidence=result.get("confidence", 0.0),
            contamination_type=result.get("type", "none"),
            description=result.get("description", "No contamination detected"),
        )

    alert = Alert(
        alert_id=str(uuid4()),
        detected_at=datetime.now(timezone.utc),
        contamination_type=result["type"],
        confidence=result["confidence"],
        sentinel_bbox=req.bbox,
        sentinel_image_id=f"S2_{req.date}_{req.bbox[0]:.2f}_{req.bbox[1]:.2f}",
        status="pending_attribution",
    )

    from db import get_db
    db = get_db()
    db.collection("alerts").document(alert.alert_id).set(alert.model_dump(mode="json"))

    return DetectResponse(
        alert_id=alert.alert_id,
        detected=True,
        confidence=alert.confidence,
        contamination_type=alert.contamination_type,
        description=result.get("description", ""),
    )


@router.get("/alerts")
async def list_alerts(limit: int = 20):
    """Return recent alerts from Firestore ordered by detection time."""
    from db import get_db
    db = get_db()
    docs = db.collection("alerts").order_by("detected_at", direction="DESCENDING").limit(limit).stream()
    return [doc.to_dict() for doc in docs]


@router.get("/alerts/{alert_id}")
async def get_alert(alert_id: str):
    """Return a single alert by ID."""
    from db import get_db
    db = get_db()
    doc = db.collection("alerts").document(alert_id).get()
    if not doc.exists:
        raise HTTPException(404, f"Alert {alert_id} not found")
    return doc.to_dict()
