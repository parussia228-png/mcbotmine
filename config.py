"""
Конфигурация бота.
Все секреты берутся из переменных окружения (.env файл рядом с bot.py).
"""

import os
from dotenv import load_dotenv

load_dotenv()

# Токен бота, полученный от @BotFather
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Список Telegram user_id администраторов через запятую, например: 123456789,987654321
# Узнать свой user_id можно у бота @userinfobot
_admin_ids_raw = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = {
    int(x.strip()) for x in _admin_ids_raw.split(",") if x.strip().isdigit()
}

# (Необязательно) ID группового чата админов, куда будут прилетать заявки.
# Если не указан — бот будет слать заявку в личные сообщения каждому из ADMIN_IDS.
# Чтобы узнать ID группы: добавьте в неё @RawDataBot или @userinfobot.
_admin_chat_raw = os.getenv("ADMIN_CHAT_ID", "")
ADMIN_CHAT_ID = int(_admin_chat_raw) if _admin_chat_raw.strip().lstrip("-").isdigit() else None

# Путь к файлу базы данных SQLite
DB_PATH = os.getenv("DB_PATH", "applications.db")

if not BOT_TOKEN:
    raise RuntimeError(
        "Не задан BOT_TOKEN. Создайте файл .env на основе .env.example и укажите токен бота."
    )

if not ADMIN_IDS:
    raise RuntimeError(
        "Не задан ни один админ в ADMIN_IDS. Укажите свой Telegram user_id в .env."
    )
