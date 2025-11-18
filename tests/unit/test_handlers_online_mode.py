
import pytest

from app.handlers.online_mode import get_online_mode_router


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
async def test_cmd_online_start_clears_pending_and_shows_root(async_session_maker, redis_kv):
    router = get_online_mode_router(async_session_maker, redis_kv)
    handler = _get_message_handler(router, "cmd_online_start")

    key = redis_kv.pending_key(1)
    await redis_kv.set_json(key, {"type": "something"}, ex=redis_kv.ttl_seconds)

    msg = DummyMessage(text="/online", user_id=1, username="u1")
    await handler(msg)

    assert await redis_kv.get_json(key) is None
    assert msg.answers
    assert "онлайн" in msg.answers[0]["text"].lower()


@pytest.mark.asyncio
async def test_cb_create_without_collections_alerts(async_session_maker, redis_kv):
    router = get_online_mode_router(async_session_maker, redis_kv)
    handler = _get_callback_handler(router, "cb_create")

    cb = DummyCallbackQuery(data="online:create", user_id=1, username="u1")
    await handler(cb)

    assert cb.answers
    assert cb.answers[0]["show_alert"] is True
    assert "нет коллекций" in (cb.answers[0]["text"] or "").lower()


@pytest.mark.asyncio
async def test_cb_online_choose_cancel_edits_or_answers(async_session_maker, redis_kv):
    router = get_online_mode_router(async_session_maker, redis_kv)
    handler = _get_callback_handler(router, "cb_online_choose_cancel")

    cb = DummyCallbackQuery(data="online:choose_cancel", user_id=1, username="u1")
    await handler(cb)

    assert cb.answers or cb.message.edits
