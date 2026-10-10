# RideNow — Deployment Guide

> **Phase 8 — Production Deployment Reference**
> Last updated: Phase 8 implementation

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Prerequisites](#prerequisites)
3. [Environment Variables](#environment-variables)
4. [Backend Deployment](#backend-deployment)
5. [Frontend Deployment](#frontend-deployment)
6. [Database Setup](#database-setup)
7. [Redis Setup](#redis-setup)
8. [Docker / Compose Deployment](#docker--compose-deployment)
9. [Cloud Platform Options](#cloud-platform-options)
10. [Health & Readiness Checks](#health--readiness-checks)
11. [CI/CD Pipeline](#cicd-pipeline)

---

## Architecture Overview

```
Internet
   ↓
[CDN / Edge]  ←─ static SPA (React + Vite)
   ↓
[Load Balancer / Reverse Proxy]
   ↓
[FastAPI / Gunicorn + UvicornWorker]  ←─ Backend (ASGI)
   ↓
[PostgreSQL 16]   [Redis 7]
```

**Real-time (WebSocket):**
```
Driver App → FastAPI WS (/ws/driver) → Admin Fleet Radar
```

---

## Prerequisites

| Dependency | Minimum Version | Notes |
|---|---|---|
| Python | 3.11 | 3.12 works too |
| PostgreSQL | 14+ | 16-alpine recommended |
| Redis | 6+ | 7-alpine recommended (optional, graceful fallback) |
| Node.js | 18+ | 20 LTS recommended |
| Docker | 24+ | For containerised deployment |

---

## Environment Variables

Copy and fill in `backend/.env.example`:

```bash
cp backend/.env.example backend/.env
```

**Critical production overrides:**

| Variable | Production Value |
|---|---|
| `ENVIRONMENT` | `production` |
| `DATABASE_URL` | `postgresql+asyncpg://user:pass@host:5432/dbname` |
| `SECRET_KEY` | Generate: `openssl rand -hex 32` |
| `CORS_ORIGINS` | Your frontend domain(s), comma-separated |
| `REDIS_URL` | `redis://host:6379/0` |

> [!CAUTION]
> Never commit `.env` to version control. It is already in `.gitignore`.

---

## Backend Deployment

### Local Development

```bash
cd backend
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

### Production (Gunicorn + UvicornWorker)

```bash
cd backend
source venv/bin/activate
alembic upgrade head
gunicorn -c gunicorn_conf.py app.main:app
```

Tune workers via env:

```bash
WEB_CONCURRENCY=4 gunicorn -c gunicorn_conf.py app.main:app
```

### Docker

```bash
# Build image
docker build -t ridenow-backend ./backend

# Run
docker run -d \
  --name ridenow-api \
  -p 8000:8000 \
  --env-file backend/.env \
  ridenow-backend
```

---

## Frontend Deployment

### Build

```bash
cd frontend
cp .env.example .env
# Edit .env: set VITE_API_BASE_URL and VITE_WS_URL to your backend domain
npm ci
npm run build
# Output: frontend/dist/
```

### Netlify

```
Build command: npm run build
Publish directory: frontend/dist
```

The `frontend/public/_redirects` file handles SPA routing automatically.

### Vercel

Import the `frontend/` directory. `vercel.json` is pre-configured with:
- SPA rewrites (all paths → `/index.html`)
- Asset cache headers (immutable, 1 year)

Add env vars in Vercel dashboard:
- `VITE_API_BASE_URL` = `https://your-api-domain.com`
- `VITE_WS_URL` = `wss://your-api-domain.com/ws`

### Nginx (Container / VPS)

```bash
# Use the provided nginx.conf
docker run -d \
  -p 80:80 \
  -v $(pwd)/frontend/dist:/usr/share/nginx/html:ro \
  -v $(pwd)/frontend/nginx.conf:/etc/nginx/conf.d/default.conf:ro \
  nginx:alpine
```

---

## Database Setup

### Initial Schema

```bash
cd backend
alembic upgrade head
```

### Verify Migration Status

```bash
alembic current
```

### Create a New Migration

```bash
alembic revision --autogenerate -m "describe_change"
alembic upgrade head
```

---

## Redis Setup

Redis is **optional** — the app falls back to in-memory cache in development. For production, set:

```env
REDIS_URL=redis://localhost:6379/0
```

For Redis Cloud / Upstash:

```env
REDIS_URL=redis://default:password@host.upstash.io:6379
```

---

## Docker / Compose Deployment

```bash
# Copy and configure environment
cp backend/.env.example backend/.env
# Edit backend/.env

# Start all services (Postgres, Redis, Backend, Frontend)
docker compose up -d

# View logs
docker compose logs -f backend

# Run migrations
docker compose exec backend alembic upgrade head

# Stop everything
docker compose down
```

---

## Cloud Platform Options

| Platform | Backend | Frontend | Notes |
|---|---|---|---|
| **Railway** | ✅ Native Docker | ✅ Static | Easiest full-stack |
| **Render** | ✅ Web Service | ✅ Static Site | Free tier available |
| **Fly.io** | ✅ Docker | ❌ (use CDN) | Good WebSocket support |
| **Heroku** | ✅ Procfile | ❌ (use CDN) | Add `Procfile` |
| **Vercel** | ❌ Serverless incompatible | ✅ Native | Frontend only |
| **Netlify** | ❌ Serverless incompatible | ✅ Native | Frontend only |
| **AWS / GCP / Azure** | ✅ Full | ✅ Full | Manual setup required |

> [!IMPORTANT]
> FastAPI uses persistent ASGI (long-running event loops + WebSockets). It is **not compatible** with serverless platforms like Vercel Functions or Netlify Functions. Deploy the backend on a persistent service.

### Minimum Required `Procfile` (Heroku)

```
web: gunicorn -c gunicorn_conf.py app.main:app
```

---

## Health & Readiness Checks

| Endpoint | Type | Purpose |
|---|---|---|
| `GET /health` | Combined | Full health with DB + Redis status |
| `GET /health/live` | Liveness | Process alive check (no I/O) |
| `GET /health/ready` | Readiness | DB + Redis connectivity check |

**Example probe configuration (Kubernetes):**

```yaml
livenessProbe:
  httpGet:
    path: /health/live
    port: 8000
  initialDelaySeconds: 15
  periodSeconds: 30

readinessProbe:
  httpGet:
    path: /health/ready
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 10
```

---

## CI/CD Pipeline

GitHub Actions workflow at `.github/workflows/ci.yml` runs on every push and PR to `main` / `develop`:

1. **Backend job** — installs Python deps, runs `pytest -q` (uses SQLite in-memory, no external DB needed)
2. **Frontend job** — installs Node deps, runs `npm run build`

To enable: push the repository to GitHub. No additional configuration needed for the CI pipeline itself.

For deploying from CI, add platform-specific deploy steps using GitHub Secrets (never hardcode credentials).
