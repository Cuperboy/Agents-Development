from __future__ import annotations

import logging
from sqlalchemy import text
from app.db import engine
from app.models import Base

logger = logging.getLogger(__name__)

def init_db() -> None:
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()

    Base.metadata.create_all(bind=engine)
    logger.info("DB schema ensured (tables + vector extension).")
