from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

index_reply_kb = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="👤 Мой профиль"),
            KeyboardButton(text="👀 Мои коллекции"),
        ],
    ],
    resize_keyboard=True,
    one_time_keyboard=False,
)
