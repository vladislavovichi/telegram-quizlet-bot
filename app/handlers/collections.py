from __future__ import annotations
import re
from aiogram import Router, F, types

from app.repos.base import with_repos
from app.keyboards.collections import (
    collections_kb,
    collection_edit_kb,
    items_page_kb,
    item_view_kb,
    item_delete_confirm_kb,
)
from app.keyboards.common import back_to_item_kb, back_to_collections_kb
from app.filters.pending import HasPendingAction
from app.middlewares.redis_kv import RedisKVMiddleware
from app.keyboards.user import main_reply_kb

MAX_ITEMS_PER_COLLECTION = 40


def get_collections_router(async_session_maker, redis_kv) -> Router:
    router = Router(name="collections")
    router.message.middleware(RedisKVMiddleware(redis_kv))

    def _normalize_pair(text: str) -> tuple[str, str] | None:
        parts = re.split(r"\s*\|\|\s*", text, maxsplit=1)
        if len(parts) != 2:
            return None
        q, a = parts[0].strip(), parts[1].strip()
        return (q, a) if q and a else None

    @router.message(F.text == "👀 Мои коллекции")
    async def show_collections(message: types.Message) -> None:
        async with with_repos(async_session_maker) as (_, users, cols, _):
            u = await users.get_or_create(
                message.from_user.id, message.from_user.username
            )
            all_cols = await cols.list_by_user(u.id)
        await message.answer(
            "Твои коллекции:", reply_markup=collections_kb(all_cols, page=0)
        )

    # Возврат к списку коллекций
    @router.callback_query(F.data == "col:list")
    async def collections_list(cb: types.CallbackQuery) -> None:
        async with with_repos(async_session_maker) as (_, users, cols, _):
            u = await users.get_or_create(cb.from_user.id, cb.from_user.username)
            all_cols = await cols.list_by_user(u.id)
        await cb.message.edit_text(
            "Твои коллекции:", reply_markup=collections_kb(all_cols, page=0)
        )
        await cb.answer()

    @router.callback_query(F.data.startswith("col:page:"))
    async def page_collections(cb: types.CallbackQuery) -> None:
        page = int(cb.data.split(":")[-1])
        async with with_repos(async_session_maker) as (_, users, cols, _):
            u = await users.get_or_create(cb.from_user.id, cb.from_user.username)
            all_cols = await cols.list_by_user(u.id)
        await cb.message.edit_reply_markup(
            reply_markup=collections_kb(all_cols, page=page)
        )
        await cb.answer()

    @router.callback_query(F.data == "col:back")
    async def back_to_main(cb: types.CallbackQuery) -> None:
        try:
            await cb.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        await cb.message.answer("Главное меню", reply_markup=main_reply_kb)
        await cb.answer()

    @router.callback_query(F.data == "col:new")
    async def start_new(cb: types.CallbackQuery) -> None:
        key = redis_kv.pending_key(cb.from_user.id)
        await redis_kv.set_json(key, {"type": "col:new"}, ex=redis_kv.ttl_seconds)
        await cb.message.answer("Введи название новой коллекции:")
        await cb.answer()

    @router.callback_query(F.data.startswith("col:open:"))
    async def open_col(cb: types.CallbackQuery) -> None:
        cid = int(cb.data.split(":")[-1])
        async with with_repos(async_session_maker) as (_, users, cols, _):
            u = await users.get_or_create(cb.from_user.id, cb.from_user.username)
            col = await cols.get_owned(cid, u.id)
        if not col:
            await cb.answer("Коллекция не найдена", show_alert=True)
            return
        await cb.message.edit_text(
            f"Коллекция: «{col.title}»", reply_markup=collection_edit_kb(cid)
        )
        await cb.answer()

    @router.callback_query(F.data.startswith("col:rename:"))
    async def rename(cb: types.CallbackQuery) -> None:
        cid = int(cb.data.split(":")[-1])
        key = redis_kv.pending_key(cb.from_user.id)
        await redis_kv.set_json(
            key, {"type": "col:rename", "cid": cid}, ex=redis_kv.ttl_seconds
        )
        await cb.message.answer("Введи новое название коллекции:")
        await cb.answer()

    @router.callback_query(F.data.startswith("col:delete:"))
    async def delete_col(cb: types.CallbackQuery) -> None:
        cid = int(cb.data.split(":")[-1])
        async with with_repos(async_session_maker) as (_, users, cols, _):
            u = await users.get_or_create(cb.from_user.id, cb.from_user.username)
            await cols.delete_owned(cid, u.id)
            all_cols = await cols.list_by_user(u.id)
        await cb.message.edit_text(
            "Твои коллекции:", reply_markup=collections_kb(all_cols, page=0)
        )
        await cb.answer("Удалено")

    @router.callback_query(F.data.startswith("item:list:"))
    async def items_list(cb: types.CallbackQuery) -> None:
        parts = cb.data.split(":")
        cid = int(parts[2])
        page = int(parts[3]) if len(parts) > 3 else 0
        async with with_repos(async_session_maker) as (_, users, cols, items):
            u = await users.get_or_create(cb.from_user.id, cb.from_user.username)
            col = await cols.get_owned(cid, u.id)
            if not col:
                await cb.answer("Коллекция не найдена", show_alert=True)
                return
            pairs = await items.list_pairs(cid)
        titled = [(iid, f"🗂 {title[:60]}") for iid, title in pairs]
        await cb.message.edit_text(
            f"Карточки коллекции «{col.title}»",
            reply_markup=items_page_kb(cid, titled, page),
        )
        await cb.answer()

    @router.callback_query(F.data.startswith("item:page:"))
    async def items_page(cb: types.CallbackQuery) -> None:
        _, _, cid, page = cb.data.split(":")
        cid, page = int(cid), int(page)
        async with with_repos(async_session_maker) as (_, users, cols, items):
            u = await users.get_or_create(cb.from_user.id, cb.from_user.username)
            col = await cols.get_owned(cid, u.id)
            if not col:
                await cb.answer("Коллекция не найдена", show_alert=True)
                return
            pairs = await items.list_pairs(cid)
        titled = [(iid, f"🗂 {title[:60]}") for iid, title in pairs]
        await cb.message.edit_reply_markup(
            reply_markup=items_page_kb(cid, titled, page)
        )
        await cb.answer()

    @router.callback_query(F.data.startswith("item:view:"))
    async def item_view(cb: types.CallbackQuery) -> None:
        item_id = int(cb.data.split(":")[-1])
        async with with_repos(async_session_maker) as (_, users, cols, items):
            u = await users.get_or_create(cb.from_user.id, cb.from_user.username)
            item, col = await items.get_item_owned(item_id, u.id)
        if not item or not col:
            await cb.answer("Нет доступа или не найдено", show_alert=True)
            return
        text = f"Коллекция: «{col.title}»\n\n*Вопрос:* {item.question}\n*Ответ:* {item.answer}"
        await cb.message.edit_text(
            text, parse_mode="Markdown", reply_markup=item_view_kb(item_id, col.id)
        )
        await cb.answer()

    @router.callback_query(F.data.startswith("item:add:"))
    async def item_add_start(cb: types.CallbackQuery) -> None:
        cid = int(cb.data.split(":")[-1])
        async with with_repos(async_session_maker) as (_, users, cols, items):
            u = await users.get_or_create(cb.from_user.id, cb.from_user.username)
            col = await cols.get_owned(cid, u.id)
            if not col:
                await cb.answer("Коллекция не найдена", show_alert=True)
                return
            cnt = await items.count_in_collection(cid)
        if cnt >= MAX_ITEMS_PER_COLLECTION:
            await cb.answer("Лимит 40 карточек", show_alert=True)
            return
        key = redis_kv.pending_key(cb.from_user.id)
        await redis_kv.set_json(
            key, {"type": "item:add:q", "cid": cid}, ex=redis_kv.ttl_seconds
        )
        await cb.message.answer(
            "📝 Введи *вопрос* для карточки:", parse_mode="Markdown"
        )
        await cb.answer()

    @router.callback_query(F.data.startswith("item:editq:"))
    async def item_edit_q_start(cb: types.CallbackQuery) -> None:
        item_id = int(cb.data.split(":")[-1])
        async with with_repos(async_session_maker) as (_, users, _, items):
            u = await users.get_or_create(cb.from_user.id, cb.from_user.username)
            item, col = await items.get_item_owned(item_id, u.id)
        if not item or not col:
            await cb.answer("Нет доступа или не найдено", show_alert=True)
            return
        await redis_kv.set_json(
            redis_kv.pending_key(cb.from_user.id),
            {"type": "item:edit:q", "item_id": item_id},
            ex=redis_kv.ttl_seconds,
        )
        await cb.message.answer("✏️ Введи новый *вопрос*:", parse_mode="Markdown")
        await cb.answer()

    @router.callback_query(F.data.startswith("item:edita:"))
    async def item_edit_a_start(cb: types.CallbackQuery) -> None:
        item_id = int(cb.data.split(":")[-1])
        async with with_repos(async_session_maker) as (_, users, _, items):
            u = await users.get_or_create(cb.from_user.id, cb.from_user.username)
            item, col = await items.get_item_owned(item_id, u.id)
        if not item or not col:
            await cb.answer("Нет доступа или не найдено", show_alert=True)
            return
        await redis_kv.set_json(
            redis_kv.pending_key(cb.from_user.id),
            {"type": "item:edit:a", "item_id": item_id},
            ex=redis_kv.ttl_seconds,
        )
        await cb.message.answer("✏️ Введи новый *ответ*:", parse_mode="Markdown")
        await cb.answer()

    @router.callback_query(F.data.startswith("item:editqa:"))
    async def item_edit_qa_start(cb: types.CallbackQuery) -> None:
        item_id = int(cb.data.split(":")[-1])
        async with with_repos(async_session_maker) as (_, users, _, items):
            u = await users.get_or_create(cb.from_user.id, cb.from_user.username)
            item, col = await items.get_item_owned(item_id, u.id)
        if not item or not col:
            await cb.answer("Нет доступа или не найдено", show_alert=True)
            return
        await redis_kv.set_json(
            redis_kv.pending_key(cb.from_user.id),
            {"type": "item:edit:qa", "item_id": item_id},
            ex=redis_kv.ttl_seconds,
        )
        await cb.message.answer(
            "Пришли новую пару в формате:\n`вопрос || ответ`", parse_mode="Markdown"
        )
        await cb.answer()

    @router.callback_query(F.data.startswith("item:del:confirm:"))
    async def item_delete_confirm(cb: types.CallbackQuery) -> None:
        item_id = int(cb.data.split(":")[-1])
        async with with_repos(async_session_maker) as (_, users, cols, items):
            u = await users.get_or_create(cb.from_user.id, cb.from_user.username)
            item, col = await items.get_item_owned(item_id, u.id)
            if not item or not col:
                await cb.answer("Нет доступа или не найдено", show_alert=True)
                return
            await items.delete(item_id)
        await cb.message.edit_text(
            "🗑 Карточка удалена.", reply_markup=collection_edit_kb(col.id)
        )
        await cb.answer("Удалено")

    @router.callback_query(F.data.startswith("item:del:"))
    async def item_delete_prompt(cb: types.CallbackQuery) -> None:
        item_id = int(cb.data.split(":")[-1])
        async with with_repos(async_session_maker) as (_, users, _, items):
            u = await users.get_or_create(cb.from_user.id, cb.from_user.username)
            item, col = await items.get_item_owned(item_id, u.id)
        if not item or not col:
            await cb.answer("Нет доступа или не найдено", show_alert=True)
            return
        await cb.message.edit_text(
            "Удалить карточку безвозвратно?",
            reply_markup=item_delete_confirm_kb(item_id=item_id, collection_id=col.id),
        )
        await cb.answer()

    # pending-хэндлер с явной прокидкой Redis в фильтр
    @router.message(F.text, HasPendingAction(redis_kv))
    async def handle_pending(message: types.Message, pending: dict) -> None:
        typ = pending.get("type")
        key = redis_kv.pending_key(message.from_user.id)

        async with with_repos(async_session_maker) as (_, users, cols, items):
            u = await users.get_or_create(message.from_user.id, message.from_user.username)

            if typ == "col:new":
                title = (message.text or "").strip()
                if not title:
                    await message.answer("Не вижу текста. Введи название коллекции:")
                    return
                col = await cols.create(u.id, title)
                await redis_kv.delete(key)
                await message.answer(
                    f"✅ Коллекция «{col.title}» создана.",
                    reply_markup=collection_edit_kb(col.id),
                )
                return

            if typ == "col:rename":
                cid = int(pending["cid"])
                ok = await cols.rename(cid, u.id, (message.text or "").strip())
                await redis_kv.delete(key)
                await message.answer(
                    "✅ Переименовано." if ok else "Коллекция не найдена.",
                    reply_markup=back_to_collections_kb(),
                )
                return

            if typ == "item:add:q":
                q = (message.text or "").strip()
                if not q:
                    await message.answer("Не вижу текста. Введи вопрос:")
                    return
                await redis_kv.set_json(
                    key, {"type": "item:add:a", "cid": int(pending["cid"]), "q": q},
                    ex=redis_kv.ttl_seconds,
                )
                await message.answer("✍️ Теперь введи *ответ*:", parse_mode="Markdown")
                return

            if typ == "item:add:a":
                a = (message.text or "").strip()
                if not a:
                    await message.answer("Не вижу текста. Введи ответ:")
                    return
                cid = int(pending["cid"])
                q = pending["q"]
                col = await cols.get_owned(cid, u.id)
                if not col:
                    await redis_kv.delete(key)
                    await message.answer("Коллекция не найдена.")
                    return
                if await items.count_in_collection(cid) >= MAX_ITEMS_PER_COLLECTION:
                    await redis_kv.delete(key)
                    await message.answer("❗️ Лимит 40 карточек.")
                    return
                await items.add(cid, q, a)
                await redis_kv.delete(key)
                await message.answer("✅ Карточка добавлена.", reply_markup=collection_edit_kb(cid))
                return

            if typ == "item:edit:q":
                item_id = int(pending["item_id"])
                item, col = await items.get_item_owned(item_id, u.id)
                if not item or not col:
                    await redis_kv.delete(key)
                    await message.answer("Нет доступа/не найдено.")
                    return
                new_q = (message.text or "").strip()
                if not new_q:
                    await message.answer("Не вижу текста. Введи новый вопрос:")
                    return
                await items.update_question(item_id, new_q)
                await redis_kv.delete(key)
                await message.answer("✅ Вопрос обновлён.", reply_markup=back_to_item_kb(item_id))
                return

            if typ == "item:edit:a":
                item_id = int(pending["item_id"])
                item, col = await items.get_item_owned(item_id, u.id)
                if not item or not col:
                    await redis_kv.delete(key)
                    await message.answer("Нет доступа/не найдено.")
                    return
                new_a = (message.text or "").strip()
                if not new_a:
                    await message.answer("Не вижу текста. Введи новый ответ:")
                    return
                await items.update_answer(item_id, new_a)
                await redis_kv.delete(key)
                await message.answer("✅ Ответ обновлён.", reply_markup=back_to_item_kb(item_id))
                return

            if typ == "item:edit:qa":
                pair = _normalize_pair(message.text or "")
                if not pair:
                    await message.answer("Неверный формат. Пришли: `вопрос || ответ`", parse_mode="Markdown")
                    return
                new_q, new_a = pair
                item_id = int(pending["item_id"])
                item, col = await items.get_item_owned(item_id, u.id)
                if not item or not col:
                    await redis_kv.delete(key)
                    await message.answer("Нет доступа/не найдено.")
                    return
                await items.update_both(item_id, new_q, new_a)
                await redis_kv.delete(key)
                await message.answer("✅ Карточка обновлена.", reply_markup=back_to_item_kb(item_id))
                return

    router.priority = -10
    return router
