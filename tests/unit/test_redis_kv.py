
import pytest

from app.services.redis_kv import RedisKV


@pytest.mark.asyncio
async def test_key_building_and_pending(redis_kv: RedisKV):
    k = redis_kv._key("foo", 1, "bar")
    assert k.startswith("test:")
    assert k.endswith("foo:1:bar")
    assert redis_kv.pending_key(42) == "test:pending:42"


@pytest.mark.asyncio
async def test_set_get_delete_json(redis_kv: RedisKV):
    key = redis_kv._key("obj", "1")
    payload = {"a": 1, "b": "test"}

    await redis_kv.set_json(key, payload, ex=10)
    loaded = await redis_kv.get_json(key)
    assert loaded == payload

    await redis_kv.delete(key)
    assert await redis_kv.get_json(key) is None
