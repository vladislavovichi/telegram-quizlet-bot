from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple
from datetime import datetime
from contextlib import asynccontextmanager
import secrets

from sqlalchemy import select

from app.services.redis_kv import RedisKV
from app.services.db import get_session
from app.models.collection import Collection, CollectionItem


@dataclass(slots=True)
class GameSession:
    user_id: int
    collection_id: int
    order: List[int]
    index: int = 0 
    showing_answer: bool = False
    started_at: str = ""
    seed: int = 0  

    @property
    def total(self) -> int:
        return len(self.order)

    @property
    def seen(self) -> int:
        return min(self.index, self.total)

    @property
    def done(self) -> bool:
        return self.index >= self.total

    @staticmethod
    def _key(redis_kv: RedisKV, user_id: int) -> str:
        try:
            return redis_kv._key("game", user_id)
        except AttributeError:
            return f"game:{user_id}"

    @classmethod
    async def load(cls, redis_kv: RedisKV, user_id: int) -> Optional["GameSession"]:
        raw = await redis_kv.get_json(cls._key(redis_kv, user_id))
        if not raw:
            return None
        order = list(map(int, raw.get("order", [])))
        return GameSession(
            user_id=int(raw.get("user_id", user_id)),
            collection_id=int(raw["collection_id"]),
            order=order,
            index=int(raw.get("index", 0)),
            showing_answer=bool(raw.get("showing_answer", False)),
            started_at=str(raw.get("started_at") or ""),
            seed=int(raw.get("seed", 0)),
        )

    async def save(self, redis_kv: RedisKV, ttl: int | None = None) -> None:
        payload = {
            "user_id": self.user_id,
            "collection_id": self.collection_id,
            "order": self.order,
            "index": self.index,
            "showing_answer": self.showing_answer,
            "started_at": self.started_at,
            "seed": self.seed,
        }
        await redis_kv.set_json(self._key(redis_kv, self.user_id), payload, ex=ttl)

    @classmethod
    async def drop(cls, redis_kv: RedisKV, user_id: int) -> None:
        await redis_kv.delete(cls._key(redis_kv, user_id))

    @classmethod
    async def start_new(
        cls,
        redis_kv: RedisKV,
        user_id: int,
        collection_id: int,
        item_ids: List[int],
        ttl: int | None = None,
        avoid_order: List[int] | None = None,
    ) -> "GameSession":
        seed = secrets.randbits(64)
        rng = secrets.SystemRandom()
        order = list(item_ids)

        if len(order) > 1 and avoid_order is not None:
            for _ in range(5):
                rng.shuffle(order)
                if order != avoid_order:
                    break
        else:
            rng.shuffle(order)

        sess = GameSession(
            user_id=user_id,
            collection_id=collection_id,
            order=order,
            index=0,
            showing_answer=False,
            started_at=datetime.utcnow().isoformat(timespec="seconds") + "Z",
            seed=seed,
        )
        await sess.save(redis_kv, ttl=ttl)
        return sess

    def current_item_id(self) -> Optional[int]:
        if self.done:
            return None
        return self.order[self.index]

    def to_progress_str(self) -> str:
        return f"{min(self.index, self.total)}/{self.total}"

    def advance(self) -> None:
        if not self.done:
            self.index += 1
            self.showing_answer = False

class GameData:
    def __init__(self, async_session_maker) -> None:
        self._sm = async_session_maker

    @asynccontextmanager
    async def _session(self):
        async with get_session(self._sm) as session:
            yield session

    async def list_user_collections(self, user_owner_id: int) -> list[Collection]:
        async with self._session() as session:
            res = await session.execute(
                select(Collection).where(Collection.owner_id == user_owner_id).order_by(Collection.created_at)
            )
            return [row[0] for row in res.all()]

    async def get_collection_title_by_id(self, collection_id: int) -> Optional[str]:
        async with self._session() as session:
            res = await session.execute(
                select(Collection.title).where(Collection.id == collection_id)
            )
            row = res.first()
            return None if not row else (row[0] or "Без названия")

    async def get_item_ids(self, collection_id: int) -> List[int]:
        async with self._session() as session:
            res = await session.execute(
                select(CollectionItem.id)
                .where(CollectionItem.collection_id == collection_id)
                .order_by(CollectionItem.position.asc(), CollectionItem.id.asc())
            )
            return [row[0] for row in res.all()]

    async def get_item_qa(self, item_id: int) -> Optional[Tuple[str, str]]:
        async with self._session() as session:
            res = await session.execute(
                select(CollectionItem.question, CollectionItem.answer)
                .where(CollectionItem.id == item_id)
            )
            row = res.first()
            return None if not row else (row[0], row[1])

    async def get_collection_title_by_item(self, item_id: int) -> Optional[str]:
        async with self._session() as session:
            res = await session.execute(
                select(Collection.title)
                .join(CollectionItem, CollectionItem.collection_id == Collection.id)
                .where(CollectionItem.id == item_id)
            )
            row = res.first()
            return None if not row else (row[0] or "Без названия")
