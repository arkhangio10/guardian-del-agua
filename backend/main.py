"""Guardián del Agua — FastAPI backend entry point."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from layers import detect, attribute, predict, act, publish


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        from layers.attribute import load_concessions
        load_concessions()
        print("[OK] Concession polygons loaded")
    except FileNotFoundError as e:
        print(f"[WARN] Concession data not found: {e}")

    try:
        from layers.predict import get_model
        get_model()
        print("[OK] XGBoost model loaded")
    except FileNotFoundError:
        print("[WARN] impact_model.pkl not found — heuristic fallback active until ml/train.py is run")

    yield


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
