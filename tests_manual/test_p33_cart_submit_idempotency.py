"""
تست: P33-B — ایدبمپوتنتیِ دیتابیسیِ گذارِ سبد←سفارش (دابل‌تپ = یکِ سفارش)

باگِ ریشه‌دار: مهارِ دابل‌تپ در `checkout.cart_checkout_confirm` بر اتمیک‌بودنِ
`MemoryStorage` تکیه داشت (کامنتِ خودِ کد: «state.clear() قبل از هر I/O»). با نگهدارندهٔ
FSMِ دیتابیسی آن مهار از کار می‌افتد و دو سفارش ساخته می‌شد — MEASURED در بازاجرای
`test_checkout_c3.py` با `FSM_STORAGE=postgres`.

رفع: هر پیش‌نمایش نشانه می‌گیرد و قبلِ ساختِ سفارش، آن نشانه رویِ سطرِ سبد با یکِ UPDATE
در تراکنشِ *کوتاهِ جدا* ادعا می‌شود. چرا سشنِ جدا: تلاشِ اول همان ادعا را داخلِ تراکنشِ
 اصلی گذاشت و با `FOR UPDATE`هایِ محصول بن‌بست ساخت (`DeadlockDetectedError`، §P33).

سنجه‌هایِ این فایل:
۱. دو ادعایِ هم‌زمان با یکِ نشانه ⇒ دقیقاً یکِ برنده (این همان حالتِ دابل‌تپ است و
   برخلافِ زمانِ واقعی، قطعی است: predicate بعد ازِ قفلِ سطر دوباره ارزیابی می‌شود)
۲. نشانهٔ دیگر ⇒ ادعا می‌شود (پیش‌نمایشِ تازه قفل نمی‌ماند)
۳. نشانهٔ تهی ⇒ هیچ ادعایی پذیرفته نمی‌شود

اجرا: python3 tests_manual/run_one.py test_p33_cart_submit_idempotency.py
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from harness import reset_database  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from sqlalchemy import func, select  # noqa: E402

from app.database.models import Cart, Customer  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import cart_service, customer_service  # noqa: E402

OWNER_TG_ID = 999401
SHOP_BOT_TG_ID = 999402
CUSTOMER_TG_ID = 999403


async def _cart_id(shop_bot_id: int) -> int:
    async with session_scope() as session:
        customer = await customer_service.get_or_create_customer(session, shop_bot_id, CUSTOMER_TG_ID, "مشتری", None)
        cart = await cart_service.get_or_create_cart(session, shop_bot_id, customer.id)
        await session.commit()
        return int(cart.id)


async def test_two_concurrent_claims_of_the_same_nonce_have_one_winner() -> None:
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    cart_id = await _cart_id(shop_bot_id)

    results = await asyncio.gather(
        cart_service.claim_submit_token(cart_id, "nonce-ab12"),
        cart_service.claim_submit_token(cart_id, "nonce-ab12"),
        cart_service.claim_submit_token(cart_id, "nonce-ab12"),
    )
    assert sum(1 for ok in results if ok) == 1, f"دابل‌تپ باید فقط یکِ برنده داشته باشد؛ شد {results}"
    print("✅ test_two_concurrent_claims_of_the_same_nonce_have_one_winner PASSED")


async def test_a_fresh_nonce_is_claimable_again() -> None:
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID + 1, SHOP_BOT_TG_ID + 1)
    cart_id = await _cart_id(shop_bot_id)

    assert await cart_service.claim_submit_token(cart_id, "nonce-first"), "اولینِ ادعا باید قبول شود"
    assert not await cart_service.claim_submit_token(cart_id, "nonce-first"), "تکرارِ همان نشانه باید رد شود"
    assert await cart_service.claim_submit_token(cart_id, "nonce-second"), (
        "پیش‌نمایشِ تازه (نشانهٔ تازه) نباید به‌خاطرِ ادعایِ قبلی قفل بماند"
    )
    async with session_scope() as session:
        token = await session.scalar(select(Cart.submit_token).where(Cart.id == cart_id))
    assert token == "nonce-second", f"آخرینِ نشانه باید ثبت می‌ماند؛ شد {token!r}"

    async with session_scope() as session:
        customers = int((await session.scalar(select(func.count()).select_from(Customer).where(Customer.shop_bot_id == shop_bot_id))) or 0)
    assert customers == 1, f"سبد/سشن نباید مشتریِ تکراری بسازد؛ شد {customers}"
    print("✅ test_a_fresh_nonce_is_claimable_again PASSED")


async def test_empty_nonce_is_never_claimed() -> None:
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID + 2, SHOP_BOT_TG_ID + 2)
    cart_id = await _cart_id(shop_bot_id)
    assert not await cart_service.claim_submit_token(cart_id, ""), "نشانهٔ تهی نباید پذیرفته شود"
    assert not await cart_service.claim_submit_token(cart_id, ""), "دوباره هم نباید"
    print("✅ test_empty_nonce_is_never_claimed PASSED")


async def main() -> None:
    await test_two_concurrent_claims_of_the_same_nonce_have_one_winner()
    await test_a_fresh_nonce_is_claimable_again()
    await test_empty_nonce_is_never_claimed()


if __name__ == "__main__":
    asyncio.run(main())
