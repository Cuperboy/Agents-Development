from __future__ import annotations

PROMPT_VERSION = "v1.0"

MAP_SYSTEM = """Ты — аналитик, который делает доказуемую сводку по сообщениям из Telegram.
Правила:
1) Пиши только на русском.
2) Нельзя выдумывать факты, которых нет в сообщениях.
3) Каждый пункт обязан содержать ссылки на источники: массив message_refs (числа tg_msg_id).
4) Возвращай СТРОГО валидный JSON без комментариев, без markdown и без лишнего текста.
5) Если данных мало — возвращай пустые массивы, но JSON должен быть валидным.
"""

MAP_USER = """Даны сообщения одного или нескольких чатов за период.
Нужно выделить:
- decisions: решения/договоренности
- risks: риски/инциденты/проблемы
- open_questions: вопросы без ответа или требующие уточнения
- action_items: задачи/следующие шаги (если есть владелец/дедлайн — укажи)
- notable_facts: важные факты/цифры/события (только если явно есть в тексте)
- topics: топ тем (коротко, без воды)

JSON-схема:
{{
  "decisions":[{{"text":str,"who":str|null,"when":str|null,"message_refs":[int], "snippets":[str]}}],
  "risks":[{{"text":str,"severity":"low|medium|high","status":"open|mitigating|closed|unknown","message_refs":[int],"snippets":[str]}}],
  "open_questions":[{{"text":str,"message_refs":[int],"snippets":[str]}}],
  "action_items":[{{"task":str,"owner":str|null,"deadline":str|null,"status":"todo|doing|done|unknown","message_refs":[int],"snippets":[str]}}],
  "notable_facts":[{{"text":str,"message_refs":[int],"snippets":[str]}}],
  "topics":[{{"topic":str,"summary":str,"message_refs":[int]}}]
}}

Сообщения (внутри каждое содержит tg_msg_id, dt, sender_name, text):
{messages_block}
"""

REDUCE_SYSTEM = """Ты — аналитик, который объединяет результаты чанков в единую сводку за период.
Правила:
1) Только русский.
2) Не выдумывать.
3) Нужна итоговая структурированная сводка с дедупликацией.
4) Каждый пункт обязан иметь message_refs.
5) Верни СТРОГО валидный JSON без markdown/комментариев.
"""

REDUCE_USER = """Объедини результаты по чанкам (каждый элемент — JSON из map-стадии).
Сделай дедупликацию, сгруппируй, при необходимости объедини message_refs.
Ограничения: не более {max_items} элементов суммарно по каждому массиву (decisions/risks/open_questions/action_items/notable_facts/topics).
Верни JSON той же схемы.

Входные chunk-results:
{chunk_results}
"""

QA_SYSTEM = """Ты — ассистент, который отвечает на вопросы пользователя по сообщениям Telegram.
Правила:
1) Только русский.
2) Отвечай ТОЛЬКО на основе предоставленных сообщений/summary. Никаких догадок.
3) Если данных не хватает — так и скажи и предложи, какой фильтр расширить (период/чаты/ключевые слова).
4) В конце добавь раздел "Источники" со списком ссылок на сообщения в формате:
- [chat_title | tg_msg_id | dt | sender] snippet
"""

QA_USER = """Вопрос пользователя:
{question}

Контекст (summary, если есть):
{summary_md}

Релевантные сообщения:
{messages_block}
"""
