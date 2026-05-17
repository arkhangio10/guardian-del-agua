# Pin to Bookworm (Debian 12) — Trixie (Debian 13, default since 2025) renamed/removed
# packages like libgdk-pixbuf2.0-0, libgeos-c1v5, libproj25. Bookworm has all of them.
FROM python:3.11-slim-bookworm AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gdal-bin libgdal-dev libgeos-dev libproj-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ---- final stage: shared libs only, no -dev headers ----
FROM python:3.11-slim-bookworm AS runtime

# WeasyPrint + Cairo/Pango runtime (no -dev headers needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gdal-bin libgeos-c1v5 libproj25 \
    libpango-1.0-0 libpangocairo-1.0-0 \
    libcairo2 libgdk-pixbuf2.0-0 \
    shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /usr/local

WORKDIR /app
COPY . .

ENV PYTHONUNBUFFERED=1
ENV PORT=8080
EXPOSE 8080

# JSON form with sh -c wrapper: proper signal forwarding via exec, $PORT expansion via shell.
# This is the Railway/Cloud Run recommended pattern.
CMD ["sh", "-c", "echo \"[startup] PORT=${PORT:-8080}\" && exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080} --workers 1 --log-level info"]
