from __future__ import annotations

from dataclasses import dataclass

from app.models.user import User
from app.repos.base import with_repos


@dataclass
class UserProfileData:
    user: User
    collections_count: int
    total_cards: int


async def ensure_user_exists(
    async_session_maker, tg_id: int, username: str | None
) -> User:
    async with with_repos(async_session_maker) as (_, users, _, _):
        return await users.get_or_create(tg_id, username)


async def load_profile(
    async_session_maker,
    tg_id: int,
    username: str | None,
) -> UserProfileData:
    async with with_repos(async_session_maker) as (_, users, cols, items):
        u = await users.get_or_create(tg_id, username)

        all_cols = await cols.list_by_user(u.id)
        collections_count = len(all_cols)

        total_cards = 0
        for col in all_cols:
            total_cards += await items.count_in_collection(col.id)

    return UserProfileData(
        user=u,
        collections_count=collections_count,
        total_cards=total_cards,
    )


async def update_name_and_get_profile(
    async_session_maker,
    tg_id: int,
    username: str | None,
    new_name: str,
) -> UserProfileData:
    async with with_repos(async_session_maker) as (_, users, cols, items):
        u = await users.get_or_create(tg_id, username)
        u.username = new_name
        await users.session.commit()

        all_cols = await cols.list_by_user(u.id)
        collections_count = len(all_cols)

        total_cards = 0
        for col in all_cols:
            total_cards += await items.count_in_collection(col.id)

    return UserProfileData(
        user=u,
        collections_count=collections_count,
        total_cards=total_cards,
    )
