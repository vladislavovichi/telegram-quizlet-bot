from __future__ import annotations
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def back_to_item_kb(item_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="↩️ Вернуться к карточке", callback_data=f"item:view:{item_id}")]
        ]
    )


def back_to_collections_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="↩️ К списку коллекций", callback_data="col:list")]
        ]
    )
