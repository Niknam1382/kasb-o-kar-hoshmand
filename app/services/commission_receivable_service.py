"""P21-C (F4): دفترِ «طلبِ کمیسیون» — وقتی فروشگاه اعتبار ندارد، درآمدِ پلتفرم گم نشود.

رفتارِ پیشین (PHASE 5D): تسویهٔ کمیسیون با `wallet_service.deduct` انجام می‌شود و اگر موجودی
کم باشد `settle` رد می‌شود — درست است، ولی **هیچ جایی ثبت نمی‌شد که این مبلغ هرگز گرفته
نشده**. پلتفرم فقط یک لاگ می‌دید و عدد انباشته هیچ‌جا وجود نداشت.

این سرویس همان مبلغ را به‌عنوانِ `open` ثبت می‌کند (یک ردیف به‌ازایِ هر گروهِ سفارش، با قیدِ
یکتا ⇒ دوبار-فراخوانی همان رویداد بدهیِ دوتایی نمی‌سازد) و در جابِ دوره‌ای، هر وقت موجودیِ
*قابل‌استفاده*ِ فروشگاه رسید، همان مبلغ کسر و ردیف `settled` می‌شود.

قاعدهٔ پولی که اینجا رعایت می‌شود: برایِ تسویهٔ بدهی فقط `usable_credit` خرج می‌شود (موجودی
کمِ holdِ کمیسیونِ سفارش‌هایِ درجریان) — وگرنه جمع‌آوریِ بدهی می‌تواند پولِ رزروشدهٔ یکِ
سفارشِ دیگر را بخورد.
"""

from __future__ import annotations

import datetime
import logging

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import CommissionReceivable, ShopOwner, WalletTransactionReason
from app.services import wallet_service

logger = logging.getLogger(__name__)

OPEN = "open"
SETTLED = "settled"
WAIVED = "waived"
COLLECT_LIMIT = 50


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


async def record(session: AsyncSession, *, owner_id: int, group_key: str, amount_toman: int, note: str | None = None) -> bool:
    """یک بدهی ثبت می‌کند. False ⇒ برایِ همین گروه بدهیِ باز وجود دارد (یا مبلغ نامعتبر است)."""
    if amount_toman <= 0:
        return False
    row = CommissionReceivable(
        shop_owner_id=owner_id,
        group_key=group_key[:64],
        amount_toman=int(amount_toman),
        status=OPEN,
        note=(note or "")[:180] or None,
    )
    try:
        # savepoint: قیدِ یکتا فقط درجِ همین ردیف را لغو می‌کند و نوشته‌هایِ دیگرِ همان
        # تراکنش (گذارِ وضعیتِ سفارش، ردیفِ دفتر) سالم می‌مانند.
        async with session.begin_nested():
            session.add(row)
    except IntegrityError:
        return False
    await session.flush()
    return True


async def open_for_owner(session: AsyncSession, owner_id: int) -> list[CommissionReceivable]:
    result = await session.execute(
        select(CommissionReceivable)
        .where(CommissionReceivable.shop_owner_id == owner_id, CommissionReceivable.status == OPEN)
        .order_by(CommissionReceivable.id)
    )
    return list(result.scalars().all())


async def collect_for_owner(session: AsyncSession, owner: ShopOwner, *, now: datetime.datetime | None = None) -> int:
    """بدهی‌هایِ بازِ این فروشگاه را تا جایی که *اعتبارِ قابل‌استفاده* می‌دهد تسویه می‌کند.

    هر ردیف با کلیدِ ایدمپوتنسیِ `commission-receivable:{id}` کسر می‌شود ⇒ اگر همان دورِ
    جمع‌آوری دوباره اجرا شود، کسرِ تکراری ممکن نیست.
    """
    now = now or _utcnow()
    settled = 0
    for row in await open_for_owner(session, owner.id):
        available = wallet_service.usable_credit(owner)
        if available < row.amount_toman:
            break
        # قفلِ ردیفِ فروشگاه: دو جمع‌آوریِ هم‌زمان (جاب + مسیرِ تسویه) یکیِ بدهی را دو بار خرج نکنند
        locked = (
            await session.execute(select(ShopOwner).where(ShopOwner.id == owner.id).with_for_update().execution_options(populate_existing=True))
        ).scalar_one_or_none()
        if locked is None:
            break
        ok = await wallet_service.deduct(
            session,
            locked,
            row.amount_toman,
            WalletTransactionReason.COMMISSION,
            reference=f"receivable:{row.id}",
            idempotency_key=f"commission-receivable:{row.id}",
        )
        if not ok:
            break
        row.status = SETTLED
        row.settled_at = now
        settled += 1
        owner.wallet_balance_toman = locked.wallet_balance_toman
    if settled:
        await session.flush()
        logger.info("طلبِ کمیسیون: %s ردیف برایِ shop_owner_id=%s تسویه شد.", settled, owner.id)
    return settled


async def collect_due(session: AsyncSession, limit: int = COLLECT_LIMIT) -> dict[str, int]:
    """جابِ دوره‌ای: فروشگاه‌دارهایی که بدهیِ باز دارند و حالا اعتبارشان کافی است."""
    now = _utcnow()
    owner_ids = list(
        (
            await session.execute(
                select(CommissionReceivable.shop_owner_id)
                .where(CommissionReceivable.status == OPEN)
                .group_by(CommissionReceivable.shop_owner_id)
                .order_by(func.min(CommissionReceivable.id))
                .limit(limit)
            )
        ).scalars().all()
    )
    settled_rows = 0
    owners_touched = 0
    for owner_id in owner_ids:
        owner = (
            await session.execute(select(ShopOwner).where(ShopOwner.id == owner_id).with_for_update().execution_options(populate_existing=True))
        ).scalar_one_or_none()
        if owner is None:
            continue
        owners_touched += 1
        settled_rows += await collect_for_owner(session, owner, now=now)
    return {"owners": owners_touched, "settled": settled_rows}


async def summary(session: AsyncSession) -> dict[str, int]:
    """جمعِ بدهیِ باز برایِ پنلِ ادمین: {open_count, open_toman, settled_count}."""
    row = (
        await session.execute(
            select(
                func.count().filter(CommissionReceivable.status == OPEN),
                func.coalesce(func.sum(CommissionReceivable.amount_toman).filter(CommissionReceivable.status == OPEN), 0),
                func.count().filter(CommissionReceivable.status == SETTLED),
            )
        )
    ).one()
    return {"open_count": int(row[0] or 0), "open_toman": int(row[1] or 0), "settled_count": int(row[2] or 0)}


async def open_report(session: AsyncSession, limit: int = 10) -> list[dict]:
    """بدهی‌هایِ باز با نامِ صاحبِ فروشگاه، بزرگ‌ترین اول (برایِ گزارشِ پنلِ ادمین)."""
    result = await session.execute(
        select(CommissionReceivable, ShopOwner.first_name, ShopOwner.last_name, ShopOwner.telegram_id)
        .join(ShopOwner, ShopOwner.id == CommissionReceivable.shop_owner_id)
        .where(CommissionReceivable.status == OPEN)
        .order_by(CommissionReceivable.amount_toman.desc(), CommissionReceivable.id)
        .limit(limit)
    )
    rows: list[dict] = []
    for receivable, first_name, last_name, telegram_id in result.all():
        rows.append(
            {
                "id": receivable.id,
                "amount_toman": int(receivable.amount_toman),
                "note": receivable.note,
                "owner_label": " ".join(part for part in (first_name, last_name) if part) or str(telegram_id),
            }
        )
    return rows


async def waive(session: AsyncSession, *, receivable_id: int, note: str) -> bool:
    """بخوداشتنِ یکِ بدهی (تصمیمِ دستیِ ادمین) — حذف نمی‌کند؛ سابقه می‌ماند."""
    result = await session.execute(
        update(CommissionReceivable)
        .where(CommissionReceivable.id == receivable_id, CommissionReceivable.status == OPEN)
        .values(status=WAIVED, note=note[:180])
    )
    await session.flush()
    return int(result.rowcount or 0) == 1
