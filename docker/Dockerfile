# =============================================================
# SME Productivity Assessment Platform — Dockerfile
# Multi-stage build, Python 3.12, non-root user, pinned deps.
# Single container: FastAPI backend (port 8000) + Streamlit (port 8501).
# Target runtime: Render.com free tier (512 MB RAM).
# =============================================================

# ── Stage 1: Builder ──────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# Install build-time system dependencies (gcc required for some wheels)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy pinned dependency file first (better layer caching)
COPY requirements.lock ./

# Install all dependencies into a prefix directory
RUN pip install --no-cache-dir --user -r requirements.lock


# ── Stage 2: Runtime ──────────────────────────────────────────
FROM python:3.12-slim AS runtime

# Non-root user (security hardening requirement)
RUN groupadd --gid 1001 appgroup && \
    useradd  --uid 1001 --gid appgroup --shell /bin/bash --create-home appuser

WORKDIR /app

# Copy installed Python packages from builder stage
COPY --from=builder /root/.local /home/appuser/.local

# Copy application source code
COPY backend/   ./backend/
COPY frontend/  ./frontend/
COPY data/      ./data/

# FastEmbed model cache directory (persisted within the container, not /tmp)
RUN mkdir -p /app/fastembed_cache && chown -R appuser:appgroup /app

# Runtime environment
ENV PATH=/home/appuser/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
# Point FastEmbed cache to a writable, container-local path
ENV FASTEMBED_CACHE_PATH=/app/fastembed_cache

# Expose both service ports
EXPOSE 8000 8501

# Switch to non-root user
USER appuser

# Start both services in the same container.
# FastAPI handles assessment logic; Streamlit serves the UI.
CMD ["sh", "-c", \
    "uvicorn backend.main:app --host 0.0.0.0 --port 8000 & \
     streamlit run frontend/app.py \
       --server.port=8501 \
       --server.address=0.0.0.0 \
       --server.headless=true \
       --browser.gatherUsageStats=false"]
