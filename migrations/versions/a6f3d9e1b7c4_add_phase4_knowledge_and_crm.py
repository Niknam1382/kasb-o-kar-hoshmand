"""add phase 4 knowledge gaps, learned answers and CRM columns

Revision ID: a6f3d9e1b7c4
Revises: 5e8b1c3a9d27
Create Date: 2026-10-05 00:00:00.000000

فازِ ۴ — یه مایگریشنِ واحد برایِ همه‌ی قابلیت‌هایِ تازه:
- جدولِ knowledge_gaps: سوال‌هایی که ربات نتونسته جواب بده (یکتا به‌ازایِ فروشگاه+هشِ سوال).
- جدولِ learned_answers: پرسش‌وپاسخ‌هایِ تاییدشده توسطِ فروشگاه‌دار.
- customers.crm_notes / crm_tags: یادداشت و برچسبِ CRM (هر دو نال‌پذیر؛ ردیف‌هایِ قدیمی دست‌نخورده).
- admin_settings.knowledge_gap_enabled: کلیدِ سراسریِ تشخیصِ خلأ (پیش‌فرضِ روشن).
حسابداری، بخش‌بندیِ CRM، دستیارِ مدیریتی و خلاصه‌یِ CRM جدول/ستونِ جدید نمی‌خوان
(همه از داده‌یِ موجود محاسبه می‌شن؛ دلیل‌هایِ جدیدِ کیف‌پول هم String(32) ان، نه enumِ PostgreSQL).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a6f3d9e1b7c4"
down_revision: Union[str, Sequence[str], None] = "5e8b1c3a9d27"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "knowledge_gaps",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("shop_bot_id", sa.Integer(), sa.ForeignKey("shop_bots.id"), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("question_key", sa.String(length=64), nullable=False),
        sa.Column("occurrences", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="open"),
        sa.UniqueConstraint("shop_bot_id", "question_key", name=op.f("uq_knowledge_gaps_shop_bot_id")),
    )
    op.alter_column("knowledge_gaps", "occurrences", server_default=None)
    op.alter_column("knowledge_gaps", "status", server_default=None)
    op.create_index(op.f("ix_knowledge_gaps_shop_bot_id"), "knowledge_gaps", ["shop_bot_id"], unique=False)

    op.create_table(
        "learned_answers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("shop_bot_id", sa.Integer(), sa.ForeignKey("shop_bots.id"), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("source_gap_id", sa.Integer(), sa.ForeignKey("knowledge_gaps.id"), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.alter_column("learned_answers", "is_active", server_default=None)
    op.create_index(op.f("ix_learned_answers_shop_bot_id"), "learned_answers", ["shop_bot_id"], unique=False)
    op.create_index(op.f("ix_learned_answers_source_gap_id"), "learned_answers", ["source_gap_id"], unique=False)

    op.add_column("customers", sa.Column("crm_notes", sa.Text(), nullable=True))
    op.add_column("customers", sa.Column("crm_tags", sa.String(length=255), nullable=True))

    op.add_column("admin_settings", sa.Column("knowledge_gap_enabled", sa.Boolean(), nullable=False, server_default="true"))
    op.alter_column("admin_settings", "knowledge_gap_enabled", server_default=None)


def downgrade() -> None:
    op.drop_column("admin_settings", "knowledge_gap_enabled")
    op.drop_column("customers", "crm_tags")
    op.drop_column("customers", "crm_notes")

    op.drop_index(op.f("ix_learned_answers_source_gap_id"), table_name="learned_answers")
    op.drop_index(op.f("ix_learned_answers_shop_bot_id"), table_name="learned_answers")
    op.drop_table("learned_answers")

    op.drop_index(op.f("ix_knowledge_gaps_shop_bot_id"), table_name="knowledge_gaps")
    op.drop_table("knowledge_gaps")
