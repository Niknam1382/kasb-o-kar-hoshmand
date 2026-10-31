"""add ai api key pool

Revision ID: c84a9c3c7f34
Revises: 8b5d55b35561
Create Date: 2026-09-20 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c84a9c3c7f34'
down_revision: Union[str, Sequence[str], None] = '8b5d55b35561'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'ai_api_key_pool',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('label', sa.String(length=100), nullable=False),
        sa.Column('api_key', sa.Text(), nullable=False),
        sa.Column('model', sa.String(length=100), nullable=False),
        sa.Column('base_url', sa.String(length=255), nullable=False),
        sa.Column('capability', sa.String(length=32), nullable=False, server_default='chat'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('ai_api_key_pool')
