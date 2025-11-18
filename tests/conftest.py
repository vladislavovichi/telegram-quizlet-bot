
import asyncio
from dataclasses import dataclass
from typing import Any, AsyncGenerator, Dict

import pytest
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.sqlite import JSON as SQLiteJSON
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker as _async_sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine

from app.models import Base
from app.services.redis_kv import RedisKV

# ---------- event loop (pytest-asyncio >= 0.21) ----------

@pytest.fixture(scope="session")
def event_loop() -> asyncio.AbstractEventLoop:
    """
    Own event loop for the whole test session.
    """
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ---------- FakeRedis used both in unit tests and when patching create_app() ----------

@dataclass
class FakeRedis:
    data: Dict[str, bytes]

    def __init__(self) -> None:
        self.data = {}

    async def set(self, key: str, value: bytes, ex: int | None = None) -> None:
        self.data[key] = value

    async def get(self, key: str) -> bytes | None:
        return self.data.get(key)

    async def delete(self, key: str) -> None:
        self.data.pop(key, None)

    async def aclose(self) -> None:
        # match interface of redis.asyncio.Redis
        self.data.clear()


@pytest.fixture
def fake_redis() -> FakeRedis:
    """
    Isolated in-memory Redis-like storage for unit tests.
    """
    return FakeRedis()


@pytest.fixture
def redis_kv(fake_redis: FakeRedis) -> RedisKV:
    """
    RedisKV wrapper bound to FakeRedis. Prefix is kept short and explicit so
    tests can assert on key shapes if needed.
    """
    return RedisKV(client=fake_redis, prefix="test", ttl_seconds=60)


# ---------- database fixtures (SQLite in-memory, JSONB patched to JSON) ----------

@pytest.fixture(scope="session")
async def _engine():
    """
    Single in-memory SQLite engine for the whole test run.
    We patch JSONB columns in metadata to SQLite JSON so that
    Base.metadata.create_all() works under SQLite.
    """
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        future=True,
        echo=False,
    )

    async with engine.begin() as conn:

        def _sync_create_all(sync_conn):
            # Patch JSONB -> SQLiteJSON on metadata before creating tables.
            for table in Base.metadata.tables.values():
                for col in table.c:
                    if isinstance(col.type, JSONB):
                        col.type = SQLiteJSON()
            Base.metadata.create_all(sync_conn)

        await conn.run_sync(_sync_create_all)

    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture(scope="session")
async def async_session_maker(_engine) -> _async_sessionmaker[AsyncSession]:
    """
    Factory for AsyncSession bound to the shared engine.
    Returned object is an actual SQLAlchemy async_sessionmaker, not a fixture.
    """
    return _async_sessionmaker(_engine, expire_on_commit=False)


@pytest.fixture
async def db_session(async_session_maker: _async_sessionmaker[AsyncSession]) -> AsyncGenerator[AsyncSession, None]:
    """
    Function-scoped session. We don't open nested transactions here to keep
    things simple; tests are free to commit/rollback as they like.
    """
    async with async_session_maker() as session:
        yield session


# ---------- infra patching for create_app() / main() ----------

@pytest.fixture
def patch_app_infra(monkeypatch, _engine, async_session_maker, fake_redis: FakeRedis):
    """
    Patches app.services.db.make_engine_and_session and
    app.services.redis_client.create_redis so that create_app() uses:

    - the same in-memory SQLite engine / session maker as other tests
    - FakeRedis instead of a real Redis server
    """
    from app.services import db as db_module  # type: ignore
    from app.services import redis_client as redis_module  # type: ignore

    def fake_make_engine_and_session(dsn: str):
        # Ignore DSN and reuse already prepared engine + session maker
        return _engine, async_session_maker

    async def fake_create_redis(dsn: str):
        # Ignore DSN and reuse a single FakeRedis instance
        return fake_redis

    monkeypatch.setattr(db_module, "make_engine_and_session", fake_make_engine_and_session)
    monkeypatch.setattr(redis_module, "create_redis", fake_create_redis)


# ---------- aiogram network patching (no real Telegram calls) ----------

@pytest.fixture
def patch_aiogram_network(monkeypatch):
    """
    Patch network-facing methods of aiogram objects so tests never hit Telegram.
    """
    try:
        from aiogram import Bot, Dispatcher  # type: ignore
    except Exception:
        # If aiogram is not installed – let ImportError surface in tests which
        # actually import it. This fixture stays a no-op then.
        return

    async def no_op_delete_webhook(self, *args, **kwargs):
        return None

    async def no_op_start_polling(self, *args, **kwargs):
        return None

    monkeypatch.setattr(Bot, "delete_webhook", no_op_delete_webhook, raising=False)
    monkeypatch.setattr(Dispatcher, "start_polling", no_op_start_polling, raising=False)
