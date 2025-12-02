import json
from unittest.mock import AsyncMock

import pytest

from app.services.redis_kv import RedisKV


@pytest.mark.asyncio
async def test_redis_kv_with_asyncmock_roundtrip():
    client = AsyncMock()
    kv = RedisKV(client=client, prefix="test", ttl_seconds=10)

    key = kv._key("obj", 1)
    payload = {"a": 1, "b": "x"}

    client.get.return_value = None
    await kv.set_json(key, payload, ex=5)
    client.set.assert_awaited_once()
    args, kwargs = client.set.call_args
    assert args[0] == key
    assert kwargs["ex"] == 5

    client.get.return_value = json.dumps(payload).encode("utf-8")
    loaded = await kv.get_json(key)
    assert loaded == payload

    await kv.delete(key)
    client.delete.assert_awaited_once_with(key)


@pytest.mark.asyncio
async def test_redis_kv_pending_key_with_async_client():
    client = AsyncMock()
    kv = RedisKV(client=client, prefix="edge", ttl_seconds=1)
    key = kv.pending_key(42)
    assert key.endswith("pending:42")
