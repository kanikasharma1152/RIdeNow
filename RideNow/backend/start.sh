#!/bin/bash
# =========================================================================
# RideNow — Production Startup Script
# Starts both the FastAPI server (gunicorn) and the LiveKit Voice Agent
# worker in the same container for single-service deployments (Render free).
# =========================================================================

set -e

echo "============================================================"
echo "  RIDENOW BACKEND — STARTING"
echo "============================================================"

# ── Start LiveKit Voice Agent Worker (background) ────────────────────────
if [ -n "$LIVEKIT_URL" ] && [ -n "$LIVEKIT_API_KEY" ] && [ -n "$LIVEKIT_API_SECRET" ]; then
  echo "  [VOICE] LiveKit credentials found — starting voice agent worker..."
  python -m app.ai.livekit_agent start &
  VOICE_PID=$!
  echo "  [VOICE] Voice agent worker started (PID=$VOICE_PID)"
else
  echo "  [VOICE] LIVEKIT_URL/API_KEY/API_SECRET not set — skipping voice agent"
fi

# ── Start FastAPI Server (foreground) ────────────────────────────────────
echo "  [API]   Starting gunicorn FastAPI server..."
echo "============================================================"

exec gunicorn -c gunicorn_conf.py app.main:app
