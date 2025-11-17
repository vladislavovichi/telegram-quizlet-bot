from __future__ import annotations
from typing import Sequence

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

PAGE_SIZE_COLLECTIONS = 4


def solo_collections_kb(collections: Sequence, page: int = 0) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    start = page * PAGE_SIZE_COLLECTIONS
    chunk = collections[start : start + PAGE_SIZE_COLLECTIONS]

    for col in chunk:
        title = getattr(col, "title", None) or "Без названия"
        cid = getattr(col, "id", None) or getattr(col, "collection_id", None)
        if cid is None:
            continue
        b.button(text=f"🧩 {title[:60]}", callback_data=f"solo:begin:{cid}")

    total = len(collections)
    pages = (total + PAGE_SIZE_COLLECTIONS - 1) // PAGE_SIZE_COLLECTIONS
    if pages > 1:
        nav = InlineKeyboardBuilder()
        if page > 0:
            nav.button(text="⬅️", callback_data=f"solo:page:{page-1}")
        nav.button(text=f"{page+1}/{pages}", callback_data="noop")
        if page < pages - 1:
            nav.button(text="➡️", callback_data=f"solo:page:{page+1}")
        b.row(*nav.buttons)
            
    b.button(text="❌ Отмена", callback_data="solo:choose_cancel")
    
    b.adjust(1)
    return b.as_markup()


def solo_controls_kb(
    *, showing_answer: bool, hints_used: int = 0
) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()

    if showing_answer:
        b.button(text="🙈 Скрыть ответ", callback_data="solo:hide")
    else:
        b.button(text="👁 Показать ответ", callback_data="solo:show")

    if hints_used < 3:
        b.button(text=f"💡 Подсказка ({hints_used}/3)", callback_data="solo:hint")

    b.button(text="✅ Знаю", callback_data="solo:known")
    b.button(text="❌ Не знаю", callback_data="solo:unknown")
    b.button(text="⏭ Пропустить", callback_data="solo:skip")

    b.adjust(1)
    return b.as_markup()


def solo_finished_kb(has_wrong: bool) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🔁 Повторить всё", callback_data="solo:repeat:all")
    if has_wrong:
        b.button(text="🛠 Повторить ошибочные", callback_data="solo:repeat:wrong")
    b.button(text="📄 Экспорт CSV", callback_data="solo:export")
    b.button(text="📚 К выбору коллекции", callback_data="solo:choose")
    b.button(text="↩️ К списку коллекций", callback_data="col:list")
    b.adjust(1)
    return b.as_markup()
