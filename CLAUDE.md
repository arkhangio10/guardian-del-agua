# CLAUDE.md — Guardián del Agua

## Project layout

```
indie_letam_hack/
├── _docx_extract/
│   ├── venv/          ← Python 3.11 virtual environment (all deps installed)
│   └── v1/            ← ALL project code lives here
│       ├── backend/   ← FastAPI + layers + ML + data
│       ├── frontend/  ← Next.js 14
│       ├── DEPLOY.md
│       └── README.md
```

**Working directory for all backend work:** `_docx_extract/v1/backend/`  
**Python interpreter:** `C:\Users\braya\Desktop\project_personal\indie_letam_hack\_docx_extract\venv\Scripts\python.exe`  
**Activate venv (Windows):** `_docx_extract\venv\Scripts\activate`

## Running the project

```bash
# Backend (from v1/backend/)
uvicorn main:app --reload --port 8000

# Frontend (from v1/frontend/)
npm run dev

# Train ML model (after data changes)
python ml/train.py

# Download real OEFA training data
python scripts/download_real_data.py

# Download real concession polygons
python scripts/download_concessions.py

# Seed Firestore demo data (needs .env with GCP keys)
python seed_demo.py
```

## Backend architecture

5-layer pipeline in `layers/`:

| Layer | File | Endpoint | What it does |
|-------|------|----------|-------------|
| DETECT | `layers/detect.py` | `POST /detect/run` | Sentinel-2 fetch → Claude Vision → alert stored in Firestore |
| ATTRIBUTE | `layers/attribute.py` | `POST /attribute/{id}` | Spatial intersection → named legal operator |
| PREDICT | `layers/predict.py` | `POST /predict/{id}` | XGBoost → people affected, fish die-off, economic damage |
| ACT | `layers/act.py` | `POST /act/denuncia/{id}` | Context7 RAG + Claude Haiku → PDF denuncia |
| PUBLISH | `layers/publish.py` | `POST /publish/{id}` | Zavu SMS/WhatsApp + Resend email |

Full pipeline: `POST /pipeline/run` with `{"bbox": [...], "date": "YYYY-MM-DD"}`

## Data sources (real, not synthetic)

- **ML training data (`ml/loreto_historical.csv`):** 698 real OEFA/RUIAS sanction records downloaded from `datosabiertos.gob.pe`. Columns: `contamination_type, volume_barrels, river_flow_m3s, distance_km, pop_density_per_km2, biodiversity_index, season, people_affected_7d, people_affected_30d, fish_dieoff_pct, recovery_days`
- **Concession polygons (`data/norperuana.geojson`):** 4 features with documented polygon vertices from OEFA/RAISG published maps. Feature types: `pipeline` (ONP-Tramo-I / Petroperú) and `concession` (Lote-192, Lote-8, Lote-95)
- **Attribution multiplier:** pipeline features get 8× score over concession area to correctly assign liability to pipeline operator when detection overlaps both

## Key conventions

- **No Unicode symbols in print statements** — use `[OK]`/`[WARN]` prefixes (Windows console charset issue)
- **All datetimes:** `datetime.now(timezone.utc)`, never `datetime.utcnow()`
- **Pydantic v2:** use `.model_dump()`, not `.dict()`
- **FastAPI body params:** use a `BaseModel` — FastAPI cannot parse `list[float]` from POST query params
- **GeoPandas CRS:** project to `EPSG:32718` (UTM 18S) for area calculations, keep WGS84 for storage

## Correct demo bbox (attribution test)

```json
{"bbox": [-76.1, -3.9, -75.6, -3.5], "date": "2024-03-15"}
```
Returns: Petroperú S.A. | ONP-Tramo-I | 474 prior sanctions

## Environment variables

Copy `backend/.env.example` to `backend/.env`. Required keys:
`ANTHROPIC_API_KEY`, `SENTINEL_HUB_CLIENT_ID`, `SENTINEL_HUB_CLIENT_SECRET`, `ZAVU_API_KEY`, `CONTEXT7_API_KEY`, `RESEND_API_KEY`, `GOOGLE_CLOUD_PROJECT`

Optional fallbacks (no keys needed for local testing):
- If `ANTHROPIC_API_KEY` missing → Claude calls will fail, use mock data
- If `FIRESTORE_EMULATOR_HOST=localhost:8080` → uses local Firestore emulator
- XGBoost predict has heuristic fallback if `ml/impact_model.pkl` not found

## Deployment

See `DEPLOY.md` for full Railway + Vercel instructions.
- Backend → Railway (Dockerfile, `railway.toml`)
- Frontend → Vercel (`vercel.json`, set `NEXT_PUBLIC_API_URL`)

## Frontend

Next.js 14 App Router, Tailwind CSS, MapLibre GL JS. Three routes:
- `/` — live map dashboard (fetches `GET /detect/alerts?limit=20`)
- `/alerts/[id]` — alert detail with attribution, impact, denuncia PDF button
- `/leaderboard` — company accountability table (fetches `GET /leaderboard`)

`NEXT_PUBLIC_API_URL` defaults to `http://localhost:8000` if not set.
