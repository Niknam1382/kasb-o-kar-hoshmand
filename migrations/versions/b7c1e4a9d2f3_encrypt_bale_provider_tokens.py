"""encrypt bale_provider_token on admin_settings & shop_bots (W5 / B7)

Revision ID: b7c1e4a9d2f3
Revises: d4a9c6e2b8f1
Create Date: 2026-10-28 12:00:00.000000

ستون‌ها از String(128) به String(512) (رمزِ Fernet بلندتر از توکنِ خام است) و داده‌یِ قدیمیِ خام با
`encrypt_token` رمز می‌شه (idempotent: مقدارِ از‌قبل‌رمز دوباره رمز نمی‌شه). هیچ داده‌ای پاک نمی‌شه.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b7c1e4a9d2f3"
down_revision: Union[str, Sequence[str], None] = "d4a9c6e2b8f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLES = ("admin_settings", "shop_bots")


def _is_encrypted(value: str) -> bool:
    from app.utils.encryption import decrypt_token

    try:
        decrypt_token(value)
    except Exception:  # noqa: BLE001
        return False
    return True


def upgrade() -> None:
    from app.utils.encryption import encrypt_token

    for table in _TABLES:
        op.alter_column(table, "bale_provider_token", existing_type=sa.String(length=128), type_=sa.String(length=512), existing_nullable=True)
    bind = op.get_bind()
    for table in _TABLES:
        rows = bind.execute(sa.text(f"SELECT id, bale_provider_token FROM {table} WHERE bale_provider_token IS NOT NULL")).fetchall()
        for row_id, value in rows:
            if value and not _is_encrypted(value):
                bind.execute(
                    sa.text(f"UPDATE {table} SET bale_provider_token = :v WHERE id = :i"),
                    {"v": encrypt_token(value), "i": row_id},
                )


def downgrade() -> None:
    from app.utils.encryption import decrypt_token

    bind = op.get_bind()
    for table in _TABLES:
        rows = bind.execute(sa.text(f"SELECT id, bale_provider_token FROM {table} WHERE bale_provider_token IS NOT NULL")).fetchall()
        for row_id, value in rows:
            if value and _is_encrypted(value):
                bind.execute(
                    sa.text(f"UPDATE {table} SET bale_provider_token = :v WHERE id = :i"),
                    {"v": decrypt_token(value), "i": row_id},
                )
        op.alter_column(table, "bale_provider_token", existing_type=sa.String(length=512), type_=sa.String(length=128), existing_nullable=True)
