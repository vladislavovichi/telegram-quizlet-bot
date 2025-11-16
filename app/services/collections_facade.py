from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from app.models.user import User
from app.models.collection import Collection
from app.repos.base import with_repos


@dataclass
class UserCollections:
    user: User
    collections: List[Collection]


async def get_user_and_collections(
    async_session_maker,
    tg_user_id: int,
    tg_username: Optional[str],
) -> UserCollections:
    async with with_repos(async_session_maker) as (_, users, cols, _items):
        user = await users.get_or_create(tg_user_id, tg_username)
        collections = await cols.list_by_user(user.id)

    return UserCollections(user=user, collections=collections)
