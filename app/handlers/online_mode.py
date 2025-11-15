from __future__ import annotations

import asyncio
import io
import logging
import time as pytime
from datetime import datetime

from aiogram import F, Router, types
from aiogram.filters import Command
from aiogram.types import BufferedInputFile

from app.filters.online_mode import OnlineJoinPending
from app.keyboards.online_mode import (
    online_collections_kb,
    online_join_cancel_kb,
    online_player_kb,
    online_room_owner_kb,
    online_root_kb,
)
from app.middlewares.redis_kv import RedisKVMiddleware
from app.models.online_room import MAX_PLAYERS_PER_ROOM, OnlineRoom
from app.repos.base import with_repos
from app.services.game_mode import GameData
from app.services.online_mode import (
    clear_online_join_pending,
    run_room_loop,
    set_online_join_pending,
    update_owner_room_message,
)
from app.services.redis_kv import RedisKV
from app.texts.game_mode import fmt_choose_collection
from app.texts.online_mode import (
    fmt_online_root,
    fmt_player_waiting,
    fmt_room_waiting,
)

log = logging.getLogger(__name__)

DEFAULT_SECONDS_PER_QUESTION = 15
DEFAULT_POINTS_PER_CORRECT = 100

try:
    import qrcode  # type: ignore[import]
except Exception:  # pragma: no cover
    qrcode = None


def get_online_mode_router(async_session_maker, redis_kv: RedisKV) -> Router:
    router = Router(name="online_mode")
    router.message.middleware(RedisKVMiddleware(redis_kv))

    ttl = redis_kv.ttl_seconds

    def _normalize_answer(text: str) -> str:
        return " ".join((text or "").strip().lower().split())

    def _is_correct(user_answer: str, correct: str) -> bool:
        return _normalize_answer(user_answer) == _normalize_answer(correct)

    @router.message(F.text == "🤼 Играть онлайн")
    @router.message(Command("online"))
    async def cmd_online(message: types.Message) -> None:
        await message.answer(fmt_online_root(), reply_markup=online_root_kb())

    @router.callback_query(F.data == "online:root")
    async def cb_root(cb: types.CallbackQuery) -> None:
        await cb.message.edit_text(fmt_online_root(), reply_markup=online_root_kb())
        await cb.answer()

    @router.callback_query(F.data == "online:create")
    async def cb_create(cb: types.CallbackQuery) -> None:
        existing = await OnlineRoom.load_by_user(redis_kv, cb.from_user.id)
        if existing and existing.state in {"waiting", "running"}:
            await cb.answer("Сначала выйди из текущей комнаты.", show_alert=True)
            return

        async with with_repos(async_session_maker) as (_, users, cols, _):
            u = await users.get_or_create(cb.from_user.id, cb.from_user.username)
            all_cols = await cols.list_by_user(u.id)

        if not all_cols:
            await cb.answer("У тебя пока нет коллекций.", show_alert=True)
            return

        await cb.message.edit_text(
            fmt_choose_collection(),
            reply_markup=online_collections_kb(all_cols, page=0),
        )
        await cb.answer()

    @router.callback_query(F.data.startswith("online:page:"))
    async def cb_page(cb: types.CallbackQuery) -> None:
        try:
            page = int(cb.data.split(":")[2])
        except Exception:
            page = 0

        async with with_repos(async_session_maker) as (_, users, cols, _):
            u = await users.get_or_create(cb.from_user.id, cb.from_user.username)
            all_cols = await cols.list_by_user(u.id)

        await cb.message.edit_text(
            fmt_choose_collection(),
            reply_markup=online_collections_kb(all_cols, page=page),
        )
        await cb.answer()

    @router.callback_query(F.data.startswith("online:col:"))
    async def cb_choose_collection(cb: types.CallbackQuery) -> None:
        parts = cb.data.split(":")
        try:
            collection_id = int(parts[2])
        except Exception:
            await cb.answer("Некорректная коллекция.", show_alert=True)
            return

        gd = GameData(async_session_maker)
        item_ids = await gd.get_item_ids(collection_id)
        if not item_ids:
            await cb.answer("В коллекции пока нет карточек.", show_alert=True)
            return

        room = await OnlineRoom.create(
            redis_kv,
            owner_id=cb.from_user.id,
            collection_id=collection_id,
            item_ids=item_ids,
            seconds_per_question=DEFAULT_SECONDS_PER_QUESTION,
            points_per_correct=DEFAULT_POINTS_PER_CORRECT,
            ttl=ttl,
        )

        title = await gd.get_collection_title_by_id(collection_id) or "Коллекция"

        deep_link: str | None = None
        try:
            me = await cb.bot.get_me()
            if me.username:
                deep_link = f"https://t.me/{me.username}?start=online_{room.room_id}"
        except Exception as e:  # pragma: no cover
            log.debug("failed to get bot username for deep link: %s", e)

        sent = await cb.message.answer(
            fmt_room_waiting(
                title=title,
                room_id=room.room_id,
                seconds_per_question=room.seconds_per_question,
                points_per_correct=room.points_per_correct,
                players_count=len(room.players),
                deep_link=deep_link,
            ),
            reply_markup=online_room_owner_kb(room.room_id),
        )

        room.owner_wait_chat_id = sent.chat.id
        room.owner_wait_message_id = sent.message_id
        await room.save(redis_kv, ttl=ttl)

        if deep_link and qrcode is not None:
            try:
                img = qrcode.make(deep_link)
                bio = io.BytesIO()
                img.save(bio, format="PNG")
                bio.seek(0)
                qr_file = BufferedInputFile(
                    bio.read(), filename=f"room_{room.room_id}.png"
                )
                await cb.message.answer_photo(
                    photo=qr_file,
                    caption=(
                        "Сканируй QR-код, чтобы открыть бота и автоматически "
                        "подключиться к этой комнате."
                    ),
                )
            except Exception as e:  # pragma: no cover
                log.debug("failed to generate QR: %s", e)

        await cb.answer()

    @router.callback_query(F.data == "online:join")
    async def cb_join(cb: types.CallbackQuery) -> None:
        existing = await OnlineRoom.load_by_user(redis_kv, cb.from_user.id)
        if existing and existing.state in {"waiting", "running"}:
            await cb.answer("Сначала выйди из текущей комнаты.", show_alert=True)
            return

        await set_online_join_pending(redis_kv, cb.from_user.id)
        await cb.message.answer(
            "🔑 Пришли код комнаты (6 цифр), чтобы подключиться.\n"
            "Для отмены используй кнопку ниже.",
            reply_markup=online_join_cancel_kb(),
        )
        await cb.answer()

    @router.callback_query(F.data == "online:join_cancel")
    async def cb_join_cancel(cb: types.CallbackQuery) -> None:
        await clear_online_join_pending(redis_kv, cb.from_user.id)
        try:
            await cb.message.edit_text("Подключение к комнате отменено.")
        except Exception:
            await cb.answer("Подключение отменено.")
        else:
            await cb.answer()

    @router.callback_query(F.data.startswith("online:leave:"))
    async def cb_leave(cb: types.CallbackQuery) -> None:
        room_id = cb.data.split(":")[2]
        room = await OnlineRoom.load_by_room_id(redis_kv, room_id)
        if not room:
            await cb.answer("Комната уже закрыта.", show_alert=True)
            try:
                await OnlineRoom.clear_user_room(redis_kv, cb.from_user.id)
            except Exception:
                pass
            return

        room.remove_player(cb.from_user.id)
        await OnlineRoom.clear_user_room(redis_kv, cb.from_user.id)
        await room.save(redis_kv, ttl=ttl)

        await cb.message.edit_text("Ты вышел из комнаты.")
        await cb.answer()

        if room.owner_id != cb.from_user.id and room.state == "waiting":
            await update_owner_room_message(
                async_session_maker, redis_kv, cb.bot, room.room_id
            )

    @router.callback_query(F.data.startswith("online:cancel:"))
    async def cb_cancel(cb: types.CallbackQuery) -> None:
        room_id = cb.data.split(":")[2]
        room = await OnlineRoom.load_by_room_id(redis_kv, room_id)
        if not room or room.owner_id != cb.from_user.id:
            await cb.answer("Комната не найдена или ты не владелец.", show_alert=True)
            return

        room.state = "canceled"
        await room.save(redis_kv, ttl=ttl)

        for p in room.players:
            try:
                await cb.bot.send_message(p.user_id, "Владелец отменил игру.")
            except Exception:
                pass
            await OnlineRoom.clear_user_room(redis_kv, p.user_id)

        await cb.message.edit_text("Комната закрыта.")
        await cb.answer()

    @router.callback_query(F.data.startswith("online:start:"))
    async def cb_start(cb: types.CallbackQuery) -> None:
        room_id = cb.data.split(":")[2]
        room = await OnlineRoom.load_by_room_id(redis_kv, room_id)
        if not room or room.owner_id != cb.from_user.id:
            await cb.answer("Комната не найдена или ты не владелец.", show_alert=True)
            return

        if room.state != "waiting":
            await cb.answer("Игра уже запущена или завершена.", show_alert=True)
            return

        if len(room.players) == 0:
            await cb.answer("В комнате пока нет игроков.", show_alert=True)
            return

        room.state = "running"
        room.started_at = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        room.index = 0
        room.answered_user_ids = []
        await room.save(redis_kv, ttl=ttl)

        await cb.message.edit_text(
            "Игра запущена! После каждого вопроса рейтинг будет обновляться."
        )
        await cb.answer()

        asyncio.create_task(
            run_room_loop(room.room_id, async_session_maker, redis_kv, cb.bot)
        )

    @router.message(F.text.regexp(r"^/start\s+online_"))
    async def cmd_start_online(message: types.Message) -> None:
        if not message.from_user:
            return

        text = message.text or ""
        parts = text.split(maxsplit=1)
        if len(parts) < 2:
            return

        payload = parts[1].strip()
        if not payload.startswith("online_"):
            return

        code = payload[len("online_") :]

        existing = await OnlineRoom.load_by_user(redis_kv, message.from_user.id)
        if existing and existing.state in {"waiting", "running"}:
            await message.answer("Сначала выйди из текущей комнаты.")
            return

        room = await OnlineRoom.load_by_room_id(redis_kv, code)
        if not room or room.state != "waiting":
            await message.answer("Комната не найдена или уже запущена.")
            return

        if len(room.players) >= MAX_PLAYERS_PER_ROOM:
            await message.answer("Достигнут лимит 30 игроков в комнате.")
            return

        if message.from_user.id == room.owner_id:
            await message.answer("Ты владелец комнаты и не участвуешь как игрок.")
            return

        room.add_player(message.from_user.id, message.from_user.username)
        await OnlineRoom.set_user_room(
            redis_kv, message.from_user.id, room.room_id, ttl=ttl
        )
        await room.save(redis_kv, ttl=ttl)

        gd = GameData(async_session_maker)
        title = await gd.get_collection_title_by_id(room.collection_id) or "Коллекция"

        await message.answer(
            fmt_player_waiting(
                title=title,
                room_id=room.room_id,
                seconds_per_question=room.seconds_per_question,
                points_per_correct=room.points_per_correct,
            ),
            reply_markup=online_player_kb(room.room_id),
        )

        await update_owner_room_message(
            async_session_maker, redis_kv, message.bot, room.room_id
        )

    @router.message(OnlineJoinPending(redis_kv))
    async def handle_pending_online(
        message: types.Message, online_pending: dict
    ) -> None:
        code = (message.text or "").strip()
        user_id = message.from_user.id
        await clear_online_join_pending(redis_kv, user_id)

        if not code:
            await message.answer("Не вижу кода, попробуй ещё раз.")
            return

        room = await OnlineRoom.load_by_room_id(redis_kv, code)
        if not room or room.state != "waiting":
            await message.answer("Комната не найдена или уже запущена.")
            return

        if room.has_player(user_id):
            await message.answer("Ты уже в этой комнате.")
            return

        if len(room.players) >= MAX_PLAYERS_PER_ROOM:
            await message.answer("Достигнут лимит 30 игроков в комнате.")
            return

        if user_id == room.owner_id:
            await message.answer("Ты владелец комнаты и не участвуешь как игрок.")
            return

        room.add_player(user_id, message.from_user.username)
        await OnlineRoom.set_user_room(redis_kv, user_id, room.room_id, ttl=ttl)
        await room.save(redis_kv, ttl=ttl)

        gd = GameData(async_session_maker)
        title = await gd.get_collection_title_by_id(room.collection_id) or "Коллекция"

        await message.answer(
            fmt_player_waiting(
                title=title,
                room_id=room.room_id,
                seconds_per_question=room.seconds_per_question,
                points_per_correct=room.points_per_correct,
            ),
            reply_markup=online_player_kb(room.room_id),
        )

        await update_owner_room_message(
            async_session_maker, redis_kv, message.bot, room.room_id
        )

    @router.message(F.text & ~F.text.startswith("/"))
    async def handle_answers(message: types.Message) -> None:
        if not message.from_user or not (message.text and message.text.strip()):
            return

        room = await OnlineRoom.load_by_user(redis_kv, message.from_user.id)
        if not room or room.state != "running":
            return

        if message.from_user.id == room.owner_id:
            return

        now = pytime.time()
        if room.question_deadline_ts is None or now > room.question_deadline_ts:
            return

        if message.from_user.id in room.answered_user_ids:
            await message.answer("Ответ уже принят, ждём следующий вопрос.")
            return

        item_id = room.current_item_id()
        if item_id is None:
            return

        gd = GameData(async_session_maker)
        qa = await gd.get_item_qa(item_id)
        if not qa:
            return

        _, correct_answer = qa

        start_ts = room.question_deadline_ts - room.seconds_per_question
        raw_dt = now - start_ts
        answer_time = max(0.0, min(raw_dt, float(room.seconds_per_question)))

        text = message.text or ""

        for p in room.players:
            if p.user_id == message.from_user.id:
                if _is_correct(text, correct_answer):
                    p.score += room.points_per_correct

                p.total_answer_time += answer_time
                break

        room.answered_user_ids.append(message.from_user.id)
        await room.save(redis_kv, ttl=ttl)

    router.priority = 0
    return router
