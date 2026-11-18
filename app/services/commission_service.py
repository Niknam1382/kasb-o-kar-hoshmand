"""کمیسیونِ پلتفرم از سفارش‌هایِ موفقِ فروشگاه‌دارها (PHASE 5D).

قاعده‌ها (طبقِ خواسته، و عمداً باریک):
* فقط درصدی. هیچ مبلغِ ثابت و هیچ ترکیبی ندارد.
* پیش‌فرض خاموش است (`AdminSettings.commission_enabled=False`) ⇒ تا ادمین روشن نکند،
  هیچ پولی جابه‌جا نمی‌شود و هیچ ردیفِ دفتری ساخته نمی‌شود.
* مبنایِ محاسبه = جمعِ ارزشِ سفارش‌هایِ گروه **پس از تخفیف و بدونِ هزینه‌یِ ارسال**
  (`estimated_value_toman`)؛ همان قاعدهٔ طلاییِ پروژه. بخشِ استرداشده مبنیا نیست.
* کمیسیون فقط بعد از **تاییدِ سمتِ سرورِ پرداخت** گرفته می‌شود (گذار به `paid`)؛ نه موقعِ
  ساختِ سفارش، نه موقعِ بازشدنِ صفحهٔ پرداخت، نه با ادعایِ کاربر.
* نرخِ لحظهٔ ورود به جریانِ پرداخت رویِ ردیف‌هایِ گروه snapshot می‌شود؛ تغییرِ بعدیِ ادمین
  سفارشِ باز را عوض نمی‌کند.
* رزرو: قبل از شروعِ جریانِ پرداخت، همان مبلغِ موردانتظار رویِ کیف‌پول قفل می‌شود
  (`ShopOwner.commission_reserved_toman`) تا دو سفارشِ هم‌زمان موجودی را «دو بار» خرج نکنند.
  شکست/لغو/انقضا ⇒ آزادشدن. استرداد ⇒ برگشت با ردیفِ معکوسِ جدید (تاریخچه پاک نمی‌شود).
* ایدمپوتنسی: هر اقدام با کلیدِ یکتا در دفتر و با وضعیتِ رویِ خودِ سفارش قفل می‌شود ⇒
  callbackِ دوباره‌ارسال‌شده یا دابل‌تپ، کمیسیونِ دوم نمی‌سازد.
* دریافت از کیف‌پولِ prepaidِ خودِ فروشگاه‌دار انجام می‌شود (همان کانالی که پلتفرم امروز
  برایِ مصرفِ AI دارد) ⇒ نیاز به درگاهِ جدید نیست و قابلِ ممیزی می‌ماند.
"""
from __future__ import annotations

import dataclasses
import datetime
import logging
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import OrderConsultation, ShopOwner, WalletTransaction, WalletTransactionReason
from app.services import commission_receivable_service, order_state, wallet_service

logger = logging.getLogger(__name__)

MAX_COMMISSION_PERCENT = Decimal("100")
RESERVED = "reserved"
SETTLED = "settled"
RELEASED = "released"
REVERSED = "reversed"


@dataclasses.dataclass(frozen=True)
class CommissionResult:
    """نتیجهٔ یک اقدامِ کمیسیون برایِ caller (پیامِ فارسی را UI می‌سازد، نه این سرویس)."""

    action: str
    amount_toman: int
    changed: bool
    reason: str | None = None  # None | disabled | already | insufficient | missing_rate


def valid_percent(raw) -> Decimal | None:
    """None ⇒ نامعتبر. ۰ تا ۱۰۰، حداکثر دو رقمِ اعشار (۰٫۵٪، ۱٪، ۱٫۵٪ و…)."""
    try:
        value = Decimal(str(raw).replace(",", "."))
    except (ArithmeticError, ValueError, TypeError):
        return None
    if value < 0 or value > MAX_COMMISSION_PERCENT:
        return None
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def rate_of(admin_settings) -> Decimal:
    if admin_settings is None or not admin_settings.commission_enabled:
        return Decimal("0.00")
    percent = valid_percent(admin_settings.commission_percent or 0)
    return percent if percent is not None else Decimal("0.00")


def commission_toman(eligible_amount: int, percent: Decimal) -> int:
    """commission = eligible × percent ÷ ۱۰۰ (گردِ نیم‌به‌بالا، سقفِ خودِ مبلغ)."""
    if eligible_amount <= 0 or percent <= 0:
        return 0
    raw = (Decimal(int(eligible_amount)) * Decimal(percent)) / Decimal(100)
    return max(0, min(int(eligible_amount), int(raw.quantize(Decimal("1"), rounding=ROUND_HALF_UP))))


def eligible_group_amount(rows: list[OrderConsultation]) -> int:
    """مبنایِ کمیسیونِ یک گروه: ارزشِ پس‌ازتخفیفِ ردیف‌هایی که درآمد شمرده می‌شوند.

    ردیف‌هایِ ردشده/لغوشده/منقضی/استرداشده (همان مجموعه‌ای که رزروِ موجودی را آزاد می‌کند)
    مبنیا نیستند ⇒ «بخشِ استرداشده از مبنایِ کمیسیون خارج است» (PHASE 5D).
    """
    total = 0
    for row in rows:
        if order_state.value_of(row.status) in order_state.RELEASES_RESERVATION:
            continue
        total += int(row.estimated_value_toman or 0)
    return max(0, total)


def usable_credit(owner: ShopOwner) -> int:
    """آنچه برایِ شروعِ یک جریانِِ پرداختِ جدید آزاد است (موجودیِ کم‌شده از holdِ کمیسیون).

    تعریفِ اصلی در `wallet_service` است (یک تعریف، دو مصرف‌کننده: پنلِ کیف‌پول و رزروِ کمیسیون)."""
    return wallet_service.usable_credit(owner)


async def _reload_locked(session: AsyncSession, rows: list[OrderConsultation]) -> list[OrderConsultation]:
    """ردیف‌هایِ گروه را *زیرِ قفلِ سطر* دوباره می‌خواند (پ۱۱۷).

    چرا لازم شد: `settle`/`reserve` تا اینجا با ردیف‌هایی کار می‌کردند که caller *پیش ازِ قفلِ
    صاحبِ فروشگاه* خوانده بود. دو تسویهٔ هم‌زمان رویِ یکِ گروه، هر دو `RESERVED` می‌دیدند و
    کمیسیون دو بار از کیف‌پول کم می‌شد (کلیدِ ایدبمپوتنسیِ دفتری هم جلویِ این را نمی‌گرفت، چون
    ردیفِ اول هنوز commit نشده بود). با قفلِ سطر، دومینِ فراخوانی صبر می‌کند و بعد `SETTLED`
    می‌بیند ⇒ «already».
    """
    if not rows:
        return rows
    ids = [int(row.id) for row in rows]
    fresh = list(
        (
            await session.execute(
                select(OrderConsultation).where(OrderConsultation.id.in_(ids)).with_for_update()
            )
        )
        .scalars()
        .all()
    )
    return fresh or rows


async def _lock_owner(session: AsyncSession, owner_id: int) -> ShopOwner | None:
    # populate_existing: همان session ممکن است ShopOwner را زودتر خوانده باشد (مثلاً مسیرِ
    # تاییدِ پرداخت)؛ بدونِ بازخوانی، `+=` رویِ عددِ بیاتِ پایتونی = گم‌شدنِ تغییرِ تراکنشِ دیگر
    # (همان الگویی که `_apply_balance_delta` با UPDATE ستونی ازش فرار می‌کند).
    result = await session.execute(
        select(ShopOwner).where(ShopOwner.id == owner_id).with_for_update().execution_options(populate_existing=True)
    )
    return result.scalar_one_or_none()


async def _info_row(session: AsyncSession, owner_id: int, group_key: str, action: str) -> None:
    """ردیفِ خبریِ دفتر با مبلغِ ۰ (hold رویِ موجودی دست نمی‌زند؛ همسنجی هم نمی‌شکند)."""
    session.add(
        WalletTransaction(
            shop_owner_id=owner_id,
            amount_toman=0,
            reason=WalletTransactionReason.COMMISSION,
            status=action,
            reference=f"commission:{group_key}",
            idempotency_key=f"comm-{action}:{group_key}",
        )
    )
    await session.flush()


async def _stamp_rate(session: AsyncSession, rows: list[OrderConsultation], percent: Decimal) -> None:
    """مُهرِ نرخِ همین لحظه رویِ ردیف‌هایی که هنوز نرخِ ثبت‌شده ندارند (پ۱۱۶)."""
    changed = False
    for row in rows:
        if row.commission_percent is None:
            row.commission_percent = percent
            changed = True
    if changed:
        await session.flush()


def _snapshot(rows: list[OrderConsultation]) -> Decimal | None:
    for row in rows:
        if row.commission_percent is not None:
            return Decimal(str(row.commission_percent))
    return None


async def reserve(
    session: AsyncSession,
    *,
    owner_id: int,
    group_key: str,
    rows: list[OrderConsultation],
    admin_settings,
) -> CommissionResult:
    """قفلِ کمیسیونِ موردانتظارِ یک گروه. اگر کمیسیون خامود است ⇒ بی‌اثر و صفر.

    پ۱۱۶ (یافتهٔ ۹ِ بازرسی): هر جا نرخِ معتبری محاسبه شد ولی رزرو انجام نشد (موجودیِ ناکافی)
    همان نرخ رویِ ردیف‌ها مُهر می‌شود؛ بدونِ این مهر `settle` به نرخِ زنده برمی‌گشت و تغییرِ
    نرخِ ادمین سفارشِ باز را دوباره قیمت می‌زد.
    """
    percent = rate_of(admin_settings)
    if percent <= 0:
        # کمیسیون خامود است ⇒ هیچ پولی حرکت نمی‌کند و hold ساخته نمی‌شود؛ ولی نرخِ همین لحظه
        # (صفر) مُهر می‌شود تا اگر ادمین پیش ازِ تسویه نرخ را روشن کرد، سفارشِ باز دوباته قیمت نخورد.
        await _stamp_rate(session, rows, percent)
        return CommissionResult("reserve", 0, False, "disabled")
    expected = commission_toman(eligible_group_amount(rows), percent)
    if expected <= 0:
        return CommissionResult("reserve", 0, False, "missing_rate")

    owner = await _lock_owner(session, owner_id)
    if owner is None:
        await _stamp_rate(session, rows, percent)
        return CommissionResult("reserve", 0, False, "insufficient")

    rows = await _reload_locked(session, rows)  # پ۱۱۷: دو رزروی هم‌زمان رویِ یکِ گروه
    already = sum(int(row.commission_toman or 0) for row in rows if row.commission_status == RESERVED)
    if already or all(row.commission_status in (SETTLED, REVERSED) for row in rows):
        return CommissionResult("reserve", already, False, "already")

    if usable_credit(owner) < expected:
        await _stamp_rate(session, rows, percent)
        return CommissionResult("reserve", expected, False, "insufficient")

    owner.commission_reserved_toman = int(owner.commission_reserved_toman or 0) + expected
    await _info_row(session, owner_id, group_key, RESERVED)
    for row in rows:
        row.commission_percent = percent
        row.commission_toman = expected if row is rows[0] else 0  # یک رقمِ گروهی، رویِ ردیفِ اول
        row.commission_status = RESERVED
    await session.flush()
    logger.info("رزروِ کمیسیون: گروه %s، %s تومان، نرخ %s٪", group_key, expected, percent)
    return CommissionResult("reserve", expected, True)


async def settle(
    session: AsyncSession,
    *,
    owner_id: int,
    group_key: str,
    rows: list[OrderConsultation],
    admin_settings,
    now: datetime.datetime | None = None,
) -> CommissionResult:
    """دریافتِ کمیسیون بعد از **تاییدِ پرداخت**. فقط کمیسیونِ رزروشده؛ نرخِ snapshot شده."""
    percent = _snapshot(rows)
    if percent is None:
        # گروه هرگز واردِ جریانِ پرداخت با رزرو نشده (مثلاً سفارشِ قدیمی یا مسیرِ دستیِ بدونِ رزرو)
        if rate_of(admin_settings) <= 0:
            return CommissionResult("settle", 0, False, "disabled")
        percent = rate_of(admin_settings)
    if percent <= 0:
        return CommissionResult("settle", 0, False, "disabled")

    owner = await _lock_owner(session, owner_id)
    if owner is None:
        return CommissionResult("settle", 0, False, "insufficient")

    # پ۱۱۷: قفلِ سطرهایِ گروه، بعدِ قفلِ صاحبِ فروشگاه (همان ترتیب: Owner → Order rows → Charges)
    rows = await _reload_locked(session, rows)
    percent = _snapshot(rows) or percent
    reserved_total = sum(int(row.commission_toman or 0) for row in rows if row.commission_status == RESERVED)
    if reserved_total == 0:
        if all(row.commission_status in (SETTLED, REVERSED) for row in rows):
            return CommissionResult("settle", 0, False, "already")
        # رزروی در کار نبوده ⇒ همین حالا با نرخِ snapshot محاسبه و دریافت می‌شود (سقفِ موجودی رعایت می‌شود)
        reserved_total = commission_toman(eligible_group_amount(rows), percent)
        if reserved_total <= 0:
            return CommissionResult("settle", 0, False, "missing_rate")
    if any(row.commission_status == SETTLED for row in rows):
        return CommissionResult("settle", 0, False, "already")

    actual = commission_toman(eligible_group_amount(rows), percent)
    hold = min(int(owner.commission_reserved_toman or 0), reserved_total)

    if actual > 0:
        ok = await wallet_service.deduct(
            session,
            owner,
            actual,
            WalletTransactionReason.COMMISSION,
            reference=f"commission:{group_key}",
            order_id=rows[0].id if rows else None,
            idempotency_key=f"comm-settle:{group_key}",
        )
        if not ok:
            # موجودیِ فروشگاه‌دار در لحظهٔ تسویه تمام شده. قبلاً اینجا `return` می‌شد و hold
            # برایِ همیشه رویِ کیف‌پول قفل می‌ماند (پولِ مسکوت، بدونِ هیچ ردیفِ دفتری).
            # درستِ همین: hold آزاد می‌شود، ردیف‌ها released می‌شوند و هیچ پولی گرفته نمی‌شود ⇒
            # دفتر و کشِ موجودی هم‌راستا می‌مانند.
            # P21-C (F4): مبلغِ گرفته‌نشده حالا «بدهیِ باز» ثبت می‌شود تا درآمدِ از دست رفته
            # عددِ داشته باشد و با شارژِ بعدیِ فروشگاه خودکار جمع شود (سابقه پاک نمی‌شود).
            logger.warning(
                "کمیسیونِ گروه %s از کیف‌پولِ %s کم نشد (موجودیِ ناکافی در لحظهٔ تسویه)؛ رزرو آزاد شد.", group_key, owner_id
            )
            await release(session, owner_id=owner_id, group_key=group_key, rows=rows)
            await commission_receivable_service.record(
                session, owner_id=owner_id, group_key=group_key, amount_toman=actual, note="تسویهٔ ناموفق — موجودیِ ناکافی"
            )
            return CommissionResult("settle", actual, False, "insufficient")

    owner.commission_reserved_toman = max(0, int(owner.commission_reserved_toman or 0) - hold)
    for row in rows:
        row.commission_percent = percent
        row.commission_status = SETTLED
    if rows:
        rows[0].commission_toman = actual
    await session.flush()
    logger.info("تسویهٔ کمیسیون: گروه %s، %s تومان (نرخ %s٪)", group_key, actual, percent)
    return CommissionResult("settle", actual, True)


async def release(session: AsyncSession, *, owner_id: int, group_key: str, rows: list[OrderConsultation]) -> CommissionResult:
    """آزادکردنِ hold در مسیرهایِ رد/لغو/انقضا. اگر تسویه شده باشد، کاری نمی‌کند (برگشت با reverse)."""
    hold = sum(int(row.commission_toman or 0) for row in rows if row.commission_status == RESERVED)
    if hold <= 0:
        return CommissionResult("release", 0, False, "already")
    owner = await _lock_owner(session, owner_id)
    if owner is None:
        return CommissionResult("release", hold, False, "insufficient")
    owner.commission_reserved_toman = max(0, int(owner.commission_reserved_toman or 0) - hold)
    await _info_row(session, owner_id, group_key, RELEASED)
    for row in rows:
        if row.commission_status == RESERVED:
            row.commission_status = RELEASED
            row.commission_toman = 0
    await session.flush()
    logger.info("آزادسازیِ رزروِ کمیسیون: گروه %s، %s تومان", group_key, hold)
    return CommissionResult("release", hold, True)


async def reverse(session: AsyncSession, *, owner_id: int, group_key: str, rows: list[OrderConsultation]) -> CommissionResult:
    """استردادِ کمیسیونِ گرفته‌شده با ردیفِ معکوسِ جدید (اعتبار برمی‌گردد، تاریخچه پاک نمی‌شود)."""
    settled = next((row for row in rows if row.commission_status == SETTLED), None)
    if settled is None:
        return CommissionResult("reverse", 0, False, "already")
    amount = int(settled.commission_toman or 0)
    if amount <= 0:
        return CommissionResult("reverse", 0, False, "already")
    owner = await _lock_owner(session, owner_id)
    if owner is None:
        return CommissionResult("reverse", amount, False, "insufficient")

    # برگشتِ پول باید در بسته‌ها هم دیده شود، وگرنه «موجودیِ کش‌شده ≠ مجموعِ بسته‌ها» می‌شود
    # و همسنجیِ PHASE 5E اختلاف می‌دهد ⇒ مثلِ هر برگشتِ دیگر، یک بستهٔ اعتبارِ تازه.
    await wallet_service.add_charge(
        session,
        owner,
        amount,
        reason=WalletTransactionReason.COMMISSION,
        reference=f"commission-refund:{group_key}",
    )
    for row in rows:
        if row.commission_status == SETTLED:
            row.commission_status = REVERSED
    await session.flush()
    logger.info("استردادِ کمیسیونِ گروه %s: %s تومان برگشت داده شد", group_key, amount)
    return CommissionResult("reverse", amount, True)
