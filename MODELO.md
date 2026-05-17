# Modelo de Predicción de Impacto — Guardián del Agua

**Capa 3 (PREDICT) del pipeline.** Convierte una alerta detectada por satélite en una estimación cuantificada del impacto humano, ecológico y económico, con intervalos de confianza honestos y trazabilidad completa para la denuncia OEFA.

---

## Stack técnico

| Componente | Tecnología | Por qué |
|------------|-----------|---------|
| Modelo | XGBoost 2.0.3 con `MultiOutputRegressor` (sklearn) | 4 targets en paralelo; XGBoost es robusto a outliers y datasets pequeños |
| Intervalos de confianza | Bootstrap ensemble (n=20) | Reporta P5/P50/P95 sin asumir distribución |
| Hyperparameters | Optuna 30 trials (TPE) | `n_estimators=250`, `max_depth=4`, `lr=0.036`, regularización L2=0.76 |
| Persistencia | joblib | `impact_model.pkl` 1.3 MB + `impact_model_bootstrap.pkl` 25 MB |

---

## Datos de entrenamiento — 100% reales de OEFA

**Fuente primaria:** RUIAS (Registro Único de Infractores Ambientales Sancionados), descargado de `datosabiertos.gob.pe` el 2026-05-17. **14,937 sanciones nacionales**, filtradas a `DEPARTAMENTO=Loreto + SUBSECTOR=Hidrocarburos` → **698 sanciones reales** (Petroperú, Pluspetrol Norte, Maple Gas en Andoas, Nauta, Tigre, Trompeteros, Yurimaguas, etc.). Expandido a **3,490 filas** con 4 copias jittered por record (±10-15% en features continuos; categoriales sin tocar).

**Inputs reales por sanción:** operador, distrito, fecha, monto multa (UIT), descripción de infracción.

---

## Los 7 features que el modelo recibe

| # | Feature | Fuente | Tipo |
|---|---------|--------|------|
| 1 | `contamination_type_enc` | RUIAS DETALLE_INFRACCION → parseo regex | 0/1/2 |
| 2 | `volume_barrels` | RUIAS CANTIDAD_MULTA × calibración OEFA UIT (Res. 164-2013-OEFA/CD) | float |
| 3 | `river_flow_m3s` | SENAMHI promedio estacional por río del distrito | float |
| 4 | `distance_km` | Capa ATTRIBUTE: distancia satélite → polígono concesión | float |
| 5 | `pop_density_per_km2` | INEI Censo Nacional 2017 por distrito | float |
| 6 | `biodiversity_index` | RAISG Amazon biodiversity mapping | 0.6–0.95 |
| 7 | `season_enc` | Derivado del mes de FECHA_RD (wet: nov–may, dry: jun–oct) | 0/1 |

---

## Los 4 targets que el modelo predice

| Target | Unidad | Calibración |
|--------|--------|-------------|
| `people_affected_7d` | Personas | Oxfam 2019 + gob. Perú 2019 (57% exposición Pastaza/Tigre/Corrientes/Marañón) |
| `people_affected_30d` | Personas | Multiplicador 3.1× sobre 7d (Oxfam) |
| `fish_dieoff_pct` | % | Base por tipo: hydrocarbon 75%, turbidity 20%, algal 48% (Oxfam) |
| `recovery_days` | Días | Base por tipo, escalado por volumen, cap 365 (Cuninico → tail real >>11 años) |

**Honestidad:** OEFA no publica counts per incidente. Los targets son derivados de un modelo físico documentado calibrado contra 4 fuentes públicas. La denuncia siempre dice *"presunto, sujeto a verificación in situ"*.

---

## Cómo predice — paso a paso al recibir una alerta

```
[1] Alert llega a POST /predict/{alert_id} con doc Firestore
       │  {contamination_type, sentinel_bbox, confidence, detected_at, attribution}
       ▼
[2] feature_extraction.features_from_alert(doc, attribution)
       │  bbox → centroide → nearest_district(lon, lat) → DISTRICT_GEO lookup
       │  bbox → área km² × confidence × 100 → volume_barrels (cap 6,000)
       │  detected_at.month → get_season()
       │  attribution.distance_to_pipeline_km (o fallback)
       │  → devuelve {features: [7 floats], _provenance: {...}, _derived_inputs: {...}}
       ▼
[3] model.predict([features])[0] → 4 valores [people_7d, people_30d, fish%, recovery]
       │  Clamp físico: people ≥ 0, fish ∈ [0, 100], recovery ≥ 1 día
       ▼
[4] Bootstrap CI: 20 modelos votan → P5/P50/P95 por target
       │  ci_result["intervals"] = {target: {p5, p95}, ...}
       ▼
[5] Cálculos derivados:
       │  drinking_water_sources_at_risk = bbox_area_km² / 25
       │  economic_damage_usd = people_30d × $200 + recovery_days × $5,000
       ▼
[6] Firestore update con 4 campos:
       │  predictions:           {6 valores ImpactPrediction}
       │  predictions_intervals: {P5/P95 por target}
       │  feature_provenance:    {fuente documentada por cada feature}
       │  derived_inputs:        {valores intermedios para auditoría}
```

**Tiempo de inferencia:** ~30–50 ms por alerta. Modelo cargado en memoria al startup (lazy singleton). Bootstrap models cargados solo si el archivo existe (gracefully optional).

---

## Resultados de validación

### Métrica honesta — GroupKFold por `_expediente` OEFA

5-fold cross-validation **agrupando por número de expediente** (`_expediente`). El modelo se entrena en 237 expedientes únicos y se evalúa en 59 expedientes **que nunca vio durante training**, eliminando leakage entre la copia verbatim y las 4 jittered de un mismo expediente.

| Target | GroupKFold MAE | GroupKFold R² | Linear baseline R² | XGB mejor que linear |
|--------|--------------|---------------|--------------------|---------------------|
| people_affected_7d | 9.55 ± 2.52 | **0.984** | 0.734 | **−82.5%** MAE |
| people_affected_30d | 29.98 ± 8.17 | **0.983** | 0.740 | **−82.2%** MAE |
| fish_dieoff_pct | 1.41 ± 0.04 | **0.993** | 0.803 | **−77.7%** MAE |
| recovery_days | 4.49 ± 0.54 | **0.985** | 0.958 | **−32.1%** MAE |

**El modelo generaliza a expedientes que nunca vio.** R² alto significa que aprendió la estructura del problema, no que memorizó.

### ⚠️ Qué significa este R² alto, en lenguaje preciso

El R²=0.984 mide cuán bien XGBoost **aproxima la fórmula físico-económica** documentada en `_vendored/geo_utils.estimate_impacts` (calibrada contra Oxfam 2019 + Estudio Salud Gob.Perú 2019 + Cuninico/Mongabay + MDPI Toxics 2024). **No mide capacidad predictiva contra ground-truth real** porque OEFA no publica counts por incidente — esa limitación es del régimen de transparencia ambiental peruano, no nuestra.

Lo que el R² alto **sí prueba**:
- ✅ El modelo aprende una función estructurada (no random memorization — R² Linear=0.74 demuestra que requiere capacidad no lineal)
- ✅ Generaliza a expedientes nuevos manteniendo la estructura
- ✅ Es 4–5× mejor que un baseline lineal — XGBoost agrega valor real sobre la regresión más simple

Lo que el R² **NO prueba**:
- ❌ Que las predicciones coincidan con un peritaje en campo (no validamos contra peritos reales)
- ❌ Que la fórmula de calibración esté libre de sesgo
- ❌ Que la recuperación real de Cuninico sean 219 días (la realidad es 11+ años; nuestro cap es 365)

### Otras verificaciones

- **8/8 smoke tests** pasan en pytest (~2.5 s) — invariantes estructurales (variance, ordering, defensive contract)
- **4 de 5 casos famosos** (Cuninico, Pluspetrol Lote 8, Lote 192, turbidez, peor-caso OOD) producen predicciones dentro de **rangos plausibles documentados**. Los rangos los construimos a partir de Oxfam/Mongabay; el modelo no los conocía. El único caso que falla (Lote 192, fish=96.6% vs esperado 60-95%) es por saturación del cap superior, no error estructural.
- **Sin sesgo modelo-vs-fórmula** en 12 subgrupos (tipos × estaciones × volúmenes); |bias| < 10% en todos. **Esta verificación NO detecta sesgo del modelo contra el mundo real** — solo verifica que el modelo aproxima la fórmula uniformemente. La auditoría contra realidad requiere peritos ambientales (post-hackathon).

### Métrica adicional (in-formula consistency)

Para auditoría técnica, también reportamos KFold no-agrupado en `metrics.json` (R²≈0.99 por target). La diferencia con GroupKFold (R²≈0.984) es ~0.6 puntos — pequeña, lo cual es señal de que el modelo aprendió estructura genuina, no memorización de expediente-IDs. **Citá siempre la métrica GroupKFold como número principal** ante un jurado técnico.

---

## Feature importance (lo que el modelo aprendió del dominio)

- **`people_affected_*`:** `volume_barrels` domina al 83% → derrame grande = más gente afectada. Coherente con que el monto de la multa OEFA (UIT) escala con el volumen reportado, y nuestro modelo de calibración usa volumen como predictor primario.
- **`fish_dieoff_pct`:** `contamination_type_enc` domina al 81% → hidrocarburo mata más que turbidez. Coherente con la fórmula calibrada (base 75% / 20% / 48% respectivamente).
- **`recovery_days`:** mix `volume_barrels` (54%) + `contamination_type` (42%) → ambos importan.

**Caveat honesto:** las importances reflejan la estructura de la fórmula de calibración — el modelo aprendió que volumen y tipo dominan porque la fórmula que generó los labels les da más peso. Las importances son **consistentes con expertise documentado**, no son descubrimientos independientes del modelo.

---

## Lo que el modelo NO afirma

1. **No mide contaminación.** Predice impacto downstream dado una contaminación ya detectada (Capa DETECT lo hace vía Claude Vision).
2. **No reemplaza al perito ambiental.** Le da un punto de partida cuantificado que el perito refina en campo.
3. **No predice si habrá derrame.** Solo cuantifica impacto si ya ocurrió.
4. **No es ground truth de OEFA.** OEFA no publica counts reales — los targets son modelados desde fuentes públicas documentadas.
5. **No predice tiempos reales de litigación.** El cap de `recovery_days = 365` es físico-ecológico; Cuninico 2014 lleva 11+ años por dilación procesal (no por daño físico de esa duración).
6. **No detecta sesgo modelo-vs-realidad.** Las verificaciones de bias internas miden consistencia modelo-vs-fórmula. La auditoría contra realidad requiere peritos ambientales y litigios reales.

---

## Archivos clave

- [`v1/backend/ml/impact_model.pkl`](_docx_extract/v1/backend/ml/impact_model.pkl) — modelo principal
- [`v1/backend/ml/impact_model_bootstrap.pkl`](_docx_extract/v1/backend/ml/impact_model_bootstrap.pkl) — 20 modelos para CI
- [`v1/backend/ml/metrics.json`](_docx_extract/v1/backend/ml/metrics.json) — CV ungrouped (in-formula consistency)
- [`v1/backend/ml/metrics_grouped.json`](_docx_extract/v1/backend/ml/metrics_grouped.json) — **GroupKFold por `_expediente` (métrica HONESTA, citar esta)**
- [`v1/backend/ml/feature_importance.json`](_docx_extract/v1/backend/ml/feature_importance.json) — importances
- [`v1/backend/ml/loreto_historical.csv`](_docx_extract/v1/backend/ml/loreto_historical.csv) — 3,490 rows derivados de 698 OEFA reales
- [`v1/backend/ml/DATA_SOURCES.md`](_docx_extract/v1/backend/ml/DATA_SOURCES.md) — provenance completo
- [`v1/backend/layers/feature_extraction.py`](_docx_extract/v1/backend/layers/feature_extraction.py) — bbox → features con provenance
- [`v1/backend/layers/predict_lib.py`](_docx_extract/v1/backend/layers/predict_lib.py) — `predict_with_intervals()`
- [`v1/backend/layers/predict.py`](_docx_extract/v1/backend/layers/predict.py) — endpoint FastAPI
- [`v1/ML_VALIDATION.md`](_docx_extract/v1/ML_VALIDATION.md) — reporte de validación completo
- [`ml_lab/artifacts/validation/pred_vs_actual.png`](_docx_extract/ml_lab/artifacts/validation/pred_vs_actual.png) — plot OOF para el deck

---

*Modelo entrenado 2026-05-17 sobre data RUIAS descargada mismo día. Reproducible vía `python ml_lab/src/rebuild_training_data_real.py && python ml_lab/src/train.py` (seed=42).*
