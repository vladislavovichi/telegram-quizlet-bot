from __future__ import annotations

from typing import Any, Dict, Optional
from aiogram.filters import BaseFilter
from aiogram import types
from app.services.redis_kv import RedisKV


class HasPendingAction(BaseFilter):
    def __init__(self, redis_kv: Optional[RedisKV] = None) -> None:
        self._redis_kv = redis_kv

    async def __call__(
        self,
        message: types.Message,
        event: Optional[types.TelegramObject] = None,
        **data: Any,
    ) -> Dict[str, Any] | bool:
        if not message.from_user:
            return False

        redis_kv: Optional[RedisKV] = self._redis_kv or data.get("redis_kv")
        if not redis_kv:
            return False

        key = redis_kv.pending_key(message.from_user.id)
        pending = await redis_kv.get_json(key)
        return {"pending": pending} if pending else False
