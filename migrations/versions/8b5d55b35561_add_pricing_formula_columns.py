"""add pricing formula columns

Revision ID: 8b5d55b35561
Revises: 7208342769e8
Create Date: 2026-09-19 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8b5d55b35561'
down_revision: Union[str, Sequence[str], None] = '7208342769e8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('admin_settings', sa.Column('ai_cost_usd_per_1m_tokens', sa.Numeric(10, 4), nullable=False, server_default='0.014'))
    op.alter_column('admin_settings', 'ai_cost_usd_per_1m_tokens', server_default=None)

    op.add_column('admin_settings', sa.Column('usd_to_toman_rate', sa.Integer(), nullable=False, server_default='100000'))
    op.alter_column('admin_settings', 'usd_to_toman_rate', server_default=None)

    op.add_column('admin_settings', sa.Column('wallet_markup_multiplier', sa.Numeric(5, 2), nullable=False, server_default='5.00'))
    op.alter_column('admin_settings', 'wallet_markup_multiplier', server_default=None)

    # referral_reward_value از این به بعد تنها منبعِ پورسانتِ معرفه (نه
    # referral_reward_wallet_toman که دیگه هیچ‌جا استفاده نمی‌شه ولی برای
    # سادگی و امنیتِ مهاجرت، ستونش حذف نشده). پیش‌فرض رو برای ردیف‌های
    # موجود هم به ۱۰ به‌روز می‌کنیم تا با پیش‌فرضِ جدیدِ مدل هم‌خوان بمونه.
    op.execute("UPDATE admin_settings SET referral_reward_value = 10 WHERE referral_reward_value = 7")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('admin_settings', 'wallet_markup_multiplier')
    op.drop_column('admin_settings', 'usd_to_toman_rate')
    op.drop_column('admin_settings', 'ai_cost_usd_per_1m_tokens')
