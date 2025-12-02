from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Tuple

from sqlalchemy import select

from app.models.collection import Collection, CollectionItem

from .base import Repo


class SoloModeRepo(Repo):
    async def list_user_collections(self, user_owner_id: int) -> list[Collection]:
        res = await self.session.execute(
            select(Collection)
            .where(Collection.owner_id == user_owner_id)
            .order_by(Collection.created_at)
        )
        return list(res.scalars().all())

    async def get_collection_title_by_id(self, collection_id: int) -> Optional[str]:
        res = await self.session.execute(
            select(Collection.title).where(Collection.id == collection_id)
        )
        row = res.first()
        return None if not row else (row[0] or "Без названия")

    async def get_item_ids(self, collection_id: int) -> List[int]:
        res = await self.session.execute(
            select(CollectionItem.id)
            .where(CollectionItem.collection_id == collection_id)
            .order_by(CollectionItem.position.asc(), CollectionItem.id.asc())
        )
        return [int(row[0]) for row in res.all()]

    async def get_item_qa(self, item_id: int) -> Optional[Tuple[str, str]]:
        res = await self.session.execute(
            select(CollectionItem.question, CollectionItem.answer).where(
                CollectionItem.id == item_id
            )
        )
        row = res.first()
        return None if not row else (row[0], row[1])

    async def get_collection_title_by_item(self, item_id: int) -> Optional[str]:
        res = await self.session.execute(
            select(Collection.title)
            .join(CollectionItem, CollectionItem.collection_id == Collection.id)
            .where(CollectionItem.id == item_id)
        )
        row = res.first()
        return None if not row else (row[0] or "Без названия")

    async def get_items_bulk(
        self, item_ids: Iterable[int]
    ) -> Dict[int, Tuple[str, str]]:
        ids = list(set(map(int, item_ids)))
        if not ids:
            return {}
        res = await self.session.execute(
            select(
                CollectionItem.id,
                CollectionItem.question,
                CollectionItem.answer,
            ).where(CollectionItem.id.in_(ids))
        )
        out: Dict[int, Tuple[str, str]] = {}
        for row in res.all():
            out[int(row[0])] = (row[1], row[2])
        return out
