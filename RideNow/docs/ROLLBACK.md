# RideNow — Rollback & Recovery Strategy

> **Phase 8 — Production Operations Reference**

---

## Table of Contents

1. [Rollback Decision Criteria](#rollback-decision-criteria)
2. [Application Rollback](#application-rollback)
3. [Database Migration Rollback](#database-migration-rollback)
4. [Redis Recovery](#redis-recovery)
5. [Emergency Procedures](#emergency-procedures)
6. [Post-Incident Checklist](#post-incident-checklist)

---

## Rollback Decision Criteria

Trigger an immediate rollback if any of the following occur within 15 minutes of a deployment:

- Error rate > 5% on `/health` or any API endpoint
- `/health/ready` returns 503
- WebSocket connections dropping > 10% baseline
- Database query p99 latency > 2 seconds
- Any unhandled 500 response for core flows (booking, ride, payment)

---

## Application Rollback

### Docker / Compose

```bash
# Tag releases before deploying
docker tag ridenow-backend:latest ridenow-backend:previous

# Rollback to previous image
docker stop ridenow_backend
docker run -d \
  --name ridenow_backend \
  --env-file backend/.env \
  ridenow-backend:previous

# Verify health
curl http://localhost:8000/health/live
curl http://localhost:8000/health/ready
```

### Git-based Rollback

```bash
# Find last known-good commit
git log --oneline -10

# Rollback code
git checkout <last-good-commit> -- backend/
git checkout <last-good-commit> -- frontend/

# Rebuild and redeploy
cd frontend && npm ci && npm run build
cd backend && gunicorn -c gunicorn_conf.py app.main:app
```

### Railway / Render / Fly.io

Use the platform's deployment history UI to redeploy the previous successful build (usually a single click).

---

## Database Migration Rollback

> [!WARNING]
> Always take a database backup BEFORE running migrations in production.

### Check Current State

```bash
cd backend
alembic current
alembic history --verbose
```

### Downgrade One Step

```bash
alembic downgrade -1
```

### Downgrade to Specific Revision

```bash
# List available revisions
alembic history

# Downgrade to a specific revision
alembic downgrade <revision_id>
```

### Emergency: Restore from Backup

```bash
# PostgreSQL restore
pg_restore --clean --no-acl --no-owner \
  -d $DATABASE_URL \
  backup_YYYYMMDD_HHMMSS.dump

# Verify
psql $DATABASE_URL -c "SELECT version();"
```

### Pre-deployment Backup Command

```bash
pg_dump \
  --format=custom \
  --no-acl \
  --no-owner \
  $DATABASE_URL \
  > "backup_$(date +%Y%m%d_%H%M%S).dump"
```

---

## Redis Recovery

Redis data is **ephemeral cache** — losing it is safe. The app automatically:
- Falls back to in-memory cache if Redis is unavailable
- Rebuilds cache on next request
- Rate limit windows reset (brief traffic burst may pass through)

### Redis Connection Issues

```bash
# Test connectivity
redis-cli -u $REDIS_URL ping

# Restart Redis container
docker restart ridenow_redis

# If Redis is completely unavailable, set:
# REDIS_URL=   (empty → graceful in-memory fallback)
```

---

## Emergency Procedures

### 1. Total Backend Outage

```bash
# 1. Check process
curl http://localhost:8000/health/live

# 2. Check DB
curl http://localhost:8000/health/ready

# 3. Tail logs
docker logs ridenow_backend --tail 100 -f

# 4. Restart container
docker restart ridenow_backend

# 5. If still failing — rollback to previous image (see Application Rollback)
```

### 2. Database Connection Pool Exhaustion

Symptoms: 500 errors with "connection pool timeout"

```bash
# Temporary: increase pool size in .env
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=40
# Restart backend

# Permanent: identify and close idle connections
psql $DATABASE_URL -c "
  SELECT pid, state, wait_event_type, query_start, query
  FROM pg_stat_activity
  WHERE state != 'idle'
  ORDER BY query_start;
"
```

### 3. WebSocket Disconnects

```bash
# Check WebSocket health via browser DevTools > Network > WS tab
# Backend: check log for "WebSocket disconnected" messages

# Increase timeouts in gunicorn_conf.py:
timeout = 300  # 5 minutes for long-lived WS connections
```

### 4. Frontend Shows Blank Page

```bash
# Check browser console for errors
# Most likely: VITE_API_BASE_URL points to wrong backend

# Rebuild with correct URL:
VITE_API_BASE_URL=https://your-api.com npm run build
```

---

## Post-Incident Checklist

After any incident or rollback:

- [ ] Document the timeline: what changed, when symptoms appeared, when resolved
- [ ] Check `/health` and `/health/ready` return 200
- [ ] Run full test suite: `pytest -q` (all passing)
- [ ] Verify frontend build succeeds: `npm run build`
- [ ] Review application logs for residual errors
- [ ] Take a fresh database backup
- [ ] Update `DEPLOYMENT.md` with any new learnings
- [ ] Create a post-mortem issue if the incident affected users
