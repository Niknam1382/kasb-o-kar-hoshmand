"""P18 · A1: bale bot token + auto webhook secret on admin_settings

Revision ID: e1f4a7c9b2d6
Revises: d9e3a6b8c2f5
Create Date: 2026-10-31 12:00:00.000000

افزودنی و بدونِ حذف: دو ستونِ nullable رمزنگاری‌شده (`EncryptedToken`) رویِ `admin_settings`.
`bale_bot_token` اولویت بر `BALE_BOT_TOKEN` در .env دارد؛ `bale_webhook_secret_auto` فقط در حالتِ
webhook و به‌صورتِ خودکار پر می‌شود (هرگز از ادمین پرسیده نمی‌شود). داده‌یِ قدیمی دست‌نخورده است.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e1f4a7c9b2d6"
down_revision: Union[str, Sequence[str], None] = "d9e3a6b8c2f5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_COLUMNS = ("bale_bot_token", "bale_webhook_secret_auto")


def upgrade() -> None:
    for name in _COLUMNS:
        op.add_column("admin_settings", sa.Column(name, sa.String(length=512), nullable=True))


def downgrade() -> None:
    for name in reversed(_COLUMNS):
        op.drop_column("admin_settings", name)
