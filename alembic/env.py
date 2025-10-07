# alembic/env.py
import os
import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy import engine_from_config  # нужен для offline mode only
from sqlalchemy import text
from sqlalchemy.engine import Connection

from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context
from app.models.base import Base

config = context.config
fileConfig(config.config_file_name)

# Прочитать DSN из окружения (если задан)
db_url = os.getenv("DB_DSN")
if db_url:
    config.set_main_option("sqlalchemy.url", db_url)

target_metadata = Base.metadata

def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

def do_run_migrations(connection: Connection):
    """
    Функция будет выполнена синхронно в рамках асинхронного подключения
    через connection.run_sync(...)
    """
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()

async def run_migrations_online():
    """
    Создаём асинхронный движок и используем connection.run_sync(do_run_migrations)
    чтобы выполнить синхронные Alembic операции в безопасном context-е.
    """
    connectable = create_async_engine(
        config.get_main_option("sqlalchemy.url"),
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as async_connection:
        # run_sync выполнит do_run_migrations в синхронном режиме с "raw" Connection
        await async_connection.run_sync(do_run_migrations)

    await connectable.dispose()

if context.is_offline_mode():
    run_migrations_offline()
else:
    # запускаем асинхронный поток
    asyncio.run(run_migrations_online())
