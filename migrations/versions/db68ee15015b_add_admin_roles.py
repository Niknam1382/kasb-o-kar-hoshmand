"""add admin roles

Revision ID: db68ee15015b
Revises: c84a9c3c7f34
Create Date: 2026-09-22 09:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'db68ee15015b'
down_revision: Union[str, Sequence[str], None] = 'c84a9c3c7f34'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'admin_roles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('telegram_id', sa.BigInteger(), nullable=False),
        sa.Column('role', sa.String(length=32), nullable=False, server_default='operator'),
        sa.Column('granted_by_telegram_id', sa.BigInteger(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('telegram_id', name='uq_admin_roles_telegram_id'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('admin_roles')
