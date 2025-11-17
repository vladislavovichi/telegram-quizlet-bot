from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware, types

from app.services.redis_kv import RedisKV


class RedisKVMiddleware(BaseMiddleware):
    def __init__(self, redis_kv: RedisKV) -> None:
        super().__init__()
        self.redis_kv = redis_kv

    async def __call__(
        self,
        handler: Callable[[types.TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: types.TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        data["redis_kv"] = self.redis_kv
        return await handler(event, data)
