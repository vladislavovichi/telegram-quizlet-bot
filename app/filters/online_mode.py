from __future__ import annotations

import time
from typing import Optional

from aiogram import types
from aiogram.filters import BaseFilter

from app.models.online_room import OnlineRoom
from app.services.online_mode import (
    get_online_join_pending,
    get_online_settings_pending,
)
from app.services.redis_kv import RedisKV


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


class OnlineSettingsPending(BaseFilter):
    def __init__(self, redis_kv: RedisKV):
        self.redis_kv = redis_kv

    async def __call__(self, message: types.Message) -> bool | dict:
        if not message.from_user:
            return False

        data: Optional[dict] = await get_online_settings_pending(
            self.redis_kv, message.from_user.id
        )
        if not data:
            return False

        room_id = data.get("room_id")
        field = data.get("field")
        if not room_id or field not in {"points", "seconds"}:
            return False

        room = await OnlineRoom.load_by_room_id(self.redis_kv, room_id)
        if not room or room.state != "waiting":
            return False

        if message.from_user.id != room.owner_id:
            return False

        return {"room": room, "settings_pending": data}
