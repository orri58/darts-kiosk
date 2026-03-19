# ==============================================================================
# Darts Kiosk v3.5.5 — Production Multi-Stage Dockerfile
# ==============================================================================

# --- Stage 1: Build Frontend ---
FROM node:20-alpine AS frontend-build
WORKDIR /build

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY frontend/ .
ENV REACT_APP_BACKEND_URL=
ENV ENABLE_HEALTH_CHECK=false
RUN npx craco build

# --- Stage 2: Runtime ---
FROM python:3.11-slim
WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl sqlite3 && \
    rm -rf /var/lib/apt/lists/*

# Python deps
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Backend code
COPY backend/ ./backend/

# Pre-built frontend
COPY --from=frontend-build /build/build ./frontend/build

# Data & config
RUN mkdir -p data/db data/assets data/backups data/chrome_profile logs
COPY VERSION ./

# Runtime config
ENV PYTHONPATH=/app
ENV DATA_DIR=/app/data
ENV DATABASE_URL=sqlite+aiosqlite:///./data/db/darts.sqlite
ENV SYNC_DATABASE_URL=sqlite:///./data/db/darts.sqlite

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -sf http://localhost:8001/api/health || exit 1

CMD ["python", "-m", "uvicorn", "backend.server:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "1"]
