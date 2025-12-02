from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services import hints as hints_module
from app.services.hints import generate_hint_async


@pytest.mark.asyncio
async def test_generate_hint_success(monkeypatch):
    client = MagicMock()
    response = MagicMock()
    response.json.return_value = {"hint": "  test hint "}
    response.raise_for_status.return_value = None
    client.post = AsyncMock(return_value=response)

    class DummyClientContext:
        async def __aenter__(self):
            return client

        async def __aexit__(self, exc_type, exc, tb):
            return False

    httpx_mock = MagicMock()
    httpx_mock.AsyncClient.side_effect = lambda timeout=5.0: DummyClientContext()
    monkeypatch.setattr(hints_module, "httpx", httpx_mock)

    hint = await generate_hint_async("question", "answer", ["prev"])
    assert hint == "test hint"
    client.post.assert_awaited_once()


@pytest.mark.asyncio
async def test_generate_hint_error_returns_empty(monkeypatch):
    client = MagicMock()
    client.post = AsyncMock(side_effect=RuntimeError("boom"))

    class DummyClientContext:
        async def __aenter__(self):
            return client

        async def __aexit__(self, exc_type, exc, tb):
            return False

    httpx_mock = MagicMock()
    httpx_mock.AsyncClient.side_effect = lambda timeout=5.0: DummyClientContext()
    monkeypatch.setattr(hints_module, "httpx", httpx_mock)

    hint = await generate_hint_async("q", "a")
    assert hint == ""
    client.post.assert_awaited_once()
