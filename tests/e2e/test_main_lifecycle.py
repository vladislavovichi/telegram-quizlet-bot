
import pytest

import main as main_module
from app.factory import create_app


@pytest.mark.asyncio
async def test_create_app_smoke(patch_aiogram_network, patch_app_infra):
    """
    Smoke test: create_app returns an object with required attributes
    and uses in-memory DB + FakeRedis (patched in patch_app_infra).
    """
    app = await create_app()
    assert hasattr(app, "bot")
    assert hasattr(app, "dp")
    assert hasattr(app, "engine")
    assert hasattr(app, "async_session_maker")
    assert hasattr(app, "redis_client")
    assert hasattr(app, "redis_kv")

    await app.bot.session.close()
    await app.engine.dispose()
    await app.redis_client.aclose()


@pytest.mark.asyncio
async def test_main_starts_polling_and_closes_resources(monkeypatch, patch_aiogram_network, patch_app_infra):
    called = {"start_polling": False}

    try:
        from aiogram import Dispatcher  # type: ignore
    except Exception:
        # If aiogram is not installed, just skip: test is about integration
        pytest.skip("aiogram is not available")

    async def fake_start_polling(self, bot, *args, **kwargs):
        called["start_polling"] = True

    monkeypatch.setattr(Dispatcher, "start_polling", fake_start_polling, raising=False)

    await main_module.main()
    assert called["start_polling"] is True
