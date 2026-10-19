#!/bin/bash
# =========================================================================
# RideNow — Production Startup Script
# Runs Uvicorn directly + LiveKit Voice Agent worker in background.
# Uses direct uvicorn instead of gunicorn to save ~120MB RAM on 512MB hosts.
# =========================================================================

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

# ── Start FastAPI Server with direct uvicorn (saves ~120MB RAM) ─────────
echo "  [API]   Starting uvicorn FastAPI server on port ${PORT:-8000}..."
echo "============================================================"

exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --log-level info
