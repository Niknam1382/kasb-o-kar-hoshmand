"""
سرویسِ کیف‌پول — جایگزینِ سیستمِ اشتراکِ ثابتِ ماهانه.

منطقِ اصلی:
- هر «شارژ» (WalletCharge) یه بسته‌ی مستقله با تاریخِ انقضای خودش (پیش‌فرض ۱۲
  ماه، در پنلِ ادمین قابل‌تغییر).
- مصرف به‌صورتِ FIFO از قدیمی‌ترین شارژِ منقضی‌نشده کم می‌شه؛ اگه یه مصرف بزرگ‌تر
  از یه بسته باشه، بینِ چند بسته پخش می‌شه.
- انقضا به‌صورتِ روزانه (نه لحظه‌ای) چک می‌شه، توسطِ expire_stale_charges که از
  اسکجولر صدا زده می‌شه — همینطور یادآوری‌های ۳۰/۷/۱ روزه.
- wallet_balance_toman روی ShopOwner یه مقدارِ کش‌شده‌ست (برای اینکه چک‌کردنِ
  موجودی، که توی مسیرِ داغِ هر پیامِ مشتری اتفاق می‌افته، نیازی به SUM زدن روی
  چندین ردیف نداشته باشه)؛ همیشه باید با مجموعِ remaining_toman روی
  WalletCharge های منقضی‌نشده هم‌خوان بمونه.
"""
from __future__ import annotations

import dataclasses
import datetime
import logging

from sqlalchemy import func, or_, select, update
from sqlalchemy.event import listens_for
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import set_committed_value

from app.database.models import ShopOwner, WalletCharge, WalletTransaction, WalletTransactionReason
from app import observability
from app.services import time_freeze_service
from app.services.admin_settings_service import get_admin_settings
from app.utils.dates import add_validity_months

logger = logging.getLogger(__name__)


# =============================================================================
# PHASE 5E — دفترِ فقط‌افزودنی
# ردیفِ مالیِ تاریخ‌مصرف‌شده هرگز ویرایش/حذف نمی‌شود؛ اصلاحِ اشتباه با یک ردیفِ
# معکوسِ جدید انجام می‌شود. این دو نگهبانِ سطحِ ORM، هر مسیرِ کد (از جمله پنلِ ادمین)
# را از بازنویسیِ تاریخچه منع می‌کنند.
# =============================================================================
class LedgerIsAppendOnlyError(RuntimeError):
    """تلاش برای ویرایش یا حذفِ ردیفِ دفترِ کیف‌پول — همیشه یک باگ است، نه یک قابلیت."""


@listens_for(WalletTransaction, "before_update", propagate=True)
def _block_ledger_update(mapper, connection, target):  # pragma: no cover - نگهبان
    raise LedgerIsAppendOnlyError(f"ردیفِ دفترِ کیف‌پول (id={target.id}) قابلِ ویرایش نیست؛ اصلاح با ردیفِ معکوس.")


@listens_for(WalletTransaction, "before_delete", propagate=True)
def _block_ledger_delete(mapper, connection, target):  # pragma: no cover - نگهبان
    raise LedgerIsAppendOnlyError(f"ردیفِ دفترِ کیف‌پول (id={target.id}) قابلِ حذف نیست؛ تاریخچه پاک نمی‌شود.")


async def _apply_balance_delta(session: AsyncSession, owner: ShopOwner, delta_toman: int) -> None:
    """
    wallet_balance_toman رو با یه UPDATEِ اتمیکِ سطحِ دیتابیس تغییر می‌ده
    (SET wallet_balance_toman = wallet_balance_toman + delta)، نه با
    خوندن‌وتغییردادنِ مقدارِ پایتونی (owner.wallet_balance_toman += delta)
    که در برابرِ lost update آسیب‌پذیره: چون کسرِ هزینه‌ی پاسخِ چت و کسرِ
    هزینه‌ی تشخیصِ سفارش برای هر پیامِ مشتری در دو تسکِ async مجزا (و در
    نتیجه دو session/تراکنشِ جدا) هم‌زمان اجرا می‌شن، دو نمونه‌ی جداگانه از
    owner می‌تونن هم‌زمان از یه مقدارِ قدیمی شروع کنن و یکی، تغییرِ اون
    یکی رو overwrite کنه. UPDATE با expressionِ ستونی، برخلافِ این، همیشه
    رویِ مقدارِ *فعلیِ* ردیف در دیتابیس عمل می‌کنه، نه رویِ یه کپیِ پایتونیِ
    احتمالاً stale — پس امنه حتی وقتی چند تراکنشِ هم‌زمان روی همین owner کار
    می‌کنن. بعدِ UPDATE، مقدارِ واقعیِ جدید رو از RETURNING می‌گیریم و روی
    خودِ owner هم می‌ذاریم تا کدِ بعدیِ همین تابع/caller (مثلاً چکِ آستانه‌ی
    هشدارِ موجودیِ کم) مقدارِ درست رو ببینه، نه مقدارِ قبل‌ازِ-این-تغییر رو.
    """
    result = await session.execute(
        update(ShopOwner)
        .where(ShopOwner.id == owner.id)
        # PHASE 7: موجودیِ کش‌شده هرگز منفی نمی‌شود. معمولاً این هیچ‌وقت رخ نمی‌دهد
        # (چون deduct از رویِ خودِ بسته‌ها کم می‌کند)، ولی اگر کشیده و بسته‌ها به هر
        # دلیلی از هم جدا افتاده باشند، «greatest(۰)» جلویِ بدهکارشدن را می‌گیرد و
        # خطا لاگ می‌شود؛ همان روز همسنجیِ PHASE 5E اختلاف را به ادمین می‌گوید.
        .values(wallet_balance_toman=func.greatest(0, ShopOwner.wallet_balance_toman + delta_toman))
        .returning(ShopOwner.wallet_balance_toman)
    )
    # P31: عددِ بازگشتی با `set_committed_value` نوشته می‌شود، نه با انتسابِ معمولی.
    # انتسابِ معمولی ستون را «تغییرکرده» علامت می‌زند و flushِ پایِ همین تراکنش یکِ
    # UPDATEِ دوم با همان عدد رویِ همان سطر می‌فرستد (۱۲ statement به‌ازایِ هر پیامِ مشتری
    # که یکی‌اش دقیقاً همین بود). مقدارِ درِ حافظه و درِ دیتابیس یکی است، فقط نویسهٔ
    # «کثیف» حذف می‌شود ⇒ رفتارِ مالی هیچ تغییری نمی‌کند.
    set_committed_value(owner, "wallet_balance_toman", result.scalar_one())


async def add_charge(
    session: AsyncSession,
    owner: ShopOwner,
    amount_toman: int,
    reason: WalletTransactionReason = WalletTransactionReason.TOPUP,
    payment_id: int | None = None,
    validity_months: int | None = None,
    reference: str | None = None,
    idempotency_key: str | None = None,
    merge_into_latest: bool = False,
) -> WalletCharge:
    """یه بسته‌ی شارژِ جدید می‌سازه (با انقضای مستقل) و موجودیِ کش‌شده رو آپدیت می‌کنه.

    `merge_into_latest=True` (P42 · موردِ ۵): اعتبارِ *هدیه* بسته‌ی تازه نمی‌سازد؛ رویِ شارژی
    می‌نشیند که دیرترین انقضا را دارد، تا هدیه اول از همه خرج نشود. اگر هنوز هیچ شارژِ زنده‌ای
    نباشد، همان بسته‌ی تازه ساخته می‌شود.
    """
    if amount_toman <= 0:
        raise ValueError("مبلغِ شارژ باید مثبت باشه")

    if merge_into_latest:
        latest = await latest_live_charge(session, owner)
        if latest is not None:
            latest.remaining_toman = int(latest.remaining_toman or 0) + amount_toman
            await session.flush()
            await _apply_balance_delta(session, owner, amount_toman)
            owner.wallet_empty_notified_at = None
            owner.wallet_low_balance_notified_at = None
            session.add(
                WalletTransaction(
                    shop_owner_id=owner.id,
                    wallet_charge_id=latest.id,
                    payment_id=payment_id,
                    amount_toman=amount_toman,
                    reason=reason,
                    reference=reference,
                    idempotency_key=_charge_idempotency_key(owner.id, payment_id, reference, idempotency_key),
                )
            )
            await session.flush()
            return latest

    admin_settings = await get_admin_settings(session)
    if validity_months is None:
        validity_months = admin_settings.wallet_topup_validity_months

    now = datetime.datetime.now(datetime.timezone.utc)
    # P22: «یکِ ماه» یعنی یکِ ماهِ تقویمی، نه ۳۰ روز. اشتراک از اول با relativedelta حساب
    # می‌شد و کیف‌پول ۳۰×N؛ یعنی «۱ ماه»ِ کیف‌پول در ماه‌هایِ ۳۱ روزه دو روز زودتر
    # می‌رسید و پیامِ انقضا با اشتراکِ همان فروشگاه نمی‌خواند. روزِ سرِ ماه هم clamp می‌شود
    # (۳۱ فروردین + ۱ ماه ⇒ ۲۹/۳۰ ماه بعد، نه خطا).
    expires_at = add_validity_months(now, validity_months, getattr(admin_settings, "month_length_days", 0) or 0)

    charge = WalletCharge(
        shop_owner_id=owner.id,
        payment_id=payment_id,
        amount_toman=amount_toman,
        remaining_toman=amount_toman,
        expires_at=expires_at,
    )
    session.add(charge)
    await session.flush()

    await _apply_balance_delta(session, owner, amount_toman)
    owner.wallet_empty_notified_at = None
    owner.wallet_low_balance_notified_at = None
    session.add(
        WalletTransaction(
            shop_owner_id=owner.id,
            wallet_charge_id=charge.id,
            payment_id=payment_id,
            amount_toman=amount_toman,
            reason=reason,
            reference=reference,
            # قیدِ یکتای `idempotency_key` آخرین سدِ «شارژِ دوباره» است. برایِ شارژِ کیف‌پول
            # کلید از خودِ ردیفِ پرداخت می‌آید (نه فقط reference که some مسیرها آن را نمی‌دهند)،
            # پس حتی اگر محافظِ قفلِ سطری در payment_service روزی برداشته شود، دو وب‌هوکِ
            # تکراریِ همان پرداختِ واحدِ ثانیه نمی‌توانند دو بار اعتبار بسازند.
            idempotency_key=_charge_idempotency_key(owner.id, payment_id, reference, idempotency_key),
        )
    )
    await session.flush()
    return charge


def _charge_idempotency_key(owner_id: int, payment_id: int | None, reference: str | None, explicit: str | None) -> str | None:
    if explicit:
        return explicit
    if payment_id is not None:
        return f"charge:payment:{payment_id}:owner:{owner_id}"
    if reference is not None:
        return f"charge:{reference}:owner:{owner_id}"
    return None


async def deduct(
    session: AsyncSession,
    owner: ShopOwner,
    amount_toman: int,
    reason: WalletTransactionReason,
    reference: str | None = None,
    order_id: int | None = None,
    idempotency_key: str | None = None,
    customer_id: int | None = None,
) -> bool:
    """
    از قدیمی‌ترین شارژِ منقضی‌نشده (FIFO) کم می‌کنه، حتی اگه بینِ چند بسته پخش
    بشه. اگه موجودی کافی نبود، هیچ تغییری اعمال نمی‌شه و False برمی‌گرده —
    caller باید به‌جای پاسخِ عادی، پیامِ کمبودِ اعتبار به فروشگاه‌دار نشون بده
    (نه به مشتری).

    `customer_id` (پ۵۵) فقط رویِ همان ردیفِ در حالِ نوشتن ست می‌شود؛ جملهٔ اضافه‌ای
    نمی‌زند. اگر قابلِ نسبت‌دادن نباشد (کامنتِ اینستاگرام، خلاصهٔ CRM، دستیارِ مدیریتی
    یا ردیف‌هایِ قدیمی) NULL می‌ماند و رتبه‌بندیِ مصرفِ کاربران آن را نمی‌شمارد.
    """
    if amount_toman <= 0:
        return True

    result = await session.execute(
        select(WalletCharge)
        .where(WalletCharge.shop_owner_id == owner.id, WalletCharge.is_expired.is_(False), WalletCharge.remaining_toman > 0)
        .order_by(WalletCharge.expires_at.asc())
        .with_for_update()
    )
    charges = list(result.scalars().all())

    # مهم: قبل از هرگونه mutation چک می‌کنیم که مجموعِ بسته‌ها اصلاً کافیه یا
    # نه. قبلاً این چک بعدِ حلقه بود (بعدِ اینکه charge.remaining_toman ی
    # بسته‌هایی که تا اون لحظه پردازش شده بودن از قبل کم شده بود و
    # WalletTransactionِ متناظرشون هم session.add شده بود) — یعنی حتی
    # وقتی نهایتاً False برمی‌گردوند، اون کاهش‌های نصفه‌کاره (چون هیچ
    # commit/rollbackِ صریحی هم نبود) با commitِ نهاییِ همون session
    # (مثلاً توسطِ DbSessionMiddleware در پایانِ آپدیت) واقعاً پایدار می‌شدن
    # — دقیقاً برخلافِ چیزی که این تابع ادعا می‌کرد («هیچ تغییری اعمال
    # نمی‌شه»). چون .with_for_update() از همین اول قفل گرفته، هیچ تراکنشِ
    # هم‌زمانِ دیگه‌ای نمی‌تونه بینِ این چک و حلقه‌ی پایین چیزی رو عوض کنه.
    if sum(charge.remaining_toman for charge in charges) < amount_toman:
        observability.count("wallet.deduct_denied")
        logger.warning("کسرِ %s تومنی برای shop_owner_id=%s رد شد — موجودی کافی نیست.", amount_toman, owner.id)
        return False

    remaining_to_deduct = amount_toman
    for charge in charges:
        if remaining_to_deduct <= 0:
            break
        take = min(charge.remaining_toman, remaining_to_deduct)
        charge.remaining_toman -= take
        remaining_to_deduct -= take
        session.add(
            WalletTransaction(
                shop_owner_id=owner.id,
                wallet_charge_id=charge.id,
                order_id=order_id,
                customer_id=customer_id,
                amount_toman=-take,
                reason=reason,
                reference=reference,
                # کلیدِ ایدپوتنسی به‌ازایِ (رویداد، بسته) است: یک مصرفِ بزرگ ممکن است بینِ
                # چند بسته پخش شود و قیدِ یکتا نباید جلویِ خودِ آن را بگیرد، ولی
                # اجرایِ دوبارهٔ همان رویداد رویِ همان بسته را می‌گیرد.
                idempotency_key=None if idempotency_key is None else f"{idempotency_key}:lot:{charge.id}",
            )
        )

    if remaining_to_deduct > 0:
        # به‌طورِ نظری دیگه نباید به اینجا برسیم (چونِ چکِ بالا از قبل مجموع
        # رو تایید کرده و ردیف‌ها هم قفل‌ان) — نگهش داشتیم فقط به‌عنوانِ یه
        # محافظِ نهایی در برابرِ ناسازگاریِ داده‌ای که واقعاً نباید پیش بیاد.
        logger.error(
            "ناسازگاریِ غیرمنتظره‌ی موجودیِ کیف‌پول برای shop_owner_id=%s: بعدِ تاییدِ کافی‌بودن، بازم %s تومن کم اومد.",
            owner.id,
            remaining_to_deduct,
        )
        return False

    await _apply_balance_delta(session, owner, -amount_toman)
    observability.count("wallet.deduct", amount_toman)
    await session.flush()
    return True


def compute_cost_per_1k_tokens_from_formula(admin_settings) -> int:
    """
    (هزینه‌ی خامِ AI به ازای ۱۰۰۰ توکن، به دلار) × (نرخِ دلار به تومان) ×
    (ضریبِ سود که هزینه‌ی سرور رو هم پوشش می‌ده) — نتیجه به تومان، حداقل ۱.
    این فقط محاسبه می‌کنه؛ ذخیره‌کردنِ نتیجه توی wallet_cost_per_1k_tokens_toman
    برعهده‌ی caller ـه (دکمه‌ی «محاسبه‌ی خودکار» در پنلِ ادمین).
    """
    usd_per_1k = admin_settings.ai_cost_usd_per_1m_tokens / 1000
    raw_toman = usd_per_1k * admin_settings.usd_to_toman_rate
    return max(1, round(raw_toman * admin_settings.wallet_markup_multiplier))


async def get_balance(owner: ShopOwner) -> int:
    return owner.wallet_balance_toman


async def get_recent_transactions(session: AsyncSession, owner_id: int, limit: int = 15) -> list[WalletTransaction]:
    """
    آخرین تراکنش‌های کیف‌پول رو برمی‌گردونه (جدیدترین اول) — برای نمایشِ
    تاریخچه به خودِ فروشگاه‌دار، تا فقط موجودیِ فعلی رو نبینه بلکه بدونه
    هر تغییری به چه دلیلی بوده.
    """
    result = await session.execute(
        select(WalletTransaction)
        .where(WalletTransaction.shop_owner_id == owner_id)
        .order_by(WalletTransaction.id.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


WALLET_HISTORY_PAGE_SIZE = 15


async def get_owner_history_page(
    session: AsyncSession,
    owner_id: int,
    *,
    direction: str = "older",
    cursor_id: int | None = None,
) -> tuple[list[WalletTransaction], bool, bool]:
    if direction not in {"older", "newer"}:
        raise ValueError("جهتِ تاریخچه معتبر نیست")
    if cursor_id is not None and (type(cursor_id) is not int or not 1 <= cursor_id <= 2_147_483_647):
        raise ValueError("نشانگرِ تاریخچه معتبر نیست")
    query = select(WalletTransaction).where(WalletTransaction.shop_owner_id == owner_id)
    newer = cursor_id is not None and direction == "newer"
    if cursor_id is not None:
        query = query.where(WalletTransaction.id > cursor_id if newer else WalletTransaction.id < cursor_id)
    query = query.order_by(WalletTransaction.id.asc() if newer else WalletTransaction.id.desc())
    transactions = list((await session.execute(query.limit(WALLET_HISTORY_PAGE_SIZE))).scalars().all())
    if not transactions:
        return [], False, False
    if newer:
        # Ascending LIMIT selects the nearest newer page, even after concurrent inserts.
        transactions.reverse()
    has_newer, has_older = (await session.execute(select(
        select(WalletTransaction.id).where(
            WalletTransaction.shop_owner_id == owner_id, WalletTransaction.id > transactions[0].id,
        ).exists(),
        select(WalletTransaction.id).where(
            WalletTransaction.shop_owner_id == owner_id, WalletTransaction.id < transactions[-1].id,
        ).exists(),
    ))).one()
    return transactions, bool(has_newer), bool(has_older)


async def reconcile_balances(session: AsyncSession, limit: int = 100) -> list[dict]:
    """
    PHASE 5E — همسنجیِ ادعایِ کلیدیِ کیف‌پول: «مجموعِ ردیف‌هایِ دفتر باید برابرِ
    موجودیِ کش‌شده باشد». اختلاف را به‌ازایِ هر فروشگاه‌دار برمی‌گرداند (خالی ⇒ سالم).

    دو طرفِ مقایسه در SQL جمع زده می‌شود (نه کشیدنِ ردیف‌ها در پایتون) تا با رشدِ دفتر
    هم ارزان بماند؛ فهرستِ خروجی حداکثر `limit` اختلاف است تا پنلِ ادمین قابلِ استفاده بماند.
    """
    ledger_sum = (
        select(WalletTransaction.shop_owner_id, func.coalesce(func.sum(WalletTransaction.amount_toman), 0).label("ledger_total"))
        .group_by(WalletTransaction.shop_owner_id)
        .subquery()
    )
    charge_sum = (
        select(WalletCharge.shop_owner_id, func.coalesce(func.sum(WalletCharge.remaining_toman), 0).label("lots_total"))
        .where(WalletCharge.is_expired.is_(False), WalletCharge.remaining_toman > 0)
        .group_by(WalletCharge.shop_owner_id)
        .subquery()
    )
    result = await session.execute(
        select(
            ShopOwner.id,
            ShopOwner.telegram_id,
            ShopOwner.wallet_balance_toman,
            ledger_sum.c.ledger_total,
            charge_sum.c.lots_total,
        )
        .outerjoin(ledger_sum, ledger_sum.c.shop_owner_id == ShopOwner.id)
        .outerjoin(charge_sum, charge_sum.c.shop_owner_id == ShopOwner.id)
        .where(
            or_(
                ShopOwner.wallet_balance_toman != func.coalesce(ledger_sum.c.ledger_total, 0),
                ShopOwner.wallet_balance_toman != func.coalesce(charge_sum.c.lots_total, 0),
            )
        )
        .order_by(ShopOwner.id)
        .limit(limit)
    )
    gaps: list[dict] = []
    for owner_id, telegram_id, cached, ledger_total, lots_total in result.all():
        ledger_total = int(ledger_total or 0)
        lots_total = int(lots_total or 0)
        gaps.append(
            {
                "owner_id": owner_id,
                "telegram_id": telegram_id,
                "cached_toman": int(cached or 0),
                "ledger_toman": ledger_total,
                "lots_toman": lots_total,
                "ledger_delta_toman": int(cached or 0) - ledger_total,
                "lots_delta_toman": int(cached or 0) - lots_total,
            }
        )
    return gaps


async def has_ever_had_wallet_activity(session: AsyncSession, owner: ShopOwner) -> bool:
    result = await session.execute(select(WalletCharge.id).where(WalletCharge.shop_owner_id == owner.id).limit(1))
    return result.scalar_one_or_none() is not None


EXPIRING_SOON_DAYS = 30


def usable_credit(owner: ShopOwner) -> int:
    """آنچه برایِ شروعِ یک جریانِ پرداختِ تازه آزاد است: موجودی، کمِ holdِ کمیسیونِ سفارش‌هایِ باز.

    مالِ این سرویس است (نه commission_service) چون commission_service به کیف‌پول وابسته است و
    این‌طور حلقهٔ import ساخته نمی‌شود. این همان عددی است که فروشگاه‌دار باید در پنل ببیند:
    موجودیِ خام، قابلِ خرجِ کامل نیست.
    """
    return int(owner.wallet_balance_toman or 0) - int(owner.commission_reserved_toman or 0)


@dataclasses.dataclass(frozen=True)
class ExpiryLot:
    """یک *شارژ* از کیف‌پول: باقی‌مانده و زمانِ انقضایِ همان شارژ."""

    remaining_toman: int
    expires_at: datetime.datetime
    days_left: int


async def expiry_lots(session: AsyncSession, owner: ShopOwner) -> list[ExpiryLot]:
    """شارژهایِ زنده، یکی‌به‌یکی و به همان ترتیبی که مصرف می‌شوند (FIFO).

    P42 · موردِ ۲۱: دو شارژِ خریداری‌شده در یکِ لحظه باید دو خطِ جدا بمانند — فروشگاه‌دار رویِ
    «کدامِ خریدم کِی می‌رود» حساب باز می‌کند، نه رویِ جمعِ آن‌ها. گروه‌کردنِ «به تفکیکِ روز»
    (P40) کوئری را کوتاه می‌کرد ولی همان نمایشِ درست را می‌زد؛ حالا همان یکِ SELECT بدونِ
    GROUP BY است و تعدادِ statement کم یا زیاد نشده. شارژِ *منقضی‌شده* (expires_at <= now) هم
    دیگر در فهرست نمی‌آید، چون در همان لحظه با `expire_stale_charges` صفر می‌شود.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    rows = (
        await session.execute(
            select(WalletCharge.remaining_toman, WalletCharge.expires_at)
            .where(
                WalletCharge.shop_owner_id == owner.id,
                WalletCharge.is_expired.is_(False),
                WalletCharge.remaining_toman > 0,
                WalletCharge.expires_at > now,
            )
            .order_by(WalletCharge.expires_at.asc())
        )
    ).all()
    lots: list[ExpiryLot] = []
    for remaining, expires_at in rows:
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=datetime.timezone.utc)
        days_left = max(0, int(-(-(expires_at - now).total_seconds() // 86400)))
        lots.append(ExpiryLot(remaining_toman=int(remaining or 0), expires_at=expires_at, days_left=days_left))
    return lots


async def extend_live_charges(session: AsyncSession, owner: ShopOwner, days: int) -> int:
    """P42 · موردِ ۵: «تمدیدِ روز» روی *همهٔ* بسته‌هایِ فعال می‌نشیند، نه فقط یکی.

    مثالِ مالکِ محصول: دو شارژ با ۲۵ و ۱۵ روزِ باقی‌مانده + تمدیدِ ۵ روزه ⇒ ۳۰ و ۲۰. ردیف‌ها
    قفل می‌شوند (`FOR UPDATE`) تا دو اجرایِ هم‌زمانِ همان دسته، یک شارژ را دو بار جابه‌جا نکند.
    """
    if days <= 0:
        return 0
    rows = (
        await session.execute(
            select(WalletCharge)
            .where(
                WalletCharge.shop_owner_id == owner.id,
                WalletCharge.is_expired.is_(False),
                WalletCharge.remaining_toman > 0,
            )
            .order_by(WalletCharge.expires_at.asc())
            .with_for_update()
        )
    ).scalars().all()
    for charge in rows:
        charge.expires_at = charge.expires_at + datetime.timedelta(days=days)
    if rows:
        await session.flush()
    return len(rows)


async def latest_live_charge(session: AsyncSession, owner: ShopOwner) -> WalletCharge | None:
    """دیرترین شارژِ زنده (بیشترین تاریخِ انقضا)، با قفلِ سطری."""
    return (
        await session.execute(
            select(WalletCharge)
            .where(
                WalletCharge.shop_owner_id == owner.id,
                WalletCharge.is_expired.is_(False),
                WalletCharge.remaining_toman > 0,
            )
            .order_by(WalletCharge.expires_at.desc())
            .limit(1)
            .with_for_update()
        )
    ).scalar_one_or_none()


async def credit_summary(session: AsyncSession, owner: ShopOwner) -> tuple[int, list[ExpiryLot]]:
    """(قابل‌استفاده، شارژهایِ زنده به ترتیبِ انقضا).

    «قابل‌استفاده» = موجودیِ کم‌شده از holdِ کمیسیونِ سفارش‌هایِ باز: امروز فروشگاه‌دار عددی
    می‌بیند که نمی‌تواند کاملِ آن را برایِ شروعِ یک جریانِ پرداختِ تازه استفاده کند، و انقضا
    هم دیگر یک عددِ تکیِ گمراه‌کننده نیست (P39 · باگِ ۴).
    """
    return usable_credit(owner), await expiry_lots(session, owner)


async def expire_stale_charges(session: AsyncSession) -> int:
    """
    کارِ روزانه: بسته‌هایی که تاریخِ انقضاشون گذشته رو می‌بنده و از موجودیِ
    کش‌شده کم می‌کنه. عمداً روزانه‌ست (نه لحظه‌ای) تا وسطِ یه مکالمه/مصرفِ
    درحال‌انجام چیزی قطع نشه.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    all_frozen, frozen_ids = await time_freeze_service.frozen_filter(session)  # W5 · K3: توقفِ زمان
    if all_frozen:
        return 0
    stale_query = select(WalletCharge).where(
        WalletCharge.is_expired.is_(False), WalletCharge.expires_at <= now, WalletCharge.remaining_toman > 0
    )
    if frozen_ids:
        stale_query = stale_query.where(WalletCharge.shop_owner_id.notin_(frozen_ids))
    result = await session.execute(stale_query)
    stale_charges = list(result.scalars().all())

    owner_ids = {c.shop_owner_id for c in stale_charges}
    owners_by_id: dict[int, ShopOwner] = {}
    if owner_ids:
        owners_result = await session.execute(select(ShopOwner).where(ShopOwner.id.in_(owner_ids)))
        owners_by_id = {o.id: o for o in owners_result.scalars().all()}

    count = 0
    for charge in stale_charges:
        owner = owners_by_id.get(charge.shop_owner_id)
        if owner is None:
            continue
        expired_amount = charge.remaining_toman
        await session.execute(
            update(ShopOwner)
            .where(ShopOwner.id == owner.id)
            .values(wallet_balance_toman=func.greatest(0, ShopOwner.wallet_balance_toman - expired_amount))
        )
        session.add(
            WalletTransaction(
                shop_owner_id=owner.id,
                wallet_charge_id=charge.id,
                amount_toman=-expired_amount,
                reason=WalletTransactionReason.EXPIRY,
                idempotency_key=f"expiry:{charge.id}",
            )
        )
        charge.remaining_toman = 0
        charge.is_expired = True
        count += 1

    await session.flush()
    return count


async def find_charges_needing_reminder(session: AsyncSession) -> list[tuple[WalletCharge, int]]:
    """
    بسته‌هایی که به یکی از مرزهای یادآوری (۳۰، ۷، یا ۱ روزِ مونده) رسیدن و هنوز
    یادآوریِ اون مرحله براشون نرفته رو برمی‌گردونه.

    نکته‌ی مهم: بازه‌ها باید متقابلاً منحصر باشن — بسته‌ای که مثلاً ۵ روز
    مونده داره، فقط باید تگِ «۷ روز مونده» بگیره، نه هم «۳۰ روز» هم «۷ روز»
    (که گمراه‌کننده بود، چون واقعاً ۳۰ روز نمونده). برای همین همیشه نزدیک‌ترین
    مرزِ صادق رو انتخاب می‌کنیم، نه هر مرزی که از دیدِ ریاضی بزرگ‌تره.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    due: list[tuple[WalletCharge, int]] = []

    all_frozen, frozen_ids = await time_freeze_service.frozen_filter(session)  # W5 · K3: در توقف یادآوری نمی‌ره
    if all_frozen:
        return due
    reminder_query = select(WalletCharge).where(
        WalletCharge.is_expired.is_(False),
        WalletCharge.remaining_toman > 0,
        WalletCharge.expires_at > now,
        WalletCharge.expires_at <= now + datetime.timedelta(days=30),
    )
    if frozen_ids:
        reminder_query = reminder_query.where(WalletCharge.shop_owner_id.notin_(frozen_ids))
    result = await session.execute(reminder_query)
    for charge in result.scalars().all():
        # سقف (نه کف): «۵ روزِ دیگه» برایِ ۴ روز و ۲۳ ساعتِ باقی‌مانده صادق‌تر از «۴ روز» است،
        # و آستانه‌ها هم دقیقاً سرِ مرز زده می‌شوند نه یک روز دیر.
        remaining_seconds = (charge.expires_at - now).total_seconds()
        days_left = int(-(-remaining_seconds // 86400))
        # هر آستانه فقط وقتی کاندیدِ معتبره که نه خودش قبلاً رفته، نه هیچ
        # آستانه‌ی محکم‌ترِ (نزدیک‌تر به انقضا) دیگه‌ای رفته باشه — وگرنه بعد
        # از فرستادنِ «۷ روز مونده»، ممکنه بعداً به‌اشتباه «۳۰ روز مونده» هم
        # بفرستیم که یه پسرفتِ گیج‌کننده‌ست.
        candidates = []
        if days_left <= 1 and not charge.reminder_1d_sent:
            candidates.append(1)
        if days_left <= 7 and not charge.reminder_7d_sent and not charge.reminder_1d_sent:
            candidates.append(7)
        if days_left <= 30 and not charge.reminder_30d_sent and not charge.reminder_7d_sent and not charge.reminder_1d_sent:
            candidates.append(30)
        if candidates:
            # دومی آستانه است (برایِ فلگِ «رفته») و سومی روزهایِ *واقعی* باقی‌مانده (برایِ متنِ پیام).
            # قبلاً آستانه به‌جایِ روزهایِ واقعی به کاربر نشان داده می‌شد ⇒ بسته‌ای که ۲ روز
            # فرصت دارد پیامِ «۷ روزِ دیگه منقضی می‌شه» می‌گرفت و فروشگاه‌دار دیرِ کار می‌کرد.
            due.append((charge, min(candidates), max(days_left, 0)))

    return due


async def mark_reminder_sent(session: AsyncSession, charge: WalletCharge, days: int) -> None:
    if days == 30:
        charge.reminder_30d_sent = True
    elif days == 7:
        charge.reminder_7d_sent = True
    elif days == 1:
        charge.reminder_1d_sent = True
    await session.flush()


# --- محاسبه‌ی هزینه‌ی وزن‌دار ---


def estimate_chat_cost(admin_settings, total_tokens: int | None) -> int:
    if total_tokens is None:
        total_tokens = 800  # تخمینِ محافظه‌کارانه اگه ارائه‌دهنده usage برنگردوند
    return max(1, round(total_tokens * admin_settings.wallet_cost_per_1k_tokens_toman / 1000))


def estimate_voice_cost(admin_settings, duration_seconds: int | None = None) -> int:
    """هزینهٔ یکِ پیامِ صوتی.

    قیمتِ ثابتِ «هر صوت ۳۰۰ تومان» ویسِ یک‌دقیقه‌ای را ~۱۰ برابر زیرِ هزینهٔ تمام‌شده می‌گذاشت.
    با `wallet_cost_voice_per_minute_toman` (پیش‌فرض ۰ ⇒ خاموش) هزینه می‌شود
    `max(کفِ ثابت, سقفِ دقیقه × نرخ)` — یعنی هیچ‌کس ارزان‌تر از امروز پرداخت نمی‌کند و
    فقط ویسِ بلندتر، بیشتر پول می‌دهد.
    """
    floor = int(admin_settings.wallet_cost_voice_transcription_toman or 0)
    per_minute = int(getattr(admin_settings, "wallet_cost_voice_per_minute_toman", 0) or 0)
    if per_minute <= 0 or not duration_seconds or duration_seconds <= 0:
        return max(1, floor)
    minutes = -(-int(duration_seconds) // 60)  # گردِ بالا به دقیقهٔ کامل
    return max(1, floor, minutes * per_minute)


def estimate_receipt_cost(admin_settings, total_tokens: int | None = None) -> int:
    """هزینهٔ تحلیلِ هوشمندِ رسید: توکن‌محور اگر `wallet_cost_receipt_per_1k_tokens` روشن باشد.

    ارائه‌دهنده همیشه usage برنمی‌گرداند؛ در آن حالت به همان نرخِ ثابتِ برمی‌گردد (نه تخمینِ
    ساختگی)، تا روشن‌کردنِ این گزینه هرگز هزینه را بی‌دلیل بالا نبرد.
    """
    flat = int(admin_settings.wallet_cost_receipt_analysis_toman or 0)
    per_1k = int(getattr(admin_settings, "wallet_cost_receipt_per_1k_tokens", 0) or 0)
    if per_1k <= 0 or not total_tokens or total_tokens <= 0:
        return max(1, flat)
    return max(1, round(total_tokens * per_1k / 1000))


def estimate_order_detection_cost(admin_settings, total_tokens: int | None) -> int:
    if total_tokens is None:
        return admin_settings.wallet_cost_order_detection_toman
    return max(1, round(total_tokens * admin_settings.wallet_cost_per_1k_tokens_toman / 1000))


def estimate_cart_edit_cost(admin_settings, total_tokens: int | None) -> int:
    """تحلیلِ «آیا این پیام یه دستورِ ویرایشِ سبده؟» دقیقاً از جنسِ تشخیصِ سفارشه
    (یه فراخوانیِ کوتاهِ تحلیلی که خروجیش JSON ـه)، پس همون فرمولِ وزن‌دارِ
    توکن‌محور رو استفاده می‌کنه — نه یه تنظیمِ ادمینِ جدا، تا لازم نباشه مایگریشن
    یا صفحه‌ی تنظیمات اضافه بشه."""
    return estimate_order_detection_cost(admin_settings, total_tokens)


# تعدادِ توکنِ «معمولی» برایِ تخمینِ قبل از اجرا (نمایشِ «حدودِ X تومان» و چکِ موجودی).
CRM_SUMMARY_TYPICAL_TOKENS = 1500
OWNER_ASSISTANT_TYPICAL_TOKENS = 1200


def estimate_crm_summary_cost(admin_settings, total_tokens: int | None) -> int:
    """خلاصه‌یِ هوشمندِ مشتری (فازِ ۴-ج): همون فرمولِ وزن‌دارِ توکن‌محورِ چت؛ اگه ارائه‌دهنده usage
    برنگردوند، تخمینِ محافظه‌کارانه‌یِ چت (۸۰۰ توکن). نه تنظیمِ ادمینِ جدا، نه مایگریشن."""
    return estimate_chat_cost(admin_settings, total_tokens)


def estimate_owner_assistant_cost(admin_settings, total_tokens: int | None) -> int:
    """یه پیامِ دستیارِ مدیریتی (فازِ ۴-د): همون فرمولِ توکن‌محورِ چت."""
    return estimate_chat_cost(admin_settings, total_tokens)


# --- اطلاع‌رسانیِ کمبودِ اعتبار (با محافظت در برابرِ اسپم) ---

_LOW_BALANCE_RENOTIFY_HOURS = 24
_EMPTY_RENOTIFY_HOURS = 6


async def try_claim_empty_notification(session: AsyncSession, owner: ShopOwner) -> bool:
    """
    اتمیک (UPDATE...WHERE سطحِ دیتابیس، نه چک‌وسِت پایتونی): True فقط به یه
    caller برمی‌گرده، حتی اگه دو تسکِ هم‌زمان (با سشن‌های جدا، مثلِ کسرِ
    هزینه‌ی پاسخِ چت و کسرِ هزینه‌ی تشخیصِ سفارش که واقعاً به‌صورتِ دو تسکِ
    async مجزا اجرا می‌شن) هم‌زمان صداش بزنن — دقیقاً همون کلاسِ مشکلی که
    _apply_balance_delta برایِ خودِ موجودی حلش کرده، اینجا برایِ فلگِ
    ضدِ-اسپم‌ِ اطلاع‌رسانی. قبلاً این چک با should_notify_empty (که فقط
    owner ی از یه session رو توی پایتون می‌خوند) + mark_empty_notified
    جدا انجام می‌شد؛ چون دو session ی جدا از هم بی‌خبرن، هر دو می‌تونستن
    هم‌زمان «هنوز نرفته» ببینن و هر دو پیام بفرستن — دقیقاً باگی که این
    نسخه‌ی اتمیک رفعش می‌کنه.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    threshold = now - datetime.timedelta(hours=_EMPTY_RENOTIFY_HOURS)
    result = await session.execute(
        update(ShopOwner)
        .where(
            ShopOwner.id == owner.id,
            or_(ShopOwner.wallet_empty_notified_at.is_(None), ShopOwner.wallet_empty_notified_at <= threshold),
        )
        .values(wallet_empty_notified_at=now)
        .returning(ShopOwner.id)
    )
    claimed = result.scalar_one_or_none() is not None
    if claimed:
        owner.wallet_empty_notified_at = now
    return claimed


async def try_claim_low_balance_notification(session: AsyncSession, owner: ShopOwner) -> bool:
    """مثلِ try_claim_empty_notification، ولی برایِ هشدارِ «موجودی داره کم می‌شه» (نه «تمومِ کامل»)."""
    now = datetime.datetime.now(datetime.timezone.utc)
    threshold = now - datetime.timedelta(hours=_LOW_BALANCE_RENOTIFY_HOURS)
    result = await session.execute(
        update(ShopOwner)
        .where(
            ShopOwner.id == owner.id,
            or_(ShopOwner.wallet_low_balance_notified_at.is_(None), ShopOwner.wallet_low_balance_notified_at <= threshold),
        )
        .values(wallet_low_balance_notified_at=now)
        .returning(ShopOwner.id)
    )
    claimed = result.scalar_one_or_none() is not None
    if claimed:
        owner.wallet_low_balance_notified_at = now
    return claimed
