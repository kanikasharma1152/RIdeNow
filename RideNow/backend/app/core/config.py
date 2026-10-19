"""
RideNow — Central Configuration
================================
All environment variables are loaded here via pydantic-settings.
Defaults are chosen so the app starts without any AI keys configured
(LLM and Redis features degrade gracefully).
"""
from functools import lru_cache
from typing import Optional
from urllib.parse import unquote

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine.url import make_url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Environment ────────────────────────────────────────────────
    ENVIRONMENT: str = "development"

    # ── Core Database ──────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@localhost:5432/ridenow_db"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 1800

    # ── JWT Auth ───────────────────────────────────────────────────
    SECRET_KEY: str = "change-this-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # ── Google OAuth (Phase 2) ─────────────────────────────────────
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None
    GOOGLE_REDIRECT_URI: Optional[str] = "http://localhost:5173"

    # ── CORS ───────────────────────────────────────────────────────
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:5174,http://localhost:5175"

    # ── Redis ──────────────────────────────────────────────────────
    # Set REDIS_URL to enable Redis-backed features.
    # If not set, the app falls back to in-memory dicts (development only).
    REDIS_URL: Optional[str] = None
    REDIS_CHAT_TTL_SECONDS: int = 3600          # Chat session memory TTL (1 hour)
    REDIS_RATE_LIMIT_REQUESTS: int = 30         # Max AI requests per window
    REDIS_RATE_LIMIT_WINDOW_SECONDS: int = 60   # Rate-limit window

    # ── LLM Provider (Primary: Groq) ──────────────────────────────
    LLM_PROVIDER: str = "groq"
    GROQ_MODEL: str = "openai/gpt-oss-20b"       # Ultra-fast 48ms inference with native tool calling
    GROQ_API_KEY: Optional[str] = None
    GROQ_TIMEOUT_SECONDS: float = 30.0          # Hard timeout for LLM inference (Phase 14)
    LLM_TEMPERATURE: float = 0.2                # Low temp for factual tool responses
    LLM_MAX_TOKENS: int = 1024

    # Optional secondary providers
    OPENAI_API_KEY: Optional[str] = None
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.2"

    # ── LiveKit Voice (Phase 5) ────────────────────────────────────
    LIVEKIT_URL: Optional[str] = None
    LIVEKIT_API_KEY: Optional[str] = None
    LIVEKIT_API_SECRET: Optional[str] = None
    LIVEKIT_TOKEN_TTL_MINUTES: int = 60

    # ── Cartesia STT & TTS ─────────────────────────────────────────
    CARTESIA_API_KEY: Optional[str] = None
    CARTESIA_VOICE_ID: str = "f786b574-daa5-4673-aa0c-cbe3e8534c02"  # Fast natural assistant voice
    CARTESIA_MODEL: str = "sonic-3"                                   # Ultra low-latency natural TTS
    CARTESIA_STT_MODEL: str = "ink-whisper"                           # Low-latency streaming STT (multilingual: en, hi)

    # ── AI / RAG Settings ──────────────────────────────────────────
    # ChromaDB collection name for the knowledge base
    CHROMA_COLLECTION_NAME: str = "ridenow_knowledge"
    # Path to persist ChromaDB data (relative to backend/ root)
    CHROMA_PERSIST_DIR: str = "./chroma_db"
    # Sentence-transformers model for local embeddings (no API key needed)
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    # Max number of RAG chunks to retrieve per query
    RAG_TOP_K: int = 4

    # ── Chat Agent Settings ────────────────────────────────────────
    # Max conversation history turns kept in memory (per user)
    CHAT_MAX_HISTORY_TURNS: int = 10
    # Max agent reasoning steps before giving up
    AGENT_MAX_ITERATIONS: int = 6

    # ── Feature Flags ─────────────────────────────────────────────
    AI_CHAT_ENABLED: bool = True
    WEBSOCKET_ENABLED: bool = True
    RAG_ENABLED: bool = True

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() in ("production", "prod")

    def validate_production_configuration(self) -> None:
        """Fail fast if insecure defaults, placeholders, or weak credentials are used in production."""
        if not self.is_production:
            return

        # 1. Enforce non-default, explicit SECRET_KEY
        known_placeholders = {
            "change-this-in-production",
            "change-this-in-production-to-a-strong-random-secret",
            "ridenow-super-secret-key-change-this-in-production",
            "secret",
            "secretkey",
            "your-secret-key",
            "replace_with_secure_random_key",
        }
        secret = (self.SECRET_KEY or "").strip()
        if not secret or secret.lower() in known_placeholders or len(secret) < 32:
            raise ValueError(
                "Production SECRET_KEY is missing, too short (<32 chars), or set to a placeholder. "
                "In production, configure an explicit secret generated via a cryptographically secure generator "
                "(e.g. 'python -c \"import secrets; print(secrets.token_hex(32))\"')."
            )

        # 2. Structural parsing and validation of production DATABASE_URL
        try:
            parsed_url = make_url(self.DATABASE_URL)
        except Exception:
            raise ValueError("Invalid production DATABASE_URL: unable to parse connection URL.")

        if not parsed_url.drivername.startswith("postgresql+asyncpg"):
            raise ValueError(
                "Production DATABASE_URL must explicitly use the asyncpg driver: 'postgresql+asyncpg://...'"
            )

        if not parsed_url.host or parsed_url.host.lower() in ("localhost", "127.0.0.1", "0.0.0.0"):
            raise ValueError("Production DATABASE_URL must connect to an external production host, not localhost or loopback.")

        if not parsed_url.username or not parsed_url.username.strip():
            raise ValueError("Production DATABASE_URL must specify a database username.")

        raw_password = unquote(parsed_url.password or "").strip()
        weak_passwords = {"password", "postgres", "admin", "root", "123456", "change-me", "default"}
        if not raw_password or raw_password.lower() in weak_passwords or len(raw_password) < 8:
            raise ValueError("Production DATABASE_URL must use a strong, non-default database password (minimum 8 characters).")

        if not parsed_url.database or parsed_url.database.strip() in ("", "/"):
            raise ValueError("Production DATABASE_URL must specify a target database name.")

        if parsed_url.port is not None and not (1 <= parsed_url.port <= 65535):
            raise ValueError("Production DATABASE_URL specifies an out-of-range port number.")

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def cors_origin_regex(self) -> Optional[str]:
        """In production, disallow loose localhost regex."""
        if self.is_production:
            return None
        return r"https?://(localhost|127\.0\.0\.1)(:\d+)?"

    @property
    def llm_api_key(self) -> Optional[str]:
        """Return the API key for the configured provider."""
        mapping = {
            "groq": self.GROQ_API_KEY,
            "openai": self.OPENAI_API_KEY,
            "ollama": None,
        }
        return mapping.get(self.LLM_PROVIDER.lower())

    @property
    def is_llm_configured(self) -> bool:
        """True if an LLM provider is ready to use."""
        provider = self.LLM_PROVIDER.lower()
        if provider == "ollama":
            return True
        return bool(self.llm_api_key and not self.llm_api_key.startswith("your-"))

    @property
    def is_livekit_configured(self) -> bool:
        """True if LiveKit voice credentials are fully configured."""
        return bool(
            self.LIVEKIT_URL
            and self.LIVEKIT_API_KEY
            and self.LIVEKIT_API_SECRET
            and not self.LIVEKIT_API_KEY.startswith("your-")
        )

    @property
    def is_cartesia_configured(self) -> bool:
        """True if Cartesia API credentials are configured."""
        return bool(
            self.CARTESIA_API_KEY
            and not self.CARTESIA_API_KEY.startswith("your-")
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings singleton — reads .env once."""
    return Settings()


# Convenience import: `from app.core.config import settings`
settings = get_settings()
