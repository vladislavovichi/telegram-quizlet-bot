from __future__ import annotations

from aiogram import types

from app.services.user_profile import UserProfileData


def make_profile_text(
    tg: types.User,
    profile: UserProfileData,
    name_override: str | None = None,
) -> str:
    u = profile.user

    if name_override:
        name = name_override
    else:
        name = u.username or (tg.first_name or "") or (tg.username or "")
        if tg.last_name:
            if tg.first_name:
                name = f"{tg.first_name} {tg.last_name}"
            elif not name:
                name = tg.last_name

        if not name:
            name = f"id{tg.id}"

    return (
        "👤 <b>Мой профиль</b>\n\n"
        f"Имя: <b>{name}</b>\n"
        f"ID: <code>{tg.id}</code>\n\n"
        f"Коллекций: <b>{profile.collections_count}</b>\n"
        f"Карточек всего: <b>{profile.total_cards}</b>"
    )
