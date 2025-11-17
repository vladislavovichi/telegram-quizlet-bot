from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from redis.asyncio import Redis


@dataclass(slots=True)
class RedisKV:
    client: Redis
    prefix: str
    ttl_seconds: int

    def _key(self, *parts: Any) -> str:
        return ":".join([self.prefix, *map(lambda x: str(x), parts)])

    async def set_json(self, key: str, value: dict, ex: int | None = None) -> None:
        await self.client.set(
            key, json.dumps(value, ensure_ascii=False).encode("utf-8"), ex=ex
        )

    async def get_json(self, key: str) -> dict | None:
        raw = await self.client.get(key)
        return None if raw is None else json.loads(raw.decode("utf-8"))

    async def delete(self, key: str) -> None:
        await self.client.delete(key)

    def pending_key(self, user_id: int) -> str:
        return self._key("pending", user_id)
