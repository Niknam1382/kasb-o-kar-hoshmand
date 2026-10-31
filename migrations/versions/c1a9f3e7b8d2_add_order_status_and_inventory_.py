"""add order status machine and inventory reservation

Revision ID: c1a9f3e7b8d2
Revises: 7b7447577287
Create Date: 2026-08-16 23:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1a9f3e7b8d2'
down_revision: Union[str, Sequence[str], None] = '7b7447577287'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('admin_settings', sa.Column('order_reservation_minutes', sa.Integer(), nullable=False, server_default='60'))
    op.alter_column('admin_settings', 'order_reservation_minutes', server_default=None)

    op.add_column('products', sa.Column('reserved_quantity', sa.Integer(), nullable=False, server_default='0'))
    op.alter_column('products', 'reserved_quantity', server_default=None)

    op.add_column('orders_consultations', sa.Column('status', sa.String(length=32), nullable=False, server_default='pending'))
    op.alter_column('orders_consultations', 'status', server_default=None)
    op.add_column('orders_consultations', sa.Column('stock_reserved', sa.Boolean(), nullable=False, server_default='false'))
    op.alter_column('orders_consultations', 'stock_reserved', server_default=None)
    op.add_column('orders_consultations', sa.Column('reservation_expires_at', sa.DateTime(timezone=True), nullable=True))

    # سفارش‌های قدیمی که از قبل confirmed=True بودن، باید status=confirmed بگیرن
    # تا با داده‌ی موجود سازگار بمونن (نه pending، که غلط‌انداز می‌شد).
    op.execute("UPDATE orders_consultations SET status = 'confirmed' WHERE confirmed = true")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('orders_consultations', 'reservation_expires_at')
    op.drop_column('orders_consultations', 'stock_reserved')
    op.drop_column('orders_consultations', 'status')
    op.drop_column('products', 'reserved_quantity')
    op.drop_column('admin_settings', 'order_reservation_minutes')
