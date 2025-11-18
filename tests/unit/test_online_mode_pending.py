import pytest

from app.services.online_mode import (
    clear_online_settings_pending,
    get_online_settings_pending,
    online_join_pending_key,
    online_settings_pending_key,
    set_online_join_pending,
    set_online_settings_pending,
)


@pytest.mark.asyncio
async def test_online_join_pending(redis_kv):
    key = online_join_pending_key(redis_kv, user_id=1)
    assert key.endswith("online:join_pending:1")

    await set_online_join_pending(redis_kv, user_id=1)
    data = await redis_kv.get_json(key)
    assert data is not None
    assert data["kind"] == "online_join"
    assert "created_at" in data


@pytest.mark.asyncio
async def test_online_settings_pending(redis_kv):
    key = online_settings_pending_key(redis_kv, user_id=2)
    assert key.endswith("online:settings_pending:2")

    await set_online_settings_pending(
        redis_kv, user_id=2, room_id="123456", field="points"
    )
    data = await get_online_settings_pending(redis_kv, user_id=2)
    assert data is not None
    assert data["room_id"] == "123456"
    assert data["field"] == "points"

    await redis_kv.set_json(
        key,
        {"kind": "wrong", "version": 999},
        ex=redis_kv.ttl_seconds,
    )
    bad = await get_online_settings_pending(redis_kv, user_id=2)
    assert bad is None
    assert await redis_kv.get_json(key) is None

    await set_online_settings_pending(redis_kv, user_id=2, room_id="1", field="points")
    await clear_online_settings_pending(redis_kv, user_id=2)
    assert await redis_kv.get_json(key) is None
