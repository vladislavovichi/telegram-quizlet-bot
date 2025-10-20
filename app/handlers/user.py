from aiogram import Router, types
from aiogram.filters import Command
from aiogram import F
from app.services.db import get_session


def get_user_router(async_session_maker, ranks, admin_ids, catalog_file) -> Router:
    router = Router()

    @router.message(Command("start"))
    async def cmd_start(message: types.Message):
        await message.answer(
            "Добро пожаловать! Воспользуйся клавиатурой ниже для доступа к возможностям.",
        )

    @router.message(F.text == "👤 Мой профиль")
    async def cmd_profile(message: types.Message):
        tg = message.from_user
        async with get_session(async_session_maker) as session:
            await message.answer("Профиль")

    return router