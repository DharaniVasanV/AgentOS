"""
app/services/embedder.py

STEP 3: Query Embedding Generator.
Generates 384-dimensional dense vector embeddings for query text without using an LLM.
"""

import math
import hashlib
from typing import List
from app.utils.logger import get_logger

logger = get_logger(__name__)

_MODEL = None
try:
    from sentence_transformers import SentenceTransformer
    _MODEL = SentenceTransformer("all-MiniLM-L6-v2")
except Exception as e:
    logger.warning("SentenceTransformer fallback initialized for query embedder (%s).", e)


def generate_query_embedding(query: str) -> List[float]:
    """Generates 384-dimensional vector embedding for user query."""
    if not query or not query.strip():
        return [0.0] * 384

    if _MODEL is not None:
        try:
            emb = _MODEL.encode(query, convert_to_numpy=True)
            return emb.tolist()
        except Exception as e:
            logger.warning("SentenceTransformer encode failed: %s", e)

    vec = [0.0] * 384
    words = query.lower().split()
    for idx, w in enumerate(words):
        h = int(hashlib.md5(w.encode('utf-8')).hexdigest(), 16)
        dim_idx = h % 384
        val = ((h >> 8) % 1000) / 1000.0
        vec[dim_idx] += val * (1.0 / (1.0 + idx * 0.05))

    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 0:
        vec = [v / norm for v in vec]
    return vec
