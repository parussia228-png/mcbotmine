"""
Inline-клавиатуры, используемые ботом.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def start_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("📝 Подать заявку", callback_data="apply_start")]]
    )


def confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Отправить заявку", callback_data="apply_confirm"),
                InlineKeyboardButton("❌ Отменить", callback_data="apply_cancel"),
            ]
        ]
    )


def admin_decision_keyboard(app_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Одобрить", callback_data=f"approve:{app_id}"),
                InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_menu:{app_id}"),
            ]
        ]
    )


def reject_reason_keyboard(app_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("✏️ Указать причину", callback_data=f"reject_with_reason:{app_id}")],
            [InlineKeyboardButton("🚫 Отклонить без причины", callback_data=f"reject_now:{app_id}")],
            [InlineKeyboardButton("« Назад", callback_data=f"reject_back:{app_id}")],
        ]
    )
