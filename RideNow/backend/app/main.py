import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import engine, get_db

from app.routers.user import router as user_router
from app.api.user import router as api_users_router
from app.routers.driver import router as driver_router
from app.routers.ride import router as ride_router
from app.routers.ratings import router as rating_router
from app.routers.payment import router as payment_router
from app.routers.notification import router as notification_router
from app.routers.websocket import router as websocket_router
from app.routers.chat import router as chat_router
from app.routers.voice import router as voice_router
from app.routers.copilot import router as copilot_router
from app.routers.admin_analytics import router as admin_analytics_router
from app.routers.mcp import router as mcp_router
from app.routers.vision import router as vision_router
from app.routers.ml import router as ml_router
from app.routers.safety import router as safety_router
from app.routers.mobility import router as mobility_router
from app.routers.intelligence import router as intelligence_router

from fastapi.middleware.cors import CORSMiddleware

from app.core.exceptions import RideNowError
from app.core.config import settings
from app.core.redis import init_redis, close_redis, is_using_fallback


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Fail fast if insecure defaults or malformed configs are detected in production
    settings.validate_production_configuration()
    # Startup: initialize Redis (or in-memory fallback)
    await init_redis()
    yield
    # Shutdown: clean up connections
    await close_redis()


app = FastAPI(
    title="RideNow API",
    description="AI-Powered Intelligent Mobility Platform backend",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS Setup
from app.core.logging import RequestLoggingMiddleware

origins = settings.cors_origins_list

# IMPORTANT: Starlette applies middlewares in reverse-registration order
# (last added = outermost). CORSMiddleware must be outermost so it injects
# Access-Control-Allow-Origin on ALL responses, including 4xx/5xx errors.
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=settings.cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception Handlers
@app.exception_handler(RideNowError)
async def ridenow_exception_handler(request: Request, exc: RideNowError):
    request_id = getattr(request.state, "request_id", None)
    content = {
        "success": False,
        "error": {
            "code": exc.error_code,
            "message": exc.message,
        }
    }
    if request_id:
        content["error"]["request_id"] = request_id
    return JSONResponse(status_code=exc.status_code, content=content)

from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.exceptions import RequestValidationError
import logging

_logger = logging.getLogger("ridenow")

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    if isinstance(exc, (StarletteHTTPException, RequestValidationError, RideNowError)):
        raise exc
    request_id = getattr(request.state, "request_id", "unknown")
    _logger.error(f"Unhandled 500 on {request.method} {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected server error occurred.",
                "request_id": request_id,
            },
        },
    )

# Routers
app.include_router(api_users_router)
app.include_router(payment_router)
app.include_router(driver_router)
app.include_router(user_router)
app.include_router(ride_router)
app.include_router(rating_router)
app.include_router(notification_router)
app.include_router(websocket_router)
app.include_router(chat_router)
app.include_router(voice_router)
app.include_router(copilot_router)
app.include_router(admin_analytics_router)
app.include_router(mcp_router)
app.include_router(vision_router)
app.include_router(ml_router)
app.include_router(safety_router)
app.include_router(mobility_router)
app.include_router(intelligence_router)


@app.get("/")
async def root():
    return {
        "message": "RideNow API is running"
    }

@app.get("/health")
async def health(db: AsyncSession = Depends(get_db)):
    try:
        result = await db.execute(text("SELECT 1"))

        return {
            "status": "healthy",
            "database": "connected",
            "redis": "in_memory_fallback" if is_using_fallback() else "connected",
            "result": result.scalar(),
        }


    except Exception as e:
        _logger.error(f"Database health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "database": "disconnected",
                "redis": "in_memory_fallback" if is_using_fallback() else "connected",
                "error": "Database connectivity check failed",
            },
        )


@app.get("/health/live")
async def health_live():
    """Liveness probe — checks only that the process is running (no I/O)."""
    return {"alive": True}


@app.get("/health/ready")
async def health_ready(db: AsyncSession = Depends(get_db)):
    """Readiness probe — checks DB connectivity and Redis availability."""
    db_ok = False
    redis_ok = not is_using_fallback()
    db_detail = "disconnected"
    redis_detail = "in_memory_fallback" if is_using_fallback() else "connected"

    try:
        await db.execute(text("SELECT 1"))
        db_ok = True
        db_detail = "connected"
    except Exception as e:
        _logger.error(f"Readiness DB check failed: {e}")

    ready = db_ok
    status_code = 200 if ready else 503
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ready" if ready else "not_ready",
            "database": db_detail,
            "redis": redis_detail,
        },
    )
