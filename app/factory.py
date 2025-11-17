import logging
from types import SimpleNamespace

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from app.handlers import register_handlers
from app.services.db import make_engine_and_session
from app.services.redis_client import create_redis
from app.services.redis_kv import RedisKV

from .config import settings

log = logging.getLogger(__name__)


async def create_app() -> SimpleNamespace:
    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    dp = Dispatcher(storage=MemoryStorage())
    engine, async_session_maker = make_engine_and_session(settings.DB_DSN)

    redis_client = create_redis(settings.REDIS_DSN)
    redis_kv = RedisKV(
        client=redis_client,
        prefix=settings.REDIS_PREFIX,
        ttl_seconds=settings.REDIS_TTL_SEC,
    )

    await bot.delete_webhook(drop_pending_updates=True)

    register_handlers(dp, async_session_maker=async_session_maker, redis_kv=redis_kv)

    ns = SimpleNamespace(
        bot=bot,
        dp=dp,
        engine=engine,
        async_session_maker=async_session_maker,
        redis_client=redis_client,
        redis_kv=redis_kv,
    )
    return ns
