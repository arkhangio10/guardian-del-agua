# Deploy — Guardián del Agua

Total time: ~35 minutes.  
Backend → Railway (Docker, no cold starts, $5 coupon credit).  
Frontend → Vercel (Next.js, free tier).

---

## Prerequisites

- Git repo pushed to GitHub (public or private)
- Railway account — railway.app
- Vercel account — vercel.com
- All API keys ready (see `.env.example`)

---

## Step 1 — Push to GitHub

```bash
cd C:\Users\braya\Desktop\project_personal\indie_letam_hack\_docx_extract\v1
git init
git add .
git commit -m "feat: initial guardian del agua"
git remote add origin https://github.com/YOUR_USERNAME/guardian-del-agua.git
git push -u origin main
```

---

## Step 2 — Deploy Backend to Railway

1. Go to **railway.app** → New Project → Deploy from GitHub repo
2. Select your repo → select the `backend/` folder as root
3. Railway auto-detects `Dockerfile` via `railway.toml`

### Set environment variables in Railway dashboard

Under **Variables**, add all keys from `backend/.env.example`:

| Key | Where to get it |
|-----|----------------|
| `ANTHROPIC_API_KEY` | console.anthropic.com |
| `SENTINEL_HUB_CLIENT_ID` | apps.sentinel-hub.com |
| `SENTINEL_HUB_CLIENT_SECRET` | apps.sentinel-hub.com |
| `ZAVU_API_KEY` | Zavu sponsor portal (coupon: HACKINDIES) |
| `ZAVU_BASE_URL` | `https://api.zavu.com/v1` |
| `CONTEXT7_API_KEY` | Context7 sponsor portal |
| `RESEND_API_KEY` | resend.com (free tier) |
| `GOOGLE_CLOUD_PROJECT` | GCP console |

4. Click **Deploy** — Railway builds the Docker image (~4 min)
5. Under **Settings → Networking → Generate Domain** — copy the URL (e.g. `https://guardian-del-agua-production.up.railway.app`)
6. Verify: `curl https://YOUR_RAILWAY_URL/health` → `{"status": "ok"}`

> **Railway $5 coupon:** apply at railway.app/account/billing with code from hack@latam sponsors.

---

## Step 3 — Seed Demo Data

```bash
# From your local machine (venv active):
cd _docx_extract\v1\backend

# Set FIRESTORE_EMULATOR_HOST or GOOGLE_CLOUD_PROJECT first
set GOOGLE_CLOUD_PROJECT=your-gcp-project-id
"..\..\venv\Scripts\python.exe" seed_demo.py
```

Or trigger via Railway shell:
```bash
railway run python seed_demo.py
```

---

## Step 4 — Deploy Frontend to Vercel

1. Go to **vercel.com** → New Project → Import from GitHub
2. Select your repo → set **Root Directory** to `frontend/`
3. Vercel auto-detects Next.js

### Set environment variables in Vercel dashboard

Under **Settings → Environment Variables**:

| Key | Value |
|-----|-------|
| `NEXT_PUBLIC_API_URL` | `https://YOUR_RAILWAY_URL` (no trailing slash) |
| `NEXT_PUBLIC_MAPLIBRE_STYLE` | `https://demotiles.maplibre.org/style.json` |

4. Click **Deploy** (~2 min)
5. Vercel gives you a URL like `https://guardian-del-agua.vercel.app`

---

## Step 5 — Smoke Test

```bash
BACKEND=https://YOUR_RAILWAY_URL
FRONTEND=https://YOUR_VERCEL_URL

# Backend health
curl $BACKEND/health

# Leaderboard
curl $BACKEND/leaderboard | python -m json.tool

# Run detection — pipeline bbox (returns Petroperú S.A., ONP-Tramo-I)
curl -X POST $BACKEND/pipeline/run \
  -H "Content-Type: application/json" \
  -d '{"bbox": [-76.1, -3.9, -75.6, -3.5], "date": "2024-03-15"}'

# Run detection — field bbox (returns Frontera Energy, Lote-192)
curl -X POST $BACKEND/pipeline/run \
  -H "Content-Type: application/json" \
  -d '{"bbox": [-75.3, -3.7, -75.0, -3.4], "date": "2024-03-15"}'

# Frontend
open $FRONTEND
```

---

## Keepalive (no cold starts on Railway)

Railway Pro keeps containers warm; free tier may idle.  
Add a Cloud Scheduler or UptimeRobot ping to `GET /health` every 30 seconds if needed.

---

## Rollback

```bash
# Local fallback: run backend on localhost
cd backend
..\..\..\venv\Scripts\uvicorn main:app --port 8000

# Local fallback: run frontend on localhost
cd frontend
npm run dev
```

---

## Architecture Summary

```
User Browser
    │
    ▼
Vercel (Next.js)
    │  NEXT_PUBLIC_API_URL
    ▼
Railway (FastAPI + Docker)
    ├── /detect     Claude Vision + Sentinel Hub
    ├── /attribute  GeoPandas concession polygons
    ├── /predict    XGBoost impact model
    ├── /act        Context7 RAG + Claude Haiku + WeasyPrint PDF
    ├── /publish    Zavu SMS/WhatsApp + Resend email
    ├── /leaderboard Firestore leaderboard
    └── /pipeline/run  Full 5-layer pipeline
         │
         └── Google Cloud Firestore (alerts, leaderboard)
```
