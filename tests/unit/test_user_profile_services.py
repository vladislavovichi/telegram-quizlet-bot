
import pytest

from app.models.collection import Collection, CollectionItem
from app.models.user import User
from app.services.user_profile import (
    UserProfileData,
    ensure_user_exists,
    load_profile,
    update_name_and_get_profile,
)


@pytest.mark.asyncio
async def test_ensure_user_exists(async_session_maker):
    u = await ensure_user_exists(async_session_maker, tg_id=1000, username="name")
    assert isinstance(u, User)
    assert u.tg_id == 1000
    assert u.username == "name"

    u2 = await ensure_user_exists(async_session_maker, tg_id=1000, username="other")
    assert u2.id == u.id
    assert u2.username == "name"


@pytest.mark.asyncio
async def test_load_profile_counts(async_session_maker):
    async with async_session_maker() as session:
        u = User(tg_id=200, username="u200")
        session.add(u)
        await session.flush()

        col1 = Collection(owner_id=u.id, title="C1")
        col2 = Collection(owner_id=u.id, title="C2")
        session.add_all([col1, col2])
        await session.flush()

        items = [
            CollectionItem(collection_id=col1.id, question="Q1", answer="A1", position=1),
            CollectionItem(collection_id=col2.id, question="Q2", answer="A2", position=1),
            CollectionItem(collection_id=col2.id, question="Q3", answer="A3", position=2),
        ]
        session.add_all(items)
        await session.commit()

    prof = await load_profile(async_session_maker, tg_id=200, username="u200")
    assert isinstance(prof, UserProfileData)
    assert prof.user.tg_id == 200
    assert prof.collections_count == 2
    assert prof.total_cards == 3


@pytest.mark.asyncio
async def test_update_name_and_get_profile(async_session_maker):
    u = await ensure_user_exists(async_session_maker, tg_id=300, username="old")
    assert u.username == "old"

    prof = await update_name_and_get_profile(
        async_session_maker,
        tg_id=300,
        username="old",
        new_name="new-name",
    )
    assert prof.user.username == "new-name"
