"""P23: قالبِ لینکِ پرداختِ بله‌پی (از برگه‌ای که خودِ بله صادر می‌کند)

Revision ID: b3e7d1a9c4f6
Revises: d7a2c5b8e1f3
Create Date: 2026-11-02 11:10:00.000000

یک ستونِ افزودنی: `admin_settings.bale_pay_link_template`.

چرا: MEASURED از `payment_event_logs` همین محیط — بله به `createInvoiceLink` با
`ok: true` و `result: "invoice_id=M6dm…"` جواب می‌دهد، یعنی یکِ **شناسه**، نه آدرس.
کد همان رشته را داخلِ `InlineKeyboardButton(url=…)` می‌گذاشت و تلگرام ردش می‌کرد:
«inline keyboard button URL 'invoice_id=…' is invalid: Wrong HTTP URL» ⇒ پیامِ پرداخت
هیچ‌وقت ارسال نمی‌شد و دکمه مرده به‌نظر می‌رسید (ردیفِ Payment هم ساخته شده بود).

مستنداتِ عمومیِ بله (docs.bale.ai و بخشِ مینی‌اپ) فقط می‌گوید همان رشته را «بدونِ تغییر»
به `openInvoice` بدهید و هیچ قالبِ URLِ بیرونی نمی‌دهد؛ نشانیِ بازگشتِ وب‌سرویس هم HTTPS
عمومی می‌خواهد. پس به‌جایِ حدس‌زدنِ آدرس، قالب را ادمین از برگه‌ای که بله صادر کرده
(«بازوهایِ من» › «پرداخت در بازو») برمی‌دارد و اینجا وارد می‌کند. خالی ⇒ دکمه ساخته
نمی‌شود و دلیلش صادقانه گفته می‌شود.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b3e7d1a9c4f6"
down_revision: Union[str, Sequence[str], None] = "d7a2c5b8e1f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "admin_settings",
        sa.Column("bale_pay_link_template", sa.String(length=256), nullable=True, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("admin_settings", "bale_pay_link_template")
