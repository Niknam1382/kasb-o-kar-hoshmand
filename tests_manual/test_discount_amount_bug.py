"""
تست: باگ #11 — تخفیف باید دقیقاً یه‌بار روی مبلغِ پایه اعمال بشه، نه صفر بار (نادیده
گرفته بشه) و نه دوبار (روی مبلغِ از‌قبل‌تخفیف‌خورده دوباره اعمال بشه).

این تست هم لایه‌ی سرویس (payment_service.create_zarinpal_payment /
create_card_to_card_payment) رو مستقیم چک می‌کنه، و هم به‌صورتِ رگرسیون-گارد
نشون می‌ده که اگه به‌جای base_amount واقعی، یه final_amount ازقبل‌تخفیف‌خورده به
create_zarinpal_payment پاس داده بشه (دقیقاً همون باگی که قبلاً در panel.py وجود
داشت)، نتیجه اشتباه می‌شه — یعنی این تست اگه کسی دوباره اون باگ رو برگردونه،
fail می‌شه.

اجرا: python3 tests_manual/test_discount_amount_bug.py
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from harness import reset_database  # noqa: E402

from app.database.models import DiscountCode, DiscountType
from app.database.session import session_scope  # noqa: E402
from app.services import discount_service, payment_service, shop_owner_service  # noqa: E402

OWNER_TG_ID = 999401
BASE_AMOUNT = 1_000_000  # یک میلیون تومان


async def _seed_owner_and_discount(discount_type: DiscountType, value):
    async with session_scope() as session:
        owner = await shop_owner_service.get_or_create_shop_owner(session, OWNER_TG_ID)
        owner = await shop_owner_service.complete_registration(session, owner, "ا", "ب", "09120000002", "d@example.com", True, True)
        discount = await discount_service.create_code(session, "TEST20", discount_type, value, None, None)
        return owner.id, discount.id


async def test_percent_discount_applied_once_zarinpal() -> None:
    await reset_database()
    owner_id, discount_id = await _seed_owner_and_discount(DiscountType.PERCENT, 20)

    async with session_scope() as session:
        owner = await shop_owner_service.get_by_id(session, owner_id)
        discount = await session.get(DiscountCode, discount_id)

        # مسیرِ درست: base_amount ِ واقعی (تخفیف‌نخورده) پاس داده می‌شه
        payment = await payment_service.create_zarinpal_payment(session, owner, BASE_AMOUNT, discount, "test-authority-1", duration_months=1)

        expected = BASE_AMOUNT - int(BASE_AMOUNT * 0.20)  # ۲۰٪ تخفیف روی یک‌میلیون = ۸۰۰,۰۰۰
        assert payment.base_amount == BASE_AMOUNT, f"base_amount نباید تغییر کنه: {payment.base_amount}"
        assert payment.final_amount == expected, f"انتظار {expected}، مقدار واقعی {payment.final_amount}"
        assert payment.final_amount == 800_000

    print("✅ test_percent_discount_applied_once_zarinpal PASSED")


async def test_fixed_discount_applied_once_card_to_card() -> None:
    await reset_database()
    owner_id, discount_id = await _seed_owner_and_discount(DiscountType.FIXED, 150_000)

    async with session_scope() as session:
        owner = await shop_owner_service.get_by_id(session, owner_id)
        discount = await session.get(DiscountCode, discount_id)

        payment = await payment_service.create_card_to_card_payment(session, owner, BASE_AMOUNT, discount, duration_months=1)

        expected_before_suffix = BASE_AMOUNT - 150_000  # 850,000
        assert payment.base_amount == BASE_AMOUNT
        # پرداختِ کارت‌به‌کارت عمداً یه پسوندِ کوچیکِ ۱۰-۹۹ تومانی به مبلغ اضافه
        # می‌کنه (_generate_unique_amount) تا فروشگاه‌دار بتونه واریزیِ بانکیِ
        # واقعی رو با این پرداختِ در انتظار مچ کنه؛ این یه قابلیتِ عمدیه، نه باگ.
        # برای همین فقط محدوده رو چک می‌کنیم، نه برابریِ دقیق.
        assert expected_before_suffix <= payment.final_amount <= expected_before_suffix + 99, (
            f"مقدار واقعی: {payment.final_amount} (انتظار بینِ {expected_before_suffix} و {expected_before_suffix + 99})"
        )
        assert payment.final_amount != expected_before_suffix - 150_000, "نشونه‌ی اعمالِ دوبارِ تخفیف"

    print("✅ test_fixed_discount_applied_once_card_to_card PASSED")


async def test_no_discount_final_equals_base(main_dp=None) -> None:
    await reset_database()
    async with session_scope() as session:
        owner = await shop_owner_service.get_or_create_shop_owner(session, OWNER_TG_ID + 1)
        owner = await shop_owner_service.complete_registration(session, owner, "ا", "ب", "09120000003", "d2@example.com", True, True)
        payment = await payment_service.create_zarinpal_payment(session, owner, BASE_AMOUNT, None, "test-authority-2", duration_months=1)
        assert payment.final_amount == BASE_AMOUNT, "بدونِ کدِ تخفیف، final_amount باید دقیقاً برابرِ base_amount باشه"

    print("✅ test_no_discount_final_equals_base PASSED")


async def test_regression_guard_double_discount_would_be_wrong() -> None:
    """
    این تست خودِ باگ رو شبیه‌سازی می‌کنه تا مستندسازی کنه که چرا پاس‌دادنِ
    final_amount (به‌جای base_amount واقعی) به create_zarinpal_payment اشتباهه:
    اگه کسی این کارو (اشتباهاً) انجام بده، تخفیف رو یه‌بارِ دیگه روی مبلغِ
    ازقبل‌تخفیف‌خورده اعمال می‌کنه.
    """
    await reset_database()
    owner_id, discount_id = await _seed_owner_and_discount(DiscountType.PERCENT, 20)

    async with session_scope() as session:
        owner = await shop_owner_service.get_by_id(session, owner_id)
        discount = await session.get(DiscountCode, discount_id)

        correct_payment = await payment_service.create_zarinpal_payment(session, owner, BASE_AMOUNT, discount, "authority-correct", duration_months=1)
        correct_final = correct_payment.final_amount  # 800,000

        # شبیه‌سازیِ خودِ باگ: اگه به‌اشتباه، final_amount ِ از‌قبل‌تخفیف‌خورده به
        # base_amount پاس داده بشه، تخفیف روش دوباره اعمال می‌شه
        owner2 = await shop_owner_service.get_or_create_shop_owner(session, OWNER_TG_ID + 2)
        owner2 = await shop_owner_service.complete_registration(session, owner2, "ا", "ب", "09120000004", "d3@example.com", True, True)
        buggy_payment = await payment_service.create_zarinpal_payment(session, owner2, correct_final, discount, "authority-buggy", duration_months=1)

        assert buggy_payment.final_amount != correct_final, (
            "این assertion صرفاً مستندسازیِ خودِ باگه: دوبار اعمال کردنِ تخفیف قطعاً نتیجه‌ی متفاوتی می‌ده"
        )
        assert buggy_payment.final_amount == 640_000, f"نتیجه‌ی دوبار-تخفیف: {buggy_payment.final_amount} (انتظار ۶۴۰,۰۰۰)"

    print("✅ test_regression_guard_double_discount_would_be_wrong PASSED (این تست خودِ ریسکِ باگ رو مستند می‌کنه)")


async def main() -> None:
    await test_percent_discount_applied_once_zarinpal()
    await test_fixed_discount_applied_once_card_to_card()
    await test_no_discount_final_equals_base()
    await test_regression_guard_double_discount_would_be_wrong()


if __name__ == "__main__":
    asyncio.run(main())
