"""
RideNow — Knowledge Ingestion Pipeline
======================================
Parses markdown documentation from backend/knowledge/,
chunks sections intelligently, computes local vector embeddings,
and indexes documents in ChromaDB.
"""

import os
import re
import logging
from pathlib import Path
from typing import List, Dict, Any

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.core.config import settings
from app.ai.rag.embeddings import embed_texts

logger = logging.getLogger(__name__)

KNOWLEDGE_DIR = Path(__file__).resolve().parent.parent.parent.parent / "knowledge"


def get_chroma_client():
    """Returns a persistent ChromaDB client."""
    persist_path = Path(settings.CHROMA_PERSIST_DIR).resolve()
    persist_path.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(persist_path))


def get_or_create_collection():
    """Fetches or creates the RideNow knowledge collection."""
    client = get_chroma_client()
    return client.get_or_create_collection(
        name=settings.CHROMA_COLLECTION_NAME,
        metadata={"description": "RideNow platform FAQ, policies, safety, and guides"},
    )


def chunk_markdown_file(file_path: Path) -> List[Dict[str, Any]]:
    """
    Chunks a markdown file by headers and logical sections.
    Preserves document title, section headers, and file source metadata.
    """
    text = file_path.read_text(encoding="utf-8")
    doc_name = file_path.stem

    # Extract top title if present (# Title)
    top_title_match = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    doc_title = top_title_match.group(1).strip() if top_title_match else doc_name

    # Split into sections based on ## or ### headers
    sections = re.split(r"(?=(?:^|\n)##\s+)", text)
    chunks = []

    for idx, sec in enumerate(sections):
        cleaned = sec.strip()
        if not cleaned or cleaned.startswith("# "):
            # Skip empty or top title only chunks
            continue

        # Extract section subtitle if any
        sec_header_match = re.match(r"^##\s+(.+)$", cleaned, re.MULTILINE)
        section_title = sec_header_match.group(1).strip() if sec_header_match else f"Section {idx}"

        # Prefix with document title context for better semantic retrieval
        enriched_content = f"[{doc_title} - {section_title}]\n{cleaned}"

        chunks.append({
            "id": f"{doc_name}_chunk_{idx}",
            "text": enriched_content,
            "metadata": {
                "source": file_path.name,
                "document": doc_title,
                "section": section_title,
                "chunk_index": idx,
            },
        })

    return chunks


def ingest_all_knowledge(force_reload: bool = False) -> int:
    """
    Ingests all knowledge documents from backend/knowledge/ into ChromaDB.
    If collection already has documents and not force_reload, skips.
    Returns count of chunks indexed.
    """
    collection = get_or_create_collection()
    current_count = collection.count()

    if current_count > 0 and not force_reload:
        logger.info(f"Knowledge base already indexed ({current_count} chunks). Skipping ingestion.")
        return current_count

    if not KNOWLEDGE_DIR.exists():
        logger.warning(f"Knowledge directory {KNOWLEDGE_DIR} does not exist.")
        return 0

    all_chunks = []
    for md_file in KNOWLEDGE_DIR.glob("*.md"):
        chunks = chunk_markdown_file(md_file)
        all_chunks.extend(chunks)

    if not all_chunks:
        logger.warning("No markdown knowledge chunks found to ingest.")
        return 0

    logger.info(f"Indexing {len(all_chunks)} knowledge chunks into ChromaDB...")

    texts = [c["text"] for c in all_chunks]
    ids = [c["id"] for c in all_chunks]
    metadatas = [c["metadata"] for c in all_chunks]

    # Generate embeddings
    embeddings = embed_texts(texts)

    # Upsert into ChromaDB
    collection.upsert(
        ids=ids,
        documents=texts,
        embeddings=embeddings,
        metadatas=metadatas,
    )

    logger.info(f"Successfully indexed {len(all_chunks)} chunks in ChromaDB collection '{settings.CHROMA_COLLECTION_NAME}'.")
    return len(all_chunks)


if __name__ == "__main__":
    count = ingest_all_knowledge(force_reload=True)
    print(f"Total chunks indexed: {count}")
