from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select, bindparam
from sqlalchemy.orm import Session

from pgvector.sqlalchemy import Vector

from app.config import get_settings
from app.embeddings import embed_texts
from app.models import Message, Embedding, Chat
from app.llm import chat_completion


@dataclass
class QASource:
    chat_title: str
    tg_msg_id: int
    dt_iso: str
    sender_name: str | None
    text: str
    score: float


def retrieve_top_messages(
    db: Session,
    chat_ids: list[int],
    date_from,
    date_to,
    question: str,
    top_k: int = 18,
) -> list[dict[str, Any]]:
    """
    Возвращает top_k сообщений, наиболее близких к вопросу по эмбеддингам.
    """
    s = get_settings()

    # 1) эмбеддинг вопроса
    qvec = embed_texts([question])[0]

    # гарантируем python list[float]
    qvec = [float(x) for x in qvec]

    # 2) биндим параметр как Vector(dim)
    qvec_param = bindparam("qvec", qvec, type_=Vector(s.embedding_dim))

    # 3) cosine_distance: чем меньше, тем ближе
    distance = Embedding.embedding.cosine_distance(qvec_param).label("distance")

    stmt = (
        select(
            Message.id.label("message_id"),
            Message.chat_id.label("chat_id"),
            Message.tg_msg_id.label("tg_msg_id"),
            Message.dt.label("dt"),
            Message.sender_name.label("sender_name"),
            Message.text.label("text"),
            distance,
        )
        .join(Embedding, Embedding.message_id == Message.id)
        .where(Message.chat_id.in_(chat_ids))
        .where(Message.dt >= date_from)
        .where(Message.dt <= date_to)
        .order_by(distance.asc())
        .limit(top_k)
    )

    rows = db.execute(stmt).mappings().all()
    return [dict(r) for r in rows]


def answer_question(db: Session, chat_ids: list[int], date_from, date_to, question: str, top_k: int = 18) -> str:
    """
    RAG: находим топ сообщений, собираем контекст, спрашиваем LLM, возвращаем ответ + источники.
    """
    rows = retrieve_top_messages(db, chat_ids, date_from, date_to, question, top_k=top_k)

    if not rows:
        return "Нет сообщений с эмбеддингами за выбранный период"

    # Подтянем названия чатов для источников
    chats = db.execute(select(Chat.id, Chat.title).where(Chat.id.in_(chat_ids))).all()
    chat_title_by_id = {int(c[0]): str(c[1]) for c in chats}

    sources: list[QASource] = []
    context_lines: list[str] = []

    for r in rows:
        chat_title = chat_title_by_id.get(int(r["chat_id"]), f"chat_id={r['chat_id']}")
        text = (r["text"] or "").strip()
        dt_iso = r["dt"].isoformat() if r["dt"] is not None else ""
        tg_msg_id = int(r["tg_msg_id"])
        sender_name = r.get("sender_name")
        dist = float(r["distance"])

        # dist: меньше = ближе, а score - наоборот
        score = 1.0 - dist

        sources.append(
            QASource(
                chat_title=chat_title,
                tg_msg_id=tg_msg_id,
                dt_iso=dt_iso,
                sender_name=str(sender_name) if sender_name else None,
                text=text,
                score=score,
            )
        )

        # Контекст для LLM
        who = f"{sources[-1].sender_name}: " if sources[-1].sender_name else ""
        context_lines.append(
            f"[{chat_title} | tg_msg_id={tg_msg_id} | {dt_iso}] {who}{text}"
        )

    system = (
        "Ты — помощник, ТОЛЬКО анализирующий историю чатов в Telegram и отвечающий на различные вопросы, связанные с историей чатов.\n"
        "Если ответа нет в контексте — скажи, что данных недостаточно.\n"
    )

    user = (
        f"Вопрос: {question}\n\n"
        "Контекст:\n"
        + "\n".join(context_lines)
    )

    answer = chat_completion(system=system, user=user)

    # Источники
    src_lines = []
    for s in sources[: min(len(sources), 5)]:
        src_lines.append(f"- {s.chat_title}: tg_msg_id={s.tg_msg_id} (score={s.score:.3f})")
    answer += "\n\nИсточники:\n" + "\n".join(src_lines)
    return answer
