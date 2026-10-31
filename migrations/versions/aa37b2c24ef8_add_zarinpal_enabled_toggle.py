"""add zarinpal_enabled toggle

Revision ID: aa37b2c24ef8
Revises: e59de9fae404
Create Date: 2026-08-12 12:03:22.896296

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'aa37b2c24ef8'
down_revision: Union[str, Sequence[str], None] = 'e59de9fae404'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # server_default لازمه چون ممکنه ردیفِ admin_settings از قبل وجود داشته
    # باشه؛ بدونش، ALTER TABLE با NOT NULL روی دیتای موجود fail می‌شه.
    op.add_column('admin_settings', sa.Column('zarinpal_enabled', sa.Boolean(), nullable=False, server_default=sa.true()))
    op.alter_column('admin_settings', 'zarinpal_enabled', server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('admin_settings', 'zarinpal_enabled')
