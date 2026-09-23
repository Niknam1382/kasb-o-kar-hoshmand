"""add conversation_retention_days

Revision ID: 77419b5a2dfe
Revises: a3e9c7d2f4b6
Create Date: 2026-09-18 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '77419b5a2dfe'
down_revision: Union[str, Sequence[str], None] = 'a3e9c7d2f4b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # server_default لازمه چون ممکنه ردیفِ admin_settings از قبل وجود داشته
    # باشه؛ بدونش، ALTER TABLE با NOT NULL روی دیتای موجود fail می‌شه.
    op.add_column('admin_settings', sa.Column('conversation_retention_days', sa.Integer(), nullable=False, server_default='90'))
    op.alter_column('admin_settings', 'conversation_retention_days', server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('admin_settings', 'conversation_retention_days')
