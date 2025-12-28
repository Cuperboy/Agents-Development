from __future__ import annotations
import json
import logging
from datetime import datetime, timezone

from telethon import TelegramClient
from telethon.tl.types import Channel, Chat, User

from app.config import get_settings

logger = logging.getLogger(__name__)

def make_client() -> TelegramClient:
    s = get_settings()
    client = TelegramClient(
        s.telethon_session_path,
        s.telegram_api_id,
        s.telegram_api_hash,
    )
    return client

def _peer_type(entity) -> str:
    if isinstance(entity, User):
        return "user"
    if isinstance(entity, Chat):
        return "group"
    if isinstance(entity, Channel):
        return "channel"
    return "unknown"

async def list_dialogs() -> list[dict]:
    client = make_client()
    async with client:
        dialogs = []
        async for d in client.iter_dialogs():
            e = d.entity
            dialogs.append(
                {
                    "tg_peer_id": int(e.id),
                    "title": (getattr(e, "title", None) or getattr(e, "first_name", "") or "Без названия"),
                    "username": getattr(e, "username", None),
                    "chat_type": _peer_type(e),
                    "updated_at": datetime.now(timezone.utc),
                }
            )
        return dialogs

async def resolve_entity(peer_id: int):
    client = make_client()
    async with client:
        entity = await client.get_entity(peer_id)
        return entity

async def fetch_messages(peer_id: int, date_from: datetime, date_to: datetime) -> list[dict]:
    """
    Возвращает сообщения в диапазоне [date_from, date_to] (включительно).

    Надёжная стратегия:
    - iter_messages(..., reverse=True) идёт от старых к новым
    - offset_date=date_from стартует рядом с началом периода
    - как только dt > date_to -> break
    """
    if date_from.tzinfo is None or date_to.tzinfo is None:
        raise ValueError("date_from/date_to должны быть timezone-aware (UTC или др).")

    client = make_client()
    async with client:
        entity = await client.get_entity(peer_id)

        msgs: list[dict] = []
        async for m in client.iter_messages(entity, offset_date=date_from, reverse=True):
            if m is None or m.date is None:
                continue

            dt = m.date
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)

            # пропускаем то, что строго раньше начала периода
            if dt < date_from: continue

            # как только вышли за конец периода — стоп (дальше только новее)
            if dt > date_to: break

            text = m.message or ""

            sender_id = None
            sender_name = None
            try:
                sender = await m.get_sender()
            except Exception:
                sender = None

            if sender is not None:
                sender_id = getattr(sender, "id", None)
                if getattr(sender, "username", None):
                    sender_name = "@" + str(sender.username)
                else:
                    fn = getattr(sender, "first_name", "") or ""
                    ln = getattr(sender, "last_name", "") or ""
                    full = (fn + " " + ln).strip()
                    sender_name = full if full else None

            reply_to = None
            if getattr(m, "reply_to", None) and getattr(m.reply_to, "reply_to_msg_id", None):
                reply_to = int(m.reply_to.reply_to_msg_id)
            
            raw = m.to_dict()
            raw = json.loads(json.dumps(raw, default=str))

            msgs.append(
                {
                    "tg_msg_id": int(m.id),
                    "dt": dt,
                    "sender_id": int(sender_id) if sender_id is not None else None,
                    "sender_name": sender_name,
                    "text": text,
                    "reply_to_tg_msg_id": reply_to,
                    "raw": raw,
                }
            )

        msgs.sort(key=lambda x: x["dt"])
        logger.info("Fetched %d messages for peer_id=%s", len(msgs), peer_id)
        return msgs
