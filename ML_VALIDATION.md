# ML Validation — Guardián del Agua

> 1-page summary of the impact-prediction model's validation, for the hack@latam
> 2026 pitch deck and the post-hackathon technical review.

## TL;DR

Replaced a degenerate model (trained on 698 identical rows) with one trained on
3,490 diverse rows derived from 698 real OEFA RUIAS sanctions (296 unique
expedientes) in Loreto/Hidrocarburos. The new model achieves **R² ≥ 0.983** on
all four impact targets via **GroupKFold cross-validation by `_expediente`**
(i.e., the model is tested on expedientes it never saw during training,
eliminating leakage between jittered copies of the same record). Beats a linear
baseline by **32–82% MAE**, and ships with 90% bootstrap confidence intervals.

**The R² alto NO mide capacidad predictiva contra ground-truth real** — OEFA no
publica counts por incidente. Mide cuán bien XGBoost aproxima nuestra fórmula
físico-económica calibrada (Oxfam 2019 + Estudio Salud Gob.Perú 2019 +
Cuninico/Mongabay + MDPI Toxics 2024). Ver sección "Honesty guardrails" abajo.

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
| Samples | 3,490 (1 verbatim + 4 jittered copies per real RUIAS record) |
| Real expedientes | 698 records → 296 unique `_expediente` values |
| Features | 7 (contamination_type, volume, river_flow, distance, density, biodiversity, season) |
| Targets | 4 (people_7d, people_30d, fish_dieoff_pct, recovery_days) |
| Source inputs | 100% real OEFA RUIAS (`datosabiertos.gob.pe`, descargado 2026-05-17) |
| Source labels | Modelados via `geo_utils.estimate_impacts` (formula); OEFA no publica counts |
| Calibration | OEFA UIT scale + SENAMHI flow + INEI 2017 census + RAISG biodiversity + Oxfam 2019 impact patterns + Estudio Salud Gob.Perú 2019 + Cuninico/Mongabay + MDPI Toxics 2024 |

CSV reproducible: `python src/rebuild_training_data_real.py` (seed=42).

## Cross-validated performance — HONEST (GroupKFold by `_expediente`)

| Target | XGBoost MAE | Linear MAE | Mean MAE | XGB vs Linear | XGB R² |
|--------|-------------|------------|----------|---------------|--------|
| `people_affected_7d` | **9.55 ± 2.52** | 54.65 ± 6.42 | 138.90 ± 19.69 | **82.5% lower** | 0.984 ± 0.015 |
| `people_affected_30d` | **29.98 ± 8.17** | 168.27 ± 20.79 | 428.39 ± 61.87 | **82.2% lower** | 0.983 ± 0.018 |
| `fish_dieoff_pct` | **1.41 ± 0.04** | 6.31 ± 0.32 | 13.60 ± 1.38 | **77.7% lower** | 0.993 ± 0.001 |
| `recovery_days` | **4.49 ± 0.54** | 6.61 ± 0.89 | 35.33 ± 7.48 | **32.1% lower** | 0.985 ± 0.008 |

**Lectura honesta:** GroupKFold(5) sobre 296 expedientes únicos. Cada fold testea
en ~59 expedientes que el modelo nunca vio en training. R²=0.984 mide cuán bien
XGBoost aproxima la fórmula calibrada a través del espacio de features — no es
"memorización de filas vistas". Compárese con `metrics.json` (KFold ungrouped,
R²=0.99); la diferencia de ~0.6 puntos es evidencia de que el modelo aprendió
estructura, no IDs.

Mean baseline R² ≈ 0 confirma que los targets tienen señal estructurada.
Linear baseline captura ~74-96% de la varianza; XGBoost agrega valor en
interacciones no-lineales especialmente en `fish_dieoff_pct` donde
`contamination_type` (categorial) domina y los modelos lineales no pueden
representarlo.

## Feature importance (final model)

| Target | Top driver | Importance |
|--------|------------|------------|
| `people_affected_7d` | volume_barrels | 82.7% |
| `people_affected_30d` | volume_barrels | 82.9% |
| `fish_dieoff_pct` | contamination_type | **81.4%** |
| `recovery_days` | volume_barrels (54.1%) + contamination_type (41.5%) | mix |

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

## Pitch lines (defendibles ante jurado técnico hostil)

**Líneas seguras:**
- "GroupKFold(5) sobre 296 expedientes únicos: R²=0.984 — el modelo generaliza
  a expedientes que nunca vio en training."
- "Beats linear baseline by 32–82% MAE — confirma que XGBoost agrega valor sobre
  modelos lineales en este espacio de features."
- "Every prediction ships with feature provenance and `presunto, sujeto a
  verificación in situ` legal framing."
- "All input features traceable to documented sources: Sentinel-2, SENAMHI,
  INEI 2017, RAISG, OSINERGMIN. Cited per-feature in the denuncia."
- "Isolated ML lab with reproducible test suite (`pytest tests/test_ml.py` —
  8 tests, < 3 s). Seed=42 in todo el pipeline."

**Líneas que NO uses sin contexto:**
- ❌ "R²=0.99 prueba que el modelo predice impacto real" (cierra el ciclo
  modelo-vs-fórmula, no modelo-vs-realidad)
- ❌ "Validado contra OEFA records reales" (los INPUTS son reales; los OUTPUTS
  son modelados — OEFA no publica counts por incidente)
- ❌ "Sin sesgo por subgrupo" (esa verificación mide consistencia modelo-vs-fórmula,
  no sesgo contra realidad)

**Respuesta a "¿no es R² alto señal de overfit?":**
> "GroupKFold con grouping por expediente da R²=0.984 — el modelo se evalúa en
> expedientes que no estaban en training. Si fuera overfit por leakage, el R²
> habría caído mucho. El R² alto refleja que los labels son una función calibrada
> determinística de los features (Oxfam 2019 + 3 fuentes adicionales), y XGBoost
> es muy bueno aproximando funciones suaves. Mide consistencia con expertise
> documentado, no capacidad predictiva real — esa validación requiere peritos
> ambientales y es trabajo post-hackathon."

**Respuesta a "Cuninico tomó 11 años, tu cap es 365 días":**
> "Correcto — para Cuninico nuestro modelo predice 219 días. La realidad de
> 11+ años incluye dilación procesal, no solo daño físico-ecológico. Modelamos
> impacto ecológico, no tiempos de litigación. Este es el caso documentado
> con mayor brecha en nuestra validation: lo declaramos explícitamente."
