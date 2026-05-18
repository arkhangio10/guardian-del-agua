"""Guardián del Agua — FastAPI backend entry point."""
import sys
print("[bootstrap] main.py loading...", flush=True)
print(f"[bootstrap] python={sys.version.split()[0]}", flush=True)

from contextlib import asynccontextmanager
print("[bootstrap] stdlib imports done", flush=True)

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
print("[bootstrap] fastapi imports done", flush=True)

from layers import detect, attribute, predict, act, publish, access, climate
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
app.include_router(climate.router, prefix="/climate", tags=["Layer 7 — Climate (ENSO)"])


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
    db = get_db()

    # If ATTRIBUTE can't link the detection to a registered concession/pipeline
    # (bbox falls outside every polygon in norperuana.geojson), the alert is
    # legally useless for the dossier flow — no responsible operator to denounce
    # to OEFA. Drop the freshly-created alert document so it doesn't leak into
    # the leaderboard, the map, or future /detect/alerts queries as an "orphan".
    try:
        await attribute_alert_endpoint(alert_id)
    except HTTPException as exc:
        if exc.status_code == 404:
            db.collection("alerts").document(alert_id).delete()
            print(
                f"[pipeline] Rolled back alert {alert_id}: bbox outside all known concession polygons",
                flush=True,
            )
            return {
                "detected": True,
                "attributed": False,
                "message": (
                    "Contamination detected but bbox falls outside all known concession "
                    "polygons (norperuana.geojson). Alert was rolled back. Expand the "
                    "GeoJSON dataset to cover this region before re-running."
                ),
            }
        raise

    await predict_impact_endpoint(alert_id)

    doc = db.collection("alerts").document(alert_id).get()
    return {"alert_id": alert_id, "pipeline": "complete", "alert": doc.to_dict()}


@app.post("/admin/wipe-demos", tags=["Admin"])
async def wipe_demo_alerts(confirm: str = ""):
    """
    Delete every Firestore alert document whose ID starts with the literal
    string "demo-alert-". Requires confirm=YES_WIPE_DEMOS to proceed —
    we don't want a stray probe to flush data.

    The prefix is hard-coded so this endpoint can NEVER touch real alerts
    (whose IDs are UUIDs). Returns the list of deleted IDs.
    """
    if confirm != "YES_WIPE_DEMOS":
        return {
            "wiped": False,
            "message": "Pass ?confirm=YES_WIPE_DEMOS to actually delete demo alerts.",
        }

    from db import get_db
    db = get_db()
    deleted: list[str] = []
    for doc in db.collection("alerts").stream():
        if doc.id.startswith("demo-alert-"):
            doc.reference.delete()
            deleted.append(doc.id)

    print(f"[admin] wiped {len(deleted)} demo alerts: {deleted}", flush=True)
    return {"wiped": True, "count": len(deleted), "alert_ids": deleted}


@app.post("/admin/wipe-orphans", tags=["Admin"])
async def wipe_orphan_alerts(confirm: str = ""):
    """
    Delete every Firestore alert that has no usable attribution. An "orphan" is
    a doc where:
      - sentinel_bbox is missing, not a 4-element list, or contains non-finite values
      - attribution is missing, or attribution.operator_name is empty/blank

    These slip into Firestore when /pipeline/run hit a bbox outside the
    concession dataset before the rollback fix was deployed. They render in the
    map sidebar as "Sin atribución" with no marker.

    Requires confirm=YES_WIPE_ORPHANS. Returns the list of deleted IDs and
    the reason each was deleted.
    """
    if confirm != "YES_WIPE_ORPHANS":
        return {
            "wiped": False,
            "message": "Pass ?confirm=YES_WIPE_ORPHANS to actually delete orphan alerts.",
        }

    from db import get_db
    db = get_db()
    deleted: list[dict] = []
    for doc in db.collection("alerts").stream():
        # Never touch demo seed docs from this endpoint — use /admin/wipe-demos.
        if doc.id.startswith("demo-alert-"):
            continue
        data = doc.to_dict() or {}
        bbox = data.get("sentinel_bbox")
        op = (data.get("attribution") or {}).get("operator_name") or ""
        bbox_ok = (
            isinstance(bbox, list)
            and len(bbox) == 4
            and all(isinstance(v, (int, float)) for v in bbox)
        )
        op_ok = isinstance(op, str) and op.strip() != ""
        if not bbox_ok or not op_ok:
            reasons = []
            if not bbox_ok:
                reasons.append("invalid_bbox")
            if not op_ok:
                reasons.append("no_operator")
            doc.reference.delete()
            deleted.append({"alert_id": doc.id, "reasons": reasons})

    print(f"[admin] wiped {len(deleted)} orphan alerts", flush=True)
    return {"wiped": True, "count": len(deleted), "deleted": deleted}
