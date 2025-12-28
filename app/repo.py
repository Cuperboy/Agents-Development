from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select, func, and_
from sqlalchemy.orm import Session

from app.models import Chat, Message, Summary, Embedding

def upsert_chats(db: Session, dialogs: list[dict]) -> int:
    count = 0
    for d in dialogs:
        peer_id = d["tg_peer_id"]
        existing = db.execute(select(Chat).where(Chat.tg_peer_id == peer_id)).scalar_one_or_none()
        if existing is None:
            db.add(
                Chat(
                    tg_peer_id=peer_id,
                    title=d["title"],
                    username=d.get("username"),
                    chat_type=d["chat_type"],
                    updated_at=d["updated_at"],
                )
            )
            count += 1
        else:
            existing.title = d["title"]
            existing.username = d.get("username")
            existing.chat_type = d["chat_type"]
            existing.updated_at = d["updated_at"]
    db.commit()
    return count

def list_chats(db: Session) -> list[Chat]:
    return list(db.execute(select(Chat).order_by(Chat.title.asc())).scalars().all())

def get_chat_by_id(db: Session, chat_id: int) -> Chat:
    chat = db.execute(select(Chat).where(Chat.id == chat_id)).scalar_one()
    return chat

def insert_messages(db: Session, chat_id: int, messages: list[dict]) -> tuple[int, int]:
    inserted = 0
    skipped = 0
    for m in messages:
        exists = db.execute(
            select(Message.id).where(and_(Message.chat_id == chat_id, Message.tg_msg_id == m["tg_msg_id"]))
        ).scalar_one_or_none()
        if exists is not None:
            skipped += 1
            continue

        db.add(
            Message(
                chat_id=chat_id,
                tg_msg_id=m["tg_msg_id"],
                dt=m["dt"],
                sender_id=m["sender_id"],
                sender_name=m["sender_name"],
                text=m["text"],
                reply_to_tg_msg_id=m["reply_to_tg_msg_id"],
                raw=m["raw"],
            )
        )
        inserted += 1

    db.commit()
    return inserted, skipped

def count_messages(db: Session, chat_ids: list[int], date_from: datetime, date_to: datetime) -> int:
    q = db.execute(
        select(func.count(Message.id)).where(
            and_(
                Message.chat_id.in_(chat_ids),
                Message.dt >= date_from,
                Message.dt <= date_to,
            )
        )
    ).scalar_one()
    return int(q)

def load_messages(db: Session, chat_ids: list[int], date_from: datetime, date_to: datetime) -> list[Message]:
    rows = db.execute(
        select(Message)
        .where(
            and_(
                Message.chat_id.in_(chat_ids),
                Message.dt >= date_from,
                Message.dt <= date_to,
            )
        )
        .order_by(Message.dt.asc())
    ).scalars().all()
    return list(rows)

def messages_missing_embeddings(db: Session, chat_ids: list[int], date_from: datetime, date_to: datetime, limit: int = 5000) -> list[Message]:
    rows = db.execute(
        select(Message)
        .outerjoin(Embedding, Embedding.message_id == Message.id)
        .where(
            and_(
                Message.chat_id.in_(chat_ids),
                Message.dt >= date_from,
                Message.dt <= date_to,
                Embedding.id.is_(None),
                Message.text != "",
            )
        )
        .order_by(Message.dt.asc())
        .limit(limit)
    ).scalars().all()
    return list(rows)

def save_embedding(db: Session, message_id: int, vector: list[float], model_name: str) -> None:
    db.add(Embedding(message_id=message_id, embedding=vector, model_name=model_name))
    db.commit()

def _chat_ids_key(chat_ids: list[int]) -> str:
    return ",".join(str(x) for x in sorted(chat_ids))

def upsert_summary(
    db: Session,
    chat_ids: list[int],
    date_from: datetime,
    date_to: datetime,
    provider: str,
    model: str,
    prompt_version: str,
    summary_json: dict,
    summary_md: str,
) -> Summary:
    key = _chat_ids_key(chat_ids)
    existing = db.execute(
        select(Summary).where(
            and_(
                Summary.chat_ids_key == key,
                Summary.date_from == date_from,
                Summary.date_to == date_to,
                Summary.provider == provider,
                Summary.model == model,
                Summary.prompt_version == prompt_version,
            )
        )
    ).scalar_one_or_none()

    now = datetime.now(timezone.utc)
    if existing is None:
        s = Summary(
            chat_ids_key=key,
            date_from=date_from,
            date_to=date_to,
            provider=provider,
            model=model,
            prompt_version=prompt_version,
            summary_json=summary_json,
            summary_md=summary_md,
            created_at=now,
        )
        db.add(s)
        db.commit()
        db.refresh(s)
        return s

    existing.summary_json = summary_json
    existing.summary_md = summary_md
    existing.created_at = now
    db.commit()
    db.refresh(existing)
    return existing

def get_latest_summary(db: Session, chat_ids: list[int], date_from: datetime, date_to: datetime) -> Summary | None:
    key = _chat_ids_key(chat_ids)
    return db.execute(
        select(Summary)
        .where(and_(Summary.chat_ids_key == key, Summary.date_from == date_from, Summary.date_to == date_to))
        .order_by(Summary.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()
