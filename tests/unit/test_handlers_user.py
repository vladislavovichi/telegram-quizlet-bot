import pytest

from app.handlers.user import get_user_router


class DummyUser:
    def __init__(self, user_id: int, username: str | None = None):
        self.id = user_id
        self.username = username


class DummyMessage:
    def __init__(self, text: str, user_id: int = 1, username: str | None = None):
        self.text = text
        self.from_user = DummyUser(user_id, username or f"user{user_id}")
        self.answers: list[dict] = []

    async def answer(self, text: str, reply_markup=None):
        self.answers.append({"text": text, "reply_markup": reply_markup})


class DummyCallbackQuery:
    def __init__(self, data: str, user_id: int = 1, username: str | None = None):
        self.data = data
        self.from_user = DummyUser(user_id, username or f"user{user_id}")
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
async def test_cmd_start_creates_user_and_sends_greeting(
    async_session_maker, redis_kv, monkeypatch
):
    from app.handlers import user as user_module

    router = get_user_router(async_session_maker, redis_kv)
    handler = _get_message_handler(router, "cmd_start")

    called = {}

    async def fake_ensure(async_maker, tg_id, username):
        called["args"] = (tg_id, username)

    monkeypatch.setattr(user_module, "ensure_user_exists", fake_ensure)

    msg = DummyMessage(text="/start", user_id=123, username="alice")
    await handler(msg)

    assert called["args"] == (123, "alice")
    assert msg.answers, "cmd_start must send a greeting"
    assert "привет" in msg.answers[0]["text"].lower()


@pytest.mark.asyncio
async def test_cmd_profile_loads_profile_and_sends_text(
    async_session_maker, redis_kv, monkeypatch
):
    from app.handlers import user as user_module

    router = get_user_router(async_session_maker, redis_kv)
    handler = _get_message_handler(router, "cmd_profile")

    class DummyProfile:
        def __init__(self, user_id: int):
            self.user = DummyUser(user_id, "bob")

    async def fake_load_profile(async_maker, tg_id, username):
        return DummyProfile(tg_id)

    def fake_make_profile_text(tg, profile):
        return f"PROFILE for {profile.user.username}"

    monkeypatch.setattr(user_module, "load_profile", fake_load_profile)
    monkeypatch.setattr(user_module, "make_profile_text", fake_make_profile_text)

    msg = DummyMessage(text="/profile", user_id=5, username="bob")
    await handler(msg)

    assert msg.answers
    assert "PROFILE for bob" in msg.answers[0]["text"]


@pytest.mark.asyncio
async def test_cb_profile_change_name_sets_pending(redis_kv, async_session_maker):
    router = get_user_router(async_session_maker, redis_kv)
    handler = _get_callback_handler(router, "cb_profile_change_name")

    cb = DummyCallbackQuery(data="profile:change_name", user_id=7, username="alice")
    await handler(cb)

    key = redis_kv.pending_key(7)
    stored = await redis_kv.get_json(key)
    assert stored == {"type": "profile:change_name"}
    assert cb.message.answers, "user should be prompted to enter new name"


@pytest.mark.asyncio
async def test_cb_profile_cancel_change_name_clears_pending(
    redis_kv, async_session_maker
):
    router = get_user_router(async_session_maker, redis_kv)
    handler = _get_callback_handler(router, "cb_profile_cancel_change_name")

    key = redis_kv.pending_key(9)
    await redis_kv.set_json(
        key, {"type": "profile:change_name"}, ex=redis_kv.ttl_seconds
    )

    cb = DummyCallbackQuery(data="profile:cancel_change_name", user_id=9, username="u9")
    await handler(cb)

    assert await redis_kv.get_json(key) is None


@pytest.mark.asyncio
async def test_handle_profile_pending_updates_name_and_clears_state(
    async_session_maker, redis_kv, monkeypatch
):
    from app.handlers import user as user_module

    router = get_user_router(async_session_maker, redis_kv)
    handler = _get_message_handler(router, "handle_profile_pending")

    key = redis_kv.pending_key(11)
    await redis_kv.set_json(
        key, {"type": "profile:change_name"}, ex=redis_kv.ttl_seconds
    )

    class DummyProfile:
        def __init__(self, username: str):
            self.user = DummyUser(11, username)

    async def fake_update(async_maker, tg_id, username, new_name):
        assert tg_id == 11
        assert username == "old"
        assert new_name == "New Name"
        return DummyProfile(new_name)

    def fake_make_profile_text(tg, profile, name_override=None):
        return f"PROFILE {profile.user.username}"

    monkeypatch.setattr(user_module, "update_name_and_get_profile", fake_update)
    monkeypatch.setattr(user_module, "make_profile_text", fake_make_profile_text)

    msg = DummyMessage(text="New Name", user_id=11, username="old")
    await handler(msg, pending={"type": "profile:change_name"})

    assert msg.answers
    assert "PROFILE New Name" in msg.answers[0]["text"]
    assert await redis_kv.get_json(key) is None


@pytest.mark.asyncio
async def test_cmd_cancel_clears_pending(async_session_maker, redis_kv):
    router = get_user_router(async_session_maker, redis_kv)
    handler = _get_message_handler(router, "cmd_cancel")

    key = redis_kv.pending_key(20)
    await redis_kv.set_json(key, {"type": "something"}, ex=redis_kv.ttl_seconds)

    msg = DummyMessage(text="/cancel", user_id=20, username="u20")
    await handler(msg)

    assert await redis_kv.get_json(key) is None
    assert msg.answers
