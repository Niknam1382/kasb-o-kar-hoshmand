"""P30: سوییچِ «ادامهٔ سفارش با اعتبارِ صفر» + سقفِ بدهیِ کمیسیون

Revision ID: e1b7c9d4a6f2
Revises: c4f8a2d6b9e1
Create Date: 2026-11-04 00:00:00.000000

امروز با خالی‌شدنِ کیف‌پول، رباتِ آن فروشگاه کاملاً می‌ایستد (چت و سفارش). این دو ستون
می‌گذارند ادمین یکِ سوییچِ سراسری روشن کند تا فروش ادامه یابد و بدهیِ ناشی از کمیسیون در
`commission_receivables` با وضعیتِ `open` جمع شود؛ ستونِ دوم همان بدهی را مهار می‌کند
(۰ = بی‌سقف).

افزوندی و بدونِ حذف: هر دو ستون `server_default` دارند ⇒ ردیف‌هایِ موجود دست‌نخورده‌اند
و هیچ مهاجرتِ داده‌ای لازم نیست.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e1b7c9d4a6f2"
down_revision: Union[str, Sequence[str], None] = "c4f8a2d6b9e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "admin_settings",
        sa.Column("orders_allowed_when_wallet_empty", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "admin_settings",
        sa.Column("commission_debt_ceiling_toman", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("admin_settings", "commission_debt_ceiling_toman")
    op.drop_column("admin_settings", "orders_allowed_when_wallet_empty")
