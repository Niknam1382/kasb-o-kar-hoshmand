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

import datetime
import logging

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import ShopOwner, WalletCharge, WalletTransaction, WalletTransactionReason
from app.services.admin_settings_service import get_admin_settings

logger = logging.getLogger(__name__)


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
        .values(wallet_balance_toman=ShopOwner.wallet_balance_toman + delta_toman)
        .returning(ShopOwner.wallet_balance_toman)
    )
    owner.wallet_balance_toman = result.scalar_one()


async def add_charge(
    session: AsyncSession,
    owner: ShopOwner,
    amount_toman: int,
    reason: WalletTransactionReason = WalletTransactionReason.TOPUP,
    payment_id: int | None = None,
    validity_months: int | None = None,
    reference: str | None = None,
) -> WalletCharge:
    """یه بسته‌ی شارژِ جدید می‌سازه (با انقضای مستقل) و موجودیِ کش‌شده رو آپدیت می‌کنه."""
    if amount_toman <= 0:
        raise ValueError("مبلغِ شارژ باید مثبت باشه")

    if validity_months is None:
        admin_settings = await get_admin_settings(session)
        validity_months = admin_settings.wallet_topup_validity_months

    now = datetime.datetime.now(datetime.timezone.utc)
    expires_at = now + datetime.timedelta(days=validity_months * 30)

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
            shop_owner_id=owner.id, wallet_charge_id=charge.id, amount_toman=amount_toman, reason=reason, reference=reference
        )
    )
    await session.flush()
    return charge


async def deduct(
    session: AsyncSession,
    owner: ShopOwner,
    amount_toman: int,
    reason: WalletTransactionReason,
    reference: str | None = None,
) -> bool:
    """
    از قدیمی‌ترین شارژِ منقضی‌نشده (FIFO) کم می‌کنه، حتی اگه بینِ چند بسته پخش
    بشه. اگه موجودی کافی نبود، هیچ تغییری اعمال نمی‌شه و False برمی‌گرده —
    caller باید به‌جای پاسخِ عادی، پیامِ کمبودِ اعتبار به فروشگاه‌دار نشون بده
    (نه به مشتری).
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

    remaining_to_deduct = amount_toman
    for charge in charges:
        if remaining_to_deduct <= 0:
            break
        take = min(charge.remaining_toman, remaining_to_deduct)
        charge.remaining_toman -= take
        remaining_to_deduct -= take
        session.add(
            WalletTransaction(
                shop_owner_id=owner.id, wallet_charge_id=charge.id, amount_toman=-take, reason=reason, reference=reference
            )
        )

    if remaining_to_deduct > 0:
        # این یعنی موجودیِ کش‌شده با مجموعِ واقعیِ بسته‌ها هم‌خوان نبوده —
        # یه ناسازگاریِ داده‌ست که نباید عملاً پیش بیاد؛ به‌جای خرابی/rollbackِ
        # کورکورانه، لاگ می‌کنیم و امن fail می‌کنیم تا caller خودش تصمیم بگیره.
        logger.error(
            "ناسازگاریِ موجودیِ کیف‌پول برای shop_owner_id=%s: موجودیِ کش‌شده=%s ولی جمعِ بسته‌ها کافی نبود",
            owner.id,
            owner.wallet_balance_toman,
        )
        return False

    await _apply_balance_delta(session, owner, -amount_toman)
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


async def has_ever_had_wallet_activity(session: AsyncSession, owner: ShopOwner) -> bool:
    result = await session.execute(select(WalletCharge.id).where(WalletCharge.shop_owner_id == owner.id).limit(1))
    return result.scalar_one_or_none() is not None


async def expire_stale_charges(session: AsyncSession) -> int:
    """
    کارِ روزانه: بسته‌هایی که تاریخِ انقضاشون گذشته رو می‌بنده و از موجودیِ
    کش‌شده کم می‌کنه. عمداً روزانه‌ست (نه لحظه‌ای) تا وسطِ یه مکالمه/مصرفِ
    درحال‌انجام چیزی قطع نشه.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    result = await session.execute(
        select(WalletCharge).where(
            WalletCharge.is_expired.is_(False), WalletCharge.expires_at <= now, WalletCharge.remaining_toman > 0
        )
    )
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

    result = await session.execute(
        select(WalletCharge).where(
            WalletCharge.is_expired.is_(False),
            WalletCharge.remaining_toman > 0,
            WalletCharge.expires_at > now,
            WalletCharge.expires_at <= now + datetime.timedelta(days=30),
        )
    )
    for charge in result.scalars().all():
        days_left = (charge.expires_at - now).days
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
            due.append((charge, min(candidates)))

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


def estimate_photo_cost(admin_settings) -> int:
    return admin_settings.wallet_cost_photo_analysis_toman


def estimate_voice_cost(admin_settings) -> int:
    return admin_settings.wallet_cost_voice_transcription_toman


def estimate_order_detection_cost(admin_settings, total_tokens: int | None) -> int:
    if total_tokens is None:
        return admin_settings.wallet_cost_order_detection_toman
    return max(1, round(total_tokens * admin_settings.wallet_cost_per_1k_tokens_toman / 1000))


# --- اطلاع‌رسانیِ کمبودِ اعتبار (با محافظت در برابرِ اسپم) ---

_LOW_BALANCE_RENOTIFY_HOURS = 24
_EMPTY_RENOTIFY_HOURS = 6


def should_notify_empty(owner: ShopOwner) -> bool:
    if owner.wallet_empty_notified_at is None:
        return True
    elapsed = datetime.datetime.now(datetime.timezone.utc) - owner.wallet_empty_notified_at
    return elapsed >= datetime.timedelta(hours=_EMPTY_RENOTIFY_HOURS)


def should_notify_low_balance(owner: ShopOwner) -> bool:
    if owner.wallet_low_balance_notified_at is None:
        return True
    elapsed = datetime.datetime.now(datetime.timezone.utc) - owner.wallet_low_balance_notified_at
    return elapsed >= datetime.timedelta(hours=_LOW_BALANCE_RENOTIFY_HOURS)


async def mark_empty_notified(session: AsyncSession, owner: ShopOwner) -> None:
    owner.wallet_empty_notified_at = datetime.datetime.now(datetime.timezone.utc)
    await session.flush()


async def mark_low_balance_notified(session: AsyncSession, owner: ShopOwner) -> None:
    owner.wallet_low_balance_notified_at = datetime.datetime.now(datetime.timezone.utc)
    await session.flush()
