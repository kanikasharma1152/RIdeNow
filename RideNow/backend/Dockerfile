# =========================================================================
# RideNow Backend — Dockerfile
# =========================================================================
# Multi-stage build to keep the production image lean.
# Stage 1: builder — install Python deps into a virtual environment.
# Stage 2: runtime — copy only the venv and app source.
# =========================================================================

# ── Stage 1: builder ─────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

# Install system build deps (psycopg2-binary, cryptography, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files first for layer caching
COPY requirements.txt ./

# Create a venv inside the image so we can copy it cleanly
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ── Stage 2: runtime ─────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

WORKDIR /app

# Runtime system deps only
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Copy virtualenv from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application source
COPY . .

# Non-root user for security
RUN groupadd -r ridenow && useradd -r -m -g ridenow ridenow
RUN chown -R ridenow:ridenow /app
USER ridenow

# ── Runtime configuration ─────────────────────────────────────────────────
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

EXPOSE 8000

# Liveness probe (Docker HEALTHCHECK)
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health/live || exit 1

# Copy and permission the startup script (must be done as root before USER ridenow)
USER root
COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh
USER ridenow

# Start both FastAPI server + LiveKit voice agent worker
CMD ["/bin/bash", "/app/start.sh"]
