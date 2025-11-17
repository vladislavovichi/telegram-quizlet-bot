from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession


class Repo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session


@asynccontextmanager
async def with_repos(
    async_session_maker,
) -> AsyncIterator[tuple[AsyncSession, "UsersRepo", "CollectionsRepo", "ItemsRepo"]]:  # type: ignore
    from .collections import CollectionsRepo
    from .items import ItemsRepo
    from .users import UsersRepo

    async with async_session_maker() as session:
        users = UsersRepo(session)
        cols = CollectionsRepo(session)
        items = ItemsRepo(session)
        try:
            yield session, users, cols, items
        finally:
            ...
