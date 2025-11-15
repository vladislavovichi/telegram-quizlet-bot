from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional
import random
import secrets
import time

from app.services.redis_kv import RedisKV

MAX_PLAYERS_PER_ROOM = 30


@dataclass(slots=True)
class RoomPlayer:
    user_id: int
    username: str | None = None
    score: int = 0
    total_answer_time: float = 0.0


@dataclass(slots=True)
class OnlineRoom:
    room_id: str
    owner_id: int
    collection_id: int
    seconds_per_question: int
    points_per_correct: int
    order: List[int]

    index: int = 0
    state: str = "waiting"  # waiting | running | finished | canceled

    created_at: str = ""
    started_at: str | None = None
    finished_at: str | None = None

    players: List[RoomPlayer] = field(default_factory=list)
    answered_user_ids: List[int] = field(default_factory=list)

    question_deadline_ts: float | None = None
    last_q_msg_ids: Dict[str, int] = field(default_factory=dict)

    owner_wait_chat_id: int | None = None
    owner_wait_message_id: int | None = None
    owner_score_message_id: int | None = None

    @property
    def total_questions(self) -> int:
        return len(self.order)

    @property
    def done(self) -> bool:
        return self.index >= self.total_questions

    def has_player(self, user_id: int) -> bool:
        return any(p.user_id == user_id for p in self.players)

    def add_player(self, user_id: int, username: str | None = None) -> bool:
        if self.has_player(user_id):
            return True
        if len(self.players) >= MAX_PLAYERS_PER_ROOM:
            return False
        self.players.append(
            RoomPlayer(user_id=user_id, username=username or None, score=0)
        )
        return True

    def remove_player(self, user_id: int) -> None:
        self.players = [p for p in self.players if p.user_id != user_id]
        self.answered_user_ids = [
            uid for uid in self.answered_user_ids if uid != user_id
        ]
        self.last_q_msg_ids.pop(str(user_id), None)

    def current_item_id(self) -> Optional[int]:
        if self.done:
            return None
        return self.order[self.index]

    def sorted_players(self) -> List[RoomPlayer]:
        return sorted(
            self.players,
            key=lambda p: (-p.score, p.total_answer_time),
        )

    def top_players(self, limit: int = 3) -> List[RoomPlayer]:
        return self.sorted_players()[:limit]

    def to_dict(self) -> dict:
        return {
            "room_id": self.room_id,
            "owner_id": self.owner_id,
            "collection_id": self.collection_id,
            "seconds_per_question": self.seconds_per_question,
            "points_per_correct": self.points_per_correct,
            "order": self.order,
            "index": self.index,
            "state": self.state,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "players": [
                {
                    "user_id": p.user_id,
                    "username": p.username,
                    "score": p.score,
                    "total_answer_time": p.total_answer_time,
                }
                for p in self.players
            ],
            "answered_user_ids": self.answered_user_ids,
            "question_deadline_ts": self.question_deadline_ts,
            "last_q_msg_ids": self.last_q_msg_ids,
            "owner_wait_chat_id": self.owner_wait_chat_id,
            "owner_wait_message_id": self.owner_wait_message_id,
            "owner_score_message_id": self.owner_score_message_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "OnlineRoom":
        players = [
            RoomPlayer(
                user_id=int(p.get("user_id")),
                username=p.get("username"),
                score=int(p.get("score") or 0),
                total_answer_time=float(p.get("total_answer_time") or 0.0),
            )
            for p in data.get("players", [])
        ]
        return cls(
            room_id=str(data["room_id"]),
            owner_id=int(data["owner_id"]),
            collection_id=int(data["collection_id"]),
            seconds_per_question=int(data["seconds_per_question"]),
            points_per_correct=int(data["points_per_correct"]),
            order=[int(x) for x in data.get("order", [])],
            index=int(data.get("index", 0)),
            state=str(data.get("state", "waiting")),
            created_at=str(data.get("created_at") or ""),
            started_at=data.get("started_at"),
            finished_at=data.get("finished_at"),
            players=players,
            answered_user_ids=[int(x) for x in data.get("answered_user_ids", [])],
            question_deadline_ts=(float(data.get("question_deadline_ts") or 0) or None),
            last_q_msg_ids={
                str(k): int(v) for k, v in (data.get("last_q_msg_ids") or {}).items()
            },
            owner_wait_chat_id=(
                int(data["owner_wait_chat_id"])
                if data.get("owner_wait_chat_id") is not None
                else None
            ),
            owner_wait_message_id=(
                int(data["owner_wait_message_id"])
                if data.get("owner_wait_message_id") is not None
                else None
            ),
            owner_score_message_id=(
                int(data["owner_score_message_id"])
                if data.get("owner_score_message_id") is not None
                else None
            ),
        )

    @staticmethod
    def _room_key(redis_kv: RedisKV, room_id: str) -> str:
        return redis_kv._key("online", "room", room_id)

    @staticmethod
    def _user_room_key(redis_kv: RedisKV, user_id: int) -> str:
        return redis_kv._key("online", "user_room", user_id)

    @classmethod
    async def load_by_room_id(
        cls, redis_kv: RedisKV, room_id: str
    ) -> Optional["OnlineRoom"]:
        raw = await redis_kv.get_json(cls._room_key(redis_kv, room_id))
        if not raw:
            return None
        return cls.from_dict(raw)

    @classmethod
    async def load_by_user(
        cls, redis_kv: RedisKV, user_id: int
    ) -> Optional["OnlineRoom"]:
        mapping = await redis_kv.get_json(cls._user_room_key(redis_kv, user_id))
        if not mapping:
            return None
        room_id = str(mapping.get("room_id") or "")
        if not room_id:
            return None
        return await cls.load_by_room_id(redis_kv, room_id)

    async def save(self, redis_kv: RedisKV, ttl: int | None = None) -> None:
        await redis_kv.set_json(
            self._room_key(redis_kv, self.room_id),
            self.to_dict(),
            ex=ttl,
        )

    @classmethod
    async def set_user_room(
        cls, redis_kv: RedisKV, user_id: int, room_id: str, ttl: int | None = None
    ) -> None:
        await redis_kv.set_json(
            cls._user_room_key(redis_kv, user_id),
            {"room_id": room_id},
            ex=ttl,
        )

    @classmethod
    async def clear_user_room(cls, redis_kv: RedisKV, user_id: int) -> None:
        await redis_kv.delete(cls._user_room_key(redis_kv, user_id))

    @classmethod
    async def create(
        cls,
        redis_kv: RedisKV,
        owner_id: int,
        collection_id: int,
        item_ids: List[int],
        seconds_per_question: int,
        points_per_correct: int,
        ttl: int | None = None,
    ) -> "OnlineRoom":
        order = list(item_ids)
        rnd = random.Random()
        rnd.shuffle(order)

        room_id = await cls._generate_room_id(redis_kv)
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")

        room = cls(
            room_id=room_id,
            owner_id=owner_id,
            collection_id=collection_id,
            seconds_per_question=seconds_per_question,
            points_per_correct=points_per_correct,
            order=order,
            index=0,
            state="waiting",
            created_at=now,
            players=[],
        )

        await room.save(redis_kv, ttl=ttl)
        await cls.set_user_room(redis_kv, owner_id, room_id, ttl=ttl)
        return room

    @classmethod
    async def _generate_room_id(cls, redis_kv: RedisKV) -> str:
        for _ in range(20):
            code = f"{secrets.randbelow(1_000_000):06d}"
            exists = await redis_kv.get_json(cls._room_key(redis_kv, code))
            if not exists:
                return code
        return f"{int(time.time()) % 1_000_000:06d}"
