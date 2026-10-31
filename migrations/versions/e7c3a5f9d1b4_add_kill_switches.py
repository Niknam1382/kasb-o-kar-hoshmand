"""add platform kill switches and maintenance mode

Revision ID: e7c3a5f9d1b4
Revises: d4b2e6a1c9f3
Create Date: 2026-08-17 01:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e7c3a5f9d1b4'
down_revision: Union[str, Sequence[str], None] = 'd4b2e6a1c9f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('admin_settings', sa.Column('allow_new_registrations', sa.Boolean(), nullable=False, server_default='true'))
    op.alter_column('admin_settings', 'allow_new_registrations', server_default=None)
    op.add_column('admin_settings', sa.Column('allow_wallet_topups', sa.Boolean(), nullable=False, server_default='true'))
    op.alter_column('admin_settings', 'allow_wallet_topups', server_default=None)
    op.add_column('admin_settings', sa.Column('maintenance_mode', sa.Boolean(), nullable=False, server_default='false'))
    op.alter_column('admin_settings', 'maintenance_mode', server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('admin_settings', 'maintenance_mode')
    op.drop_column('admin_settings', 'allow_wallet_topups')
    op.drop_column('admin_settings', 'allow_new_registrations')
