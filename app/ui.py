from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

import gradio as gr
import pandas as pd
from sqlalchemy.orm import Session

from app.logging_setup import setup_logging
from app.migrate import init_db
from app.db import SessionLocal
from app.repo import list_chats, count_messages
from app.ingestion import sync_chats, ingest_period
from app.build_embeddings import build_embeddings_for_period
from app.summarization import generate_summary
from app.qa import answer_question

import traceback

logger = logging.getLogger(__name__)

def _utc_dt(date_str: str, end: bool = False) -> datetime:
    # date_str: "YYYY-MM-DD"
    dt = datetime.fromisoformat(date_str)
    if end:
        dt = dt.replace(hour=23, minute=59, second=59)
    else:
        dt = dt.replace(hour=0, minute=0, second=0)
    return dt.replace(tzinfo=timezone.utc)

def _chat_choices(db: Session) -> list[tuple[str, int]]:
    chats = list_chats(db)
    return [(f"{c.title} ({c.chat_type})", c.id) for c in chats]

def _sync_chats_ui() -> tuple[pd.DataFrame, str]:
    db = SessionLocal()
    try:
        added = asyncio.run(sync_chats(db))
        chats = list_chats(db)
        df = pd.DataFrame([{
            "id": c.id,
            "title": c.title,
            "type": c.chat_type,
            "username": c.username,
            "tg_peer_id": c.tg_peer_id,
            "updated_at": c.updated_at.isoformat(),
        } for c in chats])
        return df, f"Синхронизация завершена. Новых чатов: {added}. Всего в базе: {len(chats)}."
    finally:
        db.close()

def _ingest_ui(chat_ids: list[int], date_from: str, date_to: str) -> str:
    db = SessionLocal()
    try:
        df = _utc_dt(date_from, end=False)
        dt = _utc_dt(date_to, end=True)
        res = asyncio.run(ingest_period(db, chat_ids, df, dt))
        lines = [
            f"Итог: inserted={res['total_inserted']} skipped={res['total_skipped']}",
            "",
        ]
        for b in res["by_chat"]:
            lines.append(f"- {b['chat']}: fetched={b['fetched']} inserted={b['inserted']} skipped={b['skipped']}")
        return "\n".join(lines)
    except Exception:
        logger.exception("Ошибка при сборе сообщений")
        return "Ошибка при сборе сообщений:\n\n" + traceback.format_exc()
    finally:
        db.close()


def _embed_ui(chat_ids: list[int], date_from: str, date_to: str) -> str:
    db = SessionLocal()
    try:
        df = _utc_dt(date_from, end=False)
        dt = _utc_dt(date_to, end=True)
        res = build_embeddings_for_period(db, chat_ids, df, dt, batch_size=128)
        return f"Построено новых эмбеддингов: {res['embedded']}."
    except Exception:
        logger.exception("Ошибка при построении эмбеддингов")
        return "Ошибка при построении эмбеддингов:\n\n" + traceback.format_exc()
    finally:
        db.close()

def _count_ui(chat_ids: list[int], date_from: str, date_to: str) -> str:
    db = SessionLocal()
    try:
        df = _utc_dt(date_from, end=False)
        dt = _utc_dt(date_to, end=True)
        n = count_messages(db, chat_ids, df, dt)
        return f"Сообщений в Базе Данных за период: {n}"
    finally:
        db.close()

def _summary_ui(chat_ids: list[int], date_from: str, date_to: str) -> tuple[str, str]:
    db = SessionLocal()
    try:
        df = _utc_dt(date_from, end=False)
        dt = _utc_dt(date_to, end=True)
        js, md = generate_summary(db, chat_ids, df, dt)
        return md, str(js)
    finally:
        db.close()

def _qa_respond(chat_ids: list[int], date_from: str, date_to: str, history: list[tuple[str, str]], question: str,):
    db = SessionLocal()
    try:
        if history is None:
            history = []

        df = _utc_dt(date_from, end=False)
        dt = _utc_dt(date_to, end=True)

        ans = answer_question(db, chat_ids, df, dt, question)

        # ans может быть str или (answer, sources) — делаем устойчиво
        if isinstance(ans, tuple) and len(ans) == 2:
            answer_text, sources_text = ans
            answer_text = str(answer_text)
            sources_text = str(sources_text).strip()
            if sources_text:
                answer_text += "\n\nИсточники:\n" + sources_text
        else:
            answer_text = str(ans)

        history = history + [(question, answer_text)]
        return history, ""

    except Exception:
        logger.exception("Ошибка в QA/Вопросы")
        err = "Ошибка в QA:\n\n" + traceback.format_exc()
        history = (history or []) + [(question, err)]
        return history, ""

    finally:
        db.close()


def build_app() -> gr.Blocks:
    setup_logging()
    init_db()

    with gr.Blocks(title="Telegram Chat Analyzer") as demo:
        gr.Markdown("# Анализ чатов в Telegram\nОбновление чатов -> Сбор -> Эмбеддинги -> Summary -> Questions & Answering\n")

        with gr.Tab("Чаты"):
            btn_sync = gr.Button("Синхронизировать список чатов из Telegram")
            out_df = gr.Dataframe(interactive=False, wrap=True)
            out_msg = gr.Textbox(label="Статус", lines=3)
            btn_sync.click(fn=_sync_chats_ui, inputs=[], outputs=[out_df, out_msg])

        with gr.Tab("Сбор данных"):
            gr.Markdown("Выбери чаты и период. Необходима синхронизация чатов на вкладке 'Чаты'.")
            with gr.Row():
                chat_sel = gr.Dropdown(choices=[], multiselect=True, label="Чаты")
                date_from = gr.Textbox(label="Дата начала (YYYY-MM-DD)", value="2025-12-01")
                date_to = gr.Textbox(label="Дата конца (YYYY-MM-DD)", value="2025-12-24")

            btn_refresh = gr.Button("Обновить список чатов в выпадающем списке")
            btn_count = gr.Button("Посчитать сообщения за период (если данные есть в БД)")
            btn_ingest = gr.Button("Собрать сообщения из Telegram за период (Добавитьв БД)")

            out_count = gr.Textbox(label="Кол-во", lines=2)
            out_ingest = gr.Textbox(label="Логи сбора", lines=12)

            def _refresh_choices():
                db = SessionLocal()
                try:
                    return gr.Dropdown(choices=_chat_choices(db))
                finally:
                    db.close()

            btn_refresh.click(fn=_refresh_choices, inputs=[], outputs=[chat_sel])
            btn_count.click(fn=_count_ui, inputs=[chat_sel, date_from, date_to], outputs=[out_count])
            btn_ingest.click(fn=_ingest_ui, inputs=[chat_sel, date_from, date_to], outputs=[out_ingest])

        with gr.Tab("Эмбеддинги"):
            gr.Markdown("Построение эмбеддингов, чтобы работал поиск и Question Answering (QA).")
            with gr.Row():
                chat_sel_e = gr.Dropdown(choices=[], multiselect=True, label="Чаты")
                date_from_e = gr.Textbox(label="Дата начала (YYYY-MM-DD)", value="2025-12-01")
                date_to_e = gr.Textbox(label="Дата конца (YYYY-MM-DD)", value="2025-12-24")
            btn_refresh_e = gr.Button("Обновить список чатов")
            btn_embed = gr.Button("Построить эмбеддинги")
            out_embed = gr.Textbox(label="Статус", lines=4)

            btn_refresh_e.click(fn=_refresh_choices, inputs=[], outputs=[chat_sel_e])
            btn_embed.click(fn=_embed_ui, inputs=[chat_sel_e, date_from_e, date_to_e], outputs=[out_embed])

        with gr.Tab("Summary"):
            gr.Markdown("Саммаризация с ссылками на message_id.")
            with gr.Row():
                chat_sel_s = gr.Dropdown(choices=[], multiselect=True, label="Чаты")
                date_from_s = gr.Textbox(label="Дата начала (YYYY-MM-DD)", value="2025-12-01")
                date_to_s = gr.Textbox(label="Дата конца (YYYY-MM-DD)", value="2025-12-24")
            btn_refresh_s = gr.Button("Обновить список чатов")
            btn_sum = gr.Button("Summarization")

            out_md = gr.Markdown()
            out_json = gr.Textbox(label="Summary (JSON file)", lines=18)

            btn_refresh_s.click(fn=_refresh_choices, inputs=[], outputs=[chat_sel_s])
            btn_sum.click(fn=_summary_ui, inputs=[chat_sel_s, date_from_s, date_to_s], outputs=[out_md, out_json])

        with gr.Tab("Вопросы"):
            gr.Markdown("Блок 'Вопрос - Ответ'.")
            with gr.Row():
                chat_sel_q = gr.Dropdown(choices=[], multiselect=True, label="Чаты")
                date_from_q = gr.Textbox(label="Дата начала (YYYY-MM-DD)", value="2025-12-01")
                date_to_q = gr.Textbox(label="Дата конца (YYYY-MM-DD)", value="2025-12-24")
            btn_refresh_q = gr.Button("Обновить список чатов")

            chatbot = gr.Chatbot(label="Диалоговое окно", height=420)
            question = gr.Textbox(label="Вопрос", placeholder="Например: Какие важные темы обсуждались в этом чате?")
            send = gr.Button("Отправить")

            btn_refresh_q.click(fn=_refresh_choices, inputs=[], outputs=[chat_sel_q])
            send.click(fn=_qa_respond, inputs=[chat_sel_q, date_from_q, date_to_q, chatbot, question], outputs=[chatbot, question])

    return demo
