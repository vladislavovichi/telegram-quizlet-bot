from __future__ import annotations

from typing import Sequence

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.keyboards.solo_mode import PAGE_SIZE_COLLECTIONS


def online_root_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🆕 Создать комнату", callback_data="online:create")
    b.button(text="🔑 Подключиться к комнате", callback_data="online:join")
    b.adjust(1)
    return b.as_markup()


def online_collections_kb(collections: Sequence, page: int = 0) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    start = page * PAGE_SIZE_COLLECTIONS
    chunk = collections[start : start + PAGE_SIZE_COLLECTIONS]

    for col in chunk:
        title = getattr(col, "title", None) or "Без названия"
        cid = getattr(col, "id", None) or getattr(col, "collection_id", None)
        if cid is None:
            continue
        b.button(text=f"🧩 {title[:60]}", callback_data=f"online:col:{cid}")

    total = len(collections)
    pages = (total + PAGE_SIZE_COLLECTIONS - 1) // PAGE_SIZE_COLLECTIONS
    if pages > 1:
        nav = InlineKeyboardBuilder()
        if page > 0:
            nav.button(text="⬅️", callback_data=f"online:page:{page-1}")
        nav.button(text=f"{page+1}/{pages}", callback_data="noop")
        if page < pages - 1:
            nav.button(text="➡️", callback_data=f"online:page:{page+1}")
        b.row(*nav.buttons)

    b.button(text="❌ Отмена", callback_data="online:choose_cancel")

    b.adjust(1)
    return b.as_markup()


def online_room_owner_kb(room_id: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🎯 Баллов за ответ", callback_data=f"online:set_points:{room_id}")
    b.button(text="⏱ Время на ответ", callback_data=f"online:set_time:{room_id}")
    b.button(text="🚀 Начать игру", callback_data=f"online:start:{room_id}")
    b.button(text="❌ Отмена", callback_data=f"online:cancel:{room_id}")
    b.adjust(1)
    return b.as_markup()



def online_player_kb(room_id: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🚪 Выйти из комнаты", callback_data=f"online:leave:{room_id}")
    b.adjust(1)
    return b.as_markup()


def online_join_cancel_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="❌ Отмена", callback_data="online:join_cancel")
    b.adjust(1)
    return b.as_markup()

def online_settings_cancel_kb(room_id: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="❌ Отмена", callback_data=f"online:settings_cancel:{room_id}")
    b.adjust(1)
    return b.as_markup()
