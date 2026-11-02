"""
تست: P20-A/B — درستیِ پول و باگ‌هایِ رفتاریِ رفع‌شده

پوشش (هر مورد یک باگِ تأییدشده در ممیزیِ منطقیِ پروژه):
۱. تاییدِ دوبارهٔ یک پرداخت (دو ادمین، وب‌هوکِ تکراری، رفرشِ صفحهٔ بازگشت) ⇒ یک شارژ، یک ردیفِ دفتر.
۲. کلیدِ ایدِمپوتنسیِ ردیفِ شارژ از شناسهٔ پرداخت ساخته می‌شود ⇒ سدِ دوم سرِ خودِ دیتابیس است.
۳. رزروِ هم‌زمانِ آخرینِ واحدِ یک محصول ⇒ فقط یک سفارش رزرو می‌کند (قفلِ سطریِ Product).
۴. خروجِ گروه از جریانِ پرداخت (تاییدِ دستی ⇒ pending) ⇒ holdِ کمیسیون آزاد می‌شود (نشتِ قبلی).
۵. تسویهٔ کمیسیون با موجودیِ ناکافی ⇒ hold آزاد می‌شود و ردیفِ پولیِ جعلی ساخته نمی‌شود.
۶. هدیهٔ اعتبار: خارج از بازه ⇒ رد؛ بدونِ تایید ⇒ هیچ نوشتن؛ بعد از تایید ⇒ دقیقاً یک شارژ با مرجعِ gift:.
۷. دابل‌تپِ «فعال‌سازیِ آزمایشی» ⇒ یک‌بار اعتبار.
۸. برشِ کپشن: متنِ تحویلِ دیجیتال و کپشنِ عکسِ فورواردشده از ۱۰۲۴ عبور نمی‌کنند (قبلاً BadRequest
   می‌داد و پیام برایِ همیشه به مشتری/فروشگاه‌دار نمی‌رسید).

اجرا: python3 tests_manual/test_p20_money_integrity.py
"""
from __future__ import annotations

import asyncio
import sys
from decimal import Decimal

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from sqlalchemy import select  # noqa: E402
from sqlalchemy.exc import IntegrityError  # noqa: E402

from harness import build_test_dispatchers, reset_database  # noqa: E402
from phase4_helpers import Chat, add_customer, add_order, owner_balance, wallet_transactions  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from app.bots.shop_bot import texts as shop_texts  # noqa: E402
from app.database.models import (  # noqa: E402
    OrderConsultation,
    OrderStatus,
    OrderType,
    PaymentPurpose,
    Product,
    ShopOwner,
    WalletCharge,
    WalletTransactionReason,
)
from app.database.session import session_scope  # noqa: E402
from app.services import (  # noqa: E402
    commission_service,
    digital_service,
    order_service,
    order_state,
    order_transition_service,
    payment_service,
    product_service,
    shop_owner_service,
    wallet_service,
)
from app.services.admin_settings_service import get_admin_settings  # noqa: E402
from app.utils.text_limits import TELEGRAM_CAPTION_LIMIT  # noqa: E402

ADMIN_TG_ID = 12345
OWNER_TG_ID = 999_601
SHOP_BOT_TG_ID = 999_602
CUSTOMER_TG_ID = 999_603
GROUP = "feedfacecafebeef0000111122223333"
TOPUP_TOMAN = 100_000


async def _seed_owner(balance_toman: int = 1_000_000) -> tuple[int, int]:
    """(شناسهٔ رباتِ فروشگاه، شناسهٔ فروشگاه‌دار) برایِ یک فروشگاهِ آماده با موجودیِ دلخواه."""
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID, initial_balance_toman=balance_toman)
    async with session_scope() as session:
        owner_id = (await session.execute(select(ShopOwner.id).where(ShopOwner.telegram_id == OWNER_TG_ID))).scalar_one()
    return shop_bot_id, owner_id


async def _charges(owner_id: int) -> list[WalletCharge]:
    async with session_scope() as session:
        return list((await session.execute(select(WalletCharge).where(WalletCharge.shop_owner_id == owner_id))).scalars().all())


async def _rows_in(session):
    return list((await session.execute(select(OrderConsultation).where(OrderConsultation.cart_checkout_group_id == GROUP))).scalars().all())


async def _group_rows() -> list[OrderConsultation]:
    async with session_scope() as session:
        return await _rows_in(session)


async def _hold_and_status() -> tuple[int, str | None]:
    async with session_scope() as session:
        owner = (await session.execute(select(ShopOwner).where(ShopOwner.telegram_id == OWNER_TG_ID))).scalar_one()
        order = (await _rows_in(session))[0]
        return int(owner.commission_reserved_toman or 0), order.commission_status


async def _enter_payment_flow(percent: str, balance: int) -> None:
    """گروهی در `awaiting_payment` با کمیسیونِ روشن، و رزروِ همان‌طور که چک‌اوت انجام می‌دهد."""
    shop_bot_id, _owner_id = await _seed_owner(balance)
    customer_id = await add_customer(shop_bot_id, CUSTOMER_TG_ID)
    async with session_scope() as session:
        admin = await get_admin_settings(session)
        admin.commission_enabled = True
        admin.commission_percent = Decimal(percent)
        await session.flush()
    await add_order(
        shop_bot_id,
        customer_id,
        status=OrderStatus.AWAITING_PAYMENT,
        value=200_000,
        group_id=GROUP,
        summary="سفارشِ کمیسیونی",
    )
    async with session_scope() as session:
        rows = await _rows_in(session)
        await order_transition_service.apply_commission(session, rows, order_state.AWAITING_PAYMENT)
        await session.commit()


# ============================================================================= ۱ و ۲ — پرداختِ دوباره‌تاییدشده
async def test_payment_approved_twice_credits_once() -> None:
    _shop_bot_id, owner_id = await _seed_owner()
    async with session_scope() as session:
        owner = await shop_owner_service.get_by_id(session, owner_id)
        payment = await payment_service.create_card_to_card_payment(
            session, owner, TOPUP_TOMAN, None, purpose=PaymentPurpose.WALLET_TOPUP
        )
        payment_id = payment.id
        final_amount = payment.final_amount
        balance_before = owner.wallet_balance_toman

    async with session_scope() as session:
        pay = await payment_service.get_by_id(session, payment_id)
        first, _reward = await payment_service.approve_payment(session, pay, ADMIN_TG_ID)
        assert first is not None, "تاییدِ اول باید اثر بسازد"

    async with session_scope() as session:
        pay = await payment_service.get_by_id(session, payment_id)
        second, _reward2 = await payment_service.approve_payment(session, pay, ADMIN_TG_ID)

    assert second is None, "تاییدِ دوم (وب‌هوکِ تکراری/دو ادمین/رفرشِ صفحه) نباید اثر بسازد"
    charges = await _charges(owner_id)
    assert sum(1 for c in charges if c.amount_toman == final_amount) == 1, [c.amount_toman for c in charges]
    rows = [t for t in await wallet_transactions(WalletTransactionReason.TOPUP) if t.payment_id == payment_id]
    assert len(rows) == 1, rows
    assert rows[0].idempotency_key == f"charge:payment:{payment_id}:owner:{owner_id}", rows[0].idempotency_key
    assert await owner_balance(OWNER_TG_ID) == balance_before + final_amount
    print("✅ test_payment_approved_twice_credits_once PASSED")


async def test_same_charge_reference_cannot_be_written_twice() -> None:
    _shop_bot_id, owner_id = await _seed_owner()
    raised = False
    async with session_scope() as session:
        owner = await shop_owner_service.get_by_id(session, owner_id)
        await wallet_service.add_charge(session, owner, 20_000, reason=WalletTransactionReason.TRIAL, reference="trial")
        await session.flush()
        try:
            await wallet_service.add_charge(session, owner, 20_000, reason=WalletTransactionReason.TRIAL, reference="trial")
            await session.flush()
        except IntegrityError:
            raised = True
            await session.rollback()  # تراکنش بعد از خطایِ DB دیگر قابلِ استفاده نیست (session_scope هم همین را می‌خواهد)
    assert raised, "کلیدِ ایدِمپوتنسی باید جلویِ دومینِ شارژِ همان رویدادِ واحد را بگیرد"
    print("✅ test_same_charge_reference_cannot_be_written_twice PASSED")


# ============================================================================= ۳ — موجودیِ آخرینِ واحد
async def test_concurrent_reservation_of_last_unit_sells_once() -> None:
    shop_bot_id, _owner_id = await _seed_owner()
    customer_a = await add_customer(shop_bot_id, CUSTOMER_TG_ID)
    customer_b = await add_customer(shop_bot_id, CUSTOMER_TG_ID + 1)
    async with session_scope() as session:
        product = await product_service.create_product(session, shop_bot_id, "آخرینِ واحد", None, 50_000, None, stock_quantity=1)
        product_id = product.id

    async def _buy(customer_id: int) -> bool:
        async with session_scope() as session:
            order = await order_service.create_order(
                session, shop_bot_id, customer_id, OrderType.ORDER, "خریدِ هم‌زمان", 50_000, product_id, 1
            )
            return bool(order.stock_reserved)

    results = await asyncio.gather(_buy(customer_a), _buy(customer_b))
    assert sum(results) == 1, f"فقط یک نفر باید آخرینِ واحد را رزرو کند: {results}"
    async with session_scope() as session:
        row = await session.get(Product, product_id)
        assert row.reserved_quantity == 1 and row.stock_quantity == 1, (row.reserved_quantity, row.stock_quantity)
    print("✅ test_concurrent_reservation_of_last_unit_sells_once PASSED")


# ============================================================================= ۴ — نشتِ hold در تاییدِ دستی
async def test_manual_confirmation_releases_the_commission_hold() -> None:
    await _enter_payment_flow("5.00", 1_000_000)
    reserved, status = await _hold_and_status()
    assert reserved == 10_000 and status == "reserved", (reserved, status)

    # «وجه در حسابِ خودِ فروشگاه نشست» ⇒ گذار به pending. کمیسیون فقط بعد از پرداختِ
    # راستی‌آزمایی‌شده در سرور گرفته می‌شود، پس اینجا باید رزرو *آزاد* شود نه اینکه مسکوت بماند.
    async with session_scope() as session:
        rows = await _rows_in(session)
        result = await order_transition_service.transition_group(session, rows[0], order_state.PENDING, actor_type="test")
        assert result.ok, result.reason
        await session.commit()

    reserved, status = await _hold_and_status()
    assert reserved == 0, f"hold رویِ کیف‌پول مسکوت ماند: {reserved}"
    assert status == "released", status
    money_rows = [t for t in await wallet_transactions(WalletTransactionReason.COMMISSION) if int(t.amount_toman) != 0]
    assert not money_rows, "تسویه‌ای در کار نبوده ⇒ هیچ ردیفِ پولیِ کمیسیون نباید باشد"
    print("✅ test_manual_confirmation_releases_the_commission_hold PASSED")


# ============================================================================= ۵ — تسویه با موجودیِ ناکافی
async def test_settle_with_insufficient_credit_releases_hold() -> None:
    await _enter_payment_flow("50.00", 200_000)  # کمیسیون ۱۰۰٬۰۰۰ ⇒ رزرو موفق
    reserved, _status = await _hold_and_status()
    assert reserved == 100_000, reserved

    # موجودی بینِ رزرو و تسویه خرج می‌شود (همان چیزی که در عمل می‌افتد: فروشگاه در
    # جریانِ پرداخت، پاسخِ AI مصرف کرده) ⇒ تسویه باید شکست بخورد.
    async with session_scope() as session:
        owner = (await session.execute(select(ShopOwner).where(ShopOwner.telegram_id == OWNER_TG_ID))).scalar_one()
        assert await wallet_service.deduct(session, owner, 180_000, WalletTransactionReason.CHAT_MESSAGE)
        await session.commit()

    async with session_scope() as session:
        rows = await _rows_in(session)
        owner = (await session.execute(select(ShopOwner).where(ShopOwner.telegram_id == OWNER_TG_ID))).scalar_one()
        admin = await get_admin_settings(session)
        result = await commission_service.settle(session, owner_id=owner.id, group_key=GROUP, rows=rows, admin_settings=admin)
        await session.commit()

    assert result.changed is False and result.reason == "insufficient", result
    reserved, status = await _hold_and_status()
    assert reserved == 0, f"بعد از شکستِ تسویه hold باید آزاد شود: {reserved}"
    assert status == "released", status
    money_rows = [t for t in await wallet_transactions(WalletTransactionReason.COMMISSION) if int(t.amount_toman) != 0]
    assert not money_rows, "پولی گرفته نشده ⇒ ردیفِ پولیِ کمیسیون نباید ساخته شود"
    print("✅ test_settle_with_insufficient_credit_releases_hold PASSED")


# ============================================================================= ۶ — هدیهٔ اعتبار
async def test_gift_requires_valid_range_and_confirmation(main_dp) -> None:
    _shop_bot_id, owner_id = await _seed_owner()
    before = await owner_balance(OWNER_TG_ID)
    admin = Chat(main_dp, ADMIN_TG_ID)

    await admin.tap(f"admin_owner_gift:{owner_id}")
    await admin.say("200000000")
    assert admin.last_text.startswith("مبلغِ هدیه باید بینِ"), admin.last_text
    assert await owner_balance(OWNER_TG_ID) == before, "خارج از بازه ⇒ هیچ نوشتن"

    await admin.say("500000")
    assert "تاییدِ اعطای هدیه" in admin.last_text and "۵۰۰٬۰۰۰" in admin.last_text, admin.last_text
    assert "تومان تومان" not in admin.last_text, admin.last_text
    datas = {b.callback_data for row in admin.last_markup.inline_keyboard for b in row}
    assert {"admin_gift_confirm", "admin_gift_cancel"} <= datas, datas
    assert await owner_balance(OWNER_TG_ID) == before, "بدونِ تایید، هدیه داده نمی‌شود"

    await admin.tap("admin_gift_cancel")
    assert admin.last_edit_text == "هدیه داده نشد.", admin.last_edit_text
    assert await owner_balance(OWNER_TG_ID) == before

    await admin.tap(f"admin_owner_gift:{owner_id}")
    await admin.say("500000")
    await admin.tap("admin_gift_confirm")
    assert await owner_balance(OWNER_TG_ID) == before + 500_000
    grants = await wallet_transactions(WalletTransactionReason.ADMIN_GRANT)
    assert len(grants) == 1 and (grants[0].reference or "").startswith("gift:"), grants
    await admin.tap("admin_gift_confirm")  # دابل‌تپِ همان دکمه
    assert await owner_balance(OWNER_TG_ID) == before + 500_000, "تاییدِ دوباره نباید دوباره اعتبار بسازد"
    print("✅ test_gift_requires_valid_range_and_confirmation PASSED")


# ============================================================================= ۷ — اعتبارِ آزمایشی
async def test_trial_credit_double_tap_grants_once(main_dp) -> None:
    await reset_database()
    fresh_id = 999_611
    async with session_scope() as session:
        await shop_owner_service.get_or_create_shop_owner(session, fresh_id)
    async with session_scope() as session:
        owner = await shop_owner_service.get_by_telegram_id(session, fresh_id)
        owner_id = owner.id
    assert len(await _charges(owner_id)) == 0

    user = Chat(main_dp, fresh_id)
    await user.tap("activate_trial")
    await user.tap("activate_trial")
    charges = await _charges(owner_id)
    assert len(charges) == 1, f"اعتبارِ آزمایشی باید یک‌بار داده شود: {len(charges)}"
    print("✅ test_trial_credit_double_tap_grants_once PASSED")


# ============================================================================= ۸ — برشِ کپشن
async def test_long_captions_are_clipped_not_dropped() -> None:
    shop_bot_id, _owner_id = await _seed_owner()
    async with session_scope() as session:
        pool_product = await product_service.create_product(session, shop_bot_id, "کدِ فعال‌سازی", None, 10_000, None)
        pool_product.digital_delivery = "code_pool"
        pool_product.digital_instructions = "ب" * 4000
        file_product = await product_service.create_product(session, shop_bot_id, "کتابچه", None, 10_000, None)
        file_product.digital_delivery = "file"
        file_product.digital_instructions = "ب" * 4000
        await session.flush()
        pool_id, file_id = pool_product.id, file_product.id

    async with session_scope() as session:
        pool_row = await session.get(Product, pool_id)
        text = digital_service.build_delivery_text(pool_row, ["ABC-123", "DEF-456"])
        file_row = await session.get(Product, file_id)
        file_text = digital_service.build_delivery_text(file_row, [])
    assert len(text) <= TELEGRAM_CAPTION_LIMIT, len(text)
    assert "ABC-123" in text and "DEF-456" in text, "کدِ مشتری نباید بریده شود (راهنما اول قربانیِ برش است)"
    assert len(file_text) <= TELEGRAM_CAPTION_LIMIT, len(file_text)
    assert file_text.endswith("…"), "کپشنِ بریده‌شده باید علامتِ ناقص‌بودن داشته باشد"

    caption = shop_texts.customer_photo_forward_caption("مشتریِ پرحرف", "\n\nمتنِ همراهِ عکس: " + "ی" * 3000)
    assert len(caption) <= TELEGRAM_CAPTION_LIMIT, len(caption)
    assert caption.endswith("…"), "برش‌خورده باید علامتِ «…» داشته باشد"

    short = shop_texts.customer_photo_forward_caption("علی", "\n\nمتنِ همراهِ عکس: سلام")
    assert short == "📸 مشتری «علی» یه عکس فرستاد.\n\nمتنِ همراهِ عکس: سلام", short
    print("✅ test_long_captions_are_clipped_not_dropped PASSED")


async def main() -> None:
    main_dp, _shop_dp, _bot_manager, _main_bot = build_test_dispatchers()
    await test_payment_approved_twice_credits_once()
    await test_same_charge_reference_cannot_be_written_twice()
    await test_concurrent_reservation_of_last_unit_sells_once()
    await test_manual_confirmation_releases_the_commission_hold()
    await test_settle_with_insufficient_credit_releases_hold()
    await test_gift_requires_valid_range_and_confirmation(main_dp)
    await test_trial_credit_double_tap_grants_once(main_dp)
    await test_long_captions_are_clipped_not_dropped()


if __name__ == "__main__":
    asyncio.run(main())
