"""
Run the FULL pipeline against the deployed backend for a curated list of
real concession bboxes. Results are stored in Firestore as alerts whose
classification, confidence, and predictions are produced by the actual
Claude Vision + XGBoost pipeline — not hardcoded demo values.

This is the answer to "why are we using demo data?". Demo alerts have
real bboxes (the actual locations of ONP Tramo I, Lote 192, Lote 8,
Lote 95, etc.) but hardcoded contamination types, confidences, and
human-impact estimates. Running this script replaces synthetic
contamination_type/confidence with what Claude actually sees in TODAY's
Sentinel-2 pass over those concessions.

Honest expected outcomes:
- Claude may classify many bboxes as "no contamination detected" — that
  IS the correct outcome on a clean day, and a feature, not a bug.
- The detection threshold (settings.confidence_threshold = 0.70) means
  borderline images won't generate alerts. Adjust if needed.
- Real alerts get UUIDs, not "demo-alert-NNN" — they coexist with the
  demo data; you can keep both or wipe demos first.

Usage:
    # From backend/ with venv active and BACKEND_URL set:
    python scripts/run_real_pipeline.py

    # Or against localhost:
    BACKEND_URL=http://localhost:8000 python scripts/run_real_pipeline.py

Optional flags:
    --wipe-demos      Delete demo-alert-* documents before running.
    --date YYYY-MM-DD  Use a specific date instead of "today minus 30 days".
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

import httpx


# Real concession bboxes — same ones used in seed_demo.py because those ARE
# documented locations of operators with public sanctions on OEFA record.
# We keep them small enough that contamination, if present, is detectable.
REAL_CONCESSIONS = [
    {
        "name": "ONP Tramo I (Cuatro Cuencas)",
        "bbox": [-76.1, -3.9, -75.6, -3.5],
        "expected_operator": "Petroperú S.A.",
    },
    {
        "name": "ONP Tramo I — Andoas",
        "bbox": [-75.8, -4.2, -75.3, -3.8],
        "expected_operator": "Petroperú S.A.",
    },
    {
        "name": "Lote 95 — Marañón",
        "bbox": [-74.9, -6.2, -74.2, -5.9],
        "expected_operator": "Petrotal Corp.",
    },
    {
        "name": "Lote 192 — Pastaza/Corrientes",
        "bbox": [-75.5, -4.8, -75.0, -4.3],
        "expected_operator": "Frontera Energy / Petroperú",
    },
    {
        "name": "Lote 8 — Pluspetrol",
        "bbox": [-77.6, -4.0, -77.1, -3.6],
        "expected_operator": "Pluspetrol Norte S.A.",
    },
]


def default_date() -> str:
    """Use ~30 days ago by default — Sentinel-2 likely has at least one clear pass."""
    dt = datetime.now(timezone.utc) - timedelta(days=30)
    return dt.strftime("%Y-%m-%d")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--backend",
        default=os.environ.get("BACKEND_URL", "https://guardian-del-agua-production.up.railway.app"),
        help="Backend URL (default: $BACKEND_URL or Railway prod)",
    )
    parser.add_argument("--date", default=default_date(), help="Target date YYYY-MM-DD")
    parser.add_argument(
        "--wipe-demos",
        action="store_true",
        help="Delete demo-alert-* documents from Firestore before running",
    )
    args = parser.parse_args()

    print(f"[real-pipeline] backend = {args.backend}")
    print(f"[real-pipeline] date    = {args.date}")
    print(f"[real-pipeline] running {len(REAL_CONCESSIONS)} concessions...\n")

    if args.wipe_demos:
        print("[WARN] --wipe-demos requires direct Firestore access, not HTTP.")
        print("       Run instead from a Python REPL with the firebase-admin SDK:")
        print('         from db import get_db; db = get_db()')
        print('         for d in db.collection("alerts").stream():')
        print('             if d.id.startswith("demo-alert-"): d.reference.delete()')
        print()

    summary = []
    with httpx.Client(timeout=180.0) as client:
        for i, conc in enumerate(REAL_CONCESSIONS, 1):
            payload = {"bbox": conc["bbox"], "date": args.date}
            print(f"[{i}/{len(REAL_CONCESSIONS)}] {conc['name']}")
            print(f"       bbox={conc['bbox']} expected_operator={conc['expected_operator']}")
            try:
                resp = client.post(f"{args.backend}/pipeline/run", json=payload)
                resp.raise_for_status()
                data = resp.json()
                if not data.get("alert_id"):
                    print(f"       → no contamination detected (this is honest, not a bug)")
                    summary.append({"name": conc["name"], "status": "clean", "alert_id": None})
                    continue
                alert = data.get("alert", {})
                contam = alert.get("contamination_type", "?")
                conf = alert.get("confidence", 0)
                att = (alert.get("attribution") or {}).get("operator_name", "—")
                pred = alert.get("predictions") or {}
                affected = pred.get("people_affected_30d", "—")
                print(f"       → alert_id={data['alert_id']}")
                print(f"       → type={contam} confidence={conf:.0%} operator={att}")
                print(f"       → projected 30d affected={affected}")
                summary.append({
                    "name": conc["name"],
                    "status": "detected",
                    "alert_id": data["alert_id"],
                    "type": contam,
                    "confidence": conf,
                    "operator": att,
                    "people_30d": affected,
                })
            except httpx.HTTPStatusError as e:
                print(f"       ✗ HTTP {e.response.status_code}: {e.response.text[:200]}")
                summary.append({"name": conc["name"], "status": "error", "error": str(e)})
            except Exception as e:
                print(f"       ✗ {type(e).__name__}: {e}")
                summary.append({"name": conc["name"], "status": "error", "error": str(e)})
            print()

    print("\n[real-pipeline] === Summary ===")
    detected = sum(1 for s in summary if s["status"] == "detected")
    clean = sum(1 for s in summary if s["status"] == "clean")
    errors = sum(1 for s in summary if s["status"] == "error")
    print(f"  detected: {detected}")
    print(f"  clean:    {clean}")
    print(f"  errors:   {errors}")
    if detected:
        print("\n  Real alerts created (UUID, not demo-alert-*):")
        for s in summary:
            if s["status"] == "detected":
                print(f"    - {s['alert_id'][:8]}… · {s['type']} · {s['operator']} · {s['name']}")
    sys.exit(0 if errors == 0 else 1)


if __name__ == "__main__":
    main()
