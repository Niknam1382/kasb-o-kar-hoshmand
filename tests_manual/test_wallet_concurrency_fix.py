"""
تست: رفعِ باگِ lost-update در موجودیِ کش‌شده‌ی کیف‌پول.

باگِ واقعی که پیدا شد: هر پیامِ مشتری باعثِ دو کسرِ کیف‌پولِ *هم‌زمان* می‌شه —
یکی برای پاسخِ چت (در همون تسک)، یکی برای تشخیصِ سفارش (در یه asyncio task
جدا با سشنِ خودش). چون wallet_balance_toman قبلاً با «بخون، توی پایتون کم
کن، بنویس» آپدیت می‌شد (نه یه UPDATEِ اتمیکِ سطحِ دیتابیس)، یکی از این دو کسر
می‌تونست overwrite بشه — دقیقاً همونی که تویِ اجرای واقعیِ تست‌ها با Docker
دیده شد (۱۰۵۰ - ۱۰۰ - ۱ باید ۹۴۹ می‌شد، ولی ۱۰۴۹ شد چون کسرِ ۱۰۰تومنی گم شد).

اجرا: python3 tests_manual/test_wallet_concurrency_fix.py
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from harness import reset_database  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from app.database.models import ShopOwner, WalletTransactionReason  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import shop_owner_service, wallet_service  # noqa: E402

OWNER_TG_ID = 999001
SHOP_BOT_TG_ID = 999002


async def _deduct_in_own_session(owner_id: int, amount: int) -> None:
    """دقیقاً شبیه‌سازیِ چیزی که customer.py انجام می‌ده: یه session جدا،
    owner رو مستقل می‌خونه، کسر می‌کنه — بدونِ اطلاع از سشنِ موازیِ دیگه."""
    async with session_scope() as session:
        owner = await session.get(ShopOwner, owner_id)
        await wallet_service.deduct(session, owner, amount, WalletTransactionReason.CHAT_MESSAGE)


async def test_two_concurrent_deductions_both_apply_no_lost_update() -> None:
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID, initial_balance_toman=1050)
    async with session_scope() as session:
        owner = await shop_owner_service.get_by_telegram_id(session, OWNER_TG_ID)
        owner_id = owner.id

    # دقیقاً همون سناریو: یه کسرِ ۱۰۰تومنی (پاسخِ چت) و یه کسرِ ۱تومنی
    # (تشخیصِ سفارش) هم‌زمان، هرکدوم توی سشنِ خودش — با asyncio.gather که
    # واقعاً موازی اجراشون کنه، نه پشتِ‌سرِهم.
    await asyncio.gather(
        _deduct_in_own_session(owner_id, 100),
        _deduct_in_own_session(owner_id, 1),
    )

    async with session_scope() as session:
        owner = await session.get(ShopOwner, owner_id)
        assert owner.wallet_balance_toman == 949, (
            f"هر دو کسر باید واقعاً اعمال بشن (۱۰۵۰-۱۰۰-۱=۹۴۹)، ولی {owner.wallet_balance_toman} بود "
            "— یعنی lost update دوباره برگشته"
        )

    print("✅ test_two_concurrent_deductions_both_apply_no_lost_update PASSED")


async def test_ten_concurrent_small_deductions_all_apply() -> None:
    """سخت‌گیرانه‌تر: ۱۰ تا کسرِ هم‌زمان، نه فقط ۲ تا."""
    await reset_database()
    await seed_usable_shop(OWNER_TG_ID + 1, SHOP_BOT_TG_ID + 1, initial_balance_toman=1000)
    async with session_scope() as session:
        owner = await shop_owner_service.get_by_telegram_id(session, OWNER_TG_ID + 1)
        owner_id = owner.id

    await asyncio.gather(*[_deduct_in_own_session(owner_id, 10) for _ in range(10)])

    async with session_scope() as session:
        owner = await session.get(ShopOwner, owner_id)
        assert owner.wallet_balance_toman == 900, f"باید ۱۰۰۰-۱۰۰=۹۰۰ بمونه، ولی {owner.wallet_balance_toman} بود"

    print("✅ test_ten_concurrent_small_deductions_all_apply PASSED")


async def test_concurrent_topup_and_deduction_both_apply() -> None:
    await reset_database()
    await seed_usable_shop(OWNER_TG_ID + 2, SHOP_BOT_TG_ID + 2, initial_balance_toman=500)
    async with session_scope() as session:
        owner = await shop_owner_service.get_by_telegram_id(session, OWNER_TG_ID + 2)
        owner_id = owner.id

    async def _topup():
        async with session_scope() as session:
            owner = await session.get(ShopOwner, owner_id)
            await wallet_service.add_charge(session, owner, 300, reason=WalletTransactionReason.TOPUP)

    await asyncio.gather(_topup(), _deduct_in_own_session(owner_id, 50))

    async with session_scope() as session:
        owner = await session.get(ShopOwner, owner_id)
        assert owner.wallet_balance_toman == 750, f"باید ۵۰۰+۳۰۰-۵۰=۷۵۰ بمونه، ولی {owner.wallet_balance_toman} بود"

    print("✅ test_concurrent_topup_and_deduction_both_apply PASSED")


async def main() -> None:
    await test_two_concurrent_deductions_both_apply_no_lost_update()
    await test_ten_concurrent_small_deductions_all_apply()
    await test_concurrent_topup_and_deduction_both_apply()


if __name__ == "__main__":
    asyncio.run(main())
