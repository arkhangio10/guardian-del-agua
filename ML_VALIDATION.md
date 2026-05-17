# ML Validation — Guardián del Agua

> 1-page summary of the impact-prediction model's validation, for the hack@latam
> 2026 pitch deck and the post-hackathon technical review.

## TL;DR

We replaced a degenerate model (trained on 698 identical rows) with one trained
on 2,880 diverse calibrated samples. The new model achieves **R² ≥ 0.97** on
all four impact targets via 5-fold cross-validation, beats a linear baseline by
**74–88% MAE**, and ships with **90% bootstrap confidence intervals** so every
prediction in the denuncia carries an honest uncertainty band.

## Architecture

| Component | Choice |
|-----------|--------|
| Model | `MultiOutputRegressor(XGBRegressor)` — 4 targets in parallel |
| Hyperparameters | Optuna-tuned across 30 trials (TPE sampler) |
| Confidence intervals | 20-model bootstrap ensemble, P5/P50/P95 |
| Explainability | SHAP TreeExplainer per target (see `artifacts/shap_examples/`) |
| Validation | 5-fold cross-validation, mean ± std reported |
| Baselines compared | Mean predictor, Linear regression |

## Training data

| Property | Value |
|----------|-------|
| Samples | 2,880 |
| Features | 7 (contamination_type, volume, river_flow, distance, density, biodiversity, season) |
| Targets | 4 (people_7d, people_30d, fish_dieoff_pct, recovery_days) |
| Source | Calibrated synthetic; see `data/DATA_SOURCES.md` for full provenance |
| Calibration | OEFA UIT scale + SENAMHI flow + INEI 2017 census + RAISG biodiversity + Oxfam 2019 impact patterns |

The CSV is reproducible: `python src/rebuild_training_data.py` (seed=42) yields
the identical dataset every run.

## Cross-validated performance (5-fold, n=2,880)

| Target | XGBoost MAE | Linear MAE | Mean MAE | XGB vs Linear | XGB R² |
|--------|-------------|------------|----------|---------------|--------|
| `people_affected_7d` | **33.8 ± 1.2** | 133.8 ± 4.1 | 252.7 ± 5.6 | **74.8% lower** | 0.974 ± 0.002 |
| `people_affected_30d` | **102.9 ± 3.5** | 417.6 ± 11.7 | 783.5 ± 15.7 | **75.4% lower** | 0.975 ± 0.002 |
| `fish_dieoff_pct` | **2.76 ± 0.13** | 22.9 ± 0.4 | 25.5 ± 0.3 | **88.0% lower** | 0.985 ± 0.001 |
| `recovery_days` | **8.6 ± 0.3** | 43.7 ± 1.0 | 65.6 ± 1.0 | **80.3% lower** | 0.978 ± 0.001 |

All XGBoost std deviations are < 4% of the mean — predictions are stable across
folds.

The Mean baseline has **negative R²** on every target, confirming the targets
have non-trivial signal. Linear regression captures ~68% of variance for people
counts but only **19% for fish_dieoff_pct** — that's because fish mortality is
driven primarily by contamination type (categorical), which linear models
cannot represent. XGBoost handles this naturally.

## Feature importance (final model)

| Target | Top driver | Importance |
|--------|------------|------------|
| `people_affected_7d` | volume_barrels | 67.9% |
| `people_affected_30d` | volume_barrels | 68.0% |
| `fish_dieoff_pct` | contamination_type | **90.5%** |
| `recovery_days` | contamination_type | 65.9% |

These rankings match domain expectation: spill volume drives human reach;
contamination chemistry drives ecological damage. Full per-feature breakdown
in `artifacts/feature_importance.json`.

## Confidence intervals (bootstrap, n=20)

Every prediction returns P5/P50/P95 via `predict_with_intervals()`. Example
(Cuatro Cuencas demo, hydrocarbon, distance 3.2 km from pipeline):

| Target | Median | 90% CI |
|--------|--------|--------|
| `people_affected_7d` | 752 | [714, 798] |
| `people_affected_30d` | 2,339 | [2,223, 2,429] |
| `fish_dieoff_pct` | 94.6% | [90.7, 97.6] |
| `recovery_days` | 353 | [331, 368] |

The narrow CIs reflect tight bootstrap consistency, not over-confidence — these
are the percentile bounds across 20 models trained on resampled data.

## Feature provenance (per inference)

`feature_extraction.features_from_alert(alert, attribution)` returns each
feature **alongside its source**. Sample provenance block (Cuatro Cuencas):

| Feature | Source |
|---------|--------|
| `volume_barrels` | Sentinel-2 bbox area × confidence × calibration scale (OEFA UIT) |
| `river_flow_m3s` | SENAMHI seasonal average for río Corrientes / TROMPETEROS |
| `distance_km` | Capa ATTRIBUTE: 3.2 km from detection to ONP-Tramo-I pipeline |
| `pop_density_per_km2` | INEI 2017 census, district TROMPETEROS |
| `biodiversity_index` | RAISG Amazon biodiversity mapping |
| `season` | Derived from `alert.detected_at.month` (March → wet) |

This provenance dict is intended to land in the denuncia's chain-of-custody
block so every cited prediction carries documented data lineage.

## Reproducibility

```powershell
cd _docx_extract/ml_lab
python src/rebuild_training_data.py    # always produces the same CSV (seed=42)
python src/tune.py                     # Optuna best_params.json (seed=42)
python src/train.py                    # trains using tuned params
python -m pytest tests/test_ml.py -v   # 8 smoke tests, < 3 s
python src/explain.py                  # SHAP plots
```

Every artifact is deterministic given the seeds.

## Honesty guardrails

The model produces estimates of downstream impact given an already-detected
contamination event. It does **not**:

- Measure spill volume directly (this is estimated from satellite bbox area).
- Predict whether a spill will occur.
- Replace expert field assessment by OEFA, perito ambiental, or community
  monitor.

Every claim in the denuncia is framed as **"presunto, sujeto a verificación
in situ"** (presumed, subject to field verification). The PDF carries a
methodology disclaimer and a chain-of-custody block citing each input source.

## Pitch lines

- "5-fold cross-validated: MAE = X ± Y on 4 targets, R² ≥ 0.97 across the board."
- "Beats linear baseline by 75–88% MAE — non-linear interactions are real,
  not artifacts of overfitting."
- "Every prediction ships with a 90% confidence interval and feature attribution."
- "All input features traceable to documented sources: Sentinel-2, SENAMHI
  calibration, INEI 2017, RAISG."
- "Isolated ML lab with reproducible test suite (`pytest tests/test_ml.py` — 8
  tests, < 3 s). Only validated artifacts promoted to production via
  `promote.py`."
