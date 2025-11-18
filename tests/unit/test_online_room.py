
import pytest

from app.models.online_room import MAX_PLAYERS_PER_ROOM, OnlineRoom, RoomPlayer
from app.services.redis_kv import RedisKV


def _make_room() -> OnlineRoom:
    return OnlineRoom(
        room_id="123456",
        owner_id=1,
        collection_id=10,
        seconds_per_question=30,
        points_per_correct=5,
        order=[101, 102, 103],
        index=0,
        state="waiting",
        created_at="2025-01-01T00:00:00Z",
        started_at=None,
        finished_at=None,
        deep_link=None,
        players=[],
        answered_user_ids=[],
        question_deadline_ts=None,
        last_q_msg_ids={},
        owner_wait_chat_id=None,
        owner_wait_message_id=None,
        owner_score_message_id=None,
    )


def test_total_questions_and_done():
    room = _make_room()
    assert room.total_questions == 3
    assert room.done is False
    room.index = 3
    assert room.done is True


def test_has_add_remove_player():
    room = _make_room()
    assert not room.has_player(10)

    assert room.add_player(10, username="u10") is True
    assert room.has_player(10)

    # no duplicates
    assert room.add_player(10, username="u10") is True
    assert len(room.players) == 1

    # limit
    room.players = [RoomPlayer(user_id=i) for i in range(MAX_PLAYERS_PER_ROOM)]
    assert room.add_player(999) is False

    # remove
    room.players = [RoomPlayer(user_id=1), RoomPlayer(user_id=2)]
    room.remove_player(1)
    assert [p.user_id for p in room.players] == [2]


def test_current_item_id_bounds():
    room = _make_room()
    room.index = 0
    assert room.current_item_id() == 101
    room.index = 2
    assert room.current_item_id() == 103
    room.index = 3
    assert room.current_item_id() is None


def test_sorted_and_top_players():
    room = _make_room()
    room.players = [
        RoomPlayer(user_id=1, score=10, total_answer_time=5.0),
        RoomPlayer(user_id=2, score=10, total_answer_time=3.0),
        RoomPlayer(user_id=3, score=5, total_answer_time=1.0),
    ]
    sorted_players = room.sorted_players()
    assert [p.user_id for p in sorted_players] == [2, 1, 3]
    assert [p.user_id for p in room.top_players(limit=2)] == [2, 1]


@pytest.mark.asyncio
async def test_room_to_from_dict_roundtrip(redis_kv: RedisKV):
    room = _make_room()
    room.players = [
        RoomPlayer(user_id=1, username="u1", score=3, total_answer_time=1.5)
    ]
    room.answered_user_ids = [1]
    room.question_deadline_ts = 123.45
    room.last_q_msg_ids = {1: 10}
    room.owner_wait_chat_id = 100
    room.owner_wait_message_id = 200
    room.owner_score_message_id = 300

    data = room.to_dict()
    restored = OnlineRoom.from_dict(data)
    assert restored.room_id == room.room_id
    assert restored.collection_id == room.collection_id
    assert len(restored.players) == 1
    assert restored.players[0].user_id == 1
    assert restored.owner_score_message_id == 300


@pytest.mark.asyncio
async def test_room_save_and_load(redis_kv: RedisKV):
    room = _make_room()
    await room.save(redis_kv, ttl=10)

    loaded = await OnlineRoom.load_by_room_id(redis_kv, room.room_id)
    assert loaded is not None
    assert loaded.room_id == room.room_id


@pytest.mark.asyncio
async def test_user_room_mapping(redis_kv: RedisKV):
    room = _make_room()
    await room.save(redis_kv, ttl=10)

    await OnlineRoom.set_user_room(redis_kv, user_id=42, room_id=room.room_id, ttl=10)
    loaded = await OnlineRoom.load_by_user(redis_kv, user_id=42)
    assert loaded is not None
    assert loaded.room_id == room.room_id

    await OnlineRoom.clear_user_room(redis_kv, user_id=42)
    assert await OnlineRoom.load_by_user(redis_kv, 42) is None


@pytest.mark.asyncio
async def test_generate_room_id_avoids_collision(redis_kv: RedisKV, monkeypatch):
    room = _make_room()
    room.room_id = "000001"
    await room.save(redis_kv, ttl=10)

    seq = [1, 1, 2]

    def fake_randbelow(n: int) -> int:
        return seq.pop(0)

    import secrets as _secrets

    monkeypatch.setattr(_secrets, "randbelow", fake_randbelow)

    new_id = await OnlineRoom._generate_room_id(redis_kv)
    assert new_id == "000002"


@pytest.mark.asyncio
async def test_set_room_deep_link(redis_kv: RedisKV):
    room = _make_room()
    await room.save(redis_kv, ttl=10)

    updated = await OnlineRoom.set_room_deep_link(
        redis_kv, room_id=room.room_id, deep_link="link"
    )
    assert updated is not None
    assert updated.deep_link == "link"
