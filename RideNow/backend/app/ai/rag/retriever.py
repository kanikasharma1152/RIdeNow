"""
RideNow — Knowledge Retriever
=============================
Queries ChromaDB vector collection using local query embeddings.
Returns structured relevant snippets for the AI agent context.
"""

import logging
from typing import List, Dict, Any, Optional

from app.core.config import settings
from app.ai.rag.embeddings import embed_query
from app.ai.rag.ingestion import get_or_create_collection

logger = logging.getLogger(__name__)


def retrieve_relevant_knowledge(query: str, top_k: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Search the RideNow knowledge base for information relevant to the query.
    Returns a list of dicts with keys: 'text', 'source', 'section', 'distance'.
    """
    if not settings.RAG_ENABLED:
        return []

    k = top_k or settings.RAG_TOP_K

    try:
        collection = get_or_create_collection()
        if collection.count() == 0:
            logger.warning("Knowledge collection is empty. Returning no results.")
            return []

        query_vector = embed_query(query)

        results = collection.query(
            query_embeddings=[query_vector],
            n_results=min(k, collection.count()),
            include=["documents", "metadatas", "distances"],
        )

        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        snippets = []
        for doc, meta, dist in zip(documents, metadatas, distances):
            snippets.append({
                "text": doc,
                "source": meta.get("source", "unknown"),
                "section": meta.get("section", ""),
                "distance": dist,
            })

        return snippets

    except Exception as e:
        logger.error(f"Error during knowledge retrieval: {e}")
        return []


def format_knowledge_context(snippets: List[Dict[str, Any]]) -> str:
    """Format retrieved snippets into a concise markdown context block for LLM prompts."""
    if not snippets:
        return ""

    lines = ["### Official RideNow Policy & Knowledge Documents:"]
    for i, s in enumerate(snippets, 1):
        source = s.get("source", "")
        section = s.get("section", "")
        lines.append(f"\n--- Document {i} (Source: {source} | {section}) ---")
        lines.append(s["text"].strip())

    return "\n".join(lines)
