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

# In-memory cache for Sentinel-2 thumbnails. Key includes band, phase, zoom_pct
# and any date override so each (zoom tier × date) is a distinct entry.
_image_cache: dict[str, tuple[bytes, datetime]] = {}
_IMAGE_CACHE_TTL = timedelta(hours=1)

# In-memory cache for Sentinel Hub Catalog API lookups (actual pass dates).
_pass_date_cache: dict[str, tuple[str | None, datetime]] = {}
_PASS_DATE_CACHE_TTL = timedelta(hours=6)

# How many days back from the incident the "before" baseline is fetched.
BEFORE_OFFSET_DAYS = 45

# Sentinel-2 native is 10 m/px. 2048² over a ~55 km bbox renders ~27 m/px
# effective and ~13 m/px once the user zooms to the 50%-crop tier — actually
# resolvable detail instead of pixelated CSS scaling on a 512² source.
DEFAULT_IMAGE_SIZE = 2048

# Analysis grayscale needs only enough pixels for stable per-pixel statistics;
# staying at 512² keeps compute_spectral_evidence_real() fast and PU cost low.
ANALYSIS_IMAGE_SIZE = 512

# Cloud-cover ceilings per use case. RGB/NIR are pulled tight for visual clarity;
# index overlays and grayscale analysis stay lenient so Amazon cloud cover doesn't
# starve the pipeline of usable passes.
MAX_CLOUD_VISUAL = 30
MAX_CLOUD_INDEX = 70


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


# ---------- Pure grayscale evalscripts for pixel-level analysis ----------
# These return a single-channel image where pixel intensity 0..255 maps to the
# spectral index strength on water pixels (0 elsewhere). Used by
# compute_spectral_evidence_real() to extract numeric features.

EVALSCRIPT_NHI_GRAY = """
//VERSION=3
function setup() {
  return {
    input: ["B03", "B04", "B08", "B11"],
    output: { bands: 1, sampleType: "UINT8" }
  };
}
function evaluatePixel(s) {
  var ndwi = (s.B03 - s.B08) / Math.max(s.B03 + s.B08, 0.0001);
  if (ndwi < 0.1) return [0];  // not water → no signal
  var nhi  = (s.B08 - s.B11) / Math.max(s.B08 + s.B11, 0.0001);
  // Clamp nhi to [0, 0.6] and map to 0..255
  var v = Math.max(0, Math.min(0.6, nhi)) / 0.6;
  return [Math.round(v * 255)];
}
"""

EVALSCRIPT_NDTI_GRAY = """
//VERSION=3
function setup() {
  return {
    input: ["B03", "B04", "B08"],
    output: { bands: 1, sampleType: "UINT8" }
  };
}
function evaluatePixel(s) {
  var ndwi = (s.B03 - s.B08) / Math.max(s.B03 + s.B08, 0.0001);
  if (ndwi < 0.05) return [0];
  var ndti = (s.B04 - s.B03) / Math.max(s.B04 + s.B03, 0.0001);
  var v = Math.max(0, Math.min(0.4, ndti)) / 0.4;
  return [Math.round(v * 255)];
}
"""

EVALSCRIPT_NDCI_GRAY = """
//VERSION=3
function setup() {
  return {
    input: ["B03", "B04", "B05", "B08"],
    output: { bands: 1, sampleType: "UINT8" }
  };
}
function evaluatePixel(s) {
  var ndwi = (s.B03 - s.B08) / Math.max(s.B03 + s.B08, 0.0001);
  if (ndwi < 0.05) return [0];
  var ndci = (s.B05 - s.B04) / Math.max(s.B05 + s.B04, 0.0001);
  var v = Math.max(0, Math.min(0.3, ndci)) / 0.3;
  return [Math.round(v * 255)];
}
"""


def _gray_evalscript_for(contamination_type: str) -> str | None:
    return {
        "hydrocarbon": EVALSCRIPT_NHI_GRAY,
        "turbidity": EVALSCRIPT_NDTI_GRAY,
        "algal_bloom": EVALSCRIPT_NDCI_GRAY,
    }.get(contamination_type)


def _analyze_grayscale(png_bytes: bytes) -> dict:
    """
    Decode a single-channel PNG and return statistics over the spectral index.
    Returns: mean_intensity (0..1), max_intensity (0..1), coverage_pct (0..1, pixels > threshold).
    Threshold for 'affected pixel' is intensity > 64/255 ≈ 0.25 of full scale.
    """
    from io import BytesIO
    from PIL import Image
    import numpy as np

    img = Image.open(BytesIO(png_bytes)).convert("L")
    arr = np.asarray(img, dtype=np.float32) / 255.0
    total = arr.size
    if total == 0:
        return {"mean_intensity": 0.0, "max_intensity": 0.0, "coverage_pct": 0.0}
    threshold = 64.0 / 255.0
    affected = int((arr > threshold).sum())
    return {
        "mean_intensity": float(arr.mean()),
        "max_intensity": float(arr.max()),
        "coverage_pct": float(affected / total),
    }


async def compute_spectral_evidence_real(data: dict) -> dict | None:
    """
    v1: real pixel-level spectral evidence.

    Fetches before + after Sentinel-2 imagery rendered through the contamination-
    specific spectral evalscript (pure grayscale), decodes both with Pillow, and
    computes delta statistics on the spectral index between the two dates.

    Returns None if Sentinel Hub is not configured or the fetch fails, so the
    caller can fall back to the v0 heuristic.
    """
    if not (settings.sentinel_hub_client_id and settings.sentinel_hub_client_secret):
        return None

    contamination_type = data.get("contamination_type", "none")
    evalscript = _gray_evalscript_for(contamination_type)
    if evalscript is None:
        return None

    bbox = data.get("sentinel_bbox")
    if not bbox or len(bbox) != 4:
        return None

    incident_date = _alert_incident_date(data)
    before_date = _shift_date(incident_date, -BEFORE_OFFSET_DAYS)

    try:
        # Index analysis uses a more permissive cloud threshold — partial
        # cloud cover is acceptable when we're computing pixel statistics
        # over masked water, and we'd rather have the pair than perfect skies.
        before_png = await fetch_sentinel_image(
            bbox, before_date, evalscript=evalscript, max_cloud=70
        )
        after_png = await fetch_sentinel_image(
            bbox, incident_date, evalscript=evalscript, max_cloud=70
        )
    except Exception as exc:
        print(f"[WARN] spectral pixel fetch failed: {exc}", flush=True)
        return None

    try:
        before_stats = _analyze_grayscale(before_png)
        after_stats = _analyze_grayscale(after_png)
    except Exception as exc:
        print(f"[WARN] spectral pixel decode failed: {exc}", flush=True)
        return None

    delta_mean = max(0.0, after_stats["mean_intensity"] - before_stats["mean_intensity"])
    delta_coverage = max(0.0, after_stats["coverage_pct"] - before_stats["coverage_pct"])

    # Evidence strength: weighted combination of how much MORE anomalous pixels
    # appeared AND how much stronger the average signal got. Both bounded to [0,1].
    # Geometric-style: sqrt(delta_mean × delta_coverage) emphasizes that BOTH
    # need to move, not just one.
    import math
    raw = math.sqrt(min(1.0, delta_mean * 4.0) * min(1.0, delta_coverage * 6.0))
    evidence_strength = max(0.0, min(1.0, raw))

    index_name = {
        "hydrocarbon": "NHI",
        "turbidity": "NDTI",
        "algal_bloom": "NDCI",
    }.get(contamination_type, "NDWI")

    return {
        "evidence_strength": round(evidence_strength, 3),
        "affected_area_pct": round(after_stats["coverage_pct"], 3),
        "index_name": index_name,
        "before_date": before_date,
        "after_date": incident_date,
        "before_stats": {k: round(v, 4) for k, v in before_stats.items()},
        "after_stats": {k: round(v, 4) for k, v in after_stats.items()},
        "delta_mean": round(delta_mean, 4),
        "delta_coverage": round(delta_coverage, 4),
        "_method": (
            f"v1 pixel-delta: sqrt(min(1, Δmean×4) × min(1, Δcoverage×6)) "
            f"on {index_name} grayscale rendered from Sentinel-2 L2A pair "
            f"({before_date} vs {incident_date})"
        ),
        "_method_version": "v1-pixel-delta",
    }

SENTINEL_AUTH_URL = (
    "https://services.sentinel-hub.com/auth/realms/main/protocol/openid-connect/token"
)
SENTINEL_PROCESS_URL = "https://services.sentinel-hub.com/api/v1/process"
SENTINEL_CATALOG_URL = "https://services.sentinel-hub.com/api/v1/catalog/1.0.0/search"


def _bbox_cache_key(bbox: list[float]) -> str:
    return ",".join(f"{v:.4f}" for v in bbox)


async def resolve_actual_pass_date(
    bbox: list[float],
    target_date: str,
    max_cloud: int = MAX_CLOUD_VISUAL,
    window_days: int = 15,
) -> str | None:
    """
    Consultar Sentinel Hub Catalog API y devolver la fecha (YYYY-MM-DD) de la
    pasada real más cercana al target dentro del ceiling de cobertura nubosa.

    Devuelve None si Sentinel Hub no está configurado, si el catálogo no tiene
    pasadas elegibles, o si la llamada falla — el caller debe usar la target_date
    nominal como fallback.
    """
    if not (settings.sentinel_hub_client_id and settings.sentinel_hub_client_secret):
        return None

    cache_key = f"{_bbox_cache_key(bbox)}|{target_date}|{max_cloud}"
    cached = _pass_date_cache.get(cache_key)
    if cached and datetime.now(timezone.utc) < cached[1]:
        return cached[0]

    try:
        token = await get_sentinel_token()
        target_dt = datetime.strptime(target_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        date_from = (target_dt - timedelta(days=window_days)).strftime("%Y-%m-%dT00:00:00Z")
        date_to = (target_dt + timedelta(days=window_days)).strftime("%Y-%m-%dT23:59:59Z")
        payload = {
            "bbox": bbox,
            "datetime": f"{date_from}/{date_to}",
            "collections": ["sentinel-2-l2a"],
            "limit": 50,
        }
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                SENTINEL_CATALOG_URL,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            resp.raise_for_status()
            body = resp.json()
    except Exception as exc:
        print(f"[WARN] Sentinel Catalog lookup failed for {bbox} @ {target_date}: {exc}", flush=True)
        _pass_date_cache[cache_key] = (None, datetime.now(timezone.utc) + _PASS_DATE_CACHE_TTL)
        return None

    candidates: list[tuple[int, str]] = []
    for feat in body.get("features", []):
        props = feat.get("properties", {}) or {}
        cc_raw = props.get("eo:cloud_cover")
        dt_iso = props.get("datetime", "") or ""
        if cc_raw is None or not dt_iso:
            continue
        try:
            cc = float(cc_raw)
        except (TypeError, ValueError):
            continue
        if cc > max_cloud:
            continue
        # Prefer first by cloud cover, tiebreak by temporal proximity.
        try:
            cand_dt = datetime.fromisoformat(dt_iso.replace("Z", "+00:00"))
        except ValueError:
            continue
        proximity = abs((cand_dt - target_dt).days)
        # Sort key: cloud_cover bucket first (so least-cloudy wins), proximity second.
        rank = int(cc) * 100 + proximity
        candidates.append((rank, dt_iso[:10]))

    if not candidates:
        _pass_date_cache[cache_key] = (None, datetime.now(timezone.utc) + _PASS_DATE_CACHE_TTL)
        return None
    candidates.sort()
    actual = candidates[0][1]
    _pass_date_cache[cache_key] = (actual, datetime.now(timezone.utc) + _PASS_DATE_CACHE_TTL)
    return actual

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
    size: int = DEFAULT_IMAGE_SIZE,
    max_cloud: int = MAX_CLOUD_VISUAL,
    window_days: int = 15,
) -> bytes:
    """
    Fetch a Sentinel-2 L2A render for the given bbox + date.

    Defaults: 2048×2048 at cloud-30. Sentinel-2 is 10 m/px native; a 55 km
    bbox renders ~27 m/px at this size and ~13 m/px once the user zooms to
    the 50%-crop tier. Spectral/grayscale callers pass size=ANALYSIS_IMAGE_SIZE
    (512) and max_cloud=MAX_CLOUD_INDEX (70) to keep the pixel-delta v1 robust
    against Amazon cloud cover.
    """
    token = await get_sentinel_token()
    # Sentinel-2 revisits every 5 days; Amazonia is heavily clouded.
    # Search ±window_days around the target date and let Sentinel Hub pick the least-cloudy pass.
    target_dt = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    date_from = (target_dt - timedelta(days=window_days)).strftime("%Y-%m-%dT00:00:00Z")
    date_to = (target_dt + timedelta(days=window_days)).strftime("%Y-%m-%dT23:59:59Z")

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
                        "maxCloudCoverage": max_cloud,
                        "mosaickingOrder": "leastCC",
                    },
                }
            ],
        },
        "evalscript": evalscript or EVALSCRIPT_RGB,
        "output": {
            "width": size,
            "height": size,
            "responses": [{"identifier": "default", "format": {"type": "image/png"}}],
        },
    }

    async with httpx.AsyncClient(timeout=90.0) as client:
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
async def get_alert_image(
    alert_id: str,
    band: str = "rgb",
    phase: str = "after",
    date: str | None = None,
    zoom_pct: int = 100,
    refresh: bool = False,
):
    """
    Return a satellite image of the alert's bbox.

    Query params:
    - band:  rgb (true-color, default) | nir (false-color NIR) | index (contamination-specific overlay)
    - phase: after (incident date, default) | before (incident date - 45 days, pre-baseline)
    - date:  YYYY-MM-DD override. When provided, fetches imagery for this exact
             date instead of the alert's incident date. Lets users see "the same
             location today" without creating a new alert.
    - zoom_pct: 25–100. Crops the bbox to the center N% before fetching, giving
             a true higher-resolution zoom (10 m/px native instead of CSS scale).
             100 = full bbox (default). 50 = 2× linear zoom (4× area zoom).
    - refresh: when true, bypasses the in-memory cache and forces a fresh fetch.

    Resolution order:
    - If alert.satellite_image_url is set in DB → redirect to that URL (phase=after, band=rgb only)
    - Else if Sentinel Hub credentials configured → fetch & return Sentinel-2 PNG
    - Else → redirect to free ESRI World Imagery export
    """
    band = band if band in ("rgb", "nir", "index") else "rgb"
    phase = phase if phase in ("before", "after") else "after"
    zoom_pct = max(25, min(100, int(zoom_pct or 100)))

    cache_key = f"{alert_id}|{band}|{phase}|{date or ''}|{zoom_pct}"
    if not refresh:
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

    if data.get("satellite_image_url") and band == "rgb" and phase == "after" and not date and zoom_pct == 100:
        return RedirectResponse(data["satellite_image_url"], status_code=302)

    bbox = data.get("sentinel_bbox")
    if not bbox or len(bbox) != 4:
        raise HTTPException(400, "Alert has no valid bbox")

    contamination_type = data.get("contamination_type", "none")
    incident_date = _alert_incident_date(data)
    if date:
        try:
            datetime.strptime(date, "%Y-%m-%d")
            target_date = date
        except ValueError:
            raise HTTPException(400, f"Invalid date format: {date}. Use YYYY-MM-DD.")
    else:
        target_date = _shift_date(incident_date, -BEFORE_OFFSET_DAYS) if phase == "before" else incident_date

    # True zoom: crop bbox toward the centroid before requesting Sentinel.
    # This makes each pixel cover a smaller real-world area, giving genuine detail
    # instead of CSS-amplifying a downsampled PNG.
    if zoom_pct < 100:
        lon_min, lat_min, lon_max, lat_max = bbox
        cx = (lon_min + lon_max) / 2
        cy = (lat_min + lat_max) / 2
        half_w = (lon_max - lon_min) * (zoom_pct / 100.0) / 2
        half_h = (lat_max - lat_min) * (zoom_pct / 100.0) / 2
        bbox = [cx - half_w, cy - half_h, cx + half_w, cy + half_h]

    evalscript = _resolve_evalscript(band, contamination_type)
    # RGB benefits from a strict cloud threshold for crisp visuals; spectral
    # overlays tolerate more cloud since water masking filters them out anyway.
    max_cloud = 30 if band == "rgb" else 70

    if settings.sentinel_hub_client_id and settings.sentinel_hub_client_secret:
        try:
            png_bytes = await fetch_sentinel_image(
                bbox, target_date, evalscript=evalscript, max_cloud=max_cloud
            )
            _image_cache[cache_key] = (png_bytes, datetime.now(timezone.utc) + _IMAGE_CACHE_TTL)
            return Response(content=png_bytes, media_type="image/png",
                            headers={"Cache-Control": "public, max-age=3600"})
        except Exception as e:
            print(f"[WARN] Sentinel Hub fetch failed for {alert_id} (band={band} phase={phase} date={target_date}): {e}", flush=True)

    return RedirectResponse(_esri_export_url(bbox), status_code=302)


def compute_spectral_evidence_v0(data: dict) -> dict:
    """
    v0: heuristic spectral-evidence descriptor.

    Used when Sentinel Hub is not configured, or when v1 pixel extraction
    fails. Derives from Claude Vision's confidence and a proxy for
    affected_area_pct, weighted by contamination_type sensitivity.

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


async def compute_spectral_evidence(data: dict) -> dict:
    """
    Resolve the spectral-evidence descriptor for an alert. Prefers v1 (real
    pixel delta on the before/after pair) when Sentinel Hub credentials are
    configured; falls back to v0 (heuristic from confidence + sensitivity)
    otherwise. The returned dict always includes `_method_version` so the
    chain-of-custody is explicit about what was actually measured.
    """
    if settings.sentinel_hub_client_id and settings.sentinel_hub_client_secret:
        v1 = await compute_spectral_evidence_real(data)
        if v1 is not None:
            return v1
    return compute_spectral_evidence_v0(data)


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
    return await compute_spectral_evidence(doc.to_dict())


@router.get("/alerts/{alert_id}/comparison")
async def get_alert_comparison(alert_id: str):
    """
    Return a comparison descriptor for an alert: before/after image URLs across
    the supported band combinations + metadata about the chosen dates.

    When Sentinel Hub credentials are configured, queries the Catalog API to
    resolve the *actual* Sentinel-2 pass dates that will be rendered (the
    Process API uses leastCC within ±15 days, so the nominal target date may
    differ from the real pass by up to two weeks). The frontend surfaces these
    so the dossier never claims a date that wasn't actually photographed.
    """
    import asyncio

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
    bbox = data["sentinel_bbox"]

    # Resolve real pass dates in parallel — this is the date the frontend will
    # display and what ends up in the legal denuncia, so honesty matters.
    actual_before: str | None = None
    actual_after: str | None = None
    if has_sh:
        try:
            actual_before, actual_after = await asyncio.gather(
                resolve_actual_pass_date(bbox, before_date, max_cloud=MAX_CLOUD_VISUAL),
                resolve_actual_pass_date(bbox, incident_date, max_cloud=MAX_CLOUD_VISUAL),
            )
        except Exception as exc:
            print(f"[WARN] actual-date resolution failed for {alert_id}: {exc}", flush=True)

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
        "actual_before_date": actual_before,
        "actual_after_date": actual_after,
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
                "actual_date": actual_before,
                "url_rgb":   f"{base}?band=rgb&phase=before",
                "url_nir":   f"{base}?band=nir&phase=before",
                "url_index": f"{base}?band=index&phase=before",
            },
            "after": {
                "label": "Durante / después",
                "date": incident_date,
                "actual_date": actual_after,
                "url_rgb":   f"{base}?band=rgb&phase=after",
                "url_nir":   f"{base}?band=nir&phase=after",
                "url_index": f"{base}?band=index&phase=after",
            },
        },
    }
