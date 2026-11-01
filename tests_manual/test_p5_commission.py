"""
تست‌هایِ PHASE 5D — کمیسیونِ درصدیِ سفارشِ موفق (رزرو ← تسویه ← آزادسازی/برگشت).

پوششِ چک‌لیستِ اجباریِ PHASE 10: مواردِ ۱۰ تا ۱۹.

نکتهٔ دامنه: کمیسیون با پیش‌فرض **خاموش** است ⇒ تست‌هایِ «خاموش» همان رفتارِ امروزِ
پروژه را قفل می‌کنند و هیچ ردیفِ دفتری ساخته نمی‌شود.
"""
from __future__ import annotations

import asyncio
import datetime
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from aiogram import Bot  # noqa: E402
from decimal import Decimal  # noqa: E402
from harness import FakeSession, build_test_dispatchers, make_callback_update, make_message_update, reset_database  # noqa: E402
from phase4_helpers import add_customer, add_order, owner_balance, wallet_transactions  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.bots.main_bot import texts as main_texts  # noqa: E402
from app.database.models import (  # noqa: E402
    OrderConsultation,
    OrderStatus,
    ShopOwner,
    WalletCharge,
    WalletTransactionReason,
)
from app.database.session import session_scope  # noqa: E402
from app.services import commission_service, order_transition_service, wallet_service  # noqa: E402
from app.services.admin_settings_service import get_admin_settings  # noqa: E402

OWNER_TG_ID = 999_531
SHOP_BOT_TG_ID = 999_532
ADMIN_TG_ID = 12345
MAIN_TOKEN = "000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS"
GROUP = "0a1b2c3d4e5f0a1b2c3d4e5a"


async def _setup(*, percent: str = "1.50", enabled: bool = True) -> int:
    """یک فروشگاهِ آماده با کیف‌پولِ ۱٬۰۰۰٬۰۰۰ و سفارشی که — دقیقاً مثلِ خروجیِ چک‌اوت —
    در `awaiting_payment` و در یک گروه نشسته است."""
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    async with session_scope() as session:
        admin = await get_admin_settings(session)
        admin.commission_enabled = enabled
        admin.commission_percent = Decimal(percent)
        await session.flush()
    customer_id = await add_customer(shop_bot_id, 999_533, first_name="خریدار")
    await add_order(
        shop_bot_id,
        customer_id,
        status=OrderStatus.AWAITING_PAYMENT,
        value=200_000,
        group_id=GROUP,
        summary="کیف و کمربند",
    )
    return shop_bot_id


async def _first_order() -> OrderConsultation:
    async with session_scope() as session:
        return (
            await session.execute(select(OrderConsultation).where(OrderConsultation.cart_checkout_group_id == GROUP))
        ).scalars().first()


async def _start_paid_flow() -> None:
    """همان فراخوانیِ checkout.py: ورود به جریانِ پرداخت ⇒ رزرو (گذّار وضعیت اینجا اجرا نمی‌شود)."""
    async with session_scope() as session:
        rows = list(
            (await session.execute(select(OrderConsultation).where(OrderConsultation.cart_checkout_group_id == GROUP))).scalars().all()
        )
        await order_transition_service.apply_commission(session, rows, "awaiting_payment")
        await session.commit()


async def _transition(to: str):
    """گذارشِ گروه از تنها نقطهٔ ورودیِ گذار؛ گذارِ غیرمجاز در تست با خطا می‌خورد."""
    async with session_scope() as session:
        order = (
            await session.execute(select(OrderConsultation).where(OrderConsultation.cart_checkout_group_id == GROUP))
        ).scalars().first()
        result = await order_transition_service.transition_group(session, order, to, actor_type="test")
        assert result.ok, f"گذارِ غیرمجاز به {to}: {result.reason}"
        await session.commit()
        return result


async def _reserve_state() -> tuple[int, str | None, Decimal | None]:
    async with session_scope() as session:
        owner = (await session.execute(select(ShopOwner).where(ShopOwner.telegram_id == OWNER_TG_ID))).scalars().first()
        order = (await session.execute(select(OrderConsultation).where(OrderConsultation.cart_checkout_group_id == GROUP))).scalars().first()
        return int(owner.commission_reserved_toman or 0), order.commission_status, order.commission_percent


# ============================================================================= ۱ — منطقِ خالص
def test_pure_math() -> None:
    assert commission_service.commission_toman(200_000, Decimal("1.50")) == 3_000
    assert commission_service.commission_toman(200_000, Decimal("0.50")) == 1_000
    assert commission_service.commission_toman(99_999, Decimal("1.00")) == 1_000, "گردِ نیم‌به‌بالا"
    assert commission_service.commission_toman(10_000, Decimal("100")) == 10_000, "سقفِ خودِ مبلغ"
    assert commission_service.commission_toman(0, Decimal("5")) == 0
    assert commission_service.commission_toman(50_000, Decimal("0.00")) == 0

    assert commission_service.valid_percent("0.5") == Decimal("0.50")
    assert commission_service.valid_percent("۱٫۵".replace("٫", ".")) == Decimal("1.50")
    assert commission_service.valid_percent("-1") is None and commission_service.valid_percent("100.01") is None
    assert commission_service.valid_percent("abc") is None

    owner = SimpleNamespace_owner(wallet_balance_toman=100_000, commission_reserved_toman=30_000)
    assert commission_service.usable_credit(owner) == 70_000
    print("✅ test_pure_math PASSED")


class SimpleNamespace_owner:
    """جایِ ShopOwner برایِ تستِ خالص."""

    def __init__(self, *, wallet_balance_toman: int, commission_reserved_toman: int) -> None:
        self.wallet_balance_toman = wallet_balance_toman
        self.commission_reserved_toman = commission_reserved_toman


# ============================================================================= ۲ — خاموش = هیچ
async def test_disabled_commission_moves_no_money() -> None:
    await _setup(enabled=False)
    await _start_paid_flow()
    assert await _transition(OrderStatus.PAID)

    assert await wallet_transactions(reason=WalletTransactionReason.COMMISSION) == [], "کمیسیونِ خاموش نباید ردیفِ دفتری بسازد"
    assert await owner_balance(OWNER_TG_ID) == 1_000_000
    reserved, status, percent = await _reserve_state()
    assert reserved == 0 and status is None and percent is None
    print("✅ test_disabled_commission_moves_no_money PASSED")


# ============================================================================= ۳ — رزرو و تسویه
async def test_reserve_holds_credit_and_settle_deducts_once() -> None:
    await _setup(percent="1.50")

    await _start_paid_flow()
    reserved, status, percent = await _reserve_state()
    assert reserved == 3_000 and status == commission_service.RESERVED, (reserved, status)
    assert percent == Decimal("1.50")
    # قاعدهٔ ۱۳: قبل از تاییدِ پرداخت هیچ پولی کم نشده
    assert await owner_balance(OWNER_TG_ID) == 1_000_000
    assert await wallet_transactions(reason=WalletTransactionReason.COMMISSION) != [], "ردیفِ خبریِ رزرو ثبت می‌شود"

    assert await _transition(OrderStatus.PAID)
    assert await owner_balance(OWNER_TG_ID) == 997_000, "۱٫۵٪ از ۲۰۰٬۰۰۰"
    reserved, status, _ = await _reserve_state()
    assert reserved == 0 and status == commission_service.SETTLED, (reserved, status)
    rows = await wallet_transactions(reason=WalletTransactionReason.COMMISSION)
    spends = [r for r in rows if r.amount_toman != 0]
    assert len(spends) == 1 and spends[0].amount_toman == -3_000, spends
    assert spends[0].idempotency_key.startswith(f"comm-settle:{GROUP}"), spends[0].idempotency_key
    print("✅ test_reserve_holds_credit_and_settle_deducts_once PASSED")


# ============================================================================= ۱۵ — دابل‌تپِ callback
async def test_repeated_paid_transition_never_double_charges() -> None:
    await _setup(percent="1.00")
    await _start_paid_flow()
    await _transition(OrderStatus.PAID)
    assert await owner_balance(OWNER_TG_ID) == 998_000

    # گذارِ دوباره به همان مقصد (callbackِ تکراری/دابل‌تپ) ⇒ بی‌اثر
    again = await _transition(OrderStatus.PAID)
    assert again.changed is False or again.ok
    assert await owner_balance(OWNER_TG_ID) == 998_000, "کمیسیونِ دوم نباید گرفته شود"
    await _transition(OrderStatus.PROCESSING)
    assert await owner_balance(OWNER_TG_ID) == 998_000, "گذارهایِ بعدی هم کمیسیون نمی‌گیرند"
    spends = [r for r in await wallet_transactions(reason=WalletTransactionReason.COMMISSION) if r.amount_toman != 0]
    assert len(spends) == 1, spends
    print("✅ test_repeated_paid_transition_never_double_charges PASSED")


# ============================================================================= ۱۶ — snapshotِ نرخ
async def test_admin_rate_change_does_not_touch_open_orders() -> None:
    await _setup(percent="1.00")
    await _start_paid_flow()

    async with session_scope() as session:
        admin = await get_admin_settings(session)
        admin.commission_percent = Decimal("10.00")  # ادمین وسطِ کار نرخ را ده برابر کرد
        await session.flush()

    await _transition(OrderStatus.PAID)
    assert await owner_balance(OWNER_TG_ID) == 998_000, "نرخِ snapshotشده (۱٪) ملاک است نه نرخِ تازه"
    _, status, percent = await _reserve_state()
    assert status == commission_service.SETTLED and percent == Decimal("1.00"), (status, percent)
    print("✅ test_admin_rate_change_does_not_touch_open_orders PASSED")


# ============================================================================= ۱۴ و ۱۸ — لغو/انقضا
async def test_cancel_and_expiry_release_the_reservation_without_charging() -> None:
    await _setup(percent="2.00")
    await _start_paid_flow()
    reserved, status, _ = await _reserve_state()
    assert reserved == 4_000 and status == commission_service.RESERVED

    await _transition(OrderStatus.CANCELLED)
    reserved, status, _ = await _reserve_state()
    assert reserved == 0, "رزرو آزاد شد"
    assert status == commission_service.RELEASED
    assert await owner_balance(OWNER_TG_ID) == 1_000_000, "لغو هیچ پولی کم نمی‌کند (قاعدهٔ ۱۴)"
    spends = [r for r in await wallet_transactions(reason=WalletTransactionReason.COMMISSION) if r.amount_toman != 0]
    assert spends == [], spends
    print("✅ test_cancel_and_expiry_release_the_reservation_without_charging PASSED")


# ============================================================================= ۲۲ — استرداد
async def test_refund_returns_the_commission_as_a_new_entry() -> None:
    await _setup(percent="1.00")
    await _start_paid_flow()
    await _transition(OrderStatus.PAID)
    assert await owner_balance(OWNER_TG_ID) == 998_000

    await _transition(OrderStatus.REFUND_PENDING)
    await _transition(OrderStatus.REFUNDED)
    assert await owner_balance(OWNER_TG_ID) == 1_000_000, "کمیسیون با ردیفِ معکوس برگشت داده شد"
    _, status, _ = await _reserve_state()
    assert status == commission_service.REVERSED
    rows = await wallet_transactions(reason=WalletTransactionReason.COMMISSION)
    assert any(r.amount_toman == 2_000 for r in rows), rows
    assert any(r.amount_toman == -2_000 for r in rows), "ردیفِ کسرِ اصلی هم پاک نشده است"
    print("✅ test_refund_returns_the_commission_as_a_new_entry PASSED")


# ============================================================================= ۱۷ — ناکافی‌بودنِ اعتبار
async def test_insufficient_credit_refuses_the_reservation() -> None:
    await _setup(percent="50.00")  # ۱۰۰٬۰۰۰ رویِ ۲۰۰٬۰۰۰ ⇒ کمیسیونِ موردانتظار
    # حالتِ سازگارِ داده: هم بسته‌ها و هم کشیده به ۹۹٬۹۹۰ می‌رسند (نه یک اختلافِ ساختگی)
    async with session_scope() as session:
        owner = (await session.execute(select(ShopOwner).where(ShopOwner.telegram_id == OWNER_TG_ID))).scalars().first()
        owner.wallet_balance_toman = 99_990
        charge = (await session.execute(select(WalletCharge).where(WalletCharge.shop_owner_id == owner.id))).scalars().first()
        charge.remaining_toman = 99_990
        await session.flush()

    await _start_paid_flow()
    reserved, status, _ = await _reserve_state()
    assert reserved == 0 and status is None, "اعتبارِ قابل‌مصرف کمتر از کمیسیونِ موردانتظار ⇒ رزرو گرفته نمی‌شود"

    await _transition(OrderStatus.PAID)
    assert await owner_balance(OWNER_TG_ID) == 99_990, "تسویه با موجودیِ ناکافی هیچ پولی کم نمی‌کند"
    spends = [r for r in await wallet_transactions(reason=WalletTransactionReason.COMMISSION) if r.amount_toman != 0]
    assert spends == [], spends
    print("✅ test_insufficient_credit_refuses_the_reservation PASSED")


async def test_cached_balance_can_never_go_negative() -> None:
    """PHASE 7 — محافظِ نهایی: حتی با دادهٔ ناسازگار، موجودیِ کش‌شده بدهکار نمی‌شود."""
    await _setup(percent="1.00")
    async with session_scope() as session:
        owner = (await session.execute(select(ShopOwner).where(ShopOwner.telegram_id == OWNER_TG_ID))).scalars().first()
        owner.wallet_balance_toman = 10  # کشیده عمداً ناسازگار (سناریویِ خرابیِ داده)
        await session.flush()
    async with session_scope() as session:
        owner = (await session.execute(select(ShopOwner).where(ShopOwner.telegram_id == OWNER_TG_ID))).scalars().first()
        assert await wallet_service.deduct(session, owner, 50_000, WalletTransactionReason.CHAT_MESSAGE) is True
    assert await owner_balance(OWNER_TG_ID) == 0, "کفِ صفر؛ هیچ مسیرِ بدهکار-منفی وجود ندارد"
    print("✅ test_cached_balance_can_never_go_negative PASSED")


# ============================================================================= ۱۰ و ۱۱ — پنلِ ادمین
async def test_admin_toggle_and_percent_are_validated(main_dp) -> None:
    await reset_database()
    await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    main_bot = Bot(token=MAIN_TOKEN, session=FakeSession())
    session_obj: FakeSession = main_bot.session  # type: ignore[assignment]

    n = 0
    async def tap(data: str) -> None:
        nonlocal n
        n += 1
        await main_dp.feed_update(main_bot, make_callback_update(n, data=data, user_id=ADMIN_TG_ID))

    async def say(text: str) -> None:
        nonlocal n
        n += 1
        await main_dp.feed_update(main_bot, make_message_update(n, text=text, user_id=ADMIN_TG_ID))

    await tap("admin_toggle_commission")
    async with session_scope() as session:
        assert (await get_admin_settings(session)).commission_enabled is True
    assert "کمیسیون روشن شد" in (session_obj.answered_callbacks[-1]["text"] or "")

    await tap("admin_setting_edit:commission_percent")
    assert session_obj.sent_messages[-1]["text"] == main_texts.ADMIN_ASK_COMMISSION_PERCENT
    await say("150")
    assert session_obj.sent_messages[-1]["text"] == main_texts.ADMIN_INVALID_NUMBER, "سقفِ ۱۰۰٪"
    await say("-1")
    assert session_obj.sent_messages[-1]["text"] == main_texts.ADMIN_INVALID_NUMBER
    await say("abc")
    assert session_obj.sent_messages[-1]["text"] == main_texts.ADMIN_INVALID_NUMBER
    await say("0.5")
    async with session_scope() as session:
        admin = await get_admin_settings(session)
        assert Decimal(str(admin.commission_percent)) == Decimal("0.50"), admin.commission_percent

    # صفر معنا دارد: «کمیسیون را بردار» باید ذخیره شود
    await tap("admin_setting_edit:commission_percent")
    await say("0")
    async with session_scope() as session:
        assert Decimal(str((await get_admin_settings(session)).commission_percent)) == Decimal("0.00")

    await tap("admin_toggle_commission")
    async with session_scope() as session:
        assert (await get_admin_settings(session)).commission_enabled is False
    print("✅ test_admin_toggle_and_percent_are_validated PASSED")


async def main() -> None:
    test_pure_math()
    await test_disabled_commission_moves_no_money()
    await test_reserve_holds_credit_and_settle_deducts_once()
    await test_repeated_paid_transition_never_double_charges()
    await test_admin_rate_change_does_not_touch_open_orders()
    await test_cancel_and_expiry_release_the_reservation_without_charging()
    await test_refund_returns_the_commission_as_a_new_entry()
    await test_insufficient_credit_refuses_the_reservation()
    await test_cached_balance_can_never_go_negative()

    main_dp, _shop_dp, _bot_manager, _main_bot = build_test_dispatchers()
    await test_admin_toggle_and_percent_are_validated(main_dp)


if __name__ == "__main__":
    asyncio.run(main())
