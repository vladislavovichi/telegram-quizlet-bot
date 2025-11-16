from __future__ import annotations

from typing import Any, Dict, Optional

from aiogram import types
from aiogram.filters import BaseFilter

from app.services.redis_kv import RedisKV

MAIN_BUTTONS = {
    "🎮 Играть одному",
    "👀 Мои коллекции",
    "👤 Мой профиль",
    "🤼 Играть онлайн",
}


class HasCollectionsPendingAction(BaseFilter):
    """
    Общий pending-фильтр для работы с коллекциями / карточками.
    Используется в handlers/collections.py.
    """

    def __init__(self, redis_kv: Optional[RedisKV] = None) -> None:
        self._redis_kv = redis_kv

    async def __call__(
        self,
        message: types.Message,
        **data: Any,
    ) -> Dict[str, Any] | bool:
        if not message.from_user:
            return False

        text = (message.text or "").strip()
        if text in MAIN_BUTTONS:
            return False

        redis_kv: Optional[RedisKV] = self._redis_kv or data.get("redis_kv")
        if not redis_kv:
            return False

        key = redis_kv.pending_key(message.from_user.id)
        pending = await redis_kv.get_json(key)
        return {"pending": pending} if pending else False


class HasProfilePendingAction(BaseFilter):
    def __init__(self, redis_kv: RedisKV) -> None:
        self.redis_kv = redis_kv

    async def __call__(
        self,
        message: types.Message,
        **data: Any,
    ) -> Dict[str, Any] | bool:
        if not message.from_user:
            return False

        text = (message.text or "").strip()
        if not text or text.startswith("/") or text in MAIN_BUTTONS:
            return False

        key = self.redis_kv.pending_key(message.from_user.id)
        pending = await self.redis_kv.get_json(key)
        if not pending or pending.get("type") != "profile:change_name":
            return False

        return {"pending": pending}
