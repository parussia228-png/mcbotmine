"""
Telegram-бот приёма заявок на участие в Minecraft-сервере.

Запуск:
    python bot.py

Перед запуском:
    1. pip install -r requirements.txt
    2. Скопируйте .env.example в .env и заполните BOT_TOKEN и ADMIN_IDS
"""

import logging

from telegram.ext import Application, CommandHandler, CallbackQueryHandler

import database as db
from config import BOT_TOKEN
from handlers.user import (
    start,
    build_conversation_handler,
    my_applications,
)
from handlers.admin import register_admin_handlers, pending_list, cancel_reject_reason

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def main() -> None:
    db.init_db()

    application = Application.builder().token(BOT_TOKEN).build()

    # --- команды для всех пользователей ---
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("myapplications", my_applications))

    # --- диалог подачи заявки (игроки) ---
    application.add_handler(build_conversation_handler())

    # --- команды и колбэки для админов ---
    application.add_handler(CommandHandler("pending", pending_list))
    application.add_handler(CommandHandler("cancel_reject", cancel_reject_reason))
    register_admin_handlers(application)

    logger.info("Бот запущен")
    application.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
