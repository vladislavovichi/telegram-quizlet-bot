import pytest

from app.handlers.collections import get_collections_router


class DummyUser:
    def __init__(self, user_id: int, username: str | None = None):
        self.id = user_id
        self.username = username or f"user{user_id}"


class DummyMessage:
    def __init__(self, text: str, user_id: int = 1, username: str | None = None):
        self.text = text
        self.from_user = DummyUser(user_id, username)
        self.answers: list[dict] = []

    async def answer(self, text: str, reply_markup=None):
        self.answers.append({"text": text, "reply_markup": reply_markup})


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
async def test_show_collections_sends_keyboard(async_session_maker, redis_kv):
    router = get_collections_router(async_session_maker, redis_kv)
    handler = _get_message_handler(router, "show_collections")

    msg = DummyMessage(text="👀 Мои коллекции", user_id=1, username="u1")
    await handler(msg)

    assert msg.answers
    first = msg.answers[0]
    assert "коллекц" in first["text"].lower()
    assert first["reply_markup"] is not None


@pytest.mark.asyncio
async def test_start_new_sets_pending_and_prompts(redis_kv, async_session_maker):
    router = get_collections_router(async_session_maker, redis_kv)
    handler = _get_callback_handler(router, "start_new")

    cb = DummyCallbackQuery(data="col:new", user_id=5, username="u5")
    await handler(cb)

    key = redis_kv.pending_key(5)
    stored = await redis_kv.get_json(key)
    assert stored == {"type": "col:new"}
    assert cb.message.answers
    assert "название новой коллекции" in cb.message.answers[0]["text"].lower()


@pytest.mark.asyncio
async def test_open_col_not_found_alerts_user(async_session_maker, redis_kv):
    router = get_collections_router(async_session_maker, redis_kv)
    handler = _get_callback_handler(router, "open_col")

    cb = DummyCallbackQuery(data="col:open:9999", user_id=1, username="u1")
    await handler(cb)

    assert cb.answers
    assert cb.answers[0]["show_alert"] is True
