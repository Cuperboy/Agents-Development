from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy.orm import Session

from app.llm import chat_completion, parse_json_strict
from app.prompts import MAP_SYSTEM, MAP_USER, REDUCE_SYSTEM, REDUCE_USER, PROMPT_VERSION
from app.repo import load_messages, upsert_summary
from app.schemas import SummaryJSON
from app.config import get_settings
from app.models import Chat

logger = logging.getLogger(__name__)

def _format_messages_block(messages) -> str:
    lines = []
    for m in messages:
        sender = m.sender_name or ""
        txt = (m.text or "").replace("\n", " ").strip()
        if len(txt) > 700:
            txt = txt[:700] + "…"
        lines.append(f'- {{"tg_msg_id":{m.tg_msg_id},"dt":"{m.dt.isoformat()}","sender_name":"{sender}","text":"{txt}"}}')
    return "\n".join(lines)

def _chunk_messages_by_chars(messages, max_chars: int) -> list[list]:
    chunks = []
    current = []
    cur_len = 0
    for m in messages:
        t = (m.text or "")
        add = len(t) + 120
        if current and (cur_len + add) > max_chars:
            chunks.append(current)
            current = []
            cur_len = 0
        current.append(m)
        cur_len += add
    if current:
        chunks.append(current)
    return chunks

def _dedupe_list(items: list[dict], text_key: str, max_items: int) -> list[dict]:
    seen = set()
    out = []
    for it in items:
        key = (it.get(text_key) or "").strip().lower()
        if not key:
            continue
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
        if len(out) >= max_items:
            break
    return out

def _render_markdown(chats: list[Chat], date_from: datetime, date_to: datetime, s: SummaryJSON) -> str:
    chat_titles = ", ".join([c.title for c in chats])
    md = []
    md.append(f"# Summary по Telegram\n\n**Чаты:** {chat_titles}\n\n**Период:** {date_from.date()} … {date_to.date()}\n")

    def sec(title: str, rows: list[str]):
        md.append(f"\n## {title}\n")
        if not rows:
            md.append("_Нет данных._\n")
        else:
            md.extend(rows)

    sec("Решения", [
        f"- **{d.text}**" + (f" _(кто: {d.who})_" if d.who else "") + (f" _(когда: {d.when})_" if d.when else "") +
        (f"\n  - refs: {', '.join(map(str, d.message_refs))}" if d.message_refs else "")
        for d in s.decisions
    ])

    sec("Риски / инциденты", [
        f"- **{r.text}** _(severity: {r.severity}, status: {r.status})_" +
        (f"\n  - refs: {', '.join(map(str, r.message_refs))}" if r.message_refs else "")
        for r in s.risks
    ])

    sec("Открытые вопросы", [
        f"- {q.text}" + (f"\n  - refs: {', '.join(map(str, q.message_refs))}" if q.message_refs else "")
        for q in s.open_questions
    ])

    sec("Action items", [
        f"- **{a.task}**" + (f" _(owner: {a.owner})_" if a.owner else "") + (f" _(deadline: {a.deadline})_" if a.deadline else "") + f" _(status: {a.status})_" +
        (f"\n  - refs: {', '.join(map(str, a.message_refs))}" if a.message_refs else "")
        for a in s.action_items
    ])

    sec("Важные факты", [
        f"- {f.text}" + (f"\n  - refs: {', '.join(map(str, f.message_refs))}" if f.message_refs else "")
        for f in s.notable_facts
    ])

    sec("Топ темы", [
        f"- **{t.topic}** — {t.summary}" +
        (f"\n  - refs: {', '.join(map(str, t.message_refs))}" if t.message_refs else "")
        for t in s.topics
    ])

    return "\n".join(md).strip() + "\n"

def generate_summary(db: Session, chat_ids: list[int], date_from: datetime, date_to: datetime) -> tuple[dict, str]:
    settings = get_settings()
    messages = load_messages(db, chat_ids, date_from, date_to)
    logger.info("Summarization loaded %d messages", len(messages))

    chunks = _chunk_messages_by_chars(messages, settings.map_chunk_max_chars)
    logger.info("Chunked into %d chunks", len(chunks))

    map_results: list[dict] = []
    for idx, ch in enumerate(chunks, start=1):
        block = _format_messages_block(ch)
        user = MAP_USER.format(messages_block=block)
        raw = chat_completion(MAP_SYSTEM, user)
        parsed = parse_json_strict(raw)
        # pydantic validation
        sj = SummaryJSON.model_validate(parsed)
        map_results.append(sj.model_dump())

        logger.info("Map chunk %d/%d done", idx, len(chunks))

    reduce_user = REDUCE_USER.format(
        chunk_results=str(map_results),
        max_items=settings.reduce_max_items,
    )
    reduce_raw = chat_completion(REDUCE_SYSTEM, reduce_user)
    reduce_parsed = parse_json_strict(reduce_raw)

    # hard dedupe & limits
    reduce_parsed["decisions"] = _dedupe_list(reduce_parsed.get("decisions", []), "text", settings.reduce_max_items)
    reduce_parsed["risks"] = _dedupe_list(reduce_parsed.get("risks", []), "text", settings.reduce_max_items)
    reduce_parsed["open_questions"] = _dedupe_list(reduce_parsed.get("open_questions", []), "text", settings.reduce_max_items)
    reduce_parsed["action_items"] = _dedupe_list(reduce_parsed.get("action_items", []), "task", settings.reduce_max_items)
    reduce_parsed["notable_facts"] = _dedupe_list(reduce_parsed.get("notable_facts", []), "text", settings.reduce_max_items)
    reduce_parsed["topics"] = _dedupe_list(reduce_parsed.get("topics", []), "topic", settings.reduce_max_items)

    final = SummaryJSON.model_validate(reduce_parsed)

    chats = [db.get(Chat, cid) for cid in chat_ids]
    chats = [c for c in chats if c is not None]
    md = _render_markdown(chats, date_from, date_to, final)

    upsert_summary(
        db=db,
        chat_ids=chat_ids,
        date_from=date_from,
        date_to=date_to,
        provider="huggingface_router",
        model=settings.chat_model,
        prompt_version=PROMPT_VERSION,
        summary_json=final.model_dump(),
        summary_md=md,
    )
    return final.model_dump(), md
