from __future__ import annotations

import logging
from datetime import datetime
from sqlalchemy.orm import Session

from app.embeddings import embed_texts
from app.repo import messages_missing_embeddings, save_embedding
from app.config import get_settings

logger = logging.getLogger(__name__)

def build_embeddings_for_period(db: Session, chat_ids: list[int], date_from: datetime, date_to: datetime, batch_size: int = 128) -> dict:
    s = get_settings()
    missing = messages_missing_embeddings(db, chat_ids, date_from, date_to, limit=50_000)
    logger.info("Messages missing embeddings: %d", len(missing))
    total = 0

    for i in range(0, len(missing), batch_size):
        batch = missing[i:i+batch_size]
        texts = [m.text for m in batch]
        vecs = embed_texts(texts)

        for m, v in zip(batch, vecs, strict=True):
            save_embedding(db, m.id, v, s.embedding_model_name)
            total += 1

        logger.info("Embeddings progress: %d/%d", min(i+batch_size, len(missing)), len(missing))

    return {"embedded": total, "missing_before": len(missing)}
