"""add moderation rules and audit log tables

Revision ID: f8d1c4b6a2e5
Revises: e7c3a5f9d1b4
Create Date: 2026-08-17 02:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f8d1c4b6a2e5'
down_revision: Union[str, Sequence[str], None] = 'e7c3a5f9d1b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'moderation_rules',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('pattern', sa.String(length=200), nullable=False),
        sa.Column('is_regex', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('action', sa.String(length=32), nullable=False, server_default='review'),
        sa.Column('category', sa.String(length=100), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.alter_column('moderation_rules', 'is_regex', server_default=None)
    op.alter_column('moderation_rules', 'action', server_default=None)
    op.alter_column('moderation_rules', 'is_active', server_default=None)

    op.create_table(
        'audit_log_entries',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('event_type', sa.String(length=32), nullable=False),
        sa.Column('shop_bot_id', sa.Integer(), sa.ForeignKey('shop_bots.id'), nullable=True),
        sa.Column('actor_telegram_id', sa.BigInteger(), nullable=True),
        sa.Column('details', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_audit_log_entries_event_type', 'audit_log_entries', ['event_type'])
    op.create_index('ix_audit_log_entries_shop_bot_id', 'audit_log_entries', ['shop_bot_id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_audit_log_entries_shop_bot_id', table_name='audit_log_entries')
    op.drop_index('ix_audit_log_entries_event_type', table_name='audit_log_entries')
    op.drop_table('audit_log_entries')
    op.drop_table('moderation_rules')
