from __future__ import annotations

import logging
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.telegram_client import list_dialogs, fetch_messages
from app.repo import upsert_chats, insert_messages
from app.models import Chat

logger = logging.getLogger(__name__)

async def sync_chats(db: Session) -> int:
    dialogs = await list_dialogs()
    added = upsert_chats(db, dialogs)
    logger.info("Chats synced. New: %d, total dialogs seen: %d", added, len(dialogs))
    return added

async def ingest_period(db: Session, chat_ids: list[int], date_from: datetime, date_to: datetime) -> dict:
    if date_from.tzinfo is None:
        date_from = date_from.replace(tzinfo=timezone.utc)
    if date_to.tzinfo is None:
        date_to = date_to.replace(tzinfo=timezone.utc)

    results = {"total_inserted": 0, "total_skipped": 0, "by_chat": []}

    chats = [db.get(Chat, cid) for cid in chat_ids]
    chats = [c for c in chats if c is not None]

    for c in chats:
        msgs = await fetch_messages(c.tg_peer_id, date_from, date_to)
        ins, sk = insert_messages(db, c.id, msgs)
        results["total_inserted"] += ins
        results["total_skipped"] += sk
        results["by_chat"].append({"chat": c.title, "inserted": ins, "skipped": sk, "fetched": len(msgs)})

    logger.info("Ingest done. Inserted=%d skipped=%d", results["total_inserted"], results["total_skipped"])
    return results
