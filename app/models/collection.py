from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Text,
    ForeignKey,
    func,
    Index,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship, backref
from sqlalchemy.dialects.postgresql import JSONB

from .base import Base


class Collection(Base):
    __tablename__ = "collections"

    id = Column(Integer, primary_key=True, autoincrement=True)

    owner_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    owner = relationship(
        "User",
        backref=backref("collections", lazy="selectin", cascade="all, delete-orphan"),
        lazy="joined",
    )

    title = Column(String(128), nullable=False)
    description = Column(Text, nullable=True)

    meta = Column(JSONB, nullable=False, server_default="{}")

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    items = relationship(
        "CollectionItem",
        back_populates="collection",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="CollectionItem.position.asc()",
        lazy="selectin",
    )

    def __repr__(self):
        return (
            f"<Collection id={self.id} owner_id={self.owner_id} title={self.title!r}>"
        )

    @property
    def qa_dict(self) -> dict[str, str]:
        return {item.question: item.answer for item in self.items}

    def set_items_from_dict(self, qa: dict[str, str]) -> None:
        self.items = [
            CollectionItem(question=q, answer=a, position=i)
            for i, (q, a) in enumerate(qa.items(), start=1)
        ]


class CollectionItem(Base):
    __tablename__ = "collection_items"

    id = Column(Integer, primary_key=True, autoincrement=True)

    collection_id = Column(
        Integer,
        ForeignKey("collections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    collection = relationship("Collection", back_populates="items", lazy="joined")

    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)

    position = Column(Integer, nullable=False)

    extra = Column(JSONB, nullable=False, server_default="{}")

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "collection_id", "position", name="uq_collection_item_position"
        ),
        UniqueConstraint(
            "collection_id", "question", name="uq_collection_item_question"
        ),
        Index(
            "ix_collection_items_fulltext",
            "question",
            "answer",
            postgresql_using="gin",
        ),
    )

    def __repr__(self):
        return f"<CollectionItem id={self.id} col={self.collection_id} pos={self.position}>"
