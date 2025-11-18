from __future__ import annotations

import secrets
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional, Tuple

from sqlalchemy import select

from app.models.collection import Collection, CollectionItem
from app.models.solo_mode import SoloSession
from app.services.db import get_session
from app.services.redis_kv import RedisKV


class SoloData:
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


def _session_key(redis_kv: RedisKV, user_id: int) -> str:
    try:
        return redis_kv._key("solo", user_id)
    except AttributeError:
        return f"solo:{user_id}"


async def load_solo_session(
    redis_kv: RedisKV,
    user_id: int,
) -> Optional[SoloSession]:
    raw = await redis_kv.get_json(_session_key(redis_kv, user_id))
    if not raw:
        return None

    order = list(map(int, raw.get("order", [])))
    stats = {str(k): str(v) for k, v in (raw.get("stats") or {}).items()}
    per_item_sec = {str(k): int(v) for k, v in (raw.get("per_item_sec") or {}).items()}

    return SoloSession(
        user_id=int(raw.get("user_id", user_id)),
        collection_id=int(raw["collection_id"]),
        order=order,
        index=int(raw.get("index", 0)),
        showing_answer=bool(raw.get("showing_answer", False)),
        started_at=str(raw.get("started_at") or ""),
        seed=int(raw.get("seed", 0)),
        stats=stats,
        per_item_sec=per_item_sec,
        hints={str(k): list(v) for k, v in (raw.get("hints") or {}).items()},
        total_sec=int(raw.get("total_sec", 0)),
        last_ts=float(raw.get("last_ts", 0.0)),
    )


async def save_solo_session(
    redis_kv: RedisKV,
    sess: SoloSession,
    ttl: int | None = None,
) -> None:
    payload = {
        "user_id": sess.user_id,
        "collection_id": sess.collection_id,
        "order": list(sess.order),
        "index": sess.index,
        "showing_answer": sess.showing_answer,
        "started_at": sess.started_at,
        "seed": sess.seed,
        "stats": dict(sess.stats),
        "per_item_sec": dict(sess.per_item_sec),
        "hints": {k: list(v) for k, v in sess.hints.items()},
        "total_sec": sess.total_sec,
        "last_ts": sess.last_ts,
    }
    await redis_kv.set_json(_session_key(redis_kv, sess.user_id), payload, ex=ttl)


async def drop_solo_session(redis_kv: RedisKV, user_id: int) -> None:
    await redis_kv.delete(_session_key(redis_kv, user_id))


async def start_new_solo_session(
    redis_kv: RedisKV,
    user_id: int,
    collection_id: int,
    item_ids: List[int],
    ttl: int | None = None,
    avoid_order: List[int] | None = None,
) -> SoloSession:
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

    sess = SoloSession(
        user_id=user_id,
        collection_id=collection_id,
        order=order,
        index=0,
        showing_answer=False,
        started_at=datetime.now(timezone.utc).isoformat(timespec="seconds")
        + "Z",
        seed=seed,
        stats={},
        per_item_sec={},
        hints={},
        total_sec=0,
        last_ts=now,
    )
    await save_solo_session(redis_kv, sess, ttl=ttl)
    return sess
