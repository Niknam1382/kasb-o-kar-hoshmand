"""payment event logs (P1-S5a / B12)

Revision ID: f4d8b2c6a1e9
Revises: e3c7a9d1f5b2
Create Date: 2026-10-23 02:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f4d8b2c6a1e9"
down_revision: Union[str, Sequence[str], None] = "e3c7a9d1f5b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "payment_event_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("provider", sa.String(length=16), nullable=False),
        sa.Column("direction", sa.String(length=8), nullable=False),
        sa.Column("method", sa.String(length=64), nullable=False),
        sa.Column("reference", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=True),
        sa.Column("raw", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_payment_event_logs_provider", "payment_event_logs", ["provider"])


def downgrade() -> None:
    op.drop_index("ix_payment_event_logs_provider", table_name="payment_event_logs")
    op.drop_table("payment_event_logs")
