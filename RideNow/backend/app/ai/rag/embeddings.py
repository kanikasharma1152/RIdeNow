"""
RideNow — Embedding Model Provider
==================================
Provides fast, local sentence embeddings via sentence-transformers.
No external API calls or API keys required.
"""

import logging
from typing import List, Optional

logger = logging.getLogger(__name__)

_embedding_model = None


def get_embedding_model():
    """
    Singleton loader for sentence-transformers model.
    Model: all-MiniLM-L6-v2 (compact 80MB, fast, high semantic accuracy).
    """
    global _embedding_model
    if _embedding_model is None:
        from app.core.config import settings
        logger.info(f"Loading local embedding model: {settings.EMBEDDING_MODEL}...")
        try:
            from sentence_transformers import SentenceTransformer
            _embedding_model = SentenceTransformer(settings.EMBEDDING_MODEL)
            logger.info("Embedding model loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load sentence-transformers model: {e}")
            raise e
    return _embedding_model


def embed_texts(texts: List[str]) -> List[List[float]]:
    """Generate vector embeddings for a batch of text strings."""
    model = get_embedding_model()
    embeddings = model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
    return embeddings.tolist()


def embed_query(text: str) -> List[float]:
    """Generate vector embedding for a single query string."""
    model = get_embedding_model()
    embedding = model.encode(text, convert_to_numpy=True, show_progress_bar=False)
    return embedding.tolist()
