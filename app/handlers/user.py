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
        async with get_session(async_session_maker) as session:
            tg = message.from_user
            user = (
                await session.execute(select(User).where(User.tg_id == tg.id))
            ).scalar_one_or_none()
            if not user:
                user = User(tg_id=tg.id, username=tg.username)
                session.add(user)
                await session.commit()

        text = (
            "Привет! Я помогу вести коллекции карточек «вопрос-ответ».\n\n"
            "Нажми «123» или «👀 Мои коллекции», чтобы начать."
        )
        await message.answer(text, reply_markup=main_reply_kb)

    get_user_router.priority = -100
    return router
