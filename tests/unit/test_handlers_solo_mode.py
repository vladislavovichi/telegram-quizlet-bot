
import pytest

from app.handlers.solo_mode import get_solo_mode_router
from app.services.redis_kv import RedisKV
from app.services.solo_mode import load_solo_session


class DummyUser:
    def __init__(self, user_id: int, username: str | None = None):
        self.id = user_id
        self.username = username or f"user{user_id}"


class DummyMessage:
    def __init__(self, text: str, user_id: int = 1, username: str | None = None):
        self.text = text
        self.from_user = DummyUser(user_id, username)
        self.answers: list[dict] = []
        self.edits: list[dict] = []

    async def answer(self, text: str, reply_markup=None):
        self.answers.append({"text": text, "reply_markup": reply_markup})

    async def edit_text(self, text: str, reply_markup=None):
        self.edits.append({"text": text, "reply_markup": reply_markup})


class DummyCallbackQuery:
    def __init__(self, data: str, user_id: int = 1, username: str | None = None):
        self.data = data
        self.from_user = DummyUser(user_id, username)
        self.message = DummyMessage(text="", user_id=user_id, username=username)
        self.answers: list[dict] = []

    async def answer(self, text: str | None = None, show_alert: bool = False):
        self.answers.append({"text": text, "show_alert": show_alert})


def _get_message_handler(router, name: str):
    for h in router.message.handlers:
        if h.callback.__name__ == name:
            return h.callback
    raise AssertionError(f"Handler {name} not found")


def _get_callback_handler(router, name: str):
    for h in router.callback_query.handlers:
        if h.callback.__name__ == name:
            return h.callback
    raise AssertionError(f"Callback handler {name} not found")


@pytest.mark.asyncio
async def test_cmd_solo_start_shows_collection_list(async_session_maker, redis_kv: RedisKV):
    router = get_solo_mode_router(async_session_maker, redis_kv)
    handler = _get_message_handler(router, "cmd_solo_start")

    msg = DummyMessage(text="/solo", user_id=1, username="u1")
    await handler(msg)

    assert msg.answers, "User should see collection choice screen"
    assert "коллекц" in msg.answers[0]["text"].lower()


@pytest.mark.asyncio
async def test_cb_solo_begin_invalid_collection_id_shows_alert(async_session_maker, redis_kv: RedisKV):
    router = get_solo_mode_router(async_session_maker, redis_kv)
    handler = _get_callback_handler(router, "cb_solo_begin")

    cb = DummyCallbackQuery(data="solo:begin:xxx", user_id=1)
    await handler(cb)

    assert cb.answers
    assert cb.answers[0]["show_alert"] is True


@pytest.mark.asyncio
async def test_cb_solo_begin_empty_collection_shows_no_cards(async_session_maker, redis_kv: RedisKV):
    router = get_solo_mode_router(async_session_maker, redis_kv)
    handler = _get_callback_handler(router, "cb_solo_begin")

    cb = DummyCallbackQuery(data="solo:begin:9999", user_id=1)
    await handler(cb)

    assert cb.answers
    assert "нет карточек" in (cb.answers[0]["text"] or "").lower()


@pytest.mark.asyncio
async def test_cb_solo_begin_success_creates_session_and_renders_question(async_session_maker, redis_kv: RedisKV):
    from app.models.collection import Collection, CollectionItem

    async with async_session_maker() as session:
        col = Collection(owner_id=1, title="SoloCol")
        session.add(col)
        await session.flush()

        item = CollectionItem(collection_id=col.id, question="Q1", answer="A1", position=1)
        session.add(item)
        await session.commit()

        collection_id = col.id

    router = get_solo_mode_router(async_session_maker, redis_kv)
    handler = _get_callback_handler(router, "cb_solo_begin")

    cb = DummyCallbackQuery(data=f"solo:begin:{collection_id}", user_id=1)
    await handler(cb)

    assert cb.message.edits

    sess = await load_solo_session(redis_kv, user_id=1)
    assert sess is not None
    assert sess.collection_id == collection_id
