from __future__ import annotations
from typing import Optional
from sqlalchemy import select, func, update, delete
from app.models.collection import Collection, CollectionItem
from .base import Repo


class ItemsRepo(Repo):
    async def list_pairs(self, collection_id: int) -> list[tuple[int, str]]:
        rows = (
            await self.session.execute(
                select(CollectionItem.id, CollectionItem.question)
                .where(CollectionItem.collection_id == collection_id)
                .order_by(CollectionItem.created_at)
            )
        ).all()
        return [(row.id, row.question) for row in rows]  # type: ignore

    async def count_in_collection(self, collection_id: int) -> int:
        return (
            await self.session.execute(
                select(func.count())
                .select_from(CollectionItem)
                .where(CollectionItem.collection_id == collection_id)
            )
        ).scalar_one()

    async def get(self, item_id: int) -> Optional[CollectionItem]:
        return (
            await self.session.execute(
                select(CollectionItem).where(CollectionItem.id == item_id)
            )
        ).scalar_one_or_none()

    async def get_collection_owned(
        self, collection_id: int, user_id: int
    ) -> Optional[Collection]:
        return (
            await self.session.execute(
                select(Collection).where(
                    Collection.id == collection_id, Collection.user_id == user_id
                )
            )
        ).scalar_one_or_none()

    async def get_item_owned(
        self, item_id: int, user_id: int
    ) -> tuple[Optional[CollectionItem], Optional[Collection]]:
        item = await self.get(item_id)
        if not item:
            return None, None
        col = (
            await self.session.execute(
                select(Collection).where(
                    Collection.id == item.collection_id, Collection.user_id == user_id
                )
            )
        ).scalar_one_or_none()
        return item if col else None, col

    async def add(
        self, collection_id: int, question: str, answer: str
    ) -> CollectionItem:
        it = CollectionItem(
            collection_id=collection_id, question=question, answer=answer
        )
        self.session.add(it)
        await self.session.commit()
        await self.session.refresh(it)
        return it

    async def update_question(self, item_id: int, q: str) -> None:
        await self.session.execute(
            update(CollectionItem)
            .where(CollectionItem.id == item_id)
            .values(question=q)
        )
        await self.session.commit()

    async def update_answer(self, item_id: int, a: str) -> None:
        await self.session.execute(
            update(CollectionItem).where(CollectionItem.id == item_id).values(answer=a)
        )
        await self.session.commit()

    async def update_both(self, item_id: int, q: str, a: str) -> None:
        await self.session.execute(
            update(CollectionItem)
            .where(CollectionItem.id == item_id)
            .values(question=q, answer=a)
        )
        await self.session.commit()

    async def delete(self, item_id: int) -> None:
        await self.session.execute(
            delete(CollectionItem).where(CollectionItem.id == item_id)
        )
        await self.session.commit()
