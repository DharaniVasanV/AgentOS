"""
app/db/vector_store.py

STEP 8 & 9: Vector Store Storage & Indexing Manager using ChromaDB & Local Vector Storage.
Stores embeddings, metadata, chunk text, and document information.
"""

import os
import json
from typing import List, Dict, Any
from app.config.settings import get_settings
from app.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()

_CHROMA_CLIENT = None
_COLLECTION = None
JSON_STORE_FILE = "e:/meeting-agent/knowledge_agent/ingestion/chroma_db/knowledge_store.json"


def get_vector_collection():
    global _CHROMA_CLIENT, _COLLECTION
    if _COLLECTION is not None:
        return _COLLECTION

    try:
        import chromadb
        os.makedirs(settings.CHROMA_PERSIST_DIR, exist_ok=True)
        _CHROMA_CLIENT = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
        _COLLECTION = _CHROMA_CLIENT.get_or_create_collection(
            name="agentos_knowledge_base"
        )
        logger.info("🟢 ChromaDB Persistent Client connected at '%s'", settings.CHROMA_PERSIST_DIR)
        return _COLLECTION
    except Exception as e:
        logger.warning("⚠️ ChromaDB client initialization deferred (%s). Using JSON vector store.", e)
        return None


def store_in_json_store(document_id: str, chunks: List[Dict[str, Any]], embeddings: List[List[float]], doc_metadata: Dict[str, Any]):
    os.makedirs(os.path.dirname(JSON_STORE_FILE), exist_ok=True)
    existing = []
    if os.path.exists(JSON_STORE_FILE):
        try:
            with open(JSON_STORE_FILE, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except Exception:
            existing = []

    for i, c in enumerate(chunks):
        item = {
            "chunk_id": f"{document_id}_chunk_{i}",
            "document_id": str(document_id),
            "document_name": doc_metadata.get("title", "Knowledge Document"),
            "text": c["text"],
            "embedding": embeddings[i] if i < len(embeddings) else [0.0]*384,
            "metadata": doc_metadata
        }
        existing.append(item)

    with open(JSON_STORE_FILE, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2)
    logger.info("🟢 Persisted %d chunks to JSON vector store at '%s'", len(chunks), JSON_STORE_FILE)


def store_chunks_in_vector_db(
    document_id: str,
    chunks: List[Dict[str, Any]],
    embeddings: List[List[float]],
    doc_metadata: Dict[str, Any]
) -> bool:
    """Stores chunks and embeddings inside vector database and persistent JSON backup."""
    store_in_json_store(document_id, chunks, embeddings, doc_metadata)

    collection = get_vector_collection()
    if collection is not None:
        try:
            ids = [f"{document_id}_chunk_{i}" for i in range(len(chunks))]
            documents = [c["text"] for c in chunks]
            metadatas = []

            for i, c in enumerate(chunks):
                meta = {
                    "document_id": str(document_id),
                    "user_id": doc_metadata.get("user_id", "user_default"),
                    "document_type": doc_metadata.get("document_type", "Unknown"),
                    "title": doc_metadata.get("title", "Untitled Document"),
                    "source_agent": doc_metadata.get("source_agent", "Manual Upload"),
                    "chunk_index": i,
                }
                metadatas.append(meta)

            collection.upsert(
                ids=ids,
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas
            )
            logger.info("🟢 Stored %d chunk vectors in ChromaDB collection 'agentos_knowledge_base'", len(ids))
        except Exception as e:
            logger.warning("ChromaDB upsert fallback (%s). JSON backup maintained.", e)

    return True
