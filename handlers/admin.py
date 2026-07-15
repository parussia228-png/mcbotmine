"""
Обработчики для администраторов:
одобрение / отклонение заявок, включая опциональное указание причины отказа.
"""

import logging

from telegram import Update
from telegram.ext import ContextTypes, CallbackQueryHandler, MessageHandler, filters

import database as db
import keyboards as kb
from config import ADMIN_IDS

logger = logging.getLogger(__name__)

# В памяти храним, какой админ сейчас должен прислать текст причины отказа для какой заявки.
# awaiting_reason[admin_user_id] = app_id
awaiting_reason: dict[int, int] = {}


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


async def _deny_not_admin(update: Update) -> None:
    if update.callback_query:
        await update.callback_query.answer("У вас нет прав администратора.", show_alert=True)


# --------------------------------------------------------------------------
# Одобрение
# --------------------------------------------------------------------------

async def approve_application(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    admin = update.effective_user

    if not is_admin(admin.id):
        await _deny_not_admin(update)
        return

    app_id = int(query.data.split(":")[1])
    application = db.get_application(app_id)

    if application is None:
        await query.answer("Заявка не найдена.", show_alert=True)
        return
    if application.status != "pending":
        await query.answer("Заявка уже была рассмотрена.", show_alert=True)
        return

    db.set_status(app_id, "approved", admin.id)
    await query.answer("Заявка одобрена ✅")

    await query.edit_message_text(
        query.message.text + f"\n\n✅ ОДОБРЕНО администратором {admin.full_name}",
        reply_markup=None,
    )

    try:
        await context.bot.send_message(
            application.user_id,
            "🎉 Ваша заявка одобрена! Добро пожаловать на сервер!\n"
            f"Ник: {application.nickname}\n"
            "Ожидайте дальнейших инструкций от администрации по подключению.",
        )
    except Exception:
        logger.exception("Не удалось уведомить игрока %s об одобрении", application.user_id)


# --------------------------------------------------------------------------
# Отклонение: меню выбора "с причиной" / "без причины"
# --------------------------------------------------------------------------

async def reject_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    admin = update.effective_user

    if not is_admin(admin.id):
        await _deny_not_admin(update)
        return

    app_id = int(query.data.split(":")[1])
    application = db.get_application(app_id)

    if application is None:
        await query.answer("Заявка не найдена.", show_alert=True)
        return
    if application.status != "pending":
        await query.answer("Заявка уже была рассмотрена.", show_alert=True)
        return

    await query.answer()
    await query.edit_message_reply_markup(reply_markup=kb.reject_reason_keyboard(app_id))


async def reject_back(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Возврат из меню отказа обратно к кнопкам Одобрить/Отклонить."""
    query = update.callback_query
    if not is_admin(update.effective_user.id):
        await _deny_not_admin(update)
        return

    app_id = int(query.data.split(":")[1])
    await query.answer()
    await query.edit_message_reply_markup(reply_markup=kb.admin_decision_keyboard(app_id))


async def reject_now(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отклонить сразу, без указания причины."""
    query = update.callback_query
    admin = update.effective_user

    if not is_admin(admin.id):
        await _deny_not_admin(update)
        return

    app_id = int(query.data.split(":")[1])
    await _finalize_rejection(context, app_id, admin, reason=None)
    await query.answer("Заявка отклонена ❌")
    await query.edit_message_text(
        query.message.text + f"\n\n❌ ОТКЛОНЕНО администратором {admin.full_name}",
        reply_markup=None,
    )


async def reject_with_reason(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Попросить админа прислать текст причины следующим сообщением."""
    query = update.callback_query
    admin = update.effective_user

    if not is_admin(admin.id):
        await _deny_not_admin(update)
        return

    app_id = int(query.data.split(":")[1])
    application = db.get_application(app_id)
    if application is None or application.status != "pending":
        await query.answer("Заявка уже была рассмотрена или не найдена.", show_alert=True)
        return

    awaiting_reason[admin.id] = app_id
    await query.answer()
    await query.message.reply_text(
        f"Напишите причину отказа для заявки #{app_id} следующим сообщением.\n"
        "Она будет отправлена игроку. Для отмены: /cancel_reject"
    )


async def receive_reject_reason(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Ловит текстовые сообщения от админа, если он должен указать причину отказа."""
    admin = update.effective_user
    app_id = awaiting_reason.get(admin.id)
    if app_id is None:
        return  # это сообщение не относится к отклонению заявки — пропускаем

    reason = update.message.text.strip()
    awaiting_reason.pop(admin.id, None)

    await _finalize_rejection(context, app_id, admin, reason=reason)
    await update.message.reply_text(f"Причина отправлена игроку, заявка #{app_id} отклонена.")


async def cancel_reject_reason(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    admin = update.effective_user
    if awaiting_reason.pop(admin.id, None) is not None:
        await update.message.reply_text("Отмена. Заявка остаётся на рассмотрении.")
    else:
        await update.message.reply_text("Сейчас нет заявки, ожидающей причины отказа.")


async def _finalize_rejection(context: ContextTypes.DEFAULT_TYPE, app_id: int, admin, reason: str | None) -> None:
    application = db.get_application(app_id)
    if application is None or application.status != "pending":
        return

    db.set_status(app_id, "rejected", admin.id, reject_reason=reason)

    text = "😔 Ваша заявка на сервер отклонена."
    if reason:
        text += f"\nПричина: {reason}"
    text += "\nВы можете подать новую заявку позже командой /apply."

    try:
        await context.bot.send_message(application.user_id, text)
    except Exception:
        logger.exception("Не удалось уведомить игрока %s об отклонении", application.user_id)


# --------------------------------------------------------------------------
# Список заявок на рассмотрении (для админов)
# --------------------------------------------------------------------------

async def pending_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Эта команда доступна только администраторам.")
        return

    apps = db.list_pending()
    if not apps:
        await update.message.reply_text("Нет заявок на рассмотрении.")
        return

    for a in apps:
        text = (
            f"📥 Заявка #{a.id}\n"
            f"🎮 Ник: {a.nickname}\n"
            f"📊 Опыт: {a.experience}\n"
            f"🎯 Планы: {a.plans}\n"
            f"🎬 Видео:\n{a.video_links}"
        )
        await update.message.reply_text(text, reply_markup=kb.admin_decision_keyboard(a.id))


def register_admin_handlers(app) -> None:
    app.add_handler(CallbackQueryHandler(approve_application, pattern=r"^approve:\d+$"))
    app.add_handler(CallbackQueryHandler(reject_menu, pattern=r"^reject_menu:\d+$"))
    app.add_handler(CallbackQueryHandler(reject_back, pattern=r"^reject_back:\d+$"))
    app.add_handler(CallbackQueryHandler(reject_now, pattern=r"^reject_now:\d+$"))
    app.add_handler(CallbackQueryHandler(reject_with_reason, pattern=r"^reject_with_reason:\d+$"))
    # Текстовые сообщения от админов (для причины отказа) — ставим с низким приоритетом (group=1),
    # чтобы не перехватывать сообщения обычного диалога подачи заявки.
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, receive_reject_reason),
        group=1,
    )
