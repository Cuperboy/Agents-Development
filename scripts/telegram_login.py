from __future__ import annotations

import asyncio
import getpass
import logging

from telethon.errors import SessionPasswordNeededError
from telethon import TelegramClient

from app.config import get_settings
from app.logging_setup import setup_logging

logger = logging.getLogger(__name__)

async def main():
    setup_logging()
    s = get_settings()

    client = TelegramClient(s.telethon_session_path, s.telegram_api_id, s.telegram_api_hash)
    await client.connect()

    if not await client.is_user_authorized():
        logger.info("Не авторизован. Отправляю код на телефон %s", s.telegram_phone)
        await client.send_code_request(s.telegram_phone)
        code = input("Введи код из Telegram: ").strip()
        try:
            await client.sign_in(s.telegram_phone, code)
        except SessionPasswordNeededError:
            pwd = getpass.getpass("Включена 2FA. Введи пароль: ")
            await client.sign_in(password=pwd)

    me = await client.get_me()
    logger.info("Успешно. Авторизован как: %s (id=%s)", getattr(me, "username", None), getattr(me, "id", None))
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
