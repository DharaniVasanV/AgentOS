"""
app/db/vector_search.py

STEP 4, 5, 6: Cosine Similarity Search Engine with Hybrid Semantic Matching.
Searches knowledge_vectors and returns Top 5 chunks sorted by highest similarity score.
"""

import os
import json
import math
import re
from typing import List, Dict, Any
from app.config.settings import get_settings
from app.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()

JSON_STORE_FILE = "e:/meeting-agent/knowledge_agent/ingestion/chroma_db/knowledge_store.json"


def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def keyword_overlap_score(query: str, text: str) -> float:
    query_words = set(re.findall(r"\w+", query.lower()))
    text_words = set(re.findall(r"\w+", text.lower()))
    if not query_words:
        return 0.0
    matches = query_words.intersection(text_words)
    return len(matches) / len(query_words)


def search_vector_database(query: str, query_embedding: List[float], top_k: int = 5) -> List[Dict[str, Any]]:
    """Searches vector database using Cosine Similarity + Hybrid Keyword-Semantic Scoring."""
    results_map = {}

    # 1. Try JSON persistent vector store
    if os.path.exists(JSON_STORE_FILE):
        try:
            with open(JSON_STORE_FILE, "r", encoding="utf-8") as f:
                items = json.load(f)

            for item in items:
                emb = item.get("embedding", [])
                text = item.get("text", "")
                meta = item.get("metadata", {})

                sim_vec = cosine_similarity(query_embedding, emb)
                sim_kw = keyword_overlap_score(query, text)
                
                # Hybrid similarity score (70% vector cosine, 30% keyword overlap)
                hybrid_score = (sim_vec * 0.7) + (sim_kw * 0.3)
                
                if sim_kw > 0.3 and hybrid_score < 0.6:
                    hybrid_score = min(0.95, sim_kw * 0.85)

                results_map[item["chunk_id"]] = {
                    "chunk_id": item["chunk_id"],
                    "document_id": item.get("document_id", "unknown_doc"),
                    "document_name": item.get("document_name") or meta.get("title", "Knowledge Document"),
                    "similarity_score": round(float(hybrid_score), 4),
                    "metadata": meta,
                    "original_text": text
                }
        except Exception as e:
            logger.warning("JSON store search error: %s", e)

    # 2. Try ChromaDB
    try:
        import chromadb
        if os.path.exists(settings.CHROMA_PERSIST_DIR):
            client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
            collection = client.get_or_create_collection(name="agentos_knowledge_base")
            count = collection.count()
            if count > 0:
                res = collection.query(
                    query_embeddings=[query_embedding],
                    n_results=min(top_k, count),
                    include=["documents", "metadatas", "distances"]
                )
                if res and res.get("ids") and res["ids"][0]:
                    ids = res["ids"][0]
                    docs = res["documents"][0]
                    metas = res["metadatas"][0]
                    distances = res["distances"][0]

                    for i in range(len(ids)):
                        dist = distances[i] if i < len(distances) else 0.5
                        sim = max(0.0, min(1.0, 1.0 - (dist / 2.0) if dist > 1.0 else (1.0 - dist)))
                        chunk_id = ids[i]
                        meta = metas[i] if i < len(metas) else {}
                        text = docs[i] if i < len(docs) else ""

                        kw_score = keyword_overlap_score(query, text)
                        final_sim = max(sim, kw_score * 0.85)

                        results_map[chunk_id] = {
                            "chunk_id": chunk_id,
                            "document_id": meta.get("document_id", "unknown_doc"),
                            "document_name": meta.get("title", "Knowledge Document"),
                            "similarity_score": round(float(final_sim), 4),
                            "metadata": meta,
                            "original_text": text
                        }
    except Exception as e:
        logger.warning("ChromaDB query fallback: %s", e)

    chunks = list(results_map.values())
    chunks.sort(key=lambda x: x["similarity_score"], reverse=True)
    return chunks[:top_k]
