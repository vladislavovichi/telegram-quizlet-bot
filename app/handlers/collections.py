from __future__ import annotations
import io
import csv
import re
from aiogram import Router, F, types

from app.repos.base import with_repos
from app.keyboards.collections import (
    collections_root_kb,
    collection_menu_kb,
    collection_edit_kb,
    items_page_kb,
    item_view_kb,
    item_delete_confirm_kb,
    collection_delete_confirm_kb,
    collection_clear_confirm_kb,
    collection_deleted_kb,
)
from app.filters.pending import HasPendingAction
from app.middlewares.redis_kv import RedisKVMiddleware
from app.services import importers
from app.services.share_code import make_share_code, parse_share_code
from app.config import settings
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
        pairs = [(c.id, c.title) for c in all_cols]
        await message.answer(
            "Твои коллекции:",
            reply_markup=collections_root_kb(page=1, collections=pairs),
        )

    @router.callback_query(F.data == "col:list")
    async def collections_list(cb: types.CallbackQuery) -> None:
        async with with_repos(async_session_maker) as (_, users, cols, _):
            u = await users.get_or_create(cb.from_user.id, cb.from_user.username)
            all_cols = await cols.list_by_user(u.id)
        pairs = [(c.id, c.title) for c in all_cols]
        await cb.message.edit_text(
            "Твои коллекции:",
            reply_markup=collections_root_kb(page=1, collections=pairs),
        )
        await cb.answer()

    @router.callback_query(F.data.startswith("col:page:"))
    async def page_collections(cb: types.CallbackQuery) -> None:
        page = int(cb.data.split(":")[-1])
        async with with_repos(async_session_maker) as (_, users, cols, _):
            u = await users.get_or_create(cb.from_user.id, cb.from_user.username)
            all_cols = await cols.list_by_user(u.id)
        pairs = [(c.id, c.title) for c in all_cols]
        await cb.message.edit_reply_markup(
            reply_markup=collections_root_kb(page=page, collections=pairs)
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
            f"Коллекция: «{col.title}»", reply_markup=collection_menu_kb(cid, page=1)
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

    @router.callback_query(F.data.startswith("col:delete:confirm:"))
    async def delete_col_confirm(cb: types.CallbackQuery) -> None:

        cid = int(cb.data.split(":")[-1])

        async with with_repos(async_session_maker) as (_, users, cols, _):
            u = await users.get_or_create(cb.from_user.id, cb.from_user.username)
            await cols.delete_owned(cid, u.id)

        await cb.message.edit_text(
            "🗑 Коллекция удалена.", reply_markup=collection_deleted_kb()
        )

        await cb.answer("Удалено")

    @router.callback_query(F.data.startswith("col:delete:"))
    async def delete_col_prompt(cb: types.CallbackQuery) -> None:
        cid = int(cb.data.split(":")[-1])
        async with with_repos(async_session_maker) as (_, users, cols, _):
            u = await users.get_or_create(cb.from_user.id, cb.from_user.username)
            col = await cols.get_owned(cid, u.id)
        if not col:
            await cb.answer("Коллекция не найдена", show_alert=True)
            return
        await cb.message.edit_text(
            "Удалить коллекцию безвозвратно? Все карточки в ней тоже будут удалены.",
            reply_markup=collection_delete_confirm_kb(cid),
        )
        await cb.answer()

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
        text = (
            f"Коллекция: «{col.title}»\n\n"
            f"*Вопрос:* {item.question}\n"
            f"*Ответ:* {item.answer}"
        )
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

    @router.message(HasPendingAction(redis_kv))
    async def handle_pending(message: types.Message, pending: dict) -> None:
        typ = pending.get("type")
        key = redis_kv.pending_key(message.from_user.id)

        async with with_repos(async_session_maker) as (_, users, cols, items):
            u = await users.get_or_create(
                message.from_user.id, message.from_user.username
            )

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
                if not ok:
                    await message.answer("Коллекция не найдена.")
                    return
                col = await cols.get_owned(cid, u.id)
                if not col:
                    await message.answer("Коллекция не найдена.")
                    return
                text = "✅ Коллекция переименована.\n\n" f"Коллекция: «{col.title}»"
                await message.answer(text, reply_markup=collection_edit_kb(col.id))
                return

            if typ == "item:add:q":
                q = (message.text or "").strip()
                if not q:
                    await message.answer("Не вижу текста. Введи вопрос:")
                    return
                await redis_kv.set_json(
                    key,
                    {"type": "item:add:a", "cid": int(pending["cid"]), "q": q},
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
                created = await items.add(cid, q, a)
                item, col = await items.get_item_owned(created.id, u.id)
                await redis_kv.delete(key)
                text = (
                    "✅ Карточка создана.\n\n"
                    f"Коллекция: «{col.title}»\n\n"
                    f"*Вопрос:* {item.question}\n"
                    f"*Ответ:* {item.answer}"
                )
                await message.answer(
                    text,
                    parse_mode="Markdown",
                    reply_markup=item_view_kb(item.id, col.id),
                )
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
                item, col = await items.get_item_owned(item_id, u.id)
                await redis_kv.delete(key)
                text = (
                    "✅ Карточка обновлена.\n\n"
                    f"Коллекция: «{col.title}»\n\n"
                    f"*Вопрос:* {item.question}\n"
                    f"*Ответ:* {item.answer}"
                )
                await message.answer(
                    text,
                    parse_mode="Markdown",
                    reply_markup=item_view_kb(item_id, col.id),
                )
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
                item, col = await items.get_item_owned(item_id, u.id)
                await redis_kv.delete(key)
                text = (
                    "✅ Карточка обновлена.\n\n"
                    f"Коллекция: «{col.title}»\n\n"
                    f"*Вопрос:* {item.question}\n"
                    f"*Ответ:* {item.answer}"
                )
                await message.answer(
                    text,
                    parse_mode="Markdown",
                    reply_markup=item_view_kb(item_id, col.id),
                )
                return

            if typ == "item:edit:qa":
                pair = _normalize_pair(message.text or "")
                if not pair:
                    await message.answer(
                        "Неверный формат. Пришли: `вопрос || ответ`",
                        parse_mode="Markdown",
                    )
                    return
                new_q, new_a = pair
                item_id = int(pending["item_id"])
                item, col = await items.get_item_owned(item_id, u.id)
                if not item or not col:
                    await redis_kv.delete(key)
                    await message.answer("Нет доступа/не найдено.")
                    return
                await items.update_both(item_id, new_q, new_a)
                item, col = await items.get_item_owned(item_id, u.id)
                await redis_kv.delete(key)
                text = (
                    "✅ Карточка обновлена.\n\n"
                    f"Коллекция: «{col.title}»\n\n"
                    f"*Вопрос:* {item.question}\n"
                    f"*Ответ:* {item.answer}"
                )
                await message.answer(
                    text,
                    parse_mode="Markdown",
                    reply_markup=item_view_kb(item_id, col.id),
                )
                return
            if typ == "import:items:await_file":
                cid = int(pending.get("cid", 0))
                if message.document is None:
                    await message.answer("Пришлите файл .csv или .xlsx с карточками.")
                    return
                file_name = message.document.file_name or "data.csv"
                buf = io.BytesIO()
                await message.bot.download(message.document, buf)
                data = buf.getvalue()
                try:
                    pairs = importers.parse_items_file(file_name, data)
                except Exception as e:
                    await message.answer(f"Не получилось прочитать файл: {e}")
                    return

                async with with_repos(async_session_maker) as (_, users, cols, items):
                    u = await users.get_or_create(
                        message.from_user.id, message.from_user.username
                    )
                    col = await cols.get_owned(cid, u.id)
                    if not col:
                        await message.answer("Коллекция не найдена.")
                        await redis_kv.delete(key)
                        return

                    existing = set(q for _, q in await items.list_pairs(cid))
                    added = 0
                    for q, a in pairs:
                        if added + len(existing) >= MAX_ITEMS_PER_COLLECTION:
                            break
                        if q in existing:
                            continue
                        await items.add(cid, q, a)
                        added += 1
                        existing.add(q)
                await redis_kv.delete(key)
                if added == 0:
                    await message.answer(
                        "Ничего не импортировано (возможно, дубликаты или лимит достигнут)."
                    )
                else:
                    await message.answer(f"✅ Импортировано карточек: {added}")

                await message.answer(
                    "Коллекция обновлена.",
                    reply_markup=collection_menu_kb(cid, page=2),
                )
                return

            if typ == "import:collections:await_file":
                if message.document is None:
                    await message.answer("Пришлите файл .csv или .xlsx с коллекциями.")
                    return
                file_name = message.document.file_name or "collections.csv"
                buf = io.BytesIO()
                await message.bot.download(message.document, buf)
                data = buf.getvalue()
                try:
                    grouped = importers.parse_collections_file(file_name, data)
                except Exception as e:
                    await message.answer(f"Не получилось прочитать файл: {e}")
                    return

                created = 0
                total_cards = 0
                skipped = 0
                async with with_repos(async_session_maker) as (_, users, cols, items):
                    u = await users.get_or_create(
                        message.from_user.id, message.from_user.username
                    )
                    for title, pairs in grouped.items():
                        col = await cols.create(u.id, title)
                        created += 1
                        count_in_col = 0
                        seen_q = set()
                        for q, a in pairs:
                            if count_in_col >= MAX_ITEMS_PER_COLLECTION:
                                skipped += 1
                                continue
                            if q in seen_q:
                                skipped += 1
                                continue
                            await items.add(col.id, q, a)
                            seen_q.add(q)
                            count_in_col += 1
                            total_cards += 1

                await redis_kv.delete(key)
                await message.answer(
                    f"✅ Импорт завершён. Создано коллекций: {created}. Добавлено карточек: {total_cards}. Пропущено: {skipped}."
                )
                return

            if typ == "share:await_code":
                code = (message.text or "").strip()
                if not code:
                    await message.answer("Вставьте код.")
                    return
                parsed = parse_share_code(code, settings.BOT_TOKEN)
                if not parsed:
                    await message.answer("Код не распознан или повреждён.")
                    return
                cid, owner_id = parsed
                async with with_repos(async_session_maker) as (_, users, cols, items):
                    u = await users.get_or_create(
                        message.from_user.id, message.from_user.username
                    )

                    src = await cols.get_by_id(cid)
                    if not src:
                        await message.answer("Исходная коллекция не найдена.")
                        await redis_kv.delete(key)
                        return

                    new_col = await cols.create(u.id, src.title)
                    pairs = await items.list_pairs(cid)
                    for _, q in pairs:
                        pass

                from sqlalchemy import select
                from app.models.collection import CollectionItem

                async with with_repos(async_session_maker) as (
                    session,
                    users,
                    cols,
                    items,
                ):
                    pairs_rows = await session.execute(
                        select(CollectionItem.question, CollectionItem.answer)
                        .where(CollectionItem.collection_id == cid)
                        .order_by(
                            CollectionItem.position.asc(), CollectionItem.id.asc()
                        )
                    )
                    for q, a in pairs_rows.all():
                        await items.add(new_col.id, q, a)
                await redis_kv.delete(key)
                await message.answer(
                    f"✅ Коллекция «{new_col.title}» импортирована по коду.",
                    reply_markup=collection_menu_kb(new_col.id, page=1),
                )
                return

    @router.callback_query(F.data.startswith("col:menu:"))
    async def col_menu_page(cb: types.CallbackQuery) -> None:
        parts = cb.data.split(":")
        cid = int(parts[2])
        page = int(parts[3]) if len(parts) > 3 else 1
        await cb.message.edit_reply_markup(
            reply_markup=collection_menu_kb(cid, page=page)
        )
        await cb.answer()

    @router.callback_query(F.data.startswith("col:clear:confirm:"))
    async def col_clear_confirm(cb: types.CallbackQuery) -> None:
        cid = int(cb.data.split(":")[-1])
        async with with_repos(async_session_maker) as (_, users, cols, items):
            u = await users.get_or_create(cb.from_user.id, cb.from_user.username)
            col = await cols.get_owned(cid, u.id)
            if not col:
                await cb.answer("Нет доступа/не найдено", show_alert=True)
                return
            deleted = await items.delete_all_in_collection(cid)
        await cb.message.edit_text(
            f"🧹 Коллекция «{col.title}» очищена. Удалено карточек: {deleted}.",
            reply_markup=collection_menu_kb(cid, page=2),
        )
        await cb.answer("Очищено")

    @router.callback_query(F.data.startswith("col:clear:"))
    async def col_clear_prompt(cb: types.CallbackQuery) -> None:
        cid = int(cb.data.split(":")[-1])
        async with with_repos(async_session_maker) as (_, users, cols, _):
            u = await users.get_or_create(cb.from_user.id, cb.from_user.username)
            col = await cols.get_owned(cid, u.id)
        if not col:
            await cb.answer("Коллекция не найдена", show_alert=True)
            return
        await cb.message.edit_text(
            f"Вы уверены, что хотите очистить коллекцию «{col.title}»? Это удалит все карточки.",
            reply_markup=collection_clear_confirm_kb(cid),
        )
        await cb.answer()

    @router.callback_query(F.data.startswith("col:import:items:"))
    async def col_import_items_prompt(cb: types.CallbackQuery) -> None:
        cid = int(cb.data.split(":")[-1])
        await redis_kv.set_json(
            redis_kv.pending_key(cb.from_user.id),
            {"type": "import:items:await_file", "cid": cid},
            ex=redis_kv.ttl_seconds,
        )
        example = (
            "📥 Импорт карточек (CSV/Excel)\n\n"
            "Отправьте файл с колонками: *question*, *answer*.\n"
            "Первая строка — заголовки. Пример CSV:\n"
            "```csv\nquestion,answer\nСтолица Франции?,Париж\n2+2=?,4\n```\n"
            "_Максимум 40 карточек в коллекции. Дубликаты по вопросу игнорируются._"
        )
        await cb.message.answer(example, parse_mode="Markdown")
        await cb.answer("Жду файл")

    @router.callback_query(F.data == "col:import:collections:prompt")
    async def col_import_collections_prompt(cb: types.CallbackQuery) -> None:
        await redis_kv.set_json(
            redis_kv.pending_key(cb.from_user.id),
            {"type": "import:collections:await_file"},
            ex=redis_kv.ttl_seconds,
        )
        example = (
            "📦 Импорт коллекций (CSV/Excel)\n\n"
            "Отправьте файл с колонками: *title*, *question*, *answer*.\n"
            "*title* — название коллекции. Пример CSV:\n"
            "```csv\ntitle,question,answer\nГеография,Столица Франции?,Париж\nМатематика,2+2=?,4\n```"
        )
        await cb.message.answer(example, parse_mode="Markdown")
        await cb.answer("Жду файл")

    @router.callback_query(F.data.startswith("col:share:"))
    async def col_share_code(cb: types.CallbackQuery) -> None:
        cid = int(cb.data.split(":")[-1])
        async with with_repos(async_session_maker) as (_, users, cols, _):
            u = await users.get_or_create(cb.from_user.id, cb.from_user.username)
            col = await cols.get_owned(cid, u.id)
        if not col:
            await cb.answer("Коллекция не найдена", show_alert=True)
            return
        code = make_share_code(cid, u.id, settings.BOT_TOKEN)
        await cb.message.answer(
            f"🔗 Код для импорта коллекции «{col.title}»:\n`{code}`\n"
            "Передайте его другу. У него должен быть бот.",
            parse_mode="Markdown",
        )
        await cb.answer()

    @router.callback_query(F.data == "col:add_by_code")
    async def coll_add_by_code(cb: types.CallbackQuery) -> None:
        await redis_kv.set_json(
            redis_kv.pending_key(cb.from_user.id),
            {"type": "share:await_code"},
            ex=redis_kv.ttl_seconds,
        )
        await cb.message.answer("Вставьте код, которым поделился друг:")
        await cb.answer()

    @router.callback_query(F.data.startswith("col:export:csv:"))
    async def export_collection_csv(cb: types.CallbackQuery) -> None:
        try:
            cid = int(cb.data.split(":")[-1])
        except Exception:
            await cb.answer("Не удалось распознать коллекцию", show_alert=True)
            return

        from aiogram.types import BufferedInputFile
        from sqlalchemy import select
        from app.models.collection import CollectionItem

        async with with_repos(async_session_maker) as (session, users, cols, _):
            u = await users.get_or_create(cb.from_user.id, cb.from_user.username)
            col = await cols.get_owned(cid, u.id)
            if not col:
                await cb.answer("Нет доступа или коллекция не найдена", show_alert=True)
                return

            rows = await session.execute(
                select(CollectionItem.question, CollectionItem.answer)
                .where(CollectionItem.collection_id == cid)
                .order_by(CollectionItem.position.asc(), CollectionItem.id.asc())
            )
            pairs = rows.all()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["question", "answer"])
        for q, a in pairs:
            writer.writerow([q, a])
        data = output.getvalue().encode("utf-8-sig")
        output.close()

        filename = f"collection_{cid}.csv"
        await cb.message.answer_document(
            document=BufferedInputFile(data, filename=filename),
            caption=f"Экспорт коллекции «{col.title}» ({len(pairs)} карточек).",
        )
        await cb.answer()

    router.priority = -10
    return router
