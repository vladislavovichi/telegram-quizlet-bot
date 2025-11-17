import sqlalchemy as sa

from alembic import op

revision = "0fb7996f0e93"
down_revision = "0a801c877d2a"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tg_id", sa.BigInteger(), nullable=False, unique=True),
        sa.Column("username", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_index("ix_users_tg_id", "users", ["tg_id"], unique=True)


def downgrade():
    op.drop_index("ix_users_tg_id", table_name="users")
    op.drop_table("users")
