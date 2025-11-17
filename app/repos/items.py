from __future__ import annotations

from typing import List, Optional, Tuple

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.collection import Collection, CollectionItem


class ItemsRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _next_position(self, collection_id: int) -> int:
        res = await self.session.execute(
            select(func.max(CollectionItem.position)).where(
                CollectionItem.collection_id == collection_id
            )
        )
        max_pos: Optional[int] = res.scalar()
        return (max_pos or 0) + 1

    async def list_pairs(self, collection_id: int) -> List[Tuple[int, str]]:
        res = await self.session.execute(
            select(CollectionItem.id, CollectionItem.question)
            .where(CollectionItem.collection_id == collection_id)
            .order_by(CollectionItem.position.asc(), CollectionItem.id.asc())
        )
        return [(row[0], row[1]) for row in res.all()]

    async def list_question_answer_pairs(
        self, collection_id: int
    ) -> List[Tuple[str, str]]:
        res = await self.session.execute(
            select(CollectionItem.question, CollectionItem.answer)
            .where(CollectionItem.collection_id == collection_id)
            .order_by(CollectionItem.position.asc(), CollectionItem.id.asc())
        )
        return [(row[0], row[1]) for row in res.all()]

    async def count_in_collection(self, collection_id: int) -> int:
        res = await self.session.execute(
            select(func.count(CollectionItem.id)).where(
                CollectionItem.collection_id == collection_id
            )
        )
        return int(res.scalar() or 0)

    async def get_item_owned(
        self, item_id: int, user_id: int
    ) -> Tuple[Optional[CollectionItem], Optional[Collection]]:
        res = await self.session.execute(
            select(CollectionItem, Collection)
            .join(Collection, Collection.id == CollectionItem.collection_id)
            .where(CollectionItem.id == item_id, Collection.owner_id == user_id)
        )
        row = res.first()
        if not row:
            return None, None
        item: CollectionItem = row[0]
        col: Collection = row[1]
        return item, col

    async def add(
        self, collection_id: int, question: str, answer: str
    ) -> CollectionItem:
        pos = await self._next_position(collection_id)
        item = CollectionItem(
            collection_id=collection_id,
            question=question,
            answer=answer,
            position=pos,
        )
        self.session.add(item)

        await self.session.flush()
        await self.session.commit()
        return item

    async def update_question(self, item_id: int, new_q: str) -> None:
        await self.session.execute(
            update(CollectionItem)
            .where(CollectionItem.id == item_id)
            .values(question=new_q)
        )
        await self.session.commit()

    async def update_answer(self, item_id: int, new_a: str) -> None:
        await self.session.execute(
            update(CollectionItem)
            .where(CollectionItem.id == item_id)
            .values(answer=new_a)
        )
        await self.session.commit()

    async def update_both(self, item_id: int, new_q: str, new_a: str) -> None:
        await self.session.execute(
            update(CollectionItem)
            .where(CollectionItem.id == item_id)
            .values(question=new_q, answer=new_a)
        )
        await self.session.commit()

    async def delete(self, item_id: int) -> None:
        await self.session.execute(
            delete(CollectionItem).where(CollectionItem.id == item_id)
        )
        await self.session.commit()

    async def delete_all_in_collection(self, collection_id: int) -> int:
        res = await self.session.execute(
            delete(CollectionItem).where(CollectionItem.collection_id == collection_id)
        )
        await self.session.commit()

        try:
            return int(res.rowcount or 0)
        except Exception:
            return 0
