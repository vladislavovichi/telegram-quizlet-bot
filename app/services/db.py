from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from contextlib import asynccontextmanager


def make_engine_and_session(dsn: str):
    engine = create_async_engine(
        dsn,
        future=True,
        echo=False,
        pool_size=10,
        max_overflow=20,
        pool_timeout=30,
        pool_pre_ping=True,
    )

    async_session = async_sessionmaker(engine, expire_on_commit=False)
    return engine, async_session


@asynccontextmanager
async def get_session(session_maker):
    async with session_maker() as session:
        try:
            yield session
        finally:
            await session.close()