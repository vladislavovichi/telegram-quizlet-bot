from __future__ import annotations
from typing import Sequence

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

PAGE_SIZE_COLLECTIONS = 4


def game_collections_kb(collections: Sequence, page: int = 0) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    start = page * PAGE_SIZE_COLLECTIONS
    chunk = collections[start : start + PAGE_SIZE_COLLECTIONS]

    for col in chunk:
        title = getattr(col, "title", None) or "Без названия"
        b.button(text=f"🎮 {title}", callback_data=f"game:begin:{col.id}")
    b.adjust(1)

    nav = []
    if page > 0:
        nav.append(
            InlineKeyboardButton(text="⬅️ Назад", callback_data=f"game:page:{page-1}")
        )
    if start + PAGE_SIZE_COLLECTIONS < len(collections):
        nav.append(
            InlineKeyboardButton(text="Вперед ➡️", callback_data=f"game:page:{page+1}")
        )
    if nav:
        b.row(*nav)

    b.row(InlineKeyboardButton(text="↩️ К списку коллекций", callback_data="col:list"))
    return b.as_markup()


def game_controls_kb(showing_answer: bool = False) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    if not showing_answer:
        b.button(text="👀 Показать ответ", callback_data="game:show")
    else:
        b.button(text="🙈 Скрыть ответ", callback_data="game:hide")
    b.button(text="➡️ Далее", callback_data="game:next")
    b.adjust(1)
    return b.as_markup()


def game_finished_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🔁 Повторить", callback_data="game:repeat")
    b.button(text="📚 К выбору коллекции", callback_data="game:choose")
    b.button(text="↩️ К списку коллекций", callback_data="col:list")
    b.adjust(1)
    return b.as_markup()
