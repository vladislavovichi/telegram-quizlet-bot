from __future__ import annotations

from typing import Optional

from aiogram.filters import BaseFilter
from aiogram import types

from app.services.redis_kv import RedisKV
from app.services.online_mode import get_online_join_pending

from app.models.online_room import OnlineRoom
import time


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


class OnlineAnswerPending(BaseFilter):
    def __init__(self, redis_kv: RedisKV):
        self.redis_kv = redis_kv

    async def __call__(self, message: types.Message) -> bool | dict:
        if not message.from_user:
            return False

        text = (message.text or "").strip()
        if not text:
            return False

        room = await OnlineRoom.load_by_user(self.redis_kv, message.from_user.id)
        if not room or room.state != "running":
            return False

        if message.from_user.id == room.owner_id:
            return False

        now = time.time()
        if room.question_deadline_ts is None or now > room.question_deadline_ts:
            return False

        return {"room": room}
