import pytest

from app.repos.base import with_repos
from app.services.solo_mode import SoloData


@pytest.mark.asyncio
async def test_with_repos_and_solo_data(async_session_maker):
    async with with_repos(async_session_maker) as (session, users, cols, items):
        u = await users.get_or_create(tg_id=10, username="user10")
        col = await cols.create(user_id=u.id, title="Коллекция X")
        await items.add(col.id, "Q1", "A1")
        await items.add(col.id, "Q2", "A2")
        assert await items.count_in_collection(col.id) == 2

    sd = SoloData(async_session_maker)
    user_cols = await sd.list_user_collections(user_owner_id=u.id)
    assert len(user_cols) == 1
    assert user_cols[0].title == "Коллекция X"

    ids = await sd.get_item_ids(user_cols[0].id)
    assert len(ids) == 2

    qa = await sd.get_items_bulk(ids)
    assert len(qa) == 2
