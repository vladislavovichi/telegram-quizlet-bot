from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Iterable
from datetime import datetime
from contextlib import asynccontextmanager
import secrets
import time

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

    stats: Dict[str, str] = field(default_factory=dict)
    per_item_sec: Dict[str, int] = field(default_factory=dict)
    total_sec: int = 0
    last_ts: float = 0.0

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
        stats = {str(k): str(v) for k, v in (raw.get("stats") or {}).items()}
        per_item_sec = {
            str(k): int(v) for k, v in (raw.get("per_item_sec") or {}).items()
        }
        return GameSession(
            user_id=int(raw.get("user_id", user_id)),
            collection_id=int(raw["collection_id"]),
            order=order,
            index=int(raw.get("index", 0)),
            showing_answer=bool(raw.get("showing_answer", False)),
            started_at=str(raw.get("started_at") or ""),
            seed=int(raw.get("seed", 0)),
            stats=stats,
            per_item_sec=per_item_sec,
            total_sec=int(raw.get("total_sec", 0)),
            last_ts=float(raw.get("last_ts", 0.0)),
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
            "stats": self.stats,
            "per_item_sec": self.per_item_sec,
            "total_sec": self.total_sec,
            "last_ts": self.last_ts,
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

        now = time.time()

        sess = GameSession(
            user_id=user_id,
            collection_id=collection_id,
            order=order,
            index=0,
            showing_answer=False,
            started_at=datetime.utcnow().isoformat(timespec="seconds") + "Z",
            seed=seed,
            stats={},
            per_item_sec={},
            total_sec=0,
            last_ts=now,
        )
        await sess.save(redis_kv, ttl=ttl)
        return sess

    def current_item_id(self) -> Optional[int]:
        if self.done:
            return None
        return self.order[self.index]

    def to_progress_str(self) -> str:
        return f"{min(self.index, self.total)}/{self.total}"

    def _commit_time_for_current(self) -> None:
        if self.done:
            return
        now = time.time()
        delta = max(0, int(now - (self.last_ts or now)))
        item_id = self.order[self.index]
        key = str(item_id)
        self.per_item_sec[key] = int(self.per_item_sec.get(key, 0)) + delta
        self.total_sec += delta
        self.last_ts = now

    def mark_and_next(self, mark: Optional[str]) -> None:
        """
        mark in: 'known' | 'unknown' | 'skipped' | None  (None -> 'neutral')
        """
        if self.done:
            return
        self._commit_time_for_current()
        if mark is None:
            mark = "neutral"
        self.stats[str(self.order[self.index])] = mark
        # move forward
        self.index += 1
        self.showing_answer = False
        self.last_ts = time.time()

    def counts(self) -> Dict[str, int]:
        counts = {"known": 0, "unknown": 0, "skipped": 0, "neutral": 0}
        for v in self.stats.values():
            if v in counts:
                counts[v] += 1
        return counts

    def wrong_ids(self) -> List[int]:
        return [int(k) for k, v in self.stats.items() if v == "unknown"]


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
                select(Collection)
                .where(Collection.owner_id == user_owner_id)
                .order_by(Collection.created_at)
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
                select(CollectionItem.question, CollectionItem.answer).where(
                    CollectionItem.id == item_id
                )
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

    async def get_items_bulk(
        self, item_ids: Iterable[int]
    ) -> Dict[int, Tuple[str, str]]:
        ids = list(set(map(int, item_ids)))
        if not ids:
            return {}
        async with self._session() as session:
            res = await session.execute(
                select(
                    CollectionItem.id, CollectionItem.question, CollectionItem.answer
                ).where(CollectionItem.id.in_(ids))
            )
            out: Dict[int, Tuple[str, str]] = {}
            for row in res.all():
                out[int(row[0])] = (row[1], row[2])
            return out
