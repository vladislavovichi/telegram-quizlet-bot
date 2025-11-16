from __future__ import annotations

import logging
import io
import csv
from aiogram import Router, F, types
from aiogram.types import BufferedInputFile
from aiogram.filters import Command

from app.keyboards.solo_mode import (
    solo_collections_kb,
    solo_controls_kb,
    solo_finished_kb,
)
from app.services.collections_facade import get_user_and_collections
from app.texts.solo_mode import (
    fmt_question,
    fmt_answer,
    fmt_finished_summary,
    fmt_choose_collection,
)
from app.models.solo_mode import SoloSession
from app.services.solo_mode import (
    SoloData,
    load_solo_session,
    save_solo_session,
    start_new_solo_session,
)
from app.services.hints import generate_hint_async
from app.services.redis_kv import RedisKV

log = logging.getLogger(__name__)


def get_solo_mode_router(async_session_maker, redis_kv: RedisKV) -> Router:
    router = Router(name="solo_mode")

    @router.message(F.text == "🎮 Играть одному")
    @router.message(Command("solo"))
    async def cmd_solo_start(message: types.Message) -> None:
        key = redis_kv.pending_key(message.from_user.id)
        await redis_kv.delete(key)

        uc = await get_user_and_collections(
            async_session_maker,
            message.from_user.id,
            message.from_user.username,
        )
        all_cols = uc.collections

        await message.answer(
            fmt_choose_collection(),
            reply_markup=solo_collections_kb(all_cols, page=0),
        )

    @router.callback_query(F.data == "solo:choose")
    async def cb_solo_choose(cb: types.CallbackQuery) -> None:
        uc = await get_user_and_collections(
            async_session_maker,
            cb.from_user.id,
            cb.from_user.username,
        )
        all_cols = uc.collections

        await cb.message.edit_text(
            fmt_choose_collection(),
            reply_markup=solo_collections_kb(all_cols, page=0),
        )
        await cb.answer()

    @router.callback_query(F.data.startswith("solo:page:"))
    async def cb_solo_page(cb: types.CallbackQuery) -> None:
        try:
            page = int(cb.data.split(":")[2])
        except Exception:
            page = 0

        uc = await get_user_and_collections(
            async_session_maker,
            cb.from_user.id,
            cb.from_user.username,
        )
        all_cols = uc.collections

        await cb.message.edit_text(
            fmt_choose_collection(),
            reply_markup=solo_collections_kb(all_cols, page=page),
        )
        await cb.answer()

    @router.callback_query(F.data.startswith("solo:begin:"))
    async def cb_solo_begin(cb: types.CallbackQuery) -> None:
        parts = cb.data.split(":")
        try:
            collection_id = int(parts[2])
        except Exception:
            await cb.answer("Некорректная коллекция", show_alert=True)
            return

        gd = SoloData(async_session_maker)
        item_ids = await gd.get_item_ids(collection_id)
        if not item_ids:
            await cb.answer("В коллекции пока нет карточек.", show_alert=True)
            return

        sess = await start_new_solo_session(
            redis_kv,
            cb.from_user.id,
            collection_id,
            item_ids,
            ttl=getattr(redis_kv, "ttl_seconds", None),
        )

        await render_current_question(cb.message, sess)
        await cb.answer()

    @router.callback_query(F.data == "solo:show")
    async def cb_solo_show(cb: types.CallbackQuery) -> None:
        sess = await load_solo_session(redis_kv, cb.from_user.id)
        if not sess or sess.done:
            await cb.answer("Сессия не найдена. Начни игру заново.", show_alert=True)
            return

        sess.showing_answer = True
        await save_solo_session(
            redis_kv,
            sess,
            ttl=getattr(redis_kv, "ttl_seconds", None),
        )
        await render_current_question(cb.message, sess)
        await cb.answer()

    @router.callback_query(F.data == "solo:hide")
    async def cb_solo_hide(cb: types.CallbackQuery) -> None:
        sess = await load_solo_session(redis_kv, cb.from_user.id)
        if not sess or sess.done:
            await cb.answer("Сессия не найдена. Начни игру заново.", show_alert=True)
            return

        sess.showing_answer = False
        await save_solo_session(
            redis_kv,
            sess,
            ttl=getattr(redis_kv, "ttl_seconds", None),
        )
        await render_current_question(cb.message, sess)
        await cb.answer()

    @router.callback_query(F.data == "solo:known")
    async def cb_solo_known(cb: types.CallbackQuery) -> None:
        await _mark_and_go(cb, "known")

    @router.callback_query(F.data == "solo:unknown")
    async def cb_solo_unknown(cb: types.CallbackQuery) -> None:
        await _mark_and_go(cb, "unknown")

    @router.callback_query(F.data == "solo:skip")
    async def cb_solo_skip(cb: types.CallbackQuery) -> None:
        await _mark_and_go(cb, "skipped")

    async def _mark_and_go(cb: types.CallbackQuery, mark: str | None) -> None:
        sess = await load_solo_session(redis_kv, cb.from_user.id)
        if not sess:
            await cb.answer("Сессия не найдена. Начни игру заново.", show_alert=True)
            return

        was_last = sess.index + 1 >= sess.total
        sess.mark_and_next(mark)
        await save_solo_session(
            redis_kv,
            sess,
            ttl=getattr(redis_kv, "ttl_seconds", None),
        )

        if sess.done:
            await render_finished(cb.message, sess)
        else:
            await render_current_question(cb.message, sess)

        await cb.answer("Готово" if not was_last else "Финиш!")

    @router.callback_query(F.data == "solo:repeat:all")
    async def cb_solo_repeat_all(cb: types.CallbackQuery) -> None:
        sess = await load_solo_session(redis_kv, cb.from_user.id)
        if not sess:
            await cb.answer("Сессия не найдена", show_alert=True)
            return

        gd = SoloData(async_session_maker)
        item_ids = await gd.get_item_ids(sess.collection_id)

        new_sess = await start_new_solo_session(
            redis_kv,
            cb.from_user.id,
            sess.collection_id,
            item_ids,
            ttl=getattr(redis_kv, "ttl_seconds", None),
            avoid_order=sess.order,
        )
        await render_current_question(cb.message, new_sess)
        await cb.answer("Новая игра (всё)!")

    @router.callback_query(F.data == "solo:repeat:wrong")
    async def cb_solo_repeat_wrong(cb: types.CallbackQuery) -> None:
        sess = await load_solo_session(redis_kv, cb.from_user.id)
        if not sess:
            await cb.answer("Сессия не найдена", show_alert=True)
            return

        wrong = sess.wrong_ids()
        if not wrong:
            await cb.answer("Нет ошибочных карточек в этой сессии.", show_alert=True)
            return

        new_sess = await start_new_solo_session(
            redis_kv,
            cb.from_user.id,
            sess.collection_id,
            wrong,
            ttl=getattr(redis_kv, "ttl_seconds", None),
        )
        await render_current_question(cb.message, new_sess)
        await cb.answer("Новая игра (только ошибочные)!")

    @router.callback_query(F.data == "solo:export")
    async def cb_solo_export(cb: types.CallbackQuery) -> None:
        sess = await load_solo_session(redis_kv, cb.from_user.id)
        if not sess:
            await cb.answer("Сессия не найдена", show_alert=True)
            return

        gd = SoloData(async_session_maker)
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

    @router.callback_query(F.data == "solo:hint")
    async def cb_solo_hint(cb: types.CallbackQuery) -> None:
        sess = await load_solo_session(redis_kv, cb.from_user.id)
        if not sess or sess.done:
            await cb.answer("Сессия не найдена. Начни игру заново.", show_alert=True)
            return

        item_id = sess.current_item_id()
        if item_id is None:
            await cb.answer("Карточки закончились", show_alert=True)
            return

        key = str(item_id)
        hints = list(sess.hints.get(key, []))
        if len(hints) >= 3:
            await cb.answer("Лимит 3 подсказки для карточки", show_alert=True)
            return

        gd = SoloData(async_session_maker)
        qa = await gd.get_item_qa(item_id)
        if not qa:
            await cb.answer("Вопрос не найден", show_alert=True)
            return

        q, _ = qa

        try:
            await cb.answer("Генерирую подсказку…")
            new_hint = await generate_hint_async(q, hints)
        except Exception as e:
            log.exception("hint generation failed: %s", e)
            await cb.answer("Не удалось создать подсказку 😔", show_alert=True)
            return

        if not new_hint:
            await cb.answer("Нет подсказки", show_alert=True)
            return

        hints.append(str(new_hint).strip())
        sess.hints[key] = hints
        await save_solo_session(
            redis_kv,
            sess,
            ttl=getattr(redis_kv, "ttl_seconds", None),
        )

        await render_current_question(cb.message, sess)

    async def render_current_question(msg: types.Message, sess: SoloSession) -> None:
        gd = SoloData(async_session_maker)

        item_id = sess.current_item_id()
        if item_id is None:
            await render_finished(msg, sess)
            return

        qa = await gd.get_item_qa(item_id)
        title = await gd.get_collection_title_by_item(item_id)

        if not qa or title is None:
            from app.keyboards.solo_mode import solo_finished_kb

            counts = sess.counts()
            await msg.edit_text(
                "Ошибка: карточка не найдена.",
                reply_markup=solo_finished_kb(has_wrong=counts.get("unknown", 0) > 0),
            )
            return

        q, a = qa
        progress = sess.to_progress_str()
        hints = sess.hints.get(str(item_id), [])
        if sess.showing_answer:
            text = fmt_answer(title, q, a, progress, hints)
        else:
            text = fmt_question(title, q, progress, hints)

        await msg.edit_text(
            text,
            reply_markup=solo_controls_kb(
                showing_answer=sess.showing_answer,
                hints_used=len(sess.hints.get(str(item_id), [])),
            ),
        )

    async def render_finished(msg: types.Message, sess: SoloSession) -> None:
        gd = SoloData(async_session_maker)
        title = await gd.get_collection_title_by_id(sess.collection_id) or "Коллекция"
        counts = sess.counts()
        text = fmt_finished_summary(title, sess.total, counts, sess.total_sec)

        await msg.edit_text(
            text, reply_markup=solo_finished_kb(has_wrong=counts.get("unknown", 0) > 0)
        )

    router.priority = -1
    return router
