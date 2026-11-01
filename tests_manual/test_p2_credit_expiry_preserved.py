"""
تست‌هایِ قفلِ رگرسیون — PHASE 2 (حفظِ دقیقِ مکانیزمِ انقضایِ اعتبارِ شارژ).

این فایل برایِ «کشفِ باگ» نوشته نشده؛ برایِ **نقشِ محافظ** نوشته شده: هر تغییرِ بعدیِ کد
(به‌ویژه اضافه‌شدنِ کمیسیون/دفتر/دروازه‌یِ اعتبار) نباید معنا یا عددِ انقضایِ فعلی را عوض کند.
قفل‌شده‌ها (از `app/services/wallet_service.py:56` و `:201` و `app/database/models.py:463`):

۱. مدت = **ماه‌هایِ تقویمیِ** `AdminSettings.wallet_topup_validity_months` (از P22؛ قبلاً
   `×۳۰ روز` بود) و پیش‌فرضِ آن **۱۲** است. مثلِ اشتراک، «۱ ماه» یعنی همان روزِ ماهِ بعد
   (با clamp برایِ روزهایِ سرِ ماه)، پس ۲۸ تا ۳۱ روز بسته به ماه تغییر می‌کند.
۲. مبدأ زمان = لحظهٔ ساختِ شارژ (یعنی موفق‌شدنِ شارژ)، به UTC.
۳. هر شارژ = یک بستهٔ مستقل (`wallet_charges`) با `expires_at/remaining_toman/is_expired` خودش.
۴. مصرف = FIFO از قدیمی‌ترین بستهٔ منقضی‌نشده؛ بستهٔ منقضی هرگز مصرف نمی‌شود.
۵. جابِ انقضا ایدمپوتنت است (اجرایِ دوباره ⇒ صفر)، موجودیِ کش‌شده را دقیقاً یک‌بار کم می‌کند،
   ردیفِ دفتر با دلیلِ `EXPIRY` می‌نویسد و باقی‌ماندهٔ بسته را صفر می‌کند.
۶. یادآوری‌ها: نزدیک‌ترین مرزِ صادق (۳۰/۷/۱ روز)، هر مرز فقط یک‌بار، و بعدِ انقضا هیچ یادآوری.
۷. override کردنِ `validity_months` (مثلِ هدیه‌یِ ادمین K1) تنظیماتِ سراسری را عوض نمی‌کند.

هیچ «مکانیزمِ دومِ انقضا» در پروژه وجود ندارد و این تست آن را هم قفل می‌کند
(`credit_batch_service` فقط هدیه/تمدیدِ گروهی است و اعتبار را از همان `wallet_service` می‌سازد).

اجرا: python3 tests_manual/test_p2_credit_expiry_preserved.py
"""
from __future__ import annotations

import asyncio
import datetime
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from sqlalchemy import func, select  # noqa: E402
from dateutil.relativedelta import relativedelta  # noqa: E402

from harness import reset_database  # noqa: E402

from app.database.models import AdminSettings, ShopOwner, WalletCharge, WalletTransaction, WalletTransactionReason  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import shop_owner_service, time_freeze_service, wallet_service  # noqa: E402
from app.services.admin_settings_service import get_admin_settings  # noqa: E402

OWNER_TG_ID = 999_411
PINNED_DEFAULT_VALIDITY_MONTHS = 12  # models.py:315 (default=12) و مایگریشن 75d679f44f25 (server_default='12')
# P22: «ماه» دیگر ۳۰ روزِ ثابت نیست؛ همان relativedelta که اشتراک مصرف می‌کند.


async def _owner(telegram_id: int = OWNER_TG_ID) -> int:
    async with session_scope() as session:
        owner = await shop_owner_service.get_or_create_shop_owner(session, telegram_id)
        await shop_owner_service.complete_registration(
            session, owner, "انقضا", "تست", "09121111111", "expiry@example.com", True, True
        )
        return owner.id


async def _get_owner(owner_id: int):
    async with session_scope() as session:
        return (await session.execute(select(ShopOwner).where(ShopOwner.id == owner_id))).scalar_one()


async def _set_validity(months: int) -> None:
    async with session_scope() as session:
        admin = await get_admin_settings(session)
        admin.wallet_topup_validity_months = months
        await session.flush()


async def _add(owner_id: int, amount: int, **kwargs) -> tuple[int, datetime.datetime, datetime.datetime]:
    """یک بستهٔ شارژ می‌سازد و (charge_id, لحظهٔ قبل, expires_at) را برمی‌گرداند."""
    before = datetime.datetime.now(datetime.timezone.utc)
    async with session_scope() as session:
        owner = (await session.execute(select(ShopOwner).where(ShopOwner.id == owner_id))).scalar_one()
        charge = await wallet_service.add_charge(session, owner, amount, **kwargs)
        return charge.id, before, charge.expires_at


# ============================================================================= ۱ و ۲ — مدت و مبدأ
async def test_duration_is_config_calendar_months_from_the_recharge_moment() -> None:
    await reset_database()
    owner_id = await _owner()
    await _set_validity(7)

    charge_id, before, expires_at = await _add(owner_id, 100_000)
    expected = before + relativedelta(months=7)
    assert abs((expires_at - expected).total_seconds()) < 5, f"انتظار {expected}، گرفتم {expires_at}"
    actual_days = (expires_at - before).total_seconds() / 86400
    assert 28 <= actual_days <= 32 * 7, actual_days
    assert expires_at.tzinfo is not None, "انقضا باید aware/UTC باشد وگرنه جابِ روزانه اشتباه می‌کند"

    # override کردنِ per-call همان قاعده را با عددِ خودش دارد
    _, before2, expires2 = await _add(owner_id, 50_000, validity_months=2)
    assert abs((expires2 - (before2 + relativedelta(months=2))).total_seconds()) < 5
    assert charge_id  # فقط برایِ اطمینان از ساختِ ردیف
    print("✅ test_duration_is_config_calendar_months_from_the_recharge_moment PASSED")


async def test_default_validity_is_pinned_to_twelve_months() -> None:
    await reset_database()
    await _owner()

    column_default = AdminSettings.__table__.columns["wallet_topup_validity_months"].default.arg
    assert column_default == PINNED_DEFAULT_VALIDITY_MONTHS, column_default

    async with session_scope() as session:
        admin = await get_admin_settings(session)
        assert admin.wallet_topup_validity_months == PINNED_DEFAULT_VALIDITY_MONTHS
        owner = (await session.execute(select(ShopOwner).where(ShopOwner.telegram_id == OWNER_TG_ID))).scalar_one()
        now = datetime.datetime.now(datetime.timezone.utc)
        charge = await wallet_service.add_charge(session, owner, 60_000)
        assert abs((charge.expires_at - (now + relativedelta(months=PINNED_DEFAULT_VALIDITY_MONTHS))).total_seconds()) < 5, "پیش‌فرضِ ۱۲ ⇒ دوازده ماهِ تقویمی"
    print("✅ test_default_validity_is_pinned_to_twelve_months PASSED")


# ============================================================================= ۳ و ۴ — بسته‌هایِ مستقل و FIFO
async def test_each_recharge_is_an_independent_lot_and_expired_lot_is_unusable() -> None:
    await reset_database()
    owner_id = await _owner()

    # دو بسته با دو انقضایِ متفاوت (تستِ «هر شارژ یک دورهٔ مستقل»)
    old_id, _, old_expiry = await _add(owner_id, 40_000, validity_months=1)
    new_id, _, new_expiry = await _add(owner_id, 60_000, validity_months=12)
    assert old_expiry != new_expiry, "بسته‌ها باید انقضایِ مستقل داشته باشند"

    async with session_scope() as session:
        old = await session.get(WalletCharge, old_id)
        old.expires_at = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=1)
        await session.flush()

    owner = await _get_owner(owner_id)
    assert owner.wallet_balance_toman == 100_000, "قبلِ جابِ انقضا، هر دو بسته در موجودیِ کش‌شده هست"

    # جابِ انقضا فقط بستهٔ گذشته را می‌بندد
    async with session_scope() as session:
        expired_count = await wallet_service.expire_stale_charges(session)
        assert expired_count == 1, expired_count

    # مصرفِ بیشتر از بستهٔ سالم ⇒ رد (اعتبارِ منقضی‌شده هرگز جبران نمی‌کند)
    async with session_scope() as session:
        owner = (await session.execute(select(ShopOwner).where(ShopOwner.id == owner_id))).scalar_one()
        assert owner.wallet_balance_toman == 60_000, "جابِ انقضا باید موجودیِ کش‌شده را هم کم کرده باشد"
        ok = await wallet_service.deduct(session, owner, 70_000, WalletTransactionReason.CHAT_MESSAGE)
        assert ok is False, "فقط ۶۰٬۰۰۰ در بستهٔ سالم مانده؛ ۴۰٬۰۰۰ منقضی‌شده نباید حساب شود"
        # و ردیفِ دفترِ مصرفی هم ننوشته شده باشد
        spend_rows = (
            await session.execute(
                select(func.count()).select_from(WalletTransaction).where(
                    WalletTransaction.shop_owner_id == owner_id,
                    WalletTransaction.reason == WalletTransactionReason.CHAT_MESSAGE,
                )
            )
        ).scalar_one()
        assert spend_rows == 0, spend_rows

    # مصرفِ کوچک‌تر از بستهٔ سالم ⇒ قبول، و فقط از همان بسته کم می‌شود
    async with session_scope() as session:
        owner = (await session.execute(select(ShopOwner).where(ShopOwner.id == owner_id))).scalar_one()
        assert await wallet_service.deduct(session, owner, 25_000, WalletTransactionReason.CHAT_MESSAGE) is True
        assert (await session.get(WalletCharge, new_id)).remaining_toman == 35_000
        assert (await session.get(WalletCharge, old_id)).remaining_toman == 0
        assert owner.wallet_balance_toman == 35_000
    print("✅ test_each_recharge_is_an_independent_lot_and_expired_lot_is_unusable PASSED")


# ============================================================================= ۵ — جابِ انقضا
async def test_expiry_job_is_idempotent_writes_ledger_and_never_goes_negative() -> None:
    await reset_database()
    owner_id = await _owner()
    charge_id, _, _ = await _add(owner_id, 70_000, validity_months=1)

    async with session_scope() as session:
        charge = await session.get(WalletCharge, charge_id)
        charge.expires_at = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=2)
        await session.flush()

    async with session_scope() as session:
        assert await wallet_service.expire_stale_charges(session) == 1
    async with session_scope() as session:
        assert await wallet_service.expire_stale_charges(session) == 0, "اجرایِ دوباره نباید چیزی کم کند"
        assert (await session.get(ShopOwner, owner_id)).wallet_balance_toman == 0
        assert (await session.get(WalletCharge, charge_id)).is_expired is True
        rows = list(
            (
                await session.execute(
                    select(WalletTransaction).where(
                        WalletTransaction.shop_owner_id == owner_id, WalletTransaction.reason == WalletTransactionReason.EXPIRY
                    )
                )
            ).scalars().all()
        )
        assert len(rows) == 1 and rows[0].amount_toman == -70_000 and rows[0].wallet_charge_id == charge_id, rows
        # جمعِ دفتر == موجودیِ کش‌شده (همسنجی)
        total = (
            await session.execute(
                select(func.coalesce(func.sum(WalletTransaction.amount_toman), 0)).where(
                    WalletTransaction.shop_owner_id == owner_id
                )
            )
        ).scalar_one()
        assert int(total) == 0, total
    print("✅ test_expiry_job_is_idempotent_writes_ledger_and_never_goes_negative PASSED")


async def test_expiry_respects_time_freeze_without_inventing_a_second_mechanism() -> None:
    """K3 (توقفِ زمان) باید رویِ همان جابِ موجود اثر کند؛ نه جابِ دوم و نه دورزدنِ انقضا."""
    await reset_database()
    owner_id = await _owner()
    charge_id, _, _ = await _add(owner_id, 30_000, validity_months=1)

    async with session_scope() as session:
        charge = await session.get(WalletCharge, charge_id)
        charge.expires_at = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1)
        freeze = await time_freeze_service.start(
            session, scope="owner", owner_id=owner_id, max_days=3, reason="تعمیراتِ زمان", by="test"
        )
        assert freeze is not None
        await session.flush()

    async with session_scope() as session:
        assert await wallet_service.expire_stale_charges(session) == 0, "در توقفِ زمان نباید منقضی شود"
        assert (await session.get(ShopOwner, owner_id)).wallet_balance_toman == 30_000

    # ازسرگیری ⇒ همان جابِ موجود، بدونِ مکانیزمِ دوم
    async with session_scope() as session:
        await time_freeze_service.resume(session, freeze_id=freeze.id, by="test")
    async with session_scope() as session:
        assert await wallet_service.expire_stale_charges(session) >= 1, "بعدِ ازسرگیری باید همان بسته منقضی شود"
        assert (await session.get(ShopOwner, owner_id)).wallet_balance_toman == 0
    print("✅ test_expiry_respects_time_freeze_without_inventing_a_second_mechanism PASSED")


# ============================================================================= ۶ — یادآوری‌ها
async def test_reminders_pick_the_nearest_honest_threshold_once() -> None:
    await reset_database()
    owner_id = await _owner()
    charge_id, _, _ = await _add(owner_id, 25_000, validity_months=12)

    async def _set_days_left(days: int) -> None:
        async with session_scope() as session:
            charge = await session.get(WalletCharge, charge_id)
            charge.expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=days)
            await session.flush()

    await _set_days_left(5)  # نزدیک‌ترین مرزِ صادق = ۷ روز، نه ۳۰
    async with session_scope() as session:
        due = await wallet_service.find_charges_needing_reminder(session)
        # (ردیف، آستانه، روزهایِ *واقعی*) — سومی همان چیزی است که به کاربر نشان داده می‌شود؛
        # P20: قبلاً آستانه (۷) نشان داده می‌شد در حالی که ۵ روز مانده بود.
        assert [(c.id, threshold, days_left) for c, threshold, days_left in due] == [(charge_id, 7, 5)], due
        await wallet_service.mark_reminder_sent(session, due[0][0], due[0][1])
    async with session_scope() as session:
        assert await wallet_service.find_charges_needing_reminder(session) == [], "مرزِ رفته‌شده تکرار نمی‌شود"

    await _set_days_left(0)  # منقضی ⇒ دیگر یادآوری ندارد
    async with session_scope() as session:
        assert await wallet_service.find_charges_needing_reminder(session) == []
    print("✅ test_reminders_pick_the_nearest_honest_threshold_once PASSED")


# ============================================================================= ۷ — override بدونِ دست‌زدنِ سراسری
async def test_per_call_validity_does_not_change_global_config() -> None:
    await reset_database()
    owner_id = await _owner()
    await _set_validity(9)

    await _add(owner_id, 10_000, validity_months=24)
    async with session_scope() as session:
        admin = await get_admin_settings(session)
        assert admin.wallet_topup_validity_months == 9, "پیکربندیِ سراسری نباید به‌عنوانِ اثرِ جانبی عوض شود"

    # فقط ادمین از مسیرِ تنظیمات می‌تواند مدت را عوض کند (همان ستون، همان UI)
    await _set_validity(3)
    async with session_scope() as session:
        assert (await get_admin_settings(session)).wallet_topup_validity_months == 3
    print("✅ test_per_call_validity_does_not_change_global_config PASSED")


async def main() -> None:
    await test_duration_is_config_calendar_months_from_the_recharge_moment()
    await test_default_validity_is_pinned_to_twelve_months()
    await test_each_recharge_is_an_independent_lot_and_expired_lot_is_unusable()
    await test_expiry_job_is_idempotent_writes_ledger_and_never_goes_negative()
    await test_expiry_respects_time_freeze_without_inventing_a_second_mechanism()
    await test_reminders_pick_the_nearest_honest_threshold_once()
    await test_per_call_validity_does_not_change_global_config()


if __name__ == "__main__":
    asyncio.run(main())
