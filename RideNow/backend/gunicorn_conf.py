"""
Gunicorn configuration for RideNow FastAPI (ASGI) production deployment.
Usage:
    gunicorn -c gunicorn_conf.py app.main:app
"""
import os

# ── Binding ──────────────────────────────────────────────────────────────────
bind = f"0.0.0.0:{os.getenv('PORT', '8000')}"

# ── Workers ───────────────────────────────────────────────────────────────────
# uvicorn.workers.UvicornWorker runs the ASGI event loop in each worker process.
worker_class = "uvicorn.workers.UvicornWorker"

# Rule of thumb for I/O-bound ASGI apps: 2 × CPU cores + 1
workers = int(os.getenv("WEB_CONCURRENCY", "2"))

# ── Timeouts ──────────────────────────────────────────────────────────────────
timeout = int(os.getenv("GUNICORN_TIMEOUT", "120"))      # worker silent timeout (s)
keepalive = int(os.getenv("GUNICORN_KEEPALIVE", "5"))    # HTTP keep-alive (s)
graceful_timeout = 30                                     # graceful shutdown window

# ── Logging ───────────────────────────────────────────────────────────────────
loglevel = os.getenv("LOG_LEVEL", "info")
accesslog = "-"    # stdout
errorlog = "-"     # stderr
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)sµs'

# ── Server mechanics ──────────────────────────────────────────────────────────
# Max requests per worker before restart (prevents memory leaks)
max_requests = int(os.getenv("GUNICORN_MAX_REQUESTS", "1000"))
max_requests_jitter = 100   # randomise to avoid thundering herd
preload_app = False         # keep False for asyncio workers to avoid event-loop issues
