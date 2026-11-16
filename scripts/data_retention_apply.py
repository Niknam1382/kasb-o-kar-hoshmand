"""پ۹۹ · پاک‌سازیِ دادهٔ پیر با پنجرهٔ **سفارشیِ هرِ جدول** (ادامهٔ شمارشِ پ۹۳، با قفل‌هایِ پ۹۴).

مالکِ محصول برایِ سیاستِ نگهداری «پنجرهٔ سفارشی» را انتخاب کرد؛ پس اینجا هیچ پنجره‌ای پنهان نیست و هیچ
حذفی خودکار اتفاق نمی‌افتد: هرِ جدول عددِ روزهایِ خودش را با گزینهٔ جدا می‌گیرد و تا سه شرطِ هم‌زمان
برقرار نشود، اسکریپت **فقط می‌شمارد**:

۱) `--apply`                         → حالتِ حذف، وگرنه dry-run
۲) `--confirm delete-retention-rows` → تاییدِ متنیِ صریح
۳) `RETENTION_BACKUP_CONFIRMED=1`    → اذعانِ اینکه `pg_dump` گرفته شده (قاعدهٔ ۳ِ AGENTS.md)

قاعدهٔ ۴ رعایت می‌شود: هیچ ستون/جدولی حذف نمی‌شود؛ فقط ردیف‌هایِ بیرونِ پنجره می‌روند و جدول می‌ماند.
پیام‌هایِ گفتگویِ مشتری به‌صورتِ پیش‌فرض **دست‌نخورده** می‌مانند (تاریخچهٔ چت دادهٔ خودِ فروشگاه است؛
پاک‌کردنش باید صراحتاً با `--include-chat` خواسته شود).

نحوهٔ اجرا (اولِ همه dry-run، با عددهایِ خودت):
    docker compose run --rm bot python3 scripts/data_retention_apply.py \\
        --payments-days 365 --audit-days 730 --ig-days 180 --counters-days 7

اجرایِ واقعی (پس ازِ pg_dump):
    docker compose run --rm -e RETENTION_BACKUP_CONFIRMED=1 bot python3 scripts/data_retention_apply.py \\
        --payments-days 365 --audit-days 730 --ig-days 180 --counters-days 7 \\
        --apply --confirm delete-retention-rows

`--X-days 0` یعنی آنِ جدول را اصلاً دست مزن. پیش‌فرضِ **دفترِ ممیزی ۰ است** (زنجیرهٔ هشِ آن با حذفِ
ردیف‌هایِ قدیمی گره‌می‌خورد) و پیام‌هایِ گفتگو هم بدونِ `--include-chat` هرگز پاک نمی‌شوند.
خروجِ کد: ۰ = موفق (dry-run یا حذفِ کامل) ·
۲ = قفل‌ها برقرار نیست و هیچ حذفی انجام نشده. یکِ ردیفِ ممیزی با تعدادِ پاک‌شده‌ها ثبت می‌شود.
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import os
import sys

from sqlalchemy import delete, func, select

sys.path.insert(0, ".")

from app.database.models import (  # noqa: E402
    AuditEventType,
    AuditLogEntry,
    ConversationMessage,
    InstagramCommentEvent,
    PaymentEventLog,
    RuntimeCounterSnapshot,
)
from app.database.session import session_scope  # noqa: E402
from app.services import audit_log_service  # noqa: E402
from app.utils.validators import fa_grouped, fa_number  # noqa: E402

UTC = dt.timezone.utc
CONFIRM_PHRASE = "delete-retention-rows"
BACKUP_ENV = "RETENTION_BACKUP_CONFIRMED"
CHUNK = 5_000  # سقفِ ردیف در هر DELETE ⇒ قفلِ کوتاه‌مدت، نه قفلِ طولانی رویِ جدولِ بزرگ

# (کلیدِ گزینه، برچسبِ فارسی، مدل، ستونِ زمان، پنجرهٔ پیش‌فرضِ روز)
# پیش‌فرض‌ها محافظه‌کارانه‌اند و عمداً بلند: اسنادِ مالی و ممیزی زود پاک نمی‌شوند.
TABLES: tuple[tuple[str, str, object, object, int], ...] = (
    ("payments", "رویدادهایِ پرداخت", PaymentEventLog, PaymentEventLog.created_at, 365),
    # دفترِ ممیزی زنجیرهٔ هش دارد (prev_hash/row_hash) ⇒ پاک‌کردنِ ردیف‌هایِ قدیمیِ آن، ابتدا و انتهایِ
    # زنجیره را گره‌می‌زند. پیش‌فرض: ۰ = اصلاً دست نزن؛ اگر روزی خواستی، با --audit-days N صریح بخواه.
    ("audit", "دفترِ ممیزی", AuditLogEntry, AuditLogEntry.created_at, 0),
    ("ig", "رویدادِ کامنتِ اینستاگرام", InstagramCommentEvent, InstagramCommentEvent.created_at, 180),
    ("counters", "ردیفِ شمارندهٔ پروسه‌ها", RuntimeCounterSnapshot, RuntimeCounterSnapshot.updated_at, 7),
    ("chat", "پیام‌هایِ گفتگویِ مشتری", ConversationMessage, ConversationMessage.created_at, 365),
)


def _targets(windows: dict[str, int], *, include_chat: bool) -> list[tuple]:
    now = dt.datetime.now(UTC)
    out = []
    for key, label, model, column, _default in TABLES:
        days = windows.get(key, 0)
        if days <= 0:
            continue  # صفر/منفی یعنی «اینِ جدول را دست مزن»
        if key == "chat" and not include_chat:
            continue  # تاریخچهٔ چت فقط با درخواستِ صریح
        out.append((key, label, model, column, now - dt.timedelta(days=days)))
    return out


async def _count(session, model, column, cutoff) -> tuple[int, int]:
    old = (await session.execute(select(func.count()).select_from(model).where(column < cutoff))).scalar_one()
    everything = (await session.execute(select(func.count()).select_from(model))).scalar_one()
    return int(old), int(everything)


async def _delete_chunked(session, model, column, cutoff) -> int:
    """حذفِ دسته‌ای (هر بار حداکثر `CHUNK` ردیف) تا قفلِ طولانی رویِ جدولِ بزرگ نیفتد.

    شناسه‌ها با زیرکوئریِ `LIMIT` انتخاب می‌شوند؛ هیچ نامِ جدول/ستونی از ورودیِ کاربر ساخته نمی‌شود.
    """
    total = 0
    while True:
        batch = select(model.id).where(column < cutoff).order_by(model.id).limit(CHUNK).scalar_subquery()
        result = await session.execute(delete(model).where(model.id.in_(batch)))
        went = int(result.rowcount or 0)
        total += went
        if went < CHUNK:
            return total
        await session.commit()


async def run(windows: dict[str, int], *, apply: bool, confirm: str, backup_ok: bool, include_chat: bool) -> int:
    targets = _targets(windows, include_chat=include_chat)
    if not targets:
        print("هیچ پنجره‌ای فعال نیست (همهٔ روزها صفر، یا فقطِ گفتگو بدونِ `--include-chat`) ⇒ کاری انجام نشد.")
        return 0

    print("پنجره‌هایِ انتخابی: " + " · ".join(f"{label} {fa_number(windows[key])} روز" for key, label, *_rest in targets))
    if apply and (confirm != CONFIRM_PHRASE or not backup_ok):
        missing = []
        if confirm != CONFIRM_PHRASE:
            missing.append(f"`--confirm {CONFIRM_PHRASE}`")
        if not backup_ok:
            missing.append(f"مثبتِ `pg_dump` ⇒ {BACKUP_ENV}=1")
        print("⛔️ حذف انجام نشد — قفل‌ها برقرار نیست: " + " و ".join(missing))
        return 2

    total_deleted = 0
    report: list[str] = []
    async with session_scope() as session:
        for key, label, model, column, cutoff in targets:
            if not apply:
                old, everything = await _count(session, model, column, cutoff)
                print(f"  • {label}: {fa_grouped(old)} ردیف از {fa_grouped(everything)} بیرونِ پنجره است (dry-run).")
                continue
            went = await _delete_chunked(session, model, column, cutoff)
            total_deleted += went
            report.append(f"{key}={went}")
            print(f"  • {label}: {fa_grouped(went)} ردیف پاک شد.")
        if apply and total_deleted:
            await audit_log_service.log(
                session,
                AuditEventType.RETENTION_APPLIED,
                details="پاک‌سازیِ نگهداری: " + " ".join(report) + f" | جمع={total_deleted}",
            )
        await session.commit()

    if not apply:
        print(
            "یادآوری: این dry-run بود و هیچ ردیفی پاک نشد. برایِ حذفِ واقعی سه شرط لازم است: --apply، "
            f"--confirm {CONFIRM_PHRASE} و {BACKUP_ENV}=1."
        )
    else:
        print(f"جمعِ ردیف‌هایِ پاک‌شده: {fa_grouped(total_deleted)} (ستون‌ها و جدول‌ها دست‌نخورده‌اند؛ قاعدهٔ ۴).")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="پاک‌سازیِ دادهٔ پیر با پنجرهٔ سفارشیِ هرِ جدول")
    for key, label, _model, _column, default in TABLES:
        parser.add_argument(f"--{key}-days", dest=key, type=int, default=default, help=f"{label} (روز؛ ۰ = دست مزن)")
    parser.add_argument("--apply", action="store_true", help="حالتِ حذف (بدونِ این فقط dry-run)")
    parser.add_argument("--confirm", default="", help=f"عبارتِ تایید: {CONFIRM_PHRASE}")
    parser.add_argument("--include-chat", action="store_true", help="پنجرهٔ گفتگو هم اجرا شود (پیش‌فرض: نه)")
    args = parser.parse_args()
    windows = {key: getattr(args, key) for key, _label, _m, _c, _d in TABLES}
    return asyncio.run(
        run(windows, apply=args.apply, confirm=args.confirm, backup_ok=os.environ.get(BACKUP_ENV) == "1", include_chat=args.include_chat)
    )


if __name__ == "__main__":
    raise SystemExit(main())
