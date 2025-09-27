import logging
from types import SimpleNamespace
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from .config import settings
from app.services.db import make_engine_and_session

log = logging.getLogger(__name__)

async def create_app() -> SimpleNamespace:
    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    dp = Dispatcher(storage=MemoryStorage())
    engine, async_session_maker = make_engine_and_session(settings.DB_DSN)

    await bot.delete_webhook(drop_pending_updates=True)

    ns = SimpleNamespace(
        bot=bot,
        dp=dp,
        engine=engine,
        async_session_maker=async_session_maker,
    )
    return ns
