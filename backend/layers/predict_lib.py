"""
Tier 2.3 — Inference utilities, including bootstrap-based confidence intervals.

Pure Python / sklearn / xgboost. No FastAPI, no Firestore. The production layer
(`v1/backend/layers/predict.py`) will import these functions after `promote.py`
runs.

Shape contracts:
  - Single-row inference: features is a list[float] of length 7, or a 1D
    np.ndarray of shape (7,).
  - Batch inference: 2D np.ndarray of shape (n_rows, 7).
"""
from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np

FEATURES = [
    "contamination_type_enc",
    "volume_barrels",
    "river_flow_m3s",
    "distance_km",
    "pop_density_per_km2",
    "biodiversity_index",
    "season_enc",
]
TARGETS = ["people_affected_7d", "people_affected_30d", "fish_dieoff_pct", "recovery_days"]


# ---------------------------------------------------------------------------
# Model loading helpers
# ---------------------------------------------------------------------------

def load_model(path: str | Path):
    """Load a joblib-serialised model (MultiOutputRegressor)."""
    return joblib.load(str(path))


def load_bootstrap_ensemble(path: str | Path) -> list:
    """Load a list of bootstrap-trained models."""
    models = joblib.load(str(path))
    if not isinstance(models, list):
        raise TypeError(
            f"Expected a list of bootstrap models, got {type(models).__name__} "
            f"at {path}. Did training save correctly?"
        )
    return models


# ---------------------------------------------------------------------------
# Single point prediction
# ---------------------------------------------------------------------------

def predict_point(model, features: list[float] | np.ndarray) -> dict:
    """
    Point prediction for a single feature vector.

    Returns a dict keyed by the 4 targets, with the model's central estimate.
    Clamps to physically sensible ranges (no negative people, fish in [0,100],
    recovery >= 1 day).
    """
    X = np.array(features, dtype=float).reshape(1, -1)
    if X.shape[1] != len(FEATURES):
        raise ValueError(
            f"Expected {len(FEATURES)} features, got {X.shape[1]}: features={features}"
        )
    raw = model.predict(X)[0]
    return _clamp_targets(raw)


def _clamp_targets(raw: np.ndarray) -> dict:
    """Apply physical-sense clamps to a (4,) prediction vector."""
    return {
        "people_affected_7d": max(0, int(round(float(raw[0])))),
        "people_affected_30d": max(0, int(round(float(raw[1])))),
        "fish_dieoff_pct": float(np.clip(raw[2], 0.0, 100.0)),
        "recovery_days": max(1, int(round(float(raw[3])))),
    }


# ---------------------------------------------------------------------------
# Bootstrap interval prediction
# ---------------------------------------------------------------------------

def predict_with_intervals(
    models: list,
    features: list[float] | np.ndarray,
    interval_low: float = 5.0,
    interval_high: float = 95.0,
) -> dict:
    """
    Run inference across all bootstrap models, return P5/P50/P95 per target.

    `interval_low=5, interval_high=95` gives a 90% confidence band — wide enough
    to be honest, narrow enough to be useful for legal-document language.

    Returns:
        {
          "predictions": {target: median_value, ...},  # clamped, P50
          "intervals": {target: {"p5": ..., "p95": ...}, ...},
          "n_bootstrap": int,
          "confidence_level": float,  # e.g. 0.90 for 90% CI
        }
    """
    if not models:
        raise ValueError("Bootstrap ensemble is empty.")

    X = np.array(features, dtype=float).reshape(1, -1)
    if X.shape[1] != len(FEATURES):
        raise ValueError(
            f"Expected {len(FEATURES)} features, got {X.shape[1]}: features={features}"
        )

    # Each model contributes one (4,) prediction row.
    preds = np.array([m.predict(X)[0] for m in models])  # (n_bootstrap, 4)

    p_low = np.percentile(preds, interval_low, axis=0)
    p_med = np.percentile(preds, 50.0, axis=0)
    p_high = np.percentile(preds, interval_high, axis=0)

    # Guarantee p_low <= p_med <= p_high after clamping
    p_low = np.minimum(p_low, p_med)
    p_high = np.maximum(p_high, p_med)

    predictions = _clamp_targets(p_med)
    intervals: dict = {}
    for i, target in enumerate(TARGETS):
        low_val = _clamp_single(target, float(p_low[i]))
        high_val = _clamp_single(target, float(p_high[i]))
        intervals[target] = {"p5": low_val, "p95": high_val}

    return {
        "predictions": predictions,
        "intervals": intervals,
        "n_bootstrap": len(models),
        "confidence_level": (interval_high - interval_low) / 100.0,
    }


def _clamp_single(target: str, val: float) -> float | int:
    """Apply the same per-target clamp used in `_clamp_targets`, but value-only."""
    if target == "people_affected_7d" or target == "people_affected_30d":
        return max(0, int(round(val)))
    if target == "fish_dieoff_pct":
        return float(np.clip(val, 0.0, 100.0))
    if target == "recovery_days":
        return max(1, int(round(val)))
    return val
