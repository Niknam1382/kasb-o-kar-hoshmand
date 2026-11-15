"""پ۷۵ · خوشه‌بندیِ سوال‌هایِ بی‌جواب: ستونِ `knowledge_gaps.cluster_key`

Revision ID: c5f8b2d9e410
Revises: b4e9a1c7d320
Create Date: 2026-11-15 10:40:00.000000

افزودنی و خالی‌پذیر: ردیف‌هایِ موجود `NULL` می‌مانند و اولینِ بار که صفحهٔ «🧠 سوال‌هایِ مشابه»
همان فروشگاه را می‌خواند، امضا در پایتون محاسبه و همان‌جا پر می‌شود (`backfill_cluster_keys`) —
چون امضا از متنِ سوال می‌آید، نه از هیچ دادهٔ تازه‌ای، و این راهِ «مهاجرتِ داده» بدونِ اسکریپتِ جداست.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c5f8b2d9e410"
down_revision: Union[str, Sequence[str], None] = "b4e9a1c7d320"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("knowledge_gaps", sa.Column("cluster_key", sa.String(length=64), nullable=True))
    op.create_index("ix_knowledge_gaps_shop_cluster", "knowledge_gaps", ["shop_bot_id", "cluster_key"])


def downgrade() -> None:
    op.drop_index("ix_knowledge_gaps_shop_cluster", table_name="knowledge_gaps")
    op.drop_column("knowledge_gaps", "cluster_key")
