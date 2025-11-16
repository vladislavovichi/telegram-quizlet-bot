from __future__ import annotations

from typing import Optional

from aiogram.filters import BaseFilter
from aiogram import types

from app.services.redis_kv import RedisKV
from app.services.online_mode import get_online_join_pending


class OnlineJoinPending(BaseFilter):
    def __init__(self, redis_kv: RedisKV):
        self.redis_kv = redis_kv

    async def __call__(self, message: types.Message) -> bool | dict:
        if not message.from_user:
            return False

        data: Optional[dict] = await get_online_join_pending(
            self.redis_kv, message.from_user.id
        )
        if not data:
            return False

        return {"online_pending": data}
