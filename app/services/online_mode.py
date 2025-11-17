from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional

from app.models.online_room import OnlineRoom
from app.repos.base import with_repos
from app.services.solo_mode import SoloData
from app.services.redis_kv import RedisKV
from app.texts.online_mode import (
    fmt_online_answer,
    fmt_online_question,
    fmt_owner_scoreboard,
    fmt_player_scoreboard,
    fmt_room_waiting,
    format_top_lines,
)
from app.keyboards.online_mode import online_room_owner_kb

log = logging.getLogger(__name__)

ONLINE_JOIN_PENDING_VERSION = 1
ONLINE_SETTINGS_PENDING_VERSION = 1


def online_join_pending_key(redis_kv: RedisKV, user_id: int) -> str:
    return redis_kv._key("online", "join_pending", user_id)


async def set_online_join_pending(redis_kv: RedisKV, user_id: int) -> None:
    key = online_join_pending_key(redis_kv, user_id)
    payload = {
        "version": ONLINE_JOIN_PENDING_VERSION,
        "kind": "online_join",
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    await redis_kv.set_json(key, payload, ex=redis_kv.ttl_seconds)


async def get_online_join_pending(redis_kv: RedisKV, user_id: int) -> Optional[dict]:
    key = online_join_pending_key(redis_kv, user_id)
    data = await redis_kv.get_json(key)
    if not data:
        return None
    if (
        data.get("kind") != "online_join"
        or data.get("version") != ONLINE_JOIN_PENDING_VERSION
    ):
        await redis_kv.delete(key)
        return None
    return data


async def clear_online_join_pending(redis_kv: RedisKV, user_id: int) -> None:
    await redis_kv.delete(online_join_pending_key(redis_kv, user_id))


def online_settings_pending_key(redis_kv: RedisKV, user_id: int) -> str:
    return redis_kv._key("online", "settings_pending", user_id)


async def set_online_settings_pending(
    redis_kv: RedisKV,
    user_id: int,
    room_id: str,
    field: str,  # "points" | "seconds"
) -> None:
    key = online_settings_pending_key(redis_kv, user_id)
    payload = {
        "version": ONLINE_SETTINGS_PENDING_VERSION,
        "kind": "online_settings",
        "room_id": room_id,
        "field": field,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    await redis_kv.set_json(key, payload, ex=redis_kv.ttl_seconds)


async def get_online_settings_pending(
    redis_kv: RedisKV, user_id: int
) -> Optional[dict]:
    key = online_settings_pending_key(redis_kv, user_id)
    data = await redis_kv.get_json(key)
    if not data:
        return None
    if (
        data.get("kind") != "online_settings"
        or data.get("version") != ONLINE_SETTINGS_PENDING_VERSION
    ):
        await redis_kv.delete(key)
        return None
    return data


async def clear_online_settings_pending(redis_kv: RedisKV, user_id: int) -> None:
    await redis_kv.delete(online_settings_pending_key(redis_kv, user_id))


async def update_owner_room_message(
    async_session_maker,
    redis_kv: RedisKV,
    bot,
    room_id: str,
) -> None:
    room = await OnlineRoom.load_by_room_id(redis_kv, room_id)
    if not room:
        return

    if room.owner_wait_chat_id is None or room.owner_wait_message_id is None:
        return

    gd = SoloData(async_session_maker)
    title = await gd.get_collection_title_by_id(room.collection_id) or "Коллекция"

    deep_link = room.deep_link

    try:
        await bot.edit_message_text(
            fmt_room_waiting(
                title=title,
                room_id=room.room_id,
                seconds_per_question=room.seconds_per_question,
                points_per_correct=room.points_per_correct,
                players_count=len(room.players),
                deep_link=deep_link,
            ),
            chat_id=room.owner_wait_chat_id,
            message_id=room.owner_wait_message_id,
            reply_markup=online_room_owner_kb(room.room_id),
        )
    except Exception as e:  # pragma: no cover
        log.debug("failed to update owner room message: %s", e)


async def run_room_loop(
    room_id: str,
    async_session_maker,
    redis_kv: RedisKV,
    bot,
) -> None:
    gd = SoloData(async_session_maker)
    ttl = redis_kv.ttl_seconds

    while True:
        room = await OnlineRoom.load_by_room_id(redis_kv, room_id)
        if not room or room.state != "running":
            return

        players = [p for p in room.players if p.user_id != room.owner_id]

        item_id = room.current_item_id()
        if item_id is None or not players:
            await _finish_room(async_session_maker, gd, redis_kv, bot, room)
            return

        qa = await gd.get_item_qa(item_id)
        if not qa:
            room.index += 1
            room.question_deadline_ts = None
            room.answered_user_ids = []
            await room.save(redis_kv, ttl=ttl)
            continue

        question, answer = qa
        title = await gd.get_collection_title_by_item(item_id) or "Коллекция"

        q_index = room.index + 1
        total = room.total_questions

        last_ids: Dict[str, int] = {}
        now = time.time()
        room.question_deadline_ts = now + room.seconds_per_question
        room.answered_user_ids = []
        await room.save(redis_kv, ttl=ttl)

        for p in players:
            try:
                msg = await bot.send_message(
                    p.user_id,
                    fmt_online_question(
                        title=title,
                        q=question,
                        idx=q_index,
                        total=total,
                        seconds_per_question=room.seconds_per_question,
                    ),
                )
                last_ids[str(p.user_id)] = msg.message_id
            except Exception:
                continue

        room.last_q_msg_ids = last_ids
        await room.save(redis_kv, ttl=ttl)

        await asyncio.sleep(room.seconds_per_question)

        room = await OnlineRoom.load_by_room_id(redis_kv, room_id)
        if not room or room.state != "running":
            return

        players = [p for p in room.players if p.user_id != room.owner_id]

        for p in players:
            mid = room.last_q_msg_ids.get(str(p.user_id))
            if not mid:
                continue
            try:
                await bot.edit_message_text(
                    fmt_online_answer(
                        title=title,
                        q=question,
                        a=answer,
                        idx=q_index,
                        total=total,
                    ),
                    chat_id=p.user_id,
                    message_id=mid,
                )
            except Exception:
                continue

        room.index += 1
        room.question_deadline_ts = None
        room.answered_user_ids = []
        await room.save(redis_kv, ttl=ttl)

        await _send_live_scoreboard_to_owner(async_session_maker, redis_kv, bot, room)

        await asyncio.sleep(1)


async def _send_live_scoreboard_to_owner(
    async_session_maker,
    redis_kv: RedisKV,
    bot,
    room: OnlineRoom,
) -> None:
    players = [p for p in room.players if p.user_id != room.owner_id]
    if not players:
        return

    async with with_repos(async_session_maker) as (_, users, _, _):
        name_map: dict[int, str] = {}
        for p in players:
            u = await users.get_or_create(p.user_id, p.username)
            name_map[p.user_id] = u.username or p.username or f"id{p.user_id}"

    players_sorted = sorted(
        players,
        key=lambda p: (-p.score, p.total_answer_time),
    )

    lines: List[str] = []
    for i, p in enumerate(players_sorted, start=1):
        name = name_map.get(p.user_id, p.username or f"id{p.user_id}")
        lines.append(f"{i}. {name} — {p.score} очков")

    text = "📊 Текущий рейтинг игроков:\n\n" + "\n".join(lines)

    try:
        if room.owner_score_message_id:
            try:
                await bot.edit_message_text(
                    text,
                    chat_id=room.owner_id,
                    message_id=room.owner_score_message_id,
                )
            except Exception:
                msg = await bot.send_message(room.owner_id, text)
                room.owner_score_message_id = msg.message_id
                await room.save(redis_kv, ttl=redis_kv.ttl_seconds)
        else:
            msg = await bot.send_message(room.owner_id, text)
            room.owner_score_message_id = msg.message_id
            await room.save(redis_kv, ttl=redis_kv.ttl_seconds)
    except Exception as e:  # pragma: no cover
        log.debug("failed to send/update live scoreboard: %s", e)


async def _finish_room(
    async_session_maker,
    gd: SoloData,
    redis_kv: RedisKV,
    bot,
    room: OnlineRoom,
) -> None:
    room.state = "finished"
    room.finished_at = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    await room.save(redis_kv, ttl=redis_kv.ttl_seconds)

    title = await gd.get_collection_title_by_id(room.collection_id) or "Коллекция"

    players = [p for p in room.players if p.user_id != room.owner_id]
    sorted_players = sorted(
        players,
        key=lambda p: (-p.score, p.total_answer_time),
    )
    top3 = sorted_players[:3]

    async with with_repos(async_session_maker) as (_, users, _, _):
        name_map: dict[int, str] = {}
        for p in players:
            u = await users.get_or_create(p.user_id, p.username)
            name_map[p.user_id] = u.username or p.username or f"id{p.user_id}"

    top_lines_data: List[tuple[str, int, float]] = []
    for p in top3:
        name = name_map.get(p.user_id, p.username or f"id{p.user_id}")
        top_lines_data.append((name, p.score, p.total_answer_time))
    top_lines = format_top_lines(top_lines_data)

    owner_lines: List[str] = []
    for i, p in enumerate(sorted_players, start=1):
        name = name_map.get(p.user_id, p.username or f"id{p.user_id}")
        owner_lines.append(f"{i}. {name} — {p.score} очков")

    owner_text = fmt_owner_scoreboard(title, owner_lines)
    try:
        await bot.send_message(room.owner_id, owner_text)
    except Exception:
        pass

    for p in sorted_players:
        place = next(
            (i + 1 for i, sp in enumerate(sorted_players) if sp.user_id == p.user_id),
            None,
        )
        text = fmt_player_scoreboard(
            title=title,
            place=place,
            score=p.score,
            total_answer_time=p.total_answer_time,
            top_lines=top_lines,
        )
        try:
            await bot.send_message(p.user_id, text)
        except Exception:
            continue
        await OnlineRoom.clear_user_room(redis_kv, p.user_id)

    await redis_kv.delete(OnlineRoom._room_key(redis_kv, room.room_id))
    