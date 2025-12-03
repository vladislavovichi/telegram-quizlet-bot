from __future__ import annotations

from typing import List, Sequence

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

PAGE_SIZE_COLLECTIONS = 4
PAGE_SIZE_ITEMS = 6


def _paginate(total: int, per_page: int, page_index: int) -> tuple[int, int, int]:
    if per_page <= 0:
        per_page = 1
    total_pages = max(1, (total + per_page - 1) // per_page)
    page_index = max(0, min(page_index, total_pages - 1))
    start = page_index * per_page
    return page_index, total_pages, start


def collections_root_kb(*args, **kwargs) -> InlineKeyboardMarkup:
    collections = kwargs.get("collections")
    page = kwargs.get("page", 0)

    if collections is None and args:
        collections = args[0]
        if len(args) > 1 and isinstance(args[1], int):
            page = args[1]
        else:
            page = kwargs.get("page", 0)

    pairs: List[tuple[int, str]] = []
    if collections:
        for rec in collections:
            if isinstance(rec, tuple) and len(rec) >= 2 and isinstance(rec[0], int):
                pairs.append((int(rec[0]), str(rec[1])))
            else:
                cid = int(getattr(rec, "id"))
                title = str(getattr(rec, "title"))
                pairs.append((cid, title))

    total = len(pairs)
    page0, total_pages, start = _paginate(total, PAGE_SIZE_COLLECTIONS, int(page or 0))
    chunk = pairs[start : start + PAGE_SIZE_COLLECTIONS]

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

    nav: List[InlineKeyboardButton] = []
    if page0 > 0:
        nav.append(
            InlineKeyboardButton(text="⬅️ Назад", callback_data=f"col:page:{page0 - 1}")
        )
    nav.append(
        InlineKeyboardButton(
            text=f"Стр. {page0 + 1}/{total_pages}", callback_data="noop"
        )
    )
    if page0 < total_pages - 1:
        nav.append(
            InlineKeyboardButton(text="Вперёд ➡️", callback_data=f"col:page:{page0 + 1}")
        )
    if nav:
        kb.row(*nav)

    return kb.as_markup()


def collection_menu_kb(collection_id: int, page: int = 1) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()

    if page == 1:
        kb.row(
            InlineKeyboardButton(
                text="➕ Добавить карточки", callback_data=f"item:add:{collection_id}"
            ),
        )

        kb.row(
            InlineKeyboardButton(
                text="📃 Список карточек", callback_data=f"item:list:{collection_id}:0"
            ),
            InlineKeyboardButton(
                text="🎮 Играть", callback_data=f"solo:begin:{collection_id}"
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
                text="➡️ Ещё…", callback_data=f"col:menu:{collection_id}:2"
            ),
            InlineKeyboardButton(text="⬅️ К списку коллекций", callback_data="col:list"),
        )

    else:
        kb.row(
            InlineKeyboardButton(
                text="🔗 Поделиться кодом", callback_data=f"col:share:{collection_id}"
            ),
            InlineKeyboardButton(
                text="📤 Экспорт в CSV", callback_data=f"col:export:csv:{collection_id}"
            ),
        )
        kb.row(
            InlineKeyboardButton(
                text="📥 Импорт CSV/Excel",
                callback_data=f"col:import:items:{collection_id}",
            ),
            InlineKeyboardButton(
                text="🧹 Очистить коллекцию", callback_data=f"col:clear:{collection_id}"
            ),
        )
        kb.row(
            InlineKeyboardButton(
                text="⬅️ Назад", callback_data=f"col:menu:{collection_id}:1"
            ),
            InlineKeyboardButton(
                text="🏠 К списку коллекций", callback_data="col:list"
            ),
        )

    return kb.as_markup()


def collection_edit_kb(collection_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(
            text="➕ Добавить карточки", callback_data=f"item:add:{collection_id}"
        )
    )
    kb.row(
        InlineKeyboardButton(
            text="📃 Список карточек", callback_data=f"item:list:{collection_id}:0"
        ),
        InlineKeyboardButton(
            text="🎮 Играть", callback_data=f"solo:begin:{collection_id}"
        ),
    )
    kb.row(
        InlineKeyboardButton(
            text="➡️ Ещё…", callback_data=f"col:menu:{collection_id}:2"
        ),
        InlineKeyboardButton(text="⬅️ К списку коллекций", callback_data="col:list"),
    )
    return kb.as_markup()


def items_page_kb(
    collection_id: int, items: Sequence[tuple[int, str]], page: int
) -> InlineKeyboardMarkup:
    total = len(items)
    page0, total_pages, start = _paginate(total, PAGE_SIZE_ITEMS, int(page or 0))
    chunk = items[start : start + PAGE_SIZE_ITEMS]

    kb = InlineKeyboardBuilder()
    for item_id, title in chunk:
        kb.row(InlineKeyboardButton(text=title, callback_data=f"item:view:{item_id}"))

    nav: List[InlineKeyboardButton] = []
    if page0 > 0:
        nav.append(
            InlineKeyboardButton(
                text="⬅️ Назад", callback_data=f"item:page:{collection_id}:{page0 - 1}"
            )
        )
    nav.append(
        InlineKeyboardButton(
            text=f"Стр. {page0 + 1}/{total_pages}", callback_data="noop"
        )
    )
    if page0 < total_pages - 1:
        nav.append(
            InlineKeyboardButton(
                text="Вперёд ➡️", callback_data=f"item:page:{collection_id}:{page0 + 1}"
            )
        )
    if nav:
        kb.row(*nav)

    kb.row(
        InlineKeyboardButton(
            text="⬅️ К коллекции", callback_data=f"col:open:{collection_id}"
        ),
        InlineKeyboardButton(text="🏠 К списку коллекций", callback_data="col:list"),
    )
    return kb.as_markup()


def item_view_kb(item_id: int, collection_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(
            text="✏️ Изменить вопрос", callback_data=f"item:editq:{item_id}"
        ),
        InlineKeyboardButton(
            text="✏️ Изменить ответ", callback_data=f"item:edita:{item_id}"
        ),
    )
    b.row(
        InlineKeyboardButton(
            text="📝 Изменить Q/A", callback_data=f"item:editqa:{item_id}"
        )
    )
    b.row(InlineKeyboardButton(text="🗑 Удалить", callback_data=f"item:del:{item_id}"))
    b.row(
        InlineKeyboardButton(
            text="➕ Добавить еще карточки", callback_data=f"item:add:{collection_id}"
        )
    )
    b.row(
        InlineKeyboardButton(
            text="📃 Список карточек", callback_data=f"item:list:{collection_id}:0"
        ),
        InlineKeyboardButton(
            text="⬅️ К коллекции", callback_data=f"col:open:{collection_id}"
        ),
    )
    return b.as_markup()


def item_delete_confirm_kb(item_id: int, collection_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ Да, удалить", callback_data=f"item:del:confirm:{item_id}")
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


def collection_cancel_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="❌ Отмена", callback_data="col:cancel")
    b.adjust(1)
    return b.as_markup()
