"""add bale pay columns

Revision ID: 7208342769e8
Revises: 77419b5a2dfe
Create Date: 2026-09-18 00:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7208342769e8'
down_revision: Union[str, Sequence[str], None] = '77419b5a2dfe'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('payments', sa.Column('bale_invoice_payload', sa.String(length=128), nullable=True))
    op.create_index(op.f('ix_payments_bale_invoice_payload'), 'payments', ['bale_invoice_payload'], unique=False)
    op.add_column('payments', sa.Column('bale_transaction_id', sa.String(length=128), nullable=True))

    op.add_column('admin_settings', sa.Column('bale_provider_token', sa.String(length=128), nullable=True))
    op.add_column('admin_settings', sa.Column('bale_pay_enabled', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.alter_column('admin_settings', 'bale_pay_enabled', server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('admin_settings', 'bale_pay_enabled')
    op.drop_column('admin_settings', 'bale_provider_token')
    op.drop_index(op.f('ix_payments_bale_invoice_payload'), table_name='payments')
    op.drop_column('payments', 'bale_transaction_id')
    op.drop_column('payments', 'bale_invoice_payload')
