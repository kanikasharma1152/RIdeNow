"""
RideNow — Central Configuration
================================
All environment variables are loaded here via pydantic-settings.
Defaults are chosen so the app starts without any AI keys configured
(LLM and Redis features degrade gracefully).
"""
from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Core Database ──────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@localhost:5432/ridenow_db"

    # ── JWT Auth ───────────────────────────────────────────────────
    SECRET_KEY: str = "change-this-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

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
    GROQ_MODEL: str = "openai/gpt-oss-120b"     # High-speed inference with native tool calling
    GROQ_API_KEY: Optional[str] = None
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
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

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
