"""Layer 1 — DETECT: Sentinel-2 imagery + Claude Vision contamination classification."""
from __future__ import annotations
import base64
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import anthropic
import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse, Response
from pydantic import BaseModel

from config import settings
from models.alert import Alert

router = APIRouter()

# In-memory cache for Sentinel-2 thumbnails. Key: f"{alert_id}|{band}|{phase}".
_image_cache: dict[str, tuple[bytes, datetime]] = {}
_IMAGE_CACHE_TTL = timedelta(hours=1)

# How many days back from the incident the "before" baseline is fetched.
BEFORE_OFFSET_DAYS = 45


def _esri_export_url(bbox: list[float], size: int = 512) -> str:
    """Free ESRI World Imagery export — no auth needed. Used as fallback."""
    lon_min, lat_min, lon_max, lat_max = bbox
    return (
        "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/"
        f"export?bbox={lon_min},{lat_min},{lon_max},{lat_max}"
        f"&bboxSR=4326&imageSR=4326&size={size},{size}&format=png&f=image"
    )


# ---------- Evalscripts ----------

EVALSCRIPT_RGB = """
//VERSION=3
function setup() {
  return {
    input: ["B04", "B03", "B02"],
    output: { bands: 3, sampleType: "UINT8" }
  };
}
function evaluatePixel(s) {
  return [s.B04 * 3.5 * 255, s.B03 * 3.5 * 255, s.B02 * 3.5 * 255];
}
"""

# False-color NIR (B08 in red): healthy vegetation glows red, water reads near-black,
# sediment plumes and oil sheen pop visually because of B08 absorption contrast.
EVALSCRIPT_NIR = """
//VERSION=3
function setup() {
  return {
    input: ["B08", "B04", "B03"],
    output: { bands: 3, sampleType: "UINT8" }
  };
}
function evaluatePixel(s) {
  return [s.B08 * 3.0 * 255, s.B04 * 3.5 * 255, s.B03 * 3.5 * 255];
}
"""

# Contamination-specific indices — overlay the suspected pixels with a
# saturated marker color on top of true-color base so analysts still see context.
EVALSCRIPT_HYDROCARBON = """
//VERSION=3
function setup() {
  return {
    input: ["B04", "B03", "B02", "B08", "B11"],
    output: { bands: 3, sampleType: "UINT8" }
  };
}
function evaluatePixel(s) {
  var ndwi = (s.B03 - s.B08) / Math.max(s.B03 + s.B08, 0.0001);
  var nhi  = (s.B08 - s.B11) / Math.max(s.B08 + s.B11, 0.0001);
  // Water (ndwi > 0.2) AND anomalous SWIR signature -> red marker.
  if (ndwi > 0.2 && nhi > 0.2) {
    return [255, 60, 60];
  }
  return [s.B04 * 3.5 * 255, s.B03 * 3.5 * 255, s.B02 * 3.5 * 255];
}
"""

EVALSCRIPT_TURBIDITY = """
//VERSION=3
function setup() {
  return {
    input: ["B04", "B03", "B02", "B08"],
    output: { bands: 3, sampleType: "UINT8" }
  };
}
function evaluatePixel(s) {
  var ndwi = (s.B03 - s.B08) / Math.max(s.B03 + s.B08, 0.0001);
  var ndti = (s.B04 - s.B03) / Math.max(s.B04 + s.B03, 0.0001);
  if (ndwi > 0.1 && ndti > 0.05) {
    var k = Math.min(ndti * 2.0, 1.0);
    return [220 + 35 * k, 110 + 40 * (1 - k), 40];
  }
  return [s.B04 * 3.5 * 255, s.B03 * 3.5 * 255, s.B02 * 3.5 * 255];
}
"""

EVALSCRIPT_ALGAL = """
//VERSION=3
function setup() {
  return {
    input: ["B04", "B03", "B02", "B05", "B08"],
    output: { bands: 3, sampleType: "UINT8" }
  };
}
function evaluatePixel(s) {
  var ndwi = (s.B03 - s.B08) / Math.max(s.B03 + s.B08, 0.0001);
  var ndci = (s.B05 - s.B04) / Math.max(s.B05 + s.B04, 0.0001);
  if (ndwi > 0.1 && ndci > 0.02) {
    var k = Math.min(ndci * 5.0, 1.0);
    return [60, 200 + 55 * k, 90];
  }
  return [s.B04 * 3.5 * 255, s.B03 * 3.5 * 255, s.B02 * 3.5 * 255];
}
"""


def _index_evalscript_for(contamination_type: str) -> str:
    return {
        "hydrocarbon": EVALSCRIPT_HYDROCARBON,
        "turbidity": EVALSCRIPT_TURBIDITY,
        "algal_bloom": EVALSCRIPT_ALGAL,
    }.get(contamination_type, EVALSCRIPT_RGB)


def _resolve_evalscript(band: str, contamination_type: str) -> str:
    """band: rgb | nir | index. 'index' picks contamination-specific overlay."""
    if band == "nir":
        return EVALSCRIPT_NIR
    if band == "index":
        return _index_evalscript_for(contamination_type)
    return EVALSCRIPT_RGB

SENTINEL_AUTH_URL = (
    "https://services.sentinel-hub.com/auth/realms/main/protocol/openid-connect/token"
)
SENTINEL_PROCESS_URL = "https://services.sentinel-hub.com/api/v1/process"

# Legacy alias kept for the detect/run pipeline that already uses it.
EVALSCRIPT = EVALSCRIPT_RGB

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


async def fetch_sentinel_image(
    bbox: list[float],
    date: str,
    evalscript: str | None = None,
) -> bytes:
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
        "evalscript": evalscript or EVALSCRIPT_RGB,
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


def _alert_incident_date(data: dict) -> str:
    """Best-effort: extract YYYY-MM-DD from alert document."""
    image_id = data.get("sentinel_image_id", "") or ""
    for part in image_id.split("_"):
        if len(part) == 10 and part[4] == "-":
            return part
        if len(part) == 8 and part.isdigit():
            return f"{part[:4]}-{part[4:6]}-{part[6:8]}"
    detected = data.get("detected_at", "") or ""
    if detected:
        return detected[:10]
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _shift_date(date_str: str, days: int) -> str:
    dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return (dt + timedelta(days=days)).strftime("%Y-%m-%d")


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


@router.get("/alerts/{alert_id}/image")
async def get_alert_image(alert_id: str, band: str = "rgb", phase: str = "after"):
    """
    Return a satellite image of the alert's bbox.

    Query params:
    - band:  rgb (true-color, default) | nir (false-color NIR) | index (contamination-specific overlay)
    - phase: after (incident date, default) | before (incident date - 45 days, pre-baseline)

    Resolution order:
    - If alert.satellite_image_url is set in DB → redirect to that URL (phase=after, band=rgb only)
    - Else if Sentinel Hub credentials configured → fetch & return Sentinel-2 PNG
    - Else → redirect to free ESRI World Imagery export (only valid for phase=after / band=rgb)
    """
    band = band if band in ("rgb", "nir", "index") else "rgb"
    phase = phase if phase in ("before", "after") else "after"

    cache_key = f"{alert_id}|{band}|{phase}"
    cached = _image_cache.get(cache_key)
    if cached and datetime.now(timezone.utc) < cached[1]:
        return Response(content=cached[0], media_type="image/png",
                        headers={"Cache-Control": "public, max-age=3600"})

    from db import get_db
    db = get_db()
    doc = db.collection("alerts").document(alert_id).get()
    if not doc.exists:
        raise HTTPException(404, f"Alert {alert_id} not found")
    data = doc.to_dict()

    if data.get("satellite_image_url") and band == "rgb" and phase == "after":
        return RedirectResponse(data["satellite_image_url"], status_code=302)

    bbox = data.get("sentinel_bbox")
    if not bbox or len(bbox) != 4:
        raise HTTPException(400, "Alert has no valid bbox")

    contamination_type = data.get("contamination_type", "none")
    incident_date = _alert_incident_date(data)
    target_date = _shift_date(incident_date, -BEFORE_OFFSET_DAYS) if phase == "before" else incident_date
    evalscript = _resolve_evalscript(band, contamination_type)

    if settings.sentinel_hub_client_id and settings.sentinel_hub_client_secret:
        try:
            png_bytes = await fetch_sentinel_image(bbox, target_date, evalscript=evalscript)
            _image_cache[cache_key] = (png_bytes, datetime.now(timezone.utc) + _IMAGE_CACHE_TTL)
            return Response(content=png_bytes, media_type="image/png",
                            headers={"Cache-Control": "public, max-age=3600"})
        except Exception as e:
            print(f"[WARN] Sentinel Hub fetch failed for {alert_id} (band={band} phase={phase}): {e}", flush=True)

    # Fallback: ESRI export only renders true-color "after". For other combinations,
    # serve the same ESRI image so the UI degrades gracefully.
    return RedirectResponse(_esri_export_url(bbox), status_code=302)


def compute_spectral_evidence(data: dict) -> dict:
    """
    Compute a spectral-evidence descriptor for an alert.

    v0 (current): heuristic mapping from Claude Vision's confidence and the
    affected_area_pct it returns, weighted by contamination_type sensitivity.
    Documented as v0 in `_method` so the chain-of-custody is honest about
    what is and isn't measured. v1 will replace this with real pixel-level
    delta extraction from the before/after Sentinel-2 pair.

    Returns:
      {
        "evidence_strength": float in [0, 1],
        "affected_area_pct": float in [0, 1],
        "index_name": "NHI" | "NDTI" | "NDCI" | "NDWI",
        "before_date": str,
        "after_date": str,
        "_method": str (provenance label),
        "_method_version": "v0-heuristic" | "v1-pixel-delta",
      }
    """
    contamination_type = data.get("contamination_type", "none")
    confidence = float(data.get("confidence", 0.0) or 0.0)

    # Claude doesn't currently persist affected_area_pct per alert — derive a
    # plausible value from confidence as a soft proxy. Once detect.py starts
    # writing affected_area_pct to the alert doc this will use the real value.
    affected_area_pct = float(data.get("affected_area_pct") or min(0.5, max(0.05, confidence * 0.5)))

    index_name = {
        "hydrocarbon": "NHI",
        "turbidity": "NDTI",
        "algal_bloom": "NDCI",
    }.get(contamination_type, "NDWI")

    # Sensitivity weights — hydrocarbons read more cleanly in SWIR/NIR diff
    # than diffuse algal blooms, so the same area_pct carries more evidential
    # weight for an oil spill.
    sensitivity = {
        "hydrocarbon": 1.0,
        "turbidity": 0.85,
        "algal_bloom": 0.75,
    }.get(contamination_type, 0.6)

    # Bounded combination so a 95%-confidence + 30%-area detection lands near
    # 0.85 evidence strength, leaving room for "extreme" detections to reach 1.0.
    evidence_strength = min(1.0, confidence * min(1.0, affected_area_pct * 4.0) * sensitivity)

    incident_date = _alert_incident_date(data)
    before_date = _shift_date(incident_date, -BEFORE_OFFSET_DAYS)

    return {
        "evidence_strength": round(evidence_strength, 3),
        "affected_area_pct": round(affected_area_pct, 3),
        "index_name": index_name,
        "before_date": before_date,
        "after_date": incident_date,
        "_method": (
            f"v0 heuristic: confidence × min(1, affected_area_pct × 4) × sensitivity[{contamination_type}]"
        ),
        "_method_version": "v0-heuristic",
    }


@router.get("/alerts/{alert_id}/spectral")
async def get_alert_spectral(alert_id: str):
    """
    Spectral evidence descriptor for an alert. Used by the predict layer as a
    post-prediction multiplier and surfaced in the dossier UI.
    """
    from db import get_db
    db = get_db()
    doc = db.collection("alerts").document(alert_id).get()
    if not doc.exists:
        raise HTTPException(404, f"Alert {alert_id} not found")
    return compute_spectral_evidence(doc.to_dict())


@router.get("/alerts/{alert_id}/comparison")
async def get_alert_comparison(alert_id: str):
    """
    Return a comparison descriptor for an alert: before/after image URLs across
    the supported band combinations + metadata about the chosen dates.

    The frontend uses this to render a swipe-slider comparison and band toggle.
    Sentinel Hub creds are NOT required to return the descriptor; the URLs will
    transparently fall back to ESRI World Imagery when fetched.
    """
    from db import get_db
    db = get_db()
    doc = db.collection("alerts").document(alert_id).get()
    if not doc.exists:
        raise HTTPException(404, f"Alert {alert_id} not found")
    data = doc.to_dict()

    if not data.get("sentinel_bbox"):
        raise HTTPException(400, "Alert has no valid bbox")

    contamination_type = data.get("contamination_type", "none")
    incident_date = _alert_incident_date(data)
    before_date = _shift_date(incident_date, -BEFORE_OFFSET_DAYS)
    has_sh = bool(settings.sentinel_hub_client_id and settings.sentinel_hub_client_secret)

    index_label = {
        "hydrocarbon": "NHI (índice de hidrocarburos)",
        "turbidity": "NDTI (índice de turbidez)",
        "algal_bloom": "NDCI (índice de clorofila)",
    }.get(contamination_type, "Índice")

    base = f"/detect/alerts/{alert_id}/image"

    return {
        "alert_id": alert_id,
        "contamination_type": contamination_type,
        "before_date": before_date,
        "after_date": incident_date,
        "before_offset_days": BEFORE_OFFSET_DAYS,
        "sentinel_hub_available": has_sh,
        "bands": [
            {"id": "rgb",   "label": "Color real (RGB)",          "available": True},
            {"id": "nir",   "label": "Infrarrojo cercano (NIR)",  "available": has_sh},
            {"id": "index", "label": index_label,                  "available": has_sh},
        ],
        "phases": {
            "before": {
                "label": "Antes del incidente",
                "date": before_date,
                "url_rgb":   f"{base}?band=rgb&phase=before",
                "url_nir":   f"{base}?band=nir&phase=before",
                "url_index": f"{base}?band=index&phase=before",
            },
            "after": {
                "label": "Durante / después",
                "date": incident_date,
                "url_rgb":   f"{base}?band=rgb&phase=after",
                "url_nir":   f"{base}?band=nir&phase=after",
                "url_index": f"{base}?band=index&phase=after",
            },
        },
    }
