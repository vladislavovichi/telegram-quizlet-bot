from __future__ import annotations

from typing import List, Tuple
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

PAGE_SIZE_COLLECTIONS = 4
PAGE_SIZE_ITEMS = 6


def collections_root_kb(
    page: int = 1,
    has_prev: bool = False,
    has_next: bool = False,
    collections: list[tuple[int, str]] | None = None,
) -> InlineKeyboardMarkup:
    collections = collections or []

    total = len(collections)
    per_page = PAGE_SIZE_COLLECTIONS
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))
    start = (page - 1) * per_page
    end = start + per_page
    chunk = collections[start:end]

    kb = InlineKeyboardBuilder()

    kb.row(InlineKeyboardButton(text="➕ Новая коллекция", callback_data="col:new"))
    kb.row(
        InlineKeyboardButton(
            text="🔑 Добавить по коду", callback_data="col:add_by_code"
        ),
        InlineKeyboardButton(
            text="📦 Импорт из CSV/Excel", callback_data="col:import:collections:prompt"
        ),
    )

    for cid, title in chunk:
        kb.row(
            InlineKeyboardButton(text=f"📚 {title}", callback_data=f"col:open:{cid}")
        )

    nav_row = []
    if page > 1:
        nav_row.append(
            InlineKeyboardButton(text="⬅️ Назад", callback_data=f"col:list:{page-1}")
        )
    nav_row.append(
        InlineKeyboardButton(text=f"Стр. {page}/{total_pages}", callback_data="noop")
    )
    if page < total_pages:
        nav_row.append(
            InlineKeyboardButton(text="Вперёд ➡️", callback_data=f"col:list:{page+1}")
        )
    if nav_row:
        kb.row(*nav_row)

    return kb.as_markup()


def collection_menu_kb(collection_id: int, page: int = 1) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()

    if page == 1:
        kb.row(
            InlineKeyboardButton(
                text="➕ Добавить карточку",
                callback_data=f"col:add_item:{collection_id}",
            ),
        )
        kb.row(
            InlineKeyboardButton(
                text="🗂 Посмотреть карточки",
                callback_data=f"col:list_items:{collection_id}:1",
            ),
            InlineKeyboardButton(
                text="🎮 Играть", callback_data=f"col:play:{collection_id}"
            ),
        )
        kb.row(
            InlineKeyboardButton(
                text="✏️ Переименовать", callback_data=f"col:rename:{collection_id}"
            ),
            InlineKeyboardButton(
                text="🗑 Удалить коллекцию", callback_data=f"col:delete:{collection_id}"
            ),
        )
        kb.row(
            InlineKeyboardButton(
                text="⬅️ К списку коллекций", callback_data="col:list:1"
            ),
            InlineKeyboardButton(
                text="➡️ Ещё", callback_data=f"col:menu:{collection_id}:2"
            ),
        )
    else:
        kb.row(
            InlineKeyboardButton(
                text="🧹 Очистить коллекцию", callback_data=f"col:clear:{collection_id}"
            ),
        )
        kb.row(
            InlineKeyboardButton(
                text="📥 Импорт карточек (CSV/Excel)",
                callback_data=f"col:import:items:{collection_id}",
            ),
        )
        kb.row(
            InlineKeyboardButton(
                text="📤 Экспорт в CSV", callback_data=f"col:export:csv:{collection_id}"
            ),
            InlineKeyboardButton(
                text="🔗 Поделиться кодом", callback_data=f"col:share:{collection_id}"
            ),
        )
        kb.row(
            InlineKeyboardButton(
                text="⬅️ Назад", callback_data=f"col:menu:{collection_id}:1"
            ),
        )

    return kb.as_markup()


def collection_edit_kb(collection_id: int) -> InlineKeyboardMarkup:
    return collection_menu_kb(collection_id, page=1)


def items_page_kb(
    collection_id: int, items: List[Tuple[int, str]], page: int
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
    b.button(text="🗑 Удалить карточку", callback_data=f"item:delete:{item_id}")
    b.button(text="⬅️ К списку", callback_data=f"item:list:{collection_id}:0")
    b.button(text="⬅️ К коллекции", callback_data=f"col:open:{collection_id}")
    b.adjust(1)
    return b.as_markup()


def item_delete_confirm_kb(item_id: int, collection_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(
        text="✅ Да, удалить карточку", callback_data=f"item:delete:confirm:{item_id}"
    )
    b.button(text="✖️ Отмена", callback_data=f"item:view:{item_id}")
    b.button(text="⬅️ К коллекции", callback_data=f"col:open:{collection_id}")
    b.adjust(1)
    return b.as_markup()


def collection_delete_confirm_kb(collection_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ Да, удалить", callback_data=f"col:delete:confirm:{collection_id}")
    b.button(text="✖️ Отмена", callback_data=f"col:open:{collection_id}")
    b.button(text="⬅️ К списку коллекций", callback_data="col:list")
    b.adjust(1)
    return b.as_markup()


def collection_clear_confirm_kb(collection_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ Да, очистить", callback_data=f"col:clear:confirm:{collection_id}")
    b.button(text="✖️ Отмена", callback_data=f"col:menu:{collection_id}:2")
    b.button(text="⬅️ К коллекции", callback_data=f"col:open:{collection_id}")
    b.adjust(1)
    return b.as_markup()


def collection_deleted_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="➕ Новая коллекция", callback_data="col:new")
    b.button(text="⬅️ К списку коллекций", callback_data="col:list")
    b.adjust(1)
    return b.as_markup()
