"""
تست: تاییدِ/ردِ پرداختِ کارت‌به‌کارت توسط ادمین.

اجرا: python3 tests_manual/test_payment_approval.py
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from aiogram import Bot  # noqa: E402
from sqlalchemy import select  # noqa: E402

from harness import FakeSession, build_test_dispatchers, make_callback_update, reset_database  # noqa: E402

from app.database.models import Payment, PaymentPurpose, PaymentStatus, ShopOwner, Subscription  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import payment_service, shop_owner_service  # noqa: E402

ADMIN_TG_ID = 12345
OWNER_TG_ID = 999701


async def _seed_owner_with_pending_payment(amount: int = 500_000) -> tuple[int, int]:
    async with session_scope() as session:
        owner = await shop_owner_service.get_or_create_shop_owner(session, OWNER_TG_ID)
        owner = await shop_owner_service.complete_registration(session, owner, "خریدار", "تست", "09120000006", "buyer@example.com", True, True)
        payment = await payment_service.create_card_to_card_payment(session, owner, amount, None, duration_months=1)
        return owner.id, payment.id


async def test_admin_approve_activates_subscription(main_dp) -> None:
    await reset_database()
    owner_id, payment_id = await _seed_owner_with_pending_payment()
    admin_bot = Bot(token="000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS", session=FakeSession())

    await main_dp.feed_update(admin_bot, make_callback_update(1, data=f"admin_approve_payment:{payment_id}", user_id=ADMIN_TG_ID))

    async with session_scope() as session:
        payment = await session.get(Payment, payment_id)
        assert payment.status == PaymentStatus.APPROVED, f"وضعیت: {payment.status}"
        assert payment.reviewed_by_admin_id == ADMIN_TG_ID

        result = await session.execute(select(Subscription).where(Subscription.shop_owner_id == owner_id))
        subs = list(result.scalars().all())
        assert len(subs) == 1, "با تاییدِ پرداخت باید اشتراک فعال بشه"
        assert subs[0].is_trial is False

    print("✅ test_admin_approve_activates_subscription PASSED")


async def test_admin_approve_wallet_topup_credits_balance(main_dp) -> None:
    """پوششِ مستقیمِ مسیرِ جدید و حساس: تاییدِ پرداختی با purpose=WALLET_TOPUP از
    طریقِ همون فلوی واقعیِ تاییدِ ادمین (نه فقط فراخوانیِ مستقیمِ wallet_service)
    باید دقیقاً مبلغِ پرداخت‌شده رو به کیف‌پولِ فروشگاه‌دار اضافه کنه."""
    await reset_database()
    async with session_scope() as session:
        owner = await shop_owner_service.get_or_create_shop_owner(session, OWNER_TG_ID + 1)
        owner = await shop_owner_service.complete_registration(
            session, owner, "خریدار", "کیف‌پول", "09120000007", "walletbuyer@example.com", True, True
        )
        assert owner.wallet_balance_toman == 0
        payment = await payment_service.create_card_to_card_payment(
            session, owner, 250_000, None, purpose=PaymentPurpose.WALLET_TOPUP
        )
        owner_id, payment_id, expected_amount = owner.id, payment.id, payment.final_amount

    admin_bot = Bot(token="000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS", session=FakeSession())
    await main_dp.feed_update(admin_bot, make_callback_update(1, data=f"admin_approve_payment:{payment_id}", user_id=ADMIN_TG_ID))

    async with session_scope() as session:
        payment = await session.get(Payment, payment_id)
        assert payment.status == PaymentStatus.APPROVED

        owner = await session.get(ShopOwner, owner_id)
        assert owner.wallet_balance_toman == expected_amount, (
            f"باید دقیقاً {expected_amount} تومن به کیف‌پول اضافه بشه، نه {owner.wallet_balance_toman}"
        )

        # نباید هیچ اشتراکی هم ساخته بشه — این پرداخت هدفش شارژِ کیف‌پول بود، نه اشتراک
        result = await session.execute(select(Subscription).where(Subscription.shop_owner_id == owner_id))
        assert len(list(result.scalars().all())) == 0, "برای پرداختِ WALLET_TOPUP نباید هیچ اشتراکی ساخته بشه"

    print("✅ test_admin_approve_wallet_topup_credits_balance PASSED")


async def test_admin_reject_does_not_activate_subscription(main_dp) -> None:
    await reset_database()
    owner_id, payment_id = await _seed_owner_with_pending_payment()
    admin_bot = Bot(token="000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS", session=FakeSession())

    await main_dp.feed_update(admin_bot, make_callback_update(1, data=f"admin_reject_payment:{payment_id}", user_id=ADMIN_TG_ID))

    async with session_scope() as session:
        payment = await session.get(Payment, payment_id)
        assert payment.status == PaymentStatus.REJECTED, f"وضعیت: {payment.status}"

        result = await session.execute(select(Subscription).where(Subscription.shop_owner_id == owner_id))
        assert len(list(result.scalars().all())) == 0, "با ردِ پرداخت نباید اشتراکی فعال بشه"

    print("✅ test_admin_reject_does_not_activate_subscription PASSED")


async def test_already_reviewed_payment_cannot_be_approved_again(main_dp) -> None:
    await reset_database()
    owner_id, payment_id = await _seed_owner_with_pending_payment()
    admin_bot = Bot(token="000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS", session=FakeSession())

    await main_dp.feed_update(admin_bot, make_callback_update(1, data=f"admin_approve_payment:{payment_id}", user_id=ADMIN_TG_ID))
    async with session_scope() as session:
        result = await session.execute(select(Subscription).where(Subscription.shop_owner_id == owner_id))
        first_count = len(list(result.scalars().all()))

    # دوباره روی همون پرداختِ (الان دیگه APPROVED) کلیک می‌کنیم
    await main_dp.feed_update(admin_bot, make_callback_update(2, data=f"admin_approve_payment:{payment_id}", user_id=ADMIN_TG_ID))

    async with session_scope() as session:
        result = await session.execute(select(Subscription).where(Subscription.shop_owner_id == owner_id))
        second_count = len(list(result.scalars().all()))
        assert second_count == first_count, "کلیکِ دوباره روی پرداختِ از‌قبل‌بررسی‌شده نباید اشتراکِ دوم بسازه"

    print("✅ test_already_reviewed_payment_cannot_be_approved_again PASSED")


async def main() -> None:
    main_dp, shop_dp, bot_manager, main_bot = build_test_dispatchers()
    await test_admin_approve_activates_subscription(main_dp)
    await test_admin_approve_wallet_topup_credits_balance(main_dp)
    await test_admin_reject_does_not_activate_subscription(main_dp)
    await test_already_reviewed_payment_cannot_be_approved_again(main_dp)


if __name__ == "__main__":
    asyncio.run(main())
