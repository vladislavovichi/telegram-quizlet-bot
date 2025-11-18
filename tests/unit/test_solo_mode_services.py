
import pytest

from app.models.collection import Collection, CollectionItem
from app.models.solo_mode import SoloSession
from app.models.user import User
from app.services.redis_kv import RedisKV
from app.services.solo_mode import (SoloData, drop_solo_session,
                                    load_solo_session, save_solo_session,
                                    start_new_solo_session)


@pytest.mark.asyncio
async def test_solo_data_collection_and_items(async_session_maker):
    async with async_session_maker() as session:
        u = User(tg_id=900, username="solo-user")
        session.add(u)
        await session.flush()

        col = Collection(owner_id=u.id, title="Коллекция 1")
        session.add(col)
        await session.flush()

        items = [
            CollectionItem(collection_id=col.id, question="Q1", answer="A1", position=1),
            CollectionItem(collection_id=col.id, question="Q2", answer="A2", position=2),
        ]
        session.add_all(items)
        await session.commit()
        item_ids = [it.id for it in items]
        owner_id = u.id
        collection_id = col.id

    sd = SoloData(async_session_maker)

    cols = await sd.list_user_collections(user_owner_id=owner_id)
    assert len(cols) == 1
    assert cols[0].id == collection_id
    assert cols[0].title == "Коллекция 1"

    title = await sd.get_collection_title_by_id(collection_id)
    assert title == "Коллекция 1"

    ids = await sd.get_item_ids(collection_id)
    assert ids == item_ids

    qa = await sd.get_item_qa(item_ids[0])
    assert qa == ("Q1", "A1")

    t2 = await sd.get_collection_title_by_item(item_ids[0])
    assert t2 == "Коллекция 1"

    bulk = await sd.get_items_bulk(item_ids)
    assert set(bulk.keys()) == set(item_ids)
    assert bulk[item_ids[1]] == ("Q2", "A2")


@pytest.mark.asyncio
async def test_solo_session_save_load_drop(redis_kv: RedisKV):
    sess = SoloSession(
        user_id=1,
        collection_id=10,
        order=[1, 2, 3],
        index=1,
        showing_answer=True,
        started_at="2025-01-01T00:00:00Z",
        seed=42,
        stats={"1": "ok"},
        per_item_sec={"1": 3},
        hints={"1": ["h1"]},
        total_sec=3,
        last_ts=123.45,
    )

    await save_solo_session(redis_kv, sess, ttl=30)
    loaded = await load_solo_session(redis_kv, user_id=1)
    assert loaded is not None
    assert loaded.user_id == 1
    assert loaded.collection_id == 10
    assert loaded.order == [1, 2, 3]
    assert loaded.index == 1
    assert loaded.showing_answer is True
    assert loaded.stats == {"1": "ok"}
    assert loaded.per_item_sec == {"1": 3}
    assert loaded.hints == {"1": ["h1"]}
    assert loaded.total_sec == 3

    await drop_solo_session(redis_kv, user_id=1)
    assert await load_solo_session(redis_kv, 1) is None


@pytest.mark.asyncio
async def test_start_new_solo_session_avoids_same_order(redis_kv: RedisKV):
    item_ids = list(range(1, 6))
    avoid_order = item_ids.copy()

    sess = await start_new_solo_session(
        redis_kv,
        user_id=1,
        collection_id=10,
        item_ids=item_ids,
        ttl=30,
        avoid_order=avoid_order,
    )
    assert sess.user_id == 1
    assert sorted(sess.order) == sorted(item_ids)
    if len(item_ids) > 1:
        assert sess.order != avoid_order
