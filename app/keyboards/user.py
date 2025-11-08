from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

main_reply_kb = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="👤 Мой профиль"),
            KeyboardButton(text="👀 Мои коллекции"),
        ],
        [
            KeyboardButton(text="Подключиться по коду"),
        ],
    ],
    resize_keyboard=True,
    one_time_keyboard=False,
)
