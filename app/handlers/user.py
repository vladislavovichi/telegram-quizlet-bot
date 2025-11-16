from __future__ import annotations

from aiogram import Router, F, types
from aiogram.filters import CommandStart, Command

from app.keyboards.user import main_reply_kb, profile_inline_kb, profile_cancel_kb
from app.services.redis_kv import RedisKV
from app.filters.pending import HasProfilePendingAction
from app.services.user_profile import (
    ensure_user_exists,
    load_profile,
    update_name_and_get_profile,
)
from app.texts.user_profile import make_profile_text


def get_user_router(async_session_maker, redis_kv: RedisKV) -> Router:
    router = Router(name="user")

    @router.message(CommandStart(deep_link=False))
    async def cmd_start(message: types.Message) -> None:
        tg = message.from_user
        if not tg:
            return


        await ensure_user_exists(async_session_maker, tg.id, tg.username)

        text = (
            "Привет! Я квизлет бот!.\n\n"
            "Воспользуйся клавиатурой ниже для изучения моих возможностей."
        )
        await message.answer(text, reply_markup=main_reply_kb)

    @router.message(F.text == "👤 Мой профиль")
    @router.message(Command("profile"))
    async def cmd_profile(message: types.Message) -> None:
        tg = message.from_user
        if not tg:
            return

        profile = await load_profile(async_session_maker, tg.id, tg.username)
        text = make_profile_text(tg, profile)

        await message.answer(
            text,
            reply_markup=profile_inline_kb(),
        )

    @router.callback_query(F.data == "profile:change_name")
    async def cb_profile_change_name(cb: types.CallbackQuery) -> None:
        tg = cb.from_user
        if not tg:
            await cb.answer()
            return

        key = redis_kv.pending_key(tg.id)
        await redis_kv.set_json(
            key,
            {"type": "profile:change_name"},
            ex=redis_kv.ttl_seconds,
        )

        try:
            await cb.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass

        await cb.message.answer(
            "Введи новое имя, которое я буду показывать в профиле и в играх:",
            reply_markup=profile_cancel_kb(),
        )
        await cb.answer()

    @router.callback_query(F.data == "profile:cancel_change_name")
    async def cb_profile_cancel_change_name(cb: types.CallbackQuery) -> None:
        tg = cb.from_user
        if not tg:
            await cb.answer()
            return

        key = redis_kv.pending_key(tg.id)
        await redis_kv.delete(key)

        try:
            await cb.message.edit_text("Изменение имени отменено.")
        except Exception:
            await cb.message.answer("Изменение имени отменено.")

        await cb.answer()

    @router.message(HasProfilePendingAction(redis_kv))
    async def handle_profile_pending(message: types.Message, pending: dict) -> None:
        tg = message.from_user
        if not tg:
            return

        new_name = (message.text or "").strip()
        if not new_name:
            await message.answer("Не вижу текста. Введи новое имя:")
            return

        key = redis_kv.pending_key(tg.id)

        profile = await update_name_and_get_profile(
            async_session_maker,
            tg.id,
            tg.username,
            new_name,
        )

        await redis_kv.delete(key)

        text = make_profile_text(
            tg=tg,
            profile=profile,
            name_override=new_name,
        )

        await message.answer(
            text,
            reply_markup=profile_inline_kb(),
        )

    @router.message(Command("cancel"))
    async def cmd_cancel(message: types.Message) -> None:
        tg = message.from_user
        if not tg:
            return

        key = redis_kv.pending_key(tg.id)
        await redis_kv.delete(key)

        text = "Состояния успешно сброшены.\n\n"
        await message.answer(text, reply_markup=main_reply_kb)

    router.priority = -100
    return router
