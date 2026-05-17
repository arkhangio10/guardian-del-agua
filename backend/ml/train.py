"""
ML Lab — train.py

Tier 1.2 + Tier 2.1-2.4 in one orchestrator.

Steps:
  1. Load CSV, encode categoricals
  2. Train final XGBoost MultiOutputRegressor on the full dataset
  3. Sanity check: model responds to inputs
  4. K-fold cross-validation (5 folds) reporting MAE and R^2, mean +- std
  5. Feature importance per target
  6. Bootstrap ensemble (n=20) for confidence intervals at inference
  7. Baseline comparison vs Mean and Linear regressors
  8. Persist:
     - artifacts/impact_model.pkl
     - artifacts/impact_model_bootstrap.pkl
     - artifacts/metrics.json
     - artifacts/feature_importance.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.dummy import DummyRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import KFold
from sklearn.multioutput import MultiOutputRegressor
from xgboost import XGBRegressor

# Make src importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

LAB_ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = LAB_ROOT / "data" / "loreto_historical.csv"
ARTIFACTS = LAB_ROOT / "artifacts"
MODEL_PATH = ARTIFACTS / "impact_model.pkl"
BOOTSTRAP_PATH = ARTIFACTS / "impact_model_bootstrap.pkl"
METRICS_PATH = ARTIFACTS / "metrics.json"
IMPORTANCE_PATH = ARTIFACTS / "feature_importance.json"
BEST_PARAMS_PATH = ARTIFACTS / "best_params.json"

CONTAMINATION_ENCODING = {"hydrocarbon": 0, "turbidity": 1, "algal_bloom": 2}
SEASON_ENCODING = {"dry": 0, "wet": 1}

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

# Hyperparameters — shared by all model factories so CV results are comparable.
# If artifacts/best_params.json exists (produced by Optuna via `python src/tune.py`),
# those tuned hyperparameters override these defaults at import time.
XGB_PARAMS = {
    "n_estimators": 200,
    "max_depth": 4,
    "learning_rate": 0.05,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "random_state": 42,
    "verbosity": 0,
    "n_jobs": 1,
}


def _load_tuned_params() -> dict | None:
    """Return Optuna-tuned XGBoost params from best_params.json, or None if absent."""
    import json
    if not BEST_PARAMS_PATH.exists():
        return None
    try:
        payload = json.loads(BEST_PARAMS_PATH.read_text())
        return payload.get("best_params")
    except Exception:
        return None


_tuned = _load_tuned_params()
if _tuned:
    XGB_PARAMS = {**XGB_PARAMS, **_tuned}
    print(f"[INFO] Using Optuna-tuned hyperparameters from {BEST_PARAMS_PATH.name}")

RANDOM_SEED = 42
N_BOOTSTRAP = 20
N_FOLDS = 5


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_and_prepare(path: Path) -> tuple[np.ndarray, np.ndarray, pd.DataFrame]:
    """Load the CSV and return X, y, and the full DataFrame for diagnostics."""
    df = pd.read_csv(path)
    df["contamination_type_enc"] = df["contamination_type"].map(CONTAMINATION_ENCODING).fillna(0)
    df["season_enc"] = df["season"].map(SEASON_ENCODING).fillna(1)
    X = df[FEATURES].values
    y = df[TARGETS].values
    return X, y, df


# ---------------------------------------------------------------------------
# Model factories
# ---------------------------------------------------------------------------

def make_xgb() -> MultiOutputRegressor:
    return MultiOutputRegressor(XGBRegressor(**XGB_PARAMS))


def make_linear() -> MultiOutputRegressor:
    return MultiOutputRegressor(LinearRegression())


def make_mean() -> MultiOutputRegressor:
    return MultiOutputRegressor(DummyRegressor(strategy="mean"))


# ---------------------------------------------------------------------------
# Tier 1.2 — Sanity check
# ---------------------------------------------------------------------------

def sanity_check_responds(model) -> tuple[np.ndarray, np.ndarray, float]:
    """
    Assert the model produces meaningfully different outputs for contrasting inputs.

    Returns (low_pred, high_pred, sum_abs_diff) so the caller can print the values.
    Raises AssertionError if the model is degenerate.
    """
    # Low-impact: turbidity, small spill, far away, low density, dry season
    low = np.array([[1, 200, 2000, 25, 2, 0.78, 0]])
    # High-impact: hydrocarbon, big spill, close, dense pop, wet season
    high = np.array([[0, 4500, 500, 5, 7, 0.88, 1]])

    p_low = model.predict(low)[0]
    p_high = model.predict(high)[0]
    diff = float(np.abs(p_low - p_high).sum())

    assert diff > 50, (
        f"Model is degenerate: low={p_low.round(1)} vs high={p_high.round(1)} (diff={diff:.1f}). "
        "Did you fix the CSV?"
    )
    return p_low, p_high, diff


# ---------------------------------------------------------------------------
# Tier 2.1 — Cross-validation
# ---------------------------------------------------------------------------

def cross_validate(model_factory, X: np.ndarray, y: np.ndarray, label: str) -> dict:
    """Run K-fold CV with one model_factory, return per-target MAE/R^2 stats."""
    kf = KFold(n_splits=N_FOLDS, shuffle=True, random_state=RANDOM_SEED)
    fold_maes: list[list[float]] = [[] for _ in TARGETS]
    fold_r2s: list[list[float]] = [[] for _ in TARGETS]

    for fold_idx, (tr_idx, te_idx) in enumerate(kf.split(X)):
        model = model_factory()
        model.fit(X[tr_idx], y[tr_idx])
        preds = model.predict(X[te_idx])
        for i in range(len(TARGETS)):
            fold_maes[i].append(mean_absolute_error(y[te_idx, i], preds[:, i]))
            fold_r2s[i].append(r2_score(y[te_idx, i], preds[:, i]))

    result = {"model": label, "folds": N_FOLDS, "per_target": {}}
    print(f"\n[CV] {label} ({N_FOLDS}-fold)")
    for i, target in enumerate(TARGETS):
        mae_arr = np.array(fold_maes[i])
        r2_arr = np.array(fold_r2s[i])
        result["per_target"][target] = {
            "mae_mean": float(mae_arr.mean()),
            "mae_std": float(mae_arr.std()),
            "r2_mean": float(r2_arr.mean()),
            "r2_std": float(r2_arr.std()),
        }
        print(
            f"  {target:25s}  MAE = {mae_arr.mean():8.2f} +/- {mae_arr.std():6.2f}   "
            f"R^2 = {r2_arr.mean():6.3f} +/- {r2_arr.std():5.3f}"
        )
    return result


# ---------------------------------------------------------------------------
# Tier 2.2 — Feature importance
# ---------------------------------------------------------------------------

def feature_importance_report(model: MultiOutputRegressor) -> dict:
    """Extract per-target feature importances from a trained MultiOutputRegressor."""
    report = {"features": FEATURES, "targets": TARGETS, "importance_by_target": {}}
    for target_name, est in zip(TARGETS, model.estimators_):
        importances = est.feature_importances_
        ranked = sorted(
            zip(FEATURES, importances.tolist()),
            key=lambda kv: kv[1],
            reverse=True,
        )
        report["importance_by_target"][target_name] = [
            {"feature": f, "importance": float(imp)} for f, imp in ranked
        ]
        print(f"\n[IMPORTANCE] {target_name}")
        for f, imp in ranked:
            bar = "#" * int(imp * 40)
            print(f"  {f:30s} {imp:.4f}  {bar}")
    return report


# ---------------------------------------------------------------------------
# Tier 2.3 — Bootstrap ensemble
# ---------------------------------------------------------------------------

def train_bootstrap_ensemble(X: np.ndarray, y: np.ndarray, n: int = N_BOOTSTRAP) -> list:
    """Fit n XGBoost models on bootstrap resamples for confidence intervals."""
    rng = np.random.default_rng(RANDOM_SEED)
    models = []
    n_rows = len(X)
    print(f"\n[BOOTSTRAP] Training {n} bootstrap models...")
    for i in range(n):
        idx = rng.integers(0, n_rows, n_rows)
        m = make_xgb()
        m.fit(X[idx], y[idx])
        models.append(m)
        if (i + 1) % 5 == 0:
            print(f"  fitted {i + 1}/{n}")
    return models


# ---------------------------------------------------------------------------
# Main orchestration
# ---------------------------------------------------------------------------

def main() -> None:
    print(f"[INFO] Loading {DATA_PATH.name}...")
    X, y, df = load_and_prepare(DATA_PATH)
    print(f"[INFO] {len(X)} samples, {X.shape[1]} features, {y.shape[1]} targets")

    ARTIFACTS.mkdir(parents=True, exist_ok=True)

    # --- Train final model on full data ---
    print("\n[INFO] Training final XGBoost MultiOutputRegressor on full dataset...")
    final_model = make_xgb()
    final_model.fit(X, y)

    # --- Sanity check (T1.2) ---
    p_low, p_high, diff = sanity_check_responds(final_model)
    print(f"\n[OK] Sanity: low={p_low.round(1).tolist()}  high={p_high.round(1).tolist()}  diff={diff:.1f}")

    joblib.dump(final_model, MODEL_PATH)
    print(f"[OK] Saved final model to {MODEL_PATH}")

    # --- Cross-validation (T2.1) ---
    metrics: dict = {
        "n_samples": int(len(X)),
        "n_features": int(X.shape[1]),
        "n_targets": int(y.shape[1]),
        "n_folds": N_FOLDS,
        "n_bootstrap": N_BOOTSTRAP,
        "random_seed": RANDOM_SEED,
        "xgb_params": XGB_PARAMS,
        "cv": {},
        "baseline_comparison": {},
    }

    metrics["cv"]["xgboost"] = cross_validate(make_xgb, X, y, "XGBoost")

    # --- Baselines (T2.4) ---
    print("\n[INFO] Computing baseline comparison...")
    metrics["baseline_comparison"]["mean"] = cross_validate(make_mean, X, y, "Mean baseline")
    metrics["baseline_comparison"]["linear"] = cross_validate(make_linear, X, y, "Linear baseline")

    # --- Improvement table ---
    print("\n[COMPARISON] Mean per-target MAE across CV folds")
    print(f"  {'target':25s}  {'XGBoost':>10s}  {'Linear':>10s}  {'Mean':>10s}  {'XGB vs Lin':>12s}")
    for target in TARGETS:
        xgb_mae = metrics["cv"]["xgboost"]["per_target"][target]["mae_mean"]
        lin_mae = metrics["baseline_comparison"]["linear"]["per_target"][target]["mae_mean"]
        mean_mae = metrics["baseline_comparison"]["mean"]["per_target"][target]["mae_mean"]
        improvement = (lin_mae - xgb_mae) / lin_mae * 100 if lin_mae > 0 else 0
        print(
            f"  {target:25s}  {xgb_mae:10.2f}  {lin_mae:10.2f}  {mean_mae:10.2f}  "
            f"{improvement:>11.1f}%"
        )

    # --- Feature importance (T2.2) ---
    importance = feature_importance_report(final_model)
    IMPORTANCE_PATH.write_text(json.dumps(importance, indent=2))
    print(f"\n[OK] Saved feature importance to {IMPORTANCE_PATH.name}")

    # --- Bootstrap ensemble (T2.3) ---
    bootstrap_models = train_bootstrap_ensemble(X, y, n=N_BOOTSTRAP)
    joblib.dump(bootstrap_models, BOOTSTRAP_PATH)
    print(f"[OK] Saved {N_BOOTSTRAP} bootstrap models to {BOOTSTRAP_PATH.name}")

    # --- Persist all metrics ---
    METRICS_PATH.write_text(json.dumps(metrics, indent=2))
    print(f"[OK] Saved metrics to {METRICS_PATH.name}")

    print("\n[DONE] Training complete. Artifacts:")
    for p in sorted(ARTIFACTS.iterdir()):
        size_kb = p.stat().st_size / 1024
        print(f"  {p.name:35s}  {size_kb:>10.1f} KB")


if __name__ == "__main__":
    main()
