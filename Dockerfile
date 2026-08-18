# Credit Risk Decision Engine — backend (FastAPI + models)
# Multi-stage: build wheels once, ship a lean non-root runtime.

# ---------- builder ----------
FROM python:3.13-slim AS builder

WORKDIR /build

# libgomp is required by XGBoost at build+runtime.
RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential libgomp1 \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---------- runtime ----------
FROM python:3.13-slim AS runtime

# OpenMP runtime for XGBoost; curl for the container healthcheck.
RUN apt-get update \
 && apt-get install -y --no-install-recommends libgomp1 curl \
 && rm -rf /var/lib/apt/lists/* \
 && useradd --create-home --uid 10001 appuser

COPY --from=builder /install /usr/local

WORKDIR /app

# Application code + the trained artifacts the API loads on first request.
COPY --chown=appuser:appuser server.py utils.py auth.py db.py notices.py ./
COPY --chown=appuser:appuser models/ ./models/
COPY --chown=appuser:appuser data/ ./data/

# Mount point for the audit trail / accounts database (see CR_DATABASE_URL).
# It must be owned by the runtime user or SQLite cannot create the file.
RUN mkdir -p /data && chown appuser:appuser /data
VOLUME ["/data"]

USER appuser

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD curl -fsS "http://localhost:${PORT}/api/health" || exit 1

# Respect the platform-provided $PORT (Render/Railway/Fly set this).
CMD ["sh", "-c", "uvicorn server:app --host 0.0.0.0 --port ${PORT}"]
