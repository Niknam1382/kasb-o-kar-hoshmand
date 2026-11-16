"""پ۹۳ · شمارشِ فقط‌خواندنیِ داده‌هایِ «پیر» — پیش‌نیازِ تصمیمِ سیاستِ نگهداری.

هیچ چیزی حذف نمی‌کند. فقط می‌گوید اگر بخواهی N روز نگه داری، چند ردیف از هر جدول بیرونِ پنجره است:
لاگِ سیستم، دفترِ ممیزی، رویدادِ کامنتِ اینستاگرام، ردیفِ شمارندهٔ پروسه‌ها، و پیام‌هایِ گفتگویِ مشتری.
(پیام‌هایِ گفتگو و رویدادهایِ پرداخت عمداً فقط شمرده می‌شوند: پاک‌کردنِ تاریخچهٔ چت تصمیمِ مالکِ هرِ فروشگاه است، نه یکِ جاب.)

    docker compose run --rm bot python3 scripts/data_retention_probe.py --days 90
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import sys

from sqlalchemy import func, select

sys.path.insert(0, ".")

from app.database.models import (  # noqa: E402
    AuditLogEntry,
    ConversationMessage,
    PaymentEventLog,
    InstagramCommentEvent,
    RuntimeCounterSnapshot,
)
from app.database.session import session_scope  # noqa: E402
from app.utils.validators import fa_grouped, fa_number  # noqa: E402

UTC = dt.timezone.utc


async def report(days: int) -> int:
    cutoff = dt.datetime.now(UTC) - dt.timedelta(days=days)
    tables = (
        ("رویدادهایِ پرداخت", (PaymentEventLog, PaymentEventLog.created_at), cutoff),
        ("دفترِ ممیزی", (AuditLogEntry, AuditLogEntry.created_at), cutoff),
        ("رویدادِ کامنتِ اینستاگرام", (InstagramCommentEvent, InstagramCommentEvent.created_at), cutoff),
        ("ردیفِ شمارندهٔ پروسه‌ها", (RuntimeCounterSnapshot, RuntimeCounterSnapshot.updated_at), cutoff),
        ("پیام‌هایِ گفتگو (فقط شمارش)", (ConversationMessage, ConversationMessage.created_at), cutoff),
    )
    print(f"پنجرهٔ نگهداریِ پیشنهادی: {fa_number(days)} روز (قدیمی‌تر از {cutoff.date().isoformat()})")
    async with session_scope() as session:
        total_old = 0
        for label, item, moment in tables:
            model, column = item
            old = (
                await session.execute(select(func.count()).select_from(model).where(column < moment))
            ).scalar_one()
            all_rows = (await session.execute(select(func.count()).select_from(model))).scalar_one()
            total_old += int(old)
            print(f"  • {label}: {fa_grouped(int(old))} ردیفِ بیرونِ پنجره از {fa_grouped(int(all_rows))} ردیف")
    print(
        "یادآوری: این اسکریپت چیزی حذف نمی‌کند. پاک‌سازیِ خودکار لازم است با تصمیمِ مالک + مایگریشنِ "
        "افزوندی (نه حذفِ جدول) + pg_dump قبلِ اجرایِ اول انجام شود."
    )
    return 0



def main() -> int:
    parser = argparse.ArgumentParser(description="شمارشِ فقط‌خواندنیِ ردیف‌هایِ پیر")
    parser.add_argument("--days", type=int, default=90, help="پنجرهٔ نگهداری به روز (پیش‌فرض ۹۰)")
    args = parser.parse_args()
    return asyncio.run(report(args.days))


if __name__ == "__main__":
    raise SystemExit(main())
