"""
Geographic and impact-estimation utilities vendored from the production project.

Source: backend/scripts/download_real_data.py (originally vendored from ml_lab)

These functions are intentionally duplicated here (not imported from production)
so the ml_lab is fully self-contained. After lab validation, promote.py copies
the final artifacts (model + metrics) to production but does not modify the
production utilities — production keeps using its own copy of these.

Lineage of constants:
  - DISTRICT_GEO: 8 Loreto districts with SENAMHI river flow records,
    INEI 2017 census density, RAISG Amazon biodiversity index.
  - FINE_TO_VOLUME: OEFA UIT-based sanction scale (Res. 164-2013-OEFA/CD).
  - estimate_impacts: pattern calibrated against Oxfam "Shadow of Oil" (2019).
"""
from __future__ import annotations


DISTRICT_GEO = {
    "TROMPETEROS": {"river": "corrientes", "flow": 350,  "density": 2.1, "bio": 0.87, "dist": 12.0},
    "URARINAS":    {"river": "marañon",    "flow": 9000, "density": 3.2, "bio": 0.89, "dist": 8.0},
    "ANDOAS":      {"river": "pastaza",    "flow": 750,  "density": 1.9, "bio": 0.86, "dist": 20.0},
    "MORONA":      {"river": "morona",     "flow": 650,  "density": 1.7, "bio": 0.88, "dist": 18.0},
    "TIGRE":       {"river": "tigre",      "flow": 280,  "density": 2.0, "bio": 0.87, "dist": 15.0},
    "PARINARI":    {"river": "marañon",    "flow": 9000, "density": 4.1, "bio": 0.85, "dist": 10.0},
    "NAUTA":       {"river": "marañon",    "flow": 9000, "density": 7.2, "bio": 0.83, "dist": 22.0},
    "LORETO":      {"river": "marañon",    "flow": 9000, "density": 5.0, "bio": 0.84, "dist": 14.0},
    "DEFAULT":     {"river": "marañon",    "flow": 1200, "density": 4.5, "bio": 0.82, "dist": 15.0},
}

FINE_TO_VOLUME = [
    (5,   150),
    (15,  400),
    (30,  800),
    (60,  1500),
    (100, 2500),
    (200, 5000),
]


def estimate_volume(fine_uits: float) -> float:
    for threshold, volume in FINE_TO_VOLUME:
        if fine_uits <= threshold:
            return float(volume)
    return 5000.0


def get_season(month: int) -> str:
    return "wet" if month in {1, 2, 3, 4, 5, 11, 12} else "dry"


def estimate_impacts(
    c_type: str, volume: float, flow: float, distance: float, density: float
) -> dict:
    """
    Estimate impact metrics from incident features.
    Pattern calibrated against Oxfam 'Shadow of Oil' (2019) documented spill impacts.

    Inputs:
      c_type: 'hydrocarbon' | 'turbidity' | 'algal_bloom'
      volume: barrels spilled (estimated)
      flow: river flow m3/s
      distance: km from spill point to nearest community
      density: population density per km2

    Returns a dict with 4 impact targets used as labels for the XGBoost model.
    """
    # Contamination reach is bounded — even a huge spill doesn't extend infinitely.
    contamination_reach_km = min(volume / 8.0, 250.0)

    # Distance attenuates effective reach: closer communities feel more
    effective_reach = max(contamination_reach_km - distance * 0.5, 1.0)

    # Flow dilutes — high-flow rivers spread contamination but at lower concentration
    flow_factor = 1.0 / (1.0 + flow / 5000.0)

    people_7d = max(10, int(density * effective_reach * 1.6 * flow_factor))
    people_30d = max(30, int(people_7d * 3.1))

    fish_base = {"hydrocarbon": 75.0, "turbidity": 20.0, "algal_bloom": 48.0}[c_type]
    fish_dieoff = min(fish_base * min(volume / 800.0 + 0.5, 1.5), 97.0)

    recovery_base = {"hydrocarbon": 160, "turbidity": 40, "algal_bloom": 85}[c_type]
    recovery_days = min(int(recovery_base * (0.5 + volume / 2500.0)), 365)

    return {
        "people_affected_7d": people_7d,
        "people_affected_30d": people_30d,
        "fish_dieoff_pct": round(fish_dieoff, 1),
        "recovery_days": recovery_days,
    }


def nearest_district(lon: float, lat: float) -> str:
    """
    Map a bbox centroid to the nearest known Loreto district.

    Districts are approximated as point centroids (lon, lat). Returns the
    DISTRICT_GEO key for the closest district by Euclidean distance in degrees
    (good enough at this latitude band).

    Source: approximate centroids derived from INEI district shapefiles.
    """
    centroids = {
        "TROMPETEROS": (-75.05, -3.80),
        "URARINAS":    (-75.55, -4.55),
        "ANDOAS":      (-76.45, -2.90),
        "MORONA":      (-77.10, -4.10),
        "TIGRE":       (-74.70, -3.50),
        "PARINARI":    (-74.30, -4.60),
        "NAUTA":       (-73.58, -4.50),
        "LORETO":      (-73.95, -3.75),
    }
    best_name = "DEFAULT"
    best_dist = float("inf")
    for name, (clon, clat) in centroids.items():
        d = (lon - clon) ** 2 + (lat - clat) ** 2
        if d < best_dist:
            best_dist = d
            best_name = name
    return best_name
