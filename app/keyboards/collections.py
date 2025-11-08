from __future__ import annotations

from typing import Sequence
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

PAGE_SIZE_COLLECTIONS = 4
PAGE_SIZE_ITEMS = 6


def collections_kb(collections: Sequence, page: int = 0) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    start = page * PAGE_SIZE_COLLECTIONS
    chunk = collections[start : start + PAGE_SIZE_COLLECTIONS]

    for col in chunk:
        b.button(text=f"📚 {col.title}", callback_data=f"col:open:{col.id}")
    b.adjust(1)

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"col:page:{page - 1}"))
    if len(collections) > (start + PAGE_SIZE_COLLECTIONS):
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"col:page:{page + 1}"))
    if nav:
        b.row(*nav)

    b.row(
        InlineKeyboardButton(text="➕ Новая коллекция", callback_data="col:new"),
        InlineKeyboardButton(text="⬅️ Назад", callback_data="col:back"),
    )
    return b.as_markup()


def collection_edit_kb(collection_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="➕ Добавить карточку", callback_data=f"item:add:{collection_id}")
    b.button(text="🗂 Список карточек", callback_data=f"item:list:{collection_id}:0")
    b.button(text="✏️ Переименовать", callback_data=f"col:rename:{collection_id}")
    b.button(text="🗑 Удалить коллекцию", callback_data=f"col:delete:{collection_id}")
    b.button(text="⬅️ К списку", callback_data="col:page:0")
    b.adjust(1)
    return b.as_markup()


def items_page_kb(
    collection_id: int, items: list[tuple[int, str]], page: int
) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    start = page * PAGE_SIZE_ITEMS
    chunk = items[start : start + PAGE_SIZE_ITEMS]

    for iid, title in chunk:
        b.button(text=title, callback_data=f"item:view:{iid}")
    b.adjust(1)

    nav = []
    if page > 0:
        nav.append(
            InlineKeyboardButton(
                text="⬅️", callback_data=f"item:page:{collection_id}:{page - 1}"
            )
        )
    if len(items) > (start + PAGE_SIZE_ITEMS):
        nav.append(
            InlineKeyboardButton(
                text="➡️", callback_data=f"item:page:{collection_id}:{page + 1}"
            )
        )
    if nav:
        b.row(*nav)

    b.row(
        InlineKeyboardButton(
            text="⬅️ Назад к коллекции", callback_data=f"col:open:{collection_id}"
        )
    )
    return b.as_markup()


def item_view_kb(item_id: int, collection_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✏️ Изменить вопрос", callback_data=f"item:editq:{item_id}")
    b.button(text="✏️ Изменить ответ", callback_data=f"item:edita:{item_id}")
    b.button(text="✏️ Изменить (Q || A)", callback_data=f"item:editqa:{item_id}")
    b.button(text="🗑 Удалить", callback_data=f"item:del:{item_id}")
    b.button(text="⬅️ К коллекции", callback_data=f"col:open:{collection_id}")
    b.adjust(1)
    return b.as_markup()


def item_delete_confirm_kb(item_id: int, collection_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ Да, удалить", callback_data=f"item:del:confirm:{item_id}")
    b.button(text="✖️ Отмена", callback_data=f"item:view:{item_id}")
    b.button(text="⬅️ К коллекции", callback_data=f"col:open:{collection_id}")
    b.adjust(1)
    return b.as_markup()
