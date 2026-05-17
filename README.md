# Guardián del Agua

> Plataforma de evidencia probatoria grado-litigación para la Amazonía peruana · hack@latam 2026

**"Esto ya no es denuncia. Es prueba."**

El primer audit trail probatorio para denuncias ambientales en la Amazonía peruana. Sentinel-2 + Claude + Ley peruana, en español jurídico, listo para OEFA en menos de 25 horas.

Genera **evidencia técnica** de contaminación detectada por satélite, atribuye responsabilidad presunta al operador concesionario, proyecta impacto aguas abajo, redacta dossiers probatorios con base legal citable, y entrega SMS/email a federaciones indígenas — todo con cadena de custodia técnica reproducible.

**Diferenciador clave:** mientras el mercado actual (MAAP, Geobosques, Cerulean, Kayrros) ofrece *monitoreo*, Guardián del Agua produce **evidencia admisible**: chain-of-custody, fundamentos legales citados, lenguaje "presunto responsable sujeto a verificación in situ", revisión humana obligatoria antes de presentación.

---

## Quick Start

### Backend

```bash
# Activate virtual environment (created in _docx_extract/)
_docx_extract\venv\Scripts\activate      # Windows
source _docx_extract/venv/bin/activate    # macOS/Linux

# Copy and fill in API keys
cp v1/backend/.env.example v1/backend/.env
# Edit .env with your keys

cd v1/backend

# Train the XGBoost model
python ml/train.py

# Start the API server
uvicorn main:app --reload --port 8000
```

API docs available at http://localhost:8000/docs

### Frontend

```bash
cd v1/frontend
cp .env.local.example .env.local
npm install
npm run dev
```

Frontend available at http://localhost:3000

---

## Architecture — 5 Layers

```
Satellite Pass (Sentinel-2)
    │
    ▼
[DETECT]     Claude Sonnet 4.5 Vision → contamination type + confidence
    │
    ▼
[ATTRIBUTE]  Shapely geospatial intersection → named legal operator
    │
    ▼
[PREDICT]    XGBoost → people affected, fish die-off, economic damage
    │
    ▼
[ACT]        Context7 RAG + Claude Haiku → OEFA denuncia PDF (< 5s)
    │
    ▼
[PUBLISH]    Zavu SMS/WhatsApp + Resend email → federations + journalists
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | System health |
| POST | `/detect/run` | Detect contamination in bbox+date |
| GET | `/detect/alerts` | List recent alerts |
| POST | `/attribute/{alert_id}` | Attribute alert to legal operator |
| POST | `/predict/{alert_id}` | Predict downstream impact |
| POST | `/act/denuncia/{alert_id}` | Generate legal denuncia PDF |
| GET | `/act/denuncia/{alert_id}/download` | Download PDF |
| POST | `/publish/{alert_id}` | Send SMS + email notifications |
| POST | `/pipeline/run` | Run all 5 layers in sequence |

---

## Demo Seed Data

```bash
# Requires Firestore configured in .env
python v1/backend/seed_demo.py
```

Seeds 5 pre-built alerts + company leaderboard for demo.

---

## Required API Keys

| Service | Purpose | Get it |
|---------|---------|--------|
| `ANTHROPIC_API_KEY` | Claude Vision + Haiku | console.anthropic.com |
| `SENTINEL_HUB_CLIENT_ID/SECRET` | Sentinel-2 imagery | sentinel-hub.com (30-day trial) |
| `ZAVU_API_KEY` | SMS + WhatsApp delivery | Redeem coupon HACKINDIES |
| `CONTEXT7_API_KEY` | Legal RAG corpus | Context7 sponsor portal |
| `RESEND_API_KEY` | Email delivery | resend.com (free tier) |
| `GOOGLE_CLOUD_PROJECT` | Firestore + Cloud Run | console.cloud.google.com |

---

## Tech Stack

- **Backend:** Python 3.11, FastAPI, Google Cloud Run
- **AI/ML:** Claude Sonnet 4.5 (vision), Claude Haiku 4.5 (text), XGBoost, Context7 RAG
- **Geospatial:** Sentinel Hub, Shapely, GeoPandas, Rasterio
- **Communication:** Zavu (SMS/WhatsApp/Voice), Resend (email)
- **Frontend:** Next.js 14, Tailwind CSS, MapLibre GL JS
- **Database:** Google Cloud Firestore

---

## License

MIT — code · CC-BY-SA 4.0 — documentation · CC0 — aggregate alert data

Follows CARE Principles and FPIC for all Indigenous community data.
