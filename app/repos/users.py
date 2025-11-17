from __future__ import annotations

from typing import Optional

from sqlalchemy import select

from app.models.user import User

from .base import Repo


class UsersRepo(Repo):
    async def get_by_tg_id(self, tg_id: int) -> Optional[User]:
        return (
            await self.session.execute(select(User).where(User.tg_id == tg_id))
        ).scalar_one_or_none()

    async def get_or_create(self, tg_id: int, username: str | None) -> User:
        u = await self.get_by_tg_id(tg_id)
        if u:
            return u
        u = User(tg_id=tg_id, username=username)
        self.session.add(u)
        await self.session.commit()
        return u
