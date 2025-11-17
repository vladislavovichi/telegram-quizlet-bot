import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "ef0b4f66c587"
down_revision = "0fb7996f0e93"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "collections",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "owner_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "meta",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_collections_owner_id "
        "ON collections (owner_id)"
    )

    op.create_table(
        "collection_items",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "collection_id",
            sa.Integer(),
            sa.ForeignKey("collections.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column(
            "extra",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_unique_constraint(
        "uq_collection_item_position", "collection_items", ["collection_id", "position"]
    )
    op.create_unique_constraint(
        "uq_collection_item_question", "collection_items", ["collection_id", "question"]
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_collection_items_collection_id "
        "ON collection_items (collection_id)"
    )

    op.execute(
        "CREATE INDEX ix_collection_items_tsv ON collection_items USING GIN (to_tsvector('simple', coalesce(question,'') || ' ' || coalesce(answer,'')));"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_collection_items_tsv")
    op.drop_index("ix_collection_items_collection_id", table_name="collection_items")
    op.drop_constraint(
        "uq_collection_item_question", "collection_items", type_="unique"
    )
    op.drop_constraint(
        "uq_collection_item_position", "collection_items", type_="unique"
    )
    op.drop_table("collection_items")

    op.drop_index("ix_collections_owner_id", table_name="collections")
    op.drop_table("collections")
