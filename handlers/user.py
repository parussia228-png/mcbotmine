"""
Обработчики для обычных пользователей (игроков):
подача заявки на участие в сервере через пошаговый диалог (ConversationHandler).
"""

import logging

from telegram import Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

import database as db
import keyboards as kb
from config import ADMIN_IDS, ADMIN_CHAT_ID

logger = logging.getLogger(__name__)

# Состояния диалога подачи заявки
NICKNAME, EXPERIENCE, PLANS, VIDEO, CONFIRM = range(5)


# --------------------------------------------------------------------------
# /start и вход в анкету
# --------------------------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "👋 Привет! Это бот приёма заявок на bomjsquad.\n\n"
        "Чтобы попасть на сервер, нужно подать заявку и ответить на несколько вопросов:\n"
        "1. Ваш ник в Minecraft\n"
        "2. Опыт игры в Minecraft\n"
        "3. Что вы собираетесь делать на сервере\n"
        "4. Ссылка(и) на видео (геймплей/прохождение и т.п.)\n\n"
        "Заявку рассмотрит администрация, и вы получите ответ прямо в этом чате."
    )
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text(text, reply_markup=kb.start_keyboard())
    else:
        await update.message.reply_text(text, reply_markup=kb.start_keyboard())


async def apply_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Точка входа в анкету — вызывается и командой /apply, и кнопкой."""
    user = update.effective_user

    if db.has_pending_application(user.id):
        message = (
            "⏳ У вас уже есть заявка на рассмотрении. "
            "Дождитесь решения администрации, прежде чем подавать новую."
        )
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.message.reply_text(message)
        else:
            await update.message.reply_text(message)
        return ConversationHandler.END

    context.user_data["application"] = {}

    text = "Введите ваш игровой ник в Minecraft (как он отображается в игре):"
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text(text)
    else:
        await update.message.reply_text(text)
    return NICKNAME


async def get_nickname(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    nickname = update.message.text.strip()
    if not (2 <= len(nickname) <= 32):
        await update.message.reply_text("Ник выглядит некорректно. Введите ник ещё раз:")
        return NICKNAME

    context.user_data["application"]["nickname"] = nickname
    await update.message.reply_text(
        "Расскажите о вашем опыте игры в Minecraft "
        "(сколько лет играете, на каких серверах, что умеете — стройка, редстоун, PvP и т.д.):"
    )
    return EXPERIENCE


async def get_experience(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    experience = update.message.text.strip()
    if len(experience) < 5:
        await update.message.reply_text("Пожалуйста, опишите опыт немного подробнее:")
        return EXPERIENCE

    context.user_data["application"]["experience"] = experience
    await update.message.reply_text("Что вы собираетесь делать на сервере?")
    return PLANS


async def get_plans(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    plans = update.message.text.strip()
    if len(plans) < 5:
        await update.message.reply_text("Пожалуйста, опишите свои планы немного подробнее:")
        return PLANS

    context.user_data["application"]["plans"] = plans
    await update.message.reply_text(
        "Пришлите ссылку(и) на видео (например, ваш геймплей/прохождение).\n"
        "Если ссылок несколько — отправьте их одним сообщением, каждую с новой строки."
    )
    return VIDEO


async def get_video(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    raw = update.message.text.strip()
    links = [line.strip() for line in raw.splitlines() if line.strip()]

    if not links or not any(
        link.startswith("http://") or link.startswith("https://") for link in links
    ):
        await update.message.reply_text(
            "Не вижу ни одной похожей на ссылку строки. "
            "Пришлите, пожалуйста, ссылку(и) на видео (начинаются с http:// или https://):"
        )
        return VIDEO

    context.user_data["application"]["video_links"] = "\n".join(links)

    app = context.user_data["application"]
    summary = (
        "Проверьте, всё ли верно:\n\n"
        f"🎮 Ник: {app['nickname']}\n"
        f"📊 Опыт: {app['experience']}\n"
        f"🎯 Планы на сервере: {app['plans']}\n"
        f"🎬 Видео:\n{app['video_links']}\n\n"
        "Отправить заявку администрации?"
    )
    await update.message.reply_text(summary, reply_markup=kb.confirm_keyboard())
    return CONFIRM


async def confirm_application(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    app = context.user_data.get("application")
    if not app:
        await query.message.reply_text("Сессия устарела, начните заново: /apply")
        return ConversationHandler.END

    user = update.effective_user
    app_id = db.create_application(
        user_id=user.id,
        username=user.username,
        full_name=user.full_name,
        nickname=app["nickname"],
        experience=app["experience"],
        plans=app["plans"],
        video_links=app["video_links"],
    )

    await query.edit_message_text(
        "✅ Заявка отправлена! Ожидайте решения администрации — "
        "бот пришлёт вам уведомление в этот чат."
    )

    await _notify_admins(context, app_id, user, app)

    context.user_data.pop("application", None)
    return ConversationHandler.END


async def cancel_application(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data.pop("application", None)
    await query.edit_message_text("Заявка отменена. Подать новую можно командой /apply.")
    return ConversationHandler.END


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("application", None)
    await update.message.reply_text("Заполнение анкеты отменено. Подать новую — /apply.")
    return ConversationHandler.END


async def my_applications(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    apps = db.list_by_user(user.id)
    if not apps:
        await update.message.reply_text("У вас пока нет заявок. Подать заявку — /apply.")
        return

    status_names = {"pending": "⏳ на рассмотрении", "approved": "✅ одобрена", "rejected": "❌ отклонена"}
    lines = [f"#{a.id} — ник {a.nickname} — {status_names.get(a.status, a.status)}" for a in apps]
    await update.message.reply_text("Ваши заявки:\n" + "\n".join(lines))


# --------------------------------------------------------------------------
# Уведомление администраторов о новой заявке
# --------------------------------------------------------------------------

async def _notify_admins(context: ContextTypes.DEFAULT_TYPE, app_id: int, user, app: dict) -> None:
    username_part = f" (@{user.username})" if user.username else ""
    text = (
        f"📥 Новая заявка #{app_id}\n\n"
        f"👤 Отправитель: {user.full_name}{username_part}, id: {user.id}\n"
        f"🎮 Ник в Minecraft: {app['nickname']}\n"
        f"📊 Опыт: {app['experience']}\n"
        f"🎯 Планы на сервере: {app['plans']}\n"
        f"🎬 Видео:\n{app['video_links']}"
    )
    markup = kb.admin_decision_keyboard(app_id)

    if ADMIN_CHAT_ID is not None:
        try:
            await context.bot.send_message(ADMIN_CHAT_ID, text, reply_markup=markup)
        except Exception:
            logger.exception("Не удалось отправить заявку в ADMIN_CHAT_ID")
        return

    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(admin_id, text, reply_markup=markup)
        except Exception:
            # Например, если админ ни разу не запускал бота (/start) — бот не может ему написать
            logger.exception("Не удалось отправить заявку админу %s", admin_id)


def build_conversation_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CommandHandler("apply", apply_entry),
            CallbackQueryHandler(apply_entry, pattern="^apply_start$"),
        ],
        states={
            NICKNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_nickname)],
            EXPERIENCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_experience)],
            PLANS: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_plans)],
            VIDEO: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_video)],
            CONFIRM: [
                CallbackQueryHandler(confirm_application, pattern="^apply_confirm$"),
                CallbackQueryHandler(cancel_application, pattern="^apply_cancel$"),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_command)],
        name="application_conversation",
        persistent=False,
    )
