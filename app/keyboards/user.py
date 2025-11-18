from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

main_reply_kb = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="👀 Мои коллекции"),
            KeyboardButton(text="🎮 Играть одному"),
        ],
        [
            KeyboardButton(text="👤 Мой профиль"),
            KeyboardButton(text="🤼 Играть онлайн"),
        ],
    ],
    resize_keyboard=True,
    one_time_keyboard=False,
)


def profile_inline_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✏️ Изменить имя",
                    callback_data="profile:change_name",
                )
            ]
        ]
    )


def profile_cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🚫 Отменить",
                    callback_data="profile:cancel_change_name",
                )
            ]
        ]
    )
