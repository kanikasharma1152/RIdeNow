# RideNow Voice AI — Setup Guide

> **"An AI is actually operating the RideNow mobility platform — through your voice."**

This document describes how to configure, run, and verify the RideNow real-time AI Voice system,
powered by **LiveKit WebRTC + Cartesia STT/TTS + Groq LLM + Silero VAD**.

---

## Architecture Overview

```
Browser (livekit-client)
    │
    │  WebRTC audio track
    ▼
LiveKit Cloud (wss://ridenow-rfgr2bi3.livekit.cloud)
    │
    │  Worker WebSocket
    ▼
RideNow Voice Agent Worker (livekit_agent.py)
    ├── Cartesia STT  →  transcribes user speech
    ├── Silero VAD    →  detects speech start/end (barge-in support)
    ├── Groq LLM      →  llama-3.3-70b-versatile reasoning + tool calls
    ├── RideNow Tools →  execute_tool() → service layer → database
    └── Cartesia TTS  →  generates natural voice response
```

Same AI brain as the text chat — same tools, same RAG, same Groq LLM. Only the I/O channel differs.

---

## Prerequisites

| Requirement | Details |
|---|---|
| Python 3.11+ | Backend virtualenv |
| Node.js 18+ | Frontend |
| PostgreSQL | Running locally or remote |
| LiveKit Cloud account | Free tier available at https://livekit.io |
| Cartesia account | https://cartesia.ai — STT + TTS |
| Groq account | https://console.groq.com — LLM |

---

## Environment Variables

Set these in `E:\uber clone\RideNow\backend\.env`:

```env
# Groq LLM
GROQ_API_KEY=gsk_...
GROQ_MODEL=llama-3.3-70b-versatile

# LiveKit WebRTC
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=APIxxxxxxxxxxxxxxxx
LIVEKIT_API_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Cartesia Voice (STT + TTS)
CARTESIA_API_KEY=sk_car_xxxxxxxxxxxxxxxxxxxxxxxx
CARTESIA_VOICE_ID=f786b574-daa5-4673-aa0c-cbe3e8534c02
```

> **Security**: Never commit `.env` to version control. It is already in `.gitignore`.

---

## Backend: Python Packages

All voice packages are already installed in the virtualenv:

```
livekit-agents==1.8.1
livekit==1.1.18
livekit-plugins-cartesia==1.8.1
livekit-plugins-groq==1.8.1
livekit-plugins-silero==1.8.1
```

To re-install if needed:

```powershell
cd "E:\uber clone\RideNow\backend"
.\venv\Scripts\pip install livekit-agents==1.8.1 livekit-plugins-cartesia livekit-plugins-groq livekit-plugins-silero
```

---

## Running the System — Three Terminals

### Terminal 1 — FastAPI Backend

```powershell
cd "E:\uber clone\RideNow\backend"
.\venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
```

Exposes:
- `POST /voice/token` — generates LiveKit room JWT for the browser
- `GET /voice/health` — returns safe status (livekit/cartesia/groq configured: true/false)
- All existing ride, user, AI chat, websocket endpoints

### Terminal 2 — Vite Frontend

```powershell
cd "E:\uber clone\RideNow\frontend"
npm run dev
```

Access at `http://localhost:5173`

### Terminal 3 — LiveKit Voice Agent Worker

```powershell
cd "E:\uber clone\RideNow\backend"
.\venv\Scripts\python -m app.ai.livekit_agent start
```

Expected output:
```
============================================================
  RIDENOW AI — LIVEKIT REAL-TIME VOICE AGENT
============================================================
  LiveKit Server: wss://ridenow-rfgr2bi3.livekit.cloud
  Groq LLM Model: llama-3.3-70b-versatile
  Cartesia Voice: f786b574-daa5-4673-aa0c-cbe3e8534c02
  Cartesia TTS:   sonic-3
  Cartesia STT:   ink-whisper
============================================================
INFO  ridenow-voice-agent: Connected to LiveKit server, waiting for rooms...
```

The worker stays running and picks up participants when users click "Connect Voice Core" in the browser.

---

## Voice Agent — Key Files

| File | Purpose |
|---|---|
| `app/ai/livekit_agent.py` | Voice agent worker — entry point, tool factory, session setup |
| `app/services/voice.py` | Generates LiveKit JWT tokens with user metadata |
| `app/routers/voice.py` | FastAPI endpoints: /voice/token, /voice/health |
| `app/core/config.py` | Cartesia & LiveKit config with is_cartesia_configured |
| `tests/test_phase5_voice.py` | 5 voice integration tests |

---

## Voice Tools Available

### Passenger Tools (5)

| Tool | Description |
|---|---|
| `get_active_ride` | Current ride status, pickup, dropoff, fare |
| `estimate_fare` | Fare estimate given distance or addresses |
| `get_ride_history` | Recent past trips with fare and status |
| `cancel_ride` | Cancel active ride (requires confirmation) |
| `search_policies_and_faq` | RAG search over official RideNow knowledge base |

### Driver Tools (7 = 5 + 2)

| Tool | Description |
|---|---|
| `get_driver_summary` | Online status, today's earnings, today's trip count |
| `get_route_tip` | Optimization tip for current navigation context |

All tools execute via `execute_tool()` → service layer → repository → PostgreSQL.
**The voice agent never accesses the database directly.**

---

## Frontend Voice UI

Location: `frontend/src/components/ai/VoiceAssistant.jsx`

The component:
1. Calls `POST /voice/token` to get a LiveKit JWT
2. Creates a `Room` (from `livekit-client`)
3. Connects to LiveKit Cloud via WebRTC
4. Publishes local microphone track
5. Subscribes to remote audio tracks from the AI agent
6. Plays AI audio directly in the browser

States: `idle → connecting → listening → speaking → idle`

The AI Assistant page (`/ai`) has a tab switcher — "Chat" and "Voice Core" — accessible to all logged-in users.

---

## Destructive Action Safety

For any destructive operation (ride cancellation), the AI always asks for confirmation before executing:

```
User: "Cancel my ride"
AI:   "Are you sure you want to cancel ride #1234? Please confirm."
User: "Yes, cancel it"
AI:   [calls cancel_ride with confirmed=True]
AI:   "Ride #1234 has been successfully cancelled."
```

This is enforced in the tool implementation in `livekit_agent.py`.

---

## Test Suite

Run all 26 tests:

```powershell
cd "E:\uber clone\RideNow\backend"
.\venv\Scripts\python -m pytest -v
```

Expected result: **26 passed**

Voice-specific tests in `tests/test_phase5_voice.py`:
- `test_voice_token_unauthenticated` — 401/403 without JWT
- `test_voice_token_authenticated_fallback` — 200 or 503 with JWT
- `test_voice_health_endpoint` — checks all fields in /voice/health
- `test_voice_tools_generation_passenger` — 5 tools, no driver-only tools
- `test_voice_tools_generation_driver` — 7 tools including driver-only tools

---

## Cartesia Models Reference

### TTS Models

| Model | Quality | Latency |
|---|---|---|
| `sonic-3` (default) | Best | Low |
| `sonic-2` | High | Low |
| `sonic` | Good | Lowest |

### STT Models

| Model | Strength |
|---|---|
| `ink-whisper` (default) | Best multilingual (en + hi) |
| `ink-2` | English-optimized |

---

## Troubleshooting

**Voice agent not responding to speech**
- Verify `CARTESIA_API_KEY` is set and valid
- Check Silero VAD downloaded model successfully on first run
- Ensure microphone permission granted in browser

**LiveKit connection fails**
- Verify `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET` are correct
- Check network allows WebSocket connections to `wss://`

**GET /voice/health returns livekit: false**
- Check all three LiveKit env vars are set (URL + API key + API secret)

**GET /voice/health returns cartesia: false**
- `CARTESIA_API_KEY` is missing from `.env`

**Tool execution fails in voice**
- Check PostgreSQL is running and `DATABASE_URL` is set
- The voice agent opens fresh `AsyncSessionLocal()` sessions per tool call

---

## Security Notes

- **No secrets exposed**: `/voice/health` returns only true/false flags, model names, and voice ID
- **JWT required**: `/voice/token` requires a valid RideNow JWT (`Authorization: Bearer ...`)
- **User scoping**: Voice tools are scoped to the authenticated user — no cross-user data access
- **Role enforcement**: Driver-only tools only available to drivers
- **No direct DB**: Voice agent → `execute_tool()` → service layer → repository → database

