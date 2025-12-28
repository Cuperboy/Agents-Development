from __future__ import annotations

import logging
from functools import lru_cache
from sentence_transformers import SentenceTransformer

from app.config import get_settings

logger = logging.getLogger(__name__)

@lru_cache(maxsize=1)
def _model() -> SentenceTransformer:
    s = get_settings()
    logger.info("Loading embedding model: %s", s.embedding_model_name)
    return SentenceTransformer(s.embedding_model_name)

def embed_texts(texts: list[str]) -> list[list[float]]:
    m = _model()
    vecs = m.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return [v.tolist() for v in vecs]
