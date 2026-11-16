"""
بازبینیِ زنجیرهٔ هشِ گزارشِ ممیزی (P20 · بلاکرِ B1).

چرا: جدولِ `audit_log_entries` تنها شاهدِ بیرونیِ تصمیم‌هایِ مالی/اداری است. اگر کسی (با دسترسی به
دیتابیس، نه از راهِ رابطِ کاربری) یک ردیفِ قدیمی را عوض یا حذف کند، بدونِ زنجیرهٔ هش چیزی
قابلِ اثبات نیست. هر ردیفِ تازه `prev_hash` (هشِ ردیفِ هش‌دارِ قبلی) و `row_hash` را نگه می‌دارد.

خروجی: شمارشِ ردیف‌هایِ بررسی‌شده، تعدادِ «پیوندِ ناهمسایه» (نتیجهٔ هم‌زمانیِ واقعی، نه تحریف) و
در صورتِ وجود، نخستینِ چند موردِ «شکستِ هش» با شناسه. کدِ خروجِ ۱ یعنی زنجیره شکسته است.

اجرا (داخل ظرف):
    docker compose run --rm bot python3 scripts/verify_audit_chain.py [--limit N]
"""
from __future__ import annotations

import argparse
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.database.models import AuditEventType, AuditLogEntry  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services.audit_log_service import GENESIS, compute_hash  # noqa: E402

MAX_REPORTED = 10
# همان پیشوندی که `scripts/data_retention_apply.py` در مُهرِ سرِ زنجیره می‌نویسد (پ۱۰۲).
# عمداً اینجا تکرار شده تا importِ متقابلِ دو اسکریپت لازم نشود؛ تستِ پ۱۰۲ همسانیِ آن‌ها را می‌سنجد.
AUDIT_SEAL_PREFIX = "audit_head_prev="


async def verify(limit: int | None) -> int:
    async with session_scope() as session:
        query = select(AuditLogEntry).order_by(AuditLogEntry.id)
        if limit:
            query = query.limit(limit)
        rows = list((await session.execute(query)).scalars().all())
        seals = {
            part.split("=", 1)[1]
            for (text,) in (await session.execute(select(AuditLogEntry.details).where(AuditLogEntry.event_type == AuditEventType.RETENTION_APPLIED))).all()
            for part in (text or "").split()
            if part.startswith(AUDIT_SEAL_PREFIX)
        }

    checked = legacy = branch = trimmed = 0
    broken: list[str] = []
    hashes_seen: dict[str, int] = {}
    last_hashed: AuditLogEntry | None = None

    for row in rows:
        if not row.row_hash:
            legacy += 1
            continue
        checked += 1
        expected_prev = last_hashed.row_hash if last_hashed is not None else GENESIS
        if row.prev_hash != expected_prev:
            if last_hashed is None and (row.prev_hash or "") in seals:
                # پ۱۰۲: ابتدایِ زنجیره با سیاستِ نگهداری بریده شده و مُهرِ آن در همین جدول هست ⇒ سرِ تازه
                # از اینجا اعتبار می‌گیرد؛ حذفِ بی‌مُهر به‌جایِ این خط در broken می‌افتد.
                trimmed += 1
            elif row.prev_hash in hashes_seen:
                branch += 1  # هم‌زمانی: دو ردیف «پیشین» یکسانی دیده‌اند؛ پیوند به ردیفِ واقعیِ دیگری می‌رسد
            else:
                broken.append(f"id={row.id}: prev_hash به هیچ ردیفِ معتبری نمی‌رسد")
        if compute_hash(row.prev_hash or GENESIS, row) != row.row_hash:
            broken.append(f"id={row.id}: محتوا با هشِ ذخیره‌شده نمی‌خواند (تغییر/حذفِ داده)")
        hashes_seen[row.row_hash] = row.id
        last_hashed = row

    linked = checked - branch - len(broken)
    head_note = f" · {trimmed} سرِ بریده با مُهرِ نگهداری" if trimmed else ""
    print(
        f"بازبینیِ زنجیرهٔ ممیزی: {checked} ردیفِ هش‌دار · {legacy} ردیفِ قدیمی (پیش از P20) · "
        f"{linked} پیوندِ درست · {branch} پیوندِ ناهمسایه (هم‌زمانی){head_note}"
    )
    for line in broken[:MAX_REPORTED]:
        print("  ❌", line)
    if broken:
        print(f"نتیجه: زنجیره شکسته است ({len(broken)} مورد).")
        return 1
    print("نتیجه: زنجیره سالم است ✔")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="verify the audit log hash chain")
    parser.add_argument("--limit", type=int, default=None, help="فقط N ردیفِ نخست (برایِ دیتابیسِ بزرگ)")
    return asyncio.run(verify(parser.parse_args().limit))


if __name__ == "__main__":
    raise SystemExit(main())
