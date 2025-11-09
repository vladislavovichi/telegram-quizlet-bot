from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

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
