from __future__ import annotations

from aiogram import Router, types
from aiogram.filters import CommandStart
from sqlalchemy import select

from app.services.db import get_session
from app.models.user import User
from app.keyboards.user import main_reply_kb


def get_user_router(async_session_maker) -> Router:
    router = Router(name="user")

    @router.message(CommandStart())
    async def cmd_start(message: types.Message) -> None:
        tg = message.from_user
        if not tg:
            return

        async with get_session(async_session_maker) as session:
            user = (
                await session.execute(select(User).where(User.tg_id == tg.id))
            ).scalar_one_or_none()
            if not user:
                user = User(tg_id=tg.id, username=tg.username)
                session.add(user)
                await session.commit()

        text = (
            "Привет! Я квизлет бот!.\n\n"
            "Воспользуйся клавиатурой ниже для изучения моих возможностей."
        )
        await message.answer(text, reply_markup=main_reply_kb)

    router.priority = -100
    return router
