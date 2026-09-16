import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.database import engine
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

from fastapi.middleware.cors import CORSMiddleware

from app.core.exceptions import RideNowError
from app.core.config import settings
from app.core.redis import init_redis, close_redis, is_using_fallback


@asynccontextmanager
async def lifespan(app: FastAPI):
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
origins = settings.cors_origins_list

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception Handlers
@app.exception_handler(RideNowError)
async def ridenow_exception_handler(request: Request, exc: RideNowError):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": {
                "code": exc.error_code,
                "message": exc.message
            }
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

@app.get("/")
async def root():
    return {
        "message": "RideNow API is running"
    }

@app.get("/health")
async def health():
    try:
        async with engine.connect() as connection:
            result = await connection.execute(text("SELECT 1"))

        return {
            "status": "healthy",
            "database": "connected",
            "redis": "in_memory_fallback" if is_using_fallback() else "connected",
            "result": result.scalar(),
        }

    except Exception as e:
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "redis": "in_memory_fallback" if is_using_fallback() else "connected",
            "error": str(e),
        }
