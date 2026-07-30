"""
app/services/embedder.py

STEP 7: Embedding Generator.
Generates 384-dimensional dense vector embeddings for text chunks.
"""

import math
import hashlib
from typing import List
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Try importing sentence_transformers
_MODEL = None
try:
    from sentence_transformers import SentenceTransformer
    logger.info("Initializing SentenceTransformer('all-MiniLM-L6-v2')...")
    _MODEL = SentenceTransformer("all-MiniLM-L6-v2")
except Exception as e:
    logger.warning("SentenceTransformers not immediately ready (%s). Using fallback 384d semantic vector generator.", e)


def generate_embedding(text: str) -> List[float]:
    """Generates 384-dimensional float vector for input text."""
    if not text:
        return [0.0] * 384

    if _MODEL is not None:
        try:
            emb = _MODEL.encode(text, convert_to_numpy=True)
            return emb.tolist()
        except Exception as e:
            logger.warning("SentenceTransformer encode error (%s). Falling back.", e)

    # Fast, deterministic 384-dimensional feature embedding generator
    vec = [0.0] * 384
    words = text.lower().split()
    for idx, w in enumerate(words):
        h = int(hashlib.md5(w.encode('utf-8')).hexdigest(), 16)
        dim_idx = h % 384
        val = ((h >> 8) % 1000) / 1000.0
        vec[dim_idx] += val * (1.0 / (1.0 + idx * 0.05))

    # Normalize vector to unit length (L2 norm)
    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 0:
        vec = [v / norm for v in vec]
    return vec
