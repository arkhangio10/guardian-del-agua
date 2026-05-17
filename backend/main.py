"""Guardián del Agua — FastAPI backend entry point."""
import sys
print("[bootstrap] main.py loading...", flush=True)
print(f"[bootstrap] python={sys.version.split()[0]}", flush=True)

from contextlib import asynccontextmanager
print("[bootstrap] stdlib imports done", flush=True)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
print("[bootstrap] fastapi imports done", flush=True)

from layers import detect, attribute, predict, act, publish, access
print("[bootstrap] layers imports done — main module fully loaded", flush=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    import os, sys
    print(f"[startup] python={sys.version.split()[0]} cwd={os.getcwd()}", flush=True)
    print(f"[startup] PORT={os.environ.get('PORT', 'unset')}", flush=True)

    # Diagnostic: which expected env vars actually reach this container?
    # We never print values — only presence + length. Safe to leave in production logs.
    expected_env = [
        "ANTHROPIC_API_KEY",
        "SENTINEL_HUB_CLIENT_ID",
        "SENTINEL_HUB_CLIENT_SECRET",
        "ZAVU_API_KEY",
        "ZAVU_BASE_URL",
        "ZAVU_SENDER",
        "CONTEXT7_API_KEY",
        "RESEND_API_KEY",
        "GOOGLE_CLOUD_PROJECT",
        "GOOGLE_APPLICATION_CREDENTIALS_JSON",
    ]
    print("[env] --- begin diagnostic ---", flush=True)
    for key in expected_env:
        val = os.environ.get(key, "")
        status = f"SET len={len(val)}" if val else "MISSING"
        print(f"[env] {key}: {status}", flush=True)
    print("[env] --- end diagnostic ---", flush=True)

    # Concessions: best-effort, never blocks startup.
    try:
        from layers.attribute import load_concessions
        load_concessions()
        print("[OK] Concession polygons loaded", flush=True)
    except Exception as e:
        print(f"[WARN] Concession data not loaded ({type(e).__name__}): {e}", flush=True)

    # Model: best-effort, never blocks startup.
    try:
        from layers.predict import get_model
        get_model()
        print("[OK] XGBoost model loaded", flush=True)
    except Exception as e:
        print(f"[WARN] XGBoost model not loaded ({type(e).__name__}): {e} — heuristic fallback active", flush=True)

    print("[startup] FastAPI ready to serve requests", flush=True)
    yield
    print("[shutdown] FastAPI stopping", flush=True)


app = FastAPI(
    title="Guardián del Agua API",
    description="AI-powered environmental accountability platform for the Peruvian Amazon.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(detect.router, prefix="/detect", tags=["Layer 1 — Detect"])
app.include_router(attribute.router, prefix="/attribute", tags=["Layer 2 — Attribute"])
app.include_router(predict.router, prefix="/predict", tags=["Layer 3 — Predict"])
app.include_router(act.router, prefix="/act", tags=["Layer 4 — Act"])
app.include_router(publish.router, prefix="/publish", tags=["Layer 5 — Publish"])
app.include_router(access.router, prefix="/access", tags=["Layer 6 — Access requests"])


@app.get("/health", tags=["System"])
async def health():
    return {"status": "ok", "service": "guardian-del-agua", "version": "1.0.0"}


@app.get("/leaderboard", tags=["System"])
async def get_leaderboard():
    """Return operator accountability rankings from Firestore."""
    from db import get_db
    db = get_db()
    docs = db.collection("leaderboard").order_by("total_spills", direction="DESCENDING").stream()
    return [doc.to_dict() for doc in docs]


class PipelineRequest(BaseModel):
    bbox: list[float]
    date: str


@app.post("/pipeline/run", tags=["System"])
async def run_full_pipeline(req: PipelineRequest):
    """
    Run all 5 layers in sequence for a given bbox+date.
    bbox: [lon_min, lat_min, lon_max, lat_max] in EPSG:4326
    date: ISO date string, e.g. "2024-03-15"
    Returns the fully populated alert object.
    """
    from layers.detect import DetectRequest, run_detection
    from layers.attribute import attribute_alert_endpoint
    from layers.predict import predict_impact_endpoint
    from db import get_db

    detect_resp = await run_detection(DetectRequest(bbox=req.bbox, date=req.date))
    if not detect_resp.detected or not detect_resp.alert_id:
        return {"detected": False, "message": "No contamination detected above confidence threshold"}

    alert_id = detect_resp.alert_id
    await attribute_alert_endpoint(alert_id)
    await predict_impact_endpoint(alert_id)

    db = get_db()
    doc = db.collection("alerts").document(alert_id).get()
    return {"alert_id": alert_id, "pipeline": "complete", "alert": doc.to_dict()}
