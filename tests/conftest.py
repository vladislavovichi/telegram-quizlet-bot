import asyncio
from dataclasses import dataclass
from typing import AsyncGenerator, Dict, Generator

import pytest
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.sqlite import JSON as SQLiteJSON
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker as _async_sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine

from app.models import Base
from app.services.redis_kv import RedisKV


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

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
        self.data.clear()


@pytest.fixture
def fake_redis() -> FakeRedis:
    return FakeRedis()


@pytest.fixture
def redis_kv(fake_redis: FakeRedis) -> RedisKV:
    return RedisKV(client=fake_redis, prefix="test", ttl_seconds=60)


@pytest.fixture(scope="session")
async def _engine():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        future=True,
        echo=False,
    )

    async with engine.begin() as conn:

        def _sync_create_all(sync_conn):
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
    return _async_sessionmaker(_engine, expire_on_commit=False)


@pytest.fixture
async def db_session(
    async_session_maker: _async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session

@pytest.fixture
def patch_app_infra(monkeypatch, _engine, async_session_maker, fake_redis: FakeRedis):
    from app.services import db as db_module  # type: ignore
    from app.services import redis_client as redis_module  # type: ignore

    def fake_make_engine_and_session(dsn: str):
        return _engine, async_session_maker

    async def fake_create_redis(dsn: str):
        return fake_redis

    monkeypatch.setattr(
        db_module, "make_engine_and_session", fake_make_engine_and_session
    )
    monkeypatch.setattr(redis_module, "create_redis", fake_create_redis)

@pytest.fixture
def patch_aiogram_network(monkeypatch):
    try:
        from aiogram import Bot, Dispatcher  # type: ignore
    except Exception:
        return

    async def no_op_delete_webhook(self, *args, **kwargs):
        return None

    async def no_op_start_polling(self, *args, **kwargs):
        return None

    monkeypatch.setattr(Bot, "delete_webhook", no_op_delete_webhook, raising=False)
    monkeypatch.setattr(Dispatcher, "start_polling", no_op_start_polling, raising=False)
