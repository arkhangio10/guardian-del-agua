"""
Seed Firestore with demo data for the hack@latam presentation.

DEMO DATA NOTICE:
- Alert incident dates, coordinates, and barrel volumes are INVENTED for demo purposes.
- Operator names, concession IDs, and sanction counts are sourced from public
  OEFA/OSINERGMIN records as cited in the project documentation.
- Leaderboard figures (e.g. Petroperú 474 spills) are from OEFA enforcement records
  published in ANA and MINAM reports (2000–2024).
- This script must NOT be run against a production Firestore database.
"""
import sys
import json
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from db import get_db

DEMO_ALERTS = [
    # Demo showcase principal — bbox oficial documentado en CLAUDE.md.
    # Cuatro Cuencas / Oleoducto Norperuano · Tramo I. La atribución cae a
    # Petroperú (presunto responsable, sujeto a verificación in situ).
    # Dates rolled forward to 2025-2026 so Sentinel-2 imagery is recent —
    # the bboxes are real concession locations, so fetching Sentinel for
    # these recent dates returns actual satellite data of those operators
    # (regardless of whether a real incident occurred on that date).
    {
        "alert_id": "demo-alert-001",
        "detected_at": "2026-04-15T14:32:00",
        "contamination_type": "hydrocarbon",
        "confidence": 0.92,
        "sentinel_bbox": [-76.1, -3.9, -75.6, -3.5],
        "sentinel_image_id": "S2_20260415_ONP_CuatroCuencas",
        "satellite_image_url": None,
        "status": "published",
        "region_label": "Cuatro Cuencas (Pastaza/Corrientes/Tigre/Marañón)",
        "attribution": {
            "operator_name": "Petroperú S.A.",
            "concession_id": "ONP-Tramo-I",
            "osinergmin_id": "OSI-ONP-1974",
            "prior_sanctions": 474,
            "legal_status": "active",
            "parent_company": "Estado Peruano (100%)",
        },
        "predictions": {
            "people_affected_7d": 400,
            "people_affected_30d": 1200,
            "fish_dieoff_30d_pct": 80.0,
            "recovery_days": 180,
            "drinking_water_sources_at_risk": 3,
            "economic_damage_usd": 1140000,
        },
    },
    {
        "alert_id": "demo-alert-002",
        "detected_at": "2026-02-22T09:15:00",
        "contamination_type": "hydrocarbon",
        "confidence": 0.88,
        "sentinel_bbox": [-75.8, -4.2, -75.3, -3.8],
        "sentinel_image_id": "S2_20260222_ONP_Andoas",
        "satellite_image_url": None,
        "status": "act_generated",
        "attribution": {
            "operator_name": "Petroperú S.A.",
            "concession_id": "ONP-Tramo-I",
            "osinergmin_id": "OSI-ONP-1974",
            "prior_sanctions": 474,
            "legal_status": "active",
            "parent_company": "Estado Peruano (100%)",
        },
        "predictions": {
            "people_affected_7d": 220,
            "people_affected_30d": 660,
            "fish_dieoff_30d_pct": 62.0,
            "recovery_days": 125,
            "drinking_water_sources_at_risk": 2,
            "economic_damage_usd": 757500,
        },
    },
    {
        "alert_id": "demo-alert-003",
        "detected_at": "2025-11-05T07:50:00",
        "contamination_type": "turbidity",
        "confidence": 0.81,
        "sentinel_bbox": [-74.9, -6.2, -74.2, -5.9],
        "sentinel_image_id": "S2_20251105_L095",
        "satellite_image_url": None,
        "status": "predicted",
        "attribution": {
            "operator_name": "Petrotal Corp.",
            "concession_id": "Lote-95",
            "osinergmin_id": "OSIN-L095",
            "prior_sanctions": 4,
            "legal_status": "active",
            "parent_company": "Petrotal Corp. (Canadá)",
        },
        "predictions": {
            "people_affected_7d": 280,
            "people_affected_30d": 840,
            "fish_dieoff_30d_pct": 18.0,
            "recovery_days": 38,
            "drinking_water_sources_at_risk": 2,
            "economic_damage_usd": 358000,
        },
    },
    {
        "alert_id": "demo-alert-004",
        "detected_at": "2025-08-18T11:20:00",
        "contamination_type": "algal_bloom",
        "confidence": 0.76,
        "sentinel_bbox": [-75.5, -4.8, -75.0, -4.3],
        "sentinel_image_id": "S2_20250818_NP14B",
        "satellite_image_url": None,
        "status": "attributed",
        "attribution": {
            "operator_name": "Petroperú S.A.",
            "concession_id": "ONP-Tramo-I",
            "osinergmin_id": "OSI-ONP-1974",
            "prior_sanctions": 474,
            "legal_status": "active",
            "parent_company": "Estado Peruano (100%)",
        },
        "predictions": None,
    },
    {
        "alert_id": "demo-alert-005",
        "detected_at": "2024-09-11T16:05:00",
        "contamination_type": "hydrocarbon",
        "confidence": 0.95,
        "sentinel_bbox": [-77.6, -4.0, -77.1, -3.6],
        "sentinel_image_id": "S2_20240911_ONP_SPILL",
        "satellite_image_url": None,
        "status": "published",
        "attribution": {
            "operator_name": "Pluspetrol Norte S.A.",
            "concession_id": "Lote-8",
            "osinergmin_id": "OSI-008-1994",
            "prior_sanctions": 92,
            "legal_status": "active",
            "parent_company": "Pluspetrol S.A. (Argentina)",
        },
        "predictions": {
            "people_affected_7d": 900,
            "people_affected_30d": 2700,
            "fish_dieoff_30d_pct": 95.0,
            "recovery_days": 270,
            "drinking_water_sources_at_risk": 5,
            "economic_damage_usd": 2085000,
        },
    },
]

# Datos verificables de fuentes públicas (OEFA, Oxfam, Mongabay, El Comercio).
# Período: 1997-2023 para lotes; 2013-2023 para Oleoducto Norperuano.
# Total Amazonía peruana: 831 derrames documentados / 1,462 a nivel nacional.
LEADERBOARD_DATA = [
    {
        "rank": 1,
        "operator_name": "Lote 192 (ex-1AB) — operadores históricos",
        "asset_label": "Lote-192 / OXY · Pluspetrol · Petroperú · Frontera",
        "total_spills": 233,
        "spills_period": "1997-Q1 2021",
        "fines_paid": None,
        "fines_imposed": None,
        "open_sanctions": 1,
        "legal_status": "active",
        "source": "Oxfam 'La Sombra del Petróleo' + OEFA",
    },
    {
        "rank": 2,
        "operator_name": "Pluspetrol Norte S.A. (Lote 8)",
        "asset_label": "Lote-8",
        "total_spills": 189,
        "spills_period": "1997-Q1 2021",
        "fines_paid": None,
        "fines_imposed": None,
        "open_sanctions": None,
        "legal_status": "in_liquidation",
        "source": "Oxfam + OEFA",
    },
    {
        "rank": 3,
        "operator_name": "Petroperú S.A. (Oleoducto Norperuano)",
        "asset_label": "ONP-Tramo-I",
        "total_spills": 91,
        "spills_period": "2013-2023",
        "fines_paid": 22,
        "fines_imposed": 51,
        "open_sanctions": 4,
        "legal_status": "active",
        "source": "OEFA + Mongabay Latam",
    },
    {
        "rank": 4,
        "operator_name": "Pluspetrol Norte S.A. (Lote 95)",
        "asset_label": "Lote-95",
        "total_spills": 38,
        "spills_period": "2000-2023",
        "fines_paid": None,
        "fines_imposed": None,
        "open_sanctions": None,
        "legal_status": "in_liquidation",
        "source": "OEFA + RAISG 2022",
    },
]


def seed():
    db = get_db()
    print("Seeding demo alerts...")
    for alert in DEMO_ALERTS:
        db.collection("alerts").document(alert["alert_id"]).set(alert)
        print(f"  ✓ {alert['alert_id']} — {alert['contamination_type']} ({alert['status']})")

    print("\nSeeding leaderboard...")
    for entry in LEADERBOARD_DATA:
        db.collection("leaderboard").document(entry["operator_name"].replace(" ", "_")).set(entry)
        print(f"  ✓ {entry['operator_name']} — {entry['total_spills']} derrames")

    print("\n✓ Demo data seeded successfully.")


if __name__ == "__main__":
    seed()
