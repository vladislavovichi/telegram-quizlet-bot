from __future__ import annotations
from typing import Optional
from sqlalchemy import select, delete
from app.models.collection import Collection
from .base import Repo


class CollectionsRepo(Repo):
    async def list_by_user(self, user_id: int) -> list[Collection]:
        return (
            (
                await self.session.execute(
                    select(Collection)
                    .where(Collection.owner_id == user_id)
                    .order_by(Collection.created_at)
                )
            )
            .scalars()
            .all()
        )

    async def get_owned(self, collection_id: int, user_id: int) -> Optional[Collection]:
        return (
            await self.session.execute(
                select(Collection).where(
                    Collection.id == collection_id, Collection.owner_id == user_id
                )
            )
        ).scalar_one_or_none()

    async def create(self, user_id: int, title: str) -> Collection:
        c = Collection(owner_id=user_id, title=title or "Без названия")
        self.session.add(c)
        await self.session.commit()
        await self.session.refresh(c)
        return c

    async def rename(self, collection_id: int, user_id: int, new_title: str) -> bool:
        col = await self.get_owned(collection_id, user_id)
        if not col:
            return False
        col.title = new_title or "Без названия"
        await self.session.commit()
        return True

    async def delete_owned(self, collection_id: int, user_id: int) -> None:
        await self.session.execute(
            delete(Collection).where(
                Collection.id == collection_id, Collection.owner_id == user_id
            )
        )
        await self.session.commit()

    async def get_by_id(self, collection_id: int) -> Optional[Collection]:
        return (
            (
                await self.session.execute(
                    select(Collection).where(Collection.id == collection_id)
                )
            )
            .scalars()
            .first()
        )
