"""add tenant_mode to shop_bots for consultation mode

Revision ID: d4b2e6a1c9f3
Revises: c1a9f3e7b8d2
Create Date: 2026-08-17 00:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4b2e6a1c9f3'
down_revision: Union[str, Sequence[str], None] = 'c1a9f3e7b8d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('shop_bots', sa.Column('tenant_mode', sa.String(length=32), nullable=False, server_default='sales'))
    op.alter_column('shop_bots', 'tenant_mode', server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('shop_bots', 'tenant_mode')
