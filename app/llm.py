from __future__ import annotations

import json

from tenacity import retry, stop_after_attempt, wait_exponential
from openai import OpenAI

from app.config import get_settings

def _client() -> OpenAI:
    s = get_settings()
    return OpenAI(base_url=s.openai_base_url, api_key=s.openai_api_key)

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
def chat_completion(system: str, user: str) -> str:
    s = get_settings()
    client = _client()

    resp = client.chat.completions.create(
        model=s.chat_model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.2,
    )

    text = resp.choices[0].message.content
    if not isinstance(text, str) or not text.strip():
        raise RuntimeError("LLM вернул пустой ответ.")
    return text

@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=4))
def repair_json(bad_text: str) -> str:
    system = "Ты исправляешь JSON. Верни только валидный JSON без markdown."
    user = f"Исправь в валидный JSON:\n{bad_text}"
    return chat_completion(system, user)

def parse_json_strict(text: str) -> dict:
    try:
        return json.loads(text)
    except Exception:
        fixed = repair_json(text)
        return json.loads(fixed)
