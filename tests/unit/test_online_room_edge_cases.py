from unittest.mock import AsyncMock

import pytest

from app.models.online_room import OnlineRoom, RoomPlayer
from app.services.redis_kv import RedisKV


def _room_with_players():
    room = OnlineRoom(
        room_id="r1",
        owner_id=1,
        collection_id=10,
        seconds_per_question=30,
        points_per_correct=5,
        order=[1, 2, 3],
    )
    room.players = [
        RoomPlayer(user_id=1, username="u1", score=10, total_answer_time=5.0),
        RoomPlayer(user_id=2, username="u2", score=10, total_answer_time=3.0),
        RoomPlayer(user_id=3, username="u3", score=5, total_answer_time=1.0),
    ]
    return room


def test_top_players_sorts_by_score_and_time():
    room = _room_with_players()
    top = room.top_players(limit=3)
    assert [p.user_id for p in top] == [2, 1, 3]


def test_remove_player_cleans_answered_and_last_q_ids():
    room = _room_with_players()
    room.answered_user_ids = [1, 2, 3]
    room.last_q_msg_ids = {"1": 11, "2": 22, "3": 33}
    room.remove_player(2)
    ids = [p.user_id for p in room.players]
    assert ids == [1, 3]
    assert room.answered_user_ids == [1, 3]
    assert room.last_q_msg_ids == {"1": 11, "3": 33}


def test_done_and_current_item_edge_cases():
    room = OnlineRoom(
        room_id="r2",
        owner_id=1,
        collection_id=10,
        seconds_per_question=30,
        points_per_correct=5,
        order=[1, 2],
        index=2,
    )
    assert room.done is True
    assert room.current_item_id() is None
    room.index = 1
    assert room.done is False
    assert room.current_item_id() == 2


@pytest.mark.asyncio
async def test_generate_room_id_falls_back_to_time(monkeypatch):
    client = AsyncMock()
    kv = RedisKV(client=client, prefix="room", ttl_seconds=10)

    async_mock = AsyncMock(return_value={"exists": True})
    monkeypatch.setattr(RedisKV, "get_json", async_mock, raising=False)

    def fake_randbelow(n):
        return 1

    monkeypatch.setattr("app.models.online_room.secrets.randbelow", fake_randbelow)
    monkeypatch.setattr("app.models.online_room.time.time", lambda: 1234567.0)

    code = await OnlineRoom._generate_room_id(kv)
    assert code == f"{int(1234567) % 1_000_000:06d}"
    assert async_mock.await_count == 20
