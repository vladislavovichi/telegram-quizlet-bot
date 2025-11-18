import pytest

from app.repos.collections import CollectionsRepo
from app.repos.items import ItemsRepo
from app.repos.users import UsersRepo


@pytest.mark.asyncio
async def test_users_repo_get_or_create(db_session):
    repo = UsersRepo(db_session)

    u1 = await repo.get_or_create(tg_id=100, username="alpha")
    assert u1.id is not None

    u2 = await repo.get_or_create(tg_id=100, username="beta")
    assert u2.id == u1.id
    # username should not be overwritten
    assert u2.username == "alpha"


@pytest.mark.asyncio
async def test_collections_repo_crud(db_session):
    users = UsersRepo(db_session)
    cols = CollectionsRepo(db_session)

    u = await users.get_or_create(1, "user1")

    created = await cols.create(user_id=u.id, title="My collection")
    assert created.owner_id == u.id

    lst = await cols.list_by_user(u.id)
    assert [c.id for c in lst] == [created.id]

    owned = await cols.get_owned(created.id, u.id)
    assert owned is not None

    any_col = await cols.get_by_id(created.id)
    assert any_col is not None

    ok = await cols.rename(created.id, u.id, "New title")
    assert ok
    renamed = await cols.get_by_id(created.id)
    assert renamed.title == "New title"

    await cols.delete_owned(created.id, u.id)
    assert await cols.get_by_id(created.id) is None


@pytest.mark.asyncio
async def test_items_repo_crud_and_counts(db_session):
    users = UsersRepo(db_session)
    cols = CollectionsRepo(db_session)
    items = ItemsRepo(db_session)

    u = await users.get_or_create(1, "user1")
    col = await cols.create(u.id, "C1")

    it1 = await items.add(col.id, "Q1", "A1")
    it2 = await items.add(col.id, "Q2", "A2")
    assert it1.id != it2.id

    pairs_ids = await items.list_pairs(col.id)
    assert pairs_ids == [(it1.id, "Q1"), (it2.id, "Q2")]

    qa_pairs = await items.list_question_answer_pairs(col.id)
    assert qa_pairs == [("Q1", "A1"), ("Q2", "A2")]

    cnt = await items.count_in_collection(col.id)
    assert cnt == 2

    item, col2 = await items.get_item_owned(it1.id, u.id)
    assert item.id == it1.id
    assert col2.id == col.id

    await items.update_question(it1.id, "Q1*")
    await items.update_answer(it1.id, "A1*")
    await items.update_both(it2.id, "Q2*", "A2*")

    item, _ = await items.get_item_owned(it1.id, u.id)
    assert item.question == "Q1*"
    assert item.answer == "A1*"

    item2, _ = await items.get_item_owned(it2.id, u.id)
    assert item2.question == "Q2*"
    assert item2.answer == "A2*"

    await items.delete(it1.id)
    assert await items.count_in_collection(col.id) == 1

    deleted_count = await items.delete_all_in_collection(col.id)
    assert isinstance(deleted_count, int)
    assert deleted_count >= 1
    assert await items.count_in_collection(col.id) == 0
