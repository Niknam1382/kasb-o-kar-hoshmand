"""add ai fallback provider fields

Revision ID: a3e9c7d2f4b6
Revises: f8d1c4b6a2e5
Create Date: 2026-08-17 03:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3e9c7d2f4b6'
down_revision: Union[str, Sequence[str], None] = 'f8d1c4b6a2e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('admin_settings', sa.Column('ai_fallback_api_key', sa.Text(), nullable=True))
    op.add_column('admin_settings', sa.Column('ai_fallback_model', sa.String(length=100), nullable=True))
    op.add_column('admin_settings', sa.Column('ai_fallback_base_url', sa.String(length=255), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('admin_settings', 'ai_fallback_base_url')
    op.drop_column('admin_settings', 'ai_fallback_model')
    op.drop_column('admin_settings', 'ai_fallback_api_key')
