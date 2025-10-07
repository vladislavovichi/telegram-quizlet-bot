"""create table users

Revision ID: ef0b4f66c587
Revises: 0a801c877d2a
Create Date: 2025-10-07 12:14:08.840368

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'ef0b4f66c587'
down_revision = '0a801c877d2a'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('tg_id', sa.BigInteger(), nullable=False, unique=True),
        sa.Column('username', sa.String(length=64), nullable=True),
        sa.Column(
            'numbers',
            postgresql.ARRAY(sa.Integer),
            nullable=False,
            server_default=sa.text("ARRAY[]::integer[]")
        ),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text('now()')
        ),
        sa.UniqueConstraint('tg_id', name='uq_users_tg_id'),
    )

    op.create_index(
        'ix_users_numbers_gin',
        'users',
        ['numbers'],
        unique=False,
        postgresql_using='gin'
    )

def downgrade():
    op.drop_index('ix_users_numbers_gin', table_name='users')
    op.drop_table('users')