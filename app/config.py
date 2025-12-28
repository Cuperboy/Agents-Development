from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
LOG_DIR = BASE_DIR / "logs"
DATA_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

def _get_env(name: str, default: str | None = None) -> str:
    val = os.getenv(name, default)
    if val is None or val == "":
        raise RuntimeError(f"Не задана переменная окружения: {name}")
    return val

def _get_env_int(name: str, default: int | None = None) -> int:
    val = os.getenv(name)
    if val is None or val == "":
        if default is None:
            raise RuntimeError(f"Не задана переменная окружения: {name}")
        return default
    try:
        return int(val)
    except ValueError as e:
        raise RuntimeError(f"Переменная {name} должна быть числом, сейчас: {val}") from e

@dataclass(frozen=True)
class Settings:
    database_url: str

    telegram_api_id: int
    telegram_api_hash: str
    telegram_phone: str
    telethon_session_path: str

    # LLM (HuggingFace Router, OpenAI-compatible)
    openai_base_url: str
    openai_api_key: str
    chat_model: str

    embedding_model_name: str
    embedding_dim: int

    map_chunk_max_chars: int
    reduce_max_items: int

def get_settings() -> Settings:
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg2://chatgpt:chatgpt@localhost:5432/tgchat",
    )

    telegram_api_id = _get_env_int("TELEGRAM_API_ID")
    telegram_api_hash = _get_env("TELEGRAM_API_HASH")
    telegram_phone = _get_env("TELEGRAM_PHONE")

    telethon_session_path = os.getenv(
        "TELETHON_SESSION_PATH",
        str(DATA_DIR / "telethon.session"),
    )

    openai_base_url = _get_env("OPENAI_BASE_URL")
    openai_api_key = _get_env("OPENAI_API_KEY")
    chat_model = _get_env("CHAT_MODEL")

    embedding_model_name = os.getenv(
        "EMBEDDING_MODEL_NAME",
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    )
    embedding_dim = int(os.getenv("EMBEDDING_DIM", "384"))

    map_chunk_max_chars = int(os.getenv("MAP_CHUNK_MAX_CHARS", "12000"))
    reduce_max_items = int(os.getenv("REDUCE_MAX_ITEMS", "200"))

    return Settings(
        database_url=database_url,
        telegram_api_id=telegram_api_id,
        telegram_api_hash=telegram_api_hash,
        telegram_phone=telegram_phone,
        telethon_session_path=telethon_session_path,
        openai_base_url=openai_base_url,
        openai_api_key=openai_api_key,
        chat_model=chat_model,
        embedding_model_name=embedding_model_name,
        embedding_dim=embedding_dim,
        map_chunk_max_chars=map_chunk_max_chars,
        reduce_max_items=reduce_max_items,
    )
