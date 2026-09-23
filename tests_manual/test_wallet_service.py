"""
تست‌های سرویسِ کیف‌پول — چون این مستقیم با پولِ واقعی سروکار داره، پوششِ
دقیق‌تری از حدِ معمول لازم داره:
۱. شارژِ ساده و آپدیتِ درستِ موجودیِ کش‌شده
۲. مصرفِ FIFO از قدیمی‌ترین بسته
۳. مصرفی که بین دو بسته پخش می‌شه (بسته‌ی اول کافی نیست)
۴. رَدشدنِ مصرف وقتی موجودی کافی نیست (بدونِ نصفه‌کاره کم‌کردن)
۵. انقضای بسته‌های گذشته + آپدیتِ موجودیِ کش‌شده
۶. بسته‌های منقضی‌شده دیگه توی مصرفِ بعدی حساب نمی‌شن
۷. یادآوری‌های ۳۰/۷/۱ روزه پیدا و علامت‌گذاری می‌شن، و دوباره تکرار نمی‌شن

اجرا: python3 tests_manual/test_wallet_service.py
"""
from __future__ import annotations

import asyncio
import datetime
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from harness import reset_database  # noqa: E402

from app.database.models import WalletTransactionReason  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import shop_owner_service, wallet_service  # noqa: E402

OWNER_TG_ID = 999601


async def _seed_owner():
    async with session_scope() as session:
        owner = await shop_owner_service.get_or_create_shop_owner(session, OWNER_TG_ID)
        await shop_owner_service.complete_registration(session, owner, "کیف‌پول", "تست", "09120000001", "wallet@example.com", True, True)
        return owner.id


async def test_add_charge_updates_cached_balance() -> None:
    await reset_database()
    owner_id = await _seed_owner()

    async with session_scope() as session:
        from sqlalchemy import select

        from app.database.models import ShopOwner

        owner = (await session.execute(select(ShopOwner).where(ShopOwner.id == owner_id))).scalar_one()
        charge = await wallet_service.add_charge(session, owner, 500_000)
        assert owner.wallet_balance_toman == 500_000
        assert charge.remaining_toman == 500_000
        assert charge.expires_at > datetime.datetime.now(datetime.timezone.utc)

    print("✅ test_add_charge_updates_cached_balance PASSED")


async def test_deduct_uses_oldest_charge_first() -> None:
    await reset_database()
    owner_id = await _seed_owner()

    async with session_scope() as session:
        from sqlalchemy import select

        from app.database.models import ShopOwner

        owner = (await session.execute(select(ShopOwner).where(ShopOwner.id == owner_id))).scalar_one()
        old_charge = await wallet_service.add_charge(session, owner, 100_000, validity_months=1)
        new_charge = await wallet_service.add_charge(session, owner, 200_000, validity_months=12)
        assert owner.wallet_balance_toman == 300_000

        ok = await wallet_service.deduct(session, owner, 60_000, WalletTransactionReason.CHAT_MESSAGE)
        assert ok is True
        await session.refresh(old_charge)
        await session.refresh(new_charge)
        assert old_charge.remaining_toman == 40_000, "باید فقط از قدیمی‌ترین بسته (انقضای نزدیک‌تر) کم بشه"
        assert new_charge.remaining_toman == 200_000, "بسته‌ی جدیدتر نباید دست‌نخورده بمونه چون هنوز از اولی موجودی بود"
        assert owner.wallet_balance_toman == 240_000

    print("✅ test_deduct_uses_oldest_charge_first PASSED")


async def test_deduct_spans_multiple_charges() -> None:
    await reset_database()
    owner_id = await _seed_owner()

    async with session_scope() as session:
        from sqlalchemy import select

        from app.database.models import ShopOwner

        owner = (await session.execute(select(ShopOwner).where(ShopOwner.id == owner_id))).scalar_one()
        old_charge = await wallet_service.add_charge(session, owner, 30_000, validity_months=1)
        new_charge = await wallet_service.add_charge(session, owner, 100_000, validity_months=12)

        ok = await wallet_service.deduct(session, owner, 50_000, WalletTransactionReason.PHOTO_ANALYSIS)
        assert ok is True
        await session.refresh(old_charge)
        await session.refresh(new_charge)
        assert old_charge.remaining_toman == 0, "بسته‌ی قدیمی باید کاملاً خالی بشه"
        assert new_charge.remaining_toman == 80_000, "۲۰ هزار باقی‌مونده باید از بسته‌ی دوم کم بشه (۳۰+۲۰=۵۰)"
        assert owner.wallet_balance_toman == 80_000

    print("✅ test_deduct_spans_multiple_charges PASSED")


async def test_deduct_rejected_when_insufficient_balance() -> None:
    await reset_database()
    owner_id = await _seed_owner()

    async with session_scope() as session:
        from sqlalchemy import select

        from app.database.models import ShopOwner

        owner = (await session.execute(select(ShopOwner).where(ShopOwner.id == owner_id))).scalar_one()
        charge = await wallet_service.add_charge(session, owner, 10_000)

        ok = await wallet_service.deduct(session, owner, 50_000, WalletTransactionReason.VOICE_TRANSCRIPTION)
        assert ok is False, "نباید موجودیِ ناکافی رو قبول کنه"
        await session.refresh(charge)
        assert charge.remaining_toman == 10_000, "چیزی نباید نصفه‌کاره کم بشه"
        assert owner.wallet_balance_toman == 10_000

    print("✅ test_deduct_rejected_when_insufficient_balance PASSED")


async def test_expire_stale_charges() -> None:
    await reset_database()
    owner_id = await _seed_owner()

    async with session_scope() as session:
        from sqlalchemy import select

        from app.database.models import ShopOwner

        owner = (await session.execute(select(ShopOwner).where(ShopOwner.id == owner_id))).scalar_one()
        expired_charge = await wallet_service.add_charge(session, owner, 40_000, validity_months=1)
        # به‌زور تاریخِ انقضاش رو می‌بریم به دیروز، برای شبیه‌سازیِ گذشتِ زمان
        expired_charge.expires_at = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1)
        fresh_charge = await wallet_service.add_charge(session, owner, 60_000, validity_months=12)
        await session.flush()
        assert owner.wallet_balance_toman == 100_000

        expired_count = await wallet_service.expire_stale_charges(session)
        assert expired_count == 1
        await session.refresh(expired_charge)
        await session.refresh(fresh_charge)
        await session.refresh(owner)
        assert expired_charge.is_expired is True
        assert expired_charge.remaining_toman == 0
        assert fresh_charge.is_expired is False
        assert owner.wallet_balance_toman == 60_000, "فقط بسته‌ی منقضی‌شده باید از موجودی کم بشه"

        # حالا مصرف باید فقط از بسته‌ی تازه (که منقضی نشده) اجازه داده بشه
        ok = await wallet_service.deduct(session, owner, 60_000, WalletTransactionReason.CHAT_MESSAGE)
        assert ok is True
        await session.refresh(owner)
        assert owner.wallet_balance_toman == 0

    print("✅ test_expire_stale_charges PASSED")


async def test_reminders_found_and_not_repeated() -> None:
    await reset_database()
    owner_id = await _seed_owner()

    async with session_scope() as session:
        from sqlalchemy import select

        from app.database.models import ShopOwner

        owner = (await session.execute(select(ShopOwner).where(ShopOwner.id == owner_id))).scalar_one()
        charge = await wallet_service.add_charge(session, owner, 25_000, validity_months=12)
        # می‌بریمش دقیقاً توی بازه‌ی یادآوریِ «۷ روز مونده»
        charge.expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=5)
        await session.flush()

        due = await wallet_service.find_charges_needing_reminder(session)
        matching = [d for d in due if d[0].id == charge.id]
        assert len(matching) == 1, "باید توی بازه‌ی ۷ روزه پیدا بشه"
        assert matching[0][1] == 7

        await wallet_service.mark_reminder_sent(session, charge, 7)
        await session.refresh(charge)
        assert charge.reminder_7d_sent is True

        due_again = await wallet_service.find_charges_needing_reminder(session)
        matching_again = [d for d in due_again if d[0].id == charge.id]
        assert len(matching_again) == 0, "بعد از علامت‌گذاری نباید دوباره برگرده"

    print("✅ test_reminders_found_and_not_repeated PASSED")


async def main() -> None:
    await test_add_charge_updates_cached_balance()
    await test_deduct_uses_oldest_charge_first()
    await test_deduct_spans_multiple_charges()
    await test_deduct_rejected_when_insufficient_balance()
    await test_expire_stale_charges()
    await test_reminders_found_and_not_repeated()


if __name__ == "__main__":
    asyncio.run(main())
