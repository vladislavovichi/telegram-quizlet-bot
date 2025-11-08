from __future__ import annotations

import logging, io, csv
from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.types import BufferedInputFile

from app.keyboards.game_mode import (
    game_collections_kb,
    game_controls_kb,
    game_finished_kb,
)
from app.texts.game_mode import (
    fmt_question,
    fmt_answer,
    fmt_finished_summary,
    fmt_choose_collection,
)
from app.services.game_mode import GameSession, GameData
from app.repos.base import with_repos 

log = logging.getLogger(__name__)


def get_game_mode_router(async_session_maker, redis_kv) -> Router:
    router = Router(name="game_mode")

    @router.message(F.text == "🎮 Играть одному")
    async def cmd_game(message: types.Message) -> None:
        async with with_repos(async_session_maker) as (_, users, cols, _):
            u = await users.get_or_create(message.from_user.id, message.from_user.username)
            all_cols = await cols.list_by_user(u.id)
        await message.answer(fmt_choose_collection(), reply_markup=game_collections_kb(all_cols, page=0))

    @router.callback_query(F.data == "game:choose")
    async def cb_game_choose(cb: types.CallbackQuery) -> None:
        async with with_repos(async_session_maker) as (_, users, cols, _):
            u = await users.get_or_create(cb.from_user.id, cb.from_user.username)
            all_cols = await cols.list_by_user(u.id)
        await cb.message.edit_text(fmt_choose_collection(), reply_markup=game_collections_kb(all_cols, page=0))
        await cb.answer()


    @router.callback_query(F.data.startswith("game:page:"))
    async def cb_game_page(cb: types.CallbackQuery) -> None:
        try:
            page = int(cb.data.split(":")[2])
        except Exception:
            page = 0
        async with with_repos(async_session_maker) as (_, users, cols, _):
            u = await users.get_or_create(cb.from_user.id, cb.from_user.username)
            all_cols = await cols.list_by_user(u.id)
        await cb.message.edit_text(fmt_choose_collection(), reply_markup=game_collections_kb(all_cols, page=page))
        await cb.answer()


    @router.callback_query(F.data.startswith("game:begin:"))
    async def cb_game_begin(cb: types.CallbackQuery) -> None:
        parts = cb.data.split(":")
        try:
            collection_id = int(parts[2])
        except Exception:
            await cb.answer("Некорректная коллекция", show_alert=True)
            return

        gd = GameData(async_session_maker)
        item_ids = await gd.get_item_ids(collection_id)
        if not item_ids:
            await cb.answer("В коллекции пока нет карточек.", show_alert=True)
            return

        sess = await GameSession.start_new(
            redis_kv,
            cb.from_user.id,
            collection_id,
            item_ids,
            ttl=getattr(redis_kv, 'ttl_seconds', None),
        )

        await render_current_question(cb.message, sess)
        await cb.answer()


    @router.callback_query(F.data == "game:show")
    async def cb_game_show(cb: types.CallbackQuery) -> None:
        sess = await GameSession.load(redis_kv, cb.from_user.id)
        if not sess or sess.done:
            await cb.answer("Сессия не найдена. Начни игру заново.", show_alert=True)
            return

        sess.showing_answer = True
        await sess.save(redis_kv, ttl=getattr(redis_kv, 'ttl_seconds', None))
        await render_current_question(cb.message, sess)
        await cb.answer()


    @router.callback_query(F.data == "game:hide")
    async def cb_game_hide(cb: types.CallbackQuery) -> None:
        sess = await GameSession.load(redis_kv, cb.from_user.id)
        if not sess or sess.done:
            await cb.answer("Сессия не найдена. Начни игру заново.", show_alert=True)
            return

        sess.showing_answer = False
        await sess.save(redis_kv, ttl=getattr(redis_kv, 'ttl_seconds', None))
        await render_current_question(cb.message, sess)
        await cb.answer()
        

    @router.callback_query(F.data == "game:known")
    async def cb_game_known(cb: types.CallbackQuery) -> None:
        await _mark_and_go(cb, "known")


    @router.callback_query(F.data == "game:unknown")
    async def cb_game_unknown(cb: types.CallbackQuery) -> None:
        await _mark_and_go(cb, "unknown")


    @router.callback_query(F.data == "game:skip")
    async def cb_game_skip(cb: types.CallbackQuery) -> None:
        await _mark_and_go(cb, "skipped")


    @router.callback_query(F.data == "game:next")
    async def cb_game_next(cb: types.CallbackQuery) -> None:
        await _mark_and_go(cb, None)


    async def _mark_and_go(cb: types.CallbackQuery, mark: str | None) -> None:
        sess = await GameSession.load(redis_kv, cb.from_user.id)
        if not sess:
            await cb.answer("Сессия не найдена. Начни игру заново.", show_alert=True)
            return

        was_last = (sess.index + 1 >= sess.total)
        sess.mark_and_next(mark)
        await sess.save(redis_kv, ttl=getattr(redis_kv, 'ttl_seconds', None))

        if sess.done:
            await render_finished(cb.message, sess)
        else:
            await render_current_question(cb.message, sess)

        await cb.answer("Готово" if not was_last else "Финиш!")


    @router.callback_query(F.data == "game:repeat:all")
    async def cb_game_repeat_all(cb: types.CallbackQuery) -> None:
        sess = await GameSession.load(redis_kv, cb.from_user.id)
        if not sess:
            await cb.answer("Сессия не найдена", show_alert=True)
            return

        gd = GameData(async_session_maker)
        item_ids = await gd.get_item_ids(sess.collection_id)

        new_sess = await GameSession.start_new(
            redis_kv,
            cb.from_user.id,
            sess.collection_id,
            item_ids,
            ttl=getattr(redis_kv, 'ttl_seconds', None),
            avoid_order=sess.order,
        )
        await render_current_question(cb.message, new_sess)
        await cb.answer("Новая игра (всё)!")


    @router.callback_query(F.data == "game:repeat:wrong")
    async def cb_game_repeat_wrong(cb: types.CallbackQuery) -> None:
        sess = await GameSession.load(redis_kv, cb.from_user.id)
        if not sess:
            await cb.answer("Сессия не найдена", show_alert=True)
            return

        wrong = sess.wrong_ids()
        if not wrong:
            await cb.answer("Нет ошибочных карточек в этой сессии.", show_alert=True)
            return

        new_sess = await GameSession.start_new(
            redis_kv,
            cb.from_user.id,
            sess.collection_id,
            wrong,
            ttl=getattr(redis_kv, 'ttl_seconds', None),
        )
        await render_current_question(cb.message, new_sess)
        await cb.answer("Новая игра (только ошибочные)!")


    @router.callback_query(F.data == "game:export")
    async def cb_game_export(cb: types.CallbackQuery) -> None:
        sess = await GameSession.load(redis_kv, cb.from_user.id)
        if not sess:
            await cb.answer("Сессия не найдена", show_alert=True)
            return

        gd = GameData(async_session_maker)
        title = await gd.get_collection_title_by_id(sess.collection_id) or "Коллекция"
        items_map = await gd.get_items_bulk(sess.order)

        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["index", "item_id", "status", "seconds", "question", "answer"])
        for idx, item_id in enumerate(sess.order, start=1):
            st = sess.stats.get(str(item_id), "neutral")
            sec = sess.per_item_sec.get(str(item_id), 0)
            q, a = items_map.get(item_id, ("", ""))
            writer.writerow([idx, item_id, st, sec, q, a])

        data = buf.getvalue().encode("utf-8-sig")
        filename = f"export_{title.replace(' ', '_')}.csv"
        await cb.message.answer_document(BufferedInputFile(data, filename=filename))
        await cb.answer("Экспорт готов!")

    async def render_current_question(msg: types.Message, sess: GameSession) -> None:
        gd = GameData(async_session_maker)

        item_id = sess.current_item_id()
        if item_id is None:
            await render_finished(msg, sess)
            return

        qa = await gd.get_item_qa(item_id)
        title = await gd.get_collection_title_by_item(item_id)

        if not qa or title is None:
            from app.keyboards.game_mode import game_finished_kb
            counts = sess.counts()
            await msg.edit_text("Ошибка: карточка не найдена.", reply_markup=game_finished_kb(has_wrong=counts.get("unknown", 0) > 0))
            return

        q, a = qa
        progress = sess.to_progress_str()
        if sess.showing_answer:
            text = fmt_answer(title, q, a, progress)
        else:
            text = fmt_question(title, q, progress)

        await msg.edit_text(text, reply_markup=game_controls_kb(showing_answer=sess.showing_answer))


    async def render_finished(msg: types.Message, sess: GameSession) -> None:
        gd = GameData(async_session_maker)
        title = await gd.get_collection_title_by_id(sess.collection_id) or "Коллекция"
        counts = sess.counts()
        text = fmt_finished_summary(title, sess.total, counts, sess.total_sec)
        from app.keyboards.game_mode import game_finished_kb
        await msg.edit_text(text, reply_markup=game_finished_kb(has_wrong=counts.get("unknown", 0) > 0))
    
    return router
