import pytest

from app.models.solo_mode import SoloSession
from app.services.solo_mode import load_solo_session


def test_solo_session_counts_and_wrong_ids():
    sess = SoloSession(user_id=1, collection_id=1, order=[1, 2, 3])
    sess.stats = {"1": "known", "2": "unknown", "3": "skipped"}
    counts = sess.counts()
    assert counts["known"] == 1
    assert counts["unknown"] == 1
    assert counts["skipped"] == 1
    assert counts["neutral"] == 0
    wrong = sess.wrong_ids()
    assert wrong == [2]


def test_solo_session_mark_and_next_when_done_does_not_move():
    sess = SoloSession(user_id=1, collection_id=1, order=[1])
    sess.index = 1
    sess.mark_and_next("known")
    assert sess.index == 1
    assert sess.stats == {}


@pytest.mark.asyncio
async def test_load_solo_session_missing_raw_returns_none(monkeypatch):
    class DummyKV:
        async def get_json(self, key):
            return None

    sess = await load_solo_session(DummyKV(), user_id=1)
    assert sess is None


@pytest.mark.asyncio
async def test_load_solo_session_restores_basic_fields(monkeypatch):
    class DummyKV:
        def __init__(self):
            self.payload = {
                "user_id": 2,
                "collection_id": 10,
                "order": ["1", "2"],
                "index": 1,
                "showing_answer": True,
                "started_at": "2024-01-01T00:00:00Z",
                "seed": 123,
                "stats": {"1": "known"},
                "per_item_sec": {"1": 5},
                "hints": {"1": ["h1"]},
                "total_sec": 5,
                "last_ts": 10.0,
            }

        async def get_json(self, key):
            return self.payload

    sess = await load_solo_session(DummyKV(), user_id=1)
    assert sess is not None
    assert sess.user_id == 2
    assert sess.collection_id == 10
    assert sess.order == [1, 2]
    assert sess.index == 1
    assert sess.showing_answer is True
    assert sess.stats == {"1": "known"}
    assert sess.per_item_sec == {"1": 5}
    assert sess.hints == {"1": ["h1"]}
