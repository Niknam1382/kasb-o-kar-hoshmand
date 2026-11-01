"""
تست: P22 — پاک‌سازیِ دمو هرگز دادهٔ واقعی را پاک نمی‌کند (مشکلِ ۷ کاربر: «چیزهایی که تو پنل نوشتم بماند»)

باگِ مرجوب: `scripts/seed_demo.py --cleanup` ردیف‌هایِ نمایشی را با `telegram_id >= 9_600_000` و
`bot_telegram_id >= 960_000_000` می‌شمرد. شناسهٔ تلگرامِ آدم‌هایِ واقعی ۷ تا ۹ میلیارده، پس
همان دستور رویِ دیتابیسِ پر همهٔ فروشگاه‌دارها، رباتِ فعالشان، محصول‌ها و سفارش‌هایشان را
پاک می‌کرد. اولین اجرایِ واقعی فقط به‌خاطرِ خطایِ کلیدِ خارجی بی‌عمل ماند (ردیف‌هایِ واقعی به
`order_events` وصل بودند) — و همان خطا نشان داد ترتیبِ حذف هم درست نبوده.

پوشش:
۱. فروشگاهِ «واقعی» با شناسه‌هایِ درشت، سفارش/خط‌زمان/فاکتور/اعلان/آدرس/سبد — بعدِ
   پاک‌سازیِ دمو کِامِل دست‌نخورده می‌ماند (تساویِ دقیق، نه «بزرگ‌تر از»).
۲. پاک‌سازیِ محتوایِ دمو با همهٔ وابسته‌هایش بی‌خطا تمام می‌شود (ترتیبِ کلیدهایِ خارجی).
۳. پوستهٔ دمو و ردیفِ ممیزی می‌مانند (زنجیرهٔ هش نمی‌شکند) و اجرایِ دوبارهٔ `_seed`
   رباتِ دموِ دوم یا محصولِ تکراری نمی‌سازد.

اجرا: python3 tests_manual/run_one.py test_p22_seed_cleanup_safety.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests_manual"))
sys.path.insert(0, str(ROOT / "scripts"))

from sqlalchemy import func, select  # noqa: E402

import seed_demo  # noqa: E402
from harness import reset_database  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from app.database.models import (  # noqa: E402
    AuditEventType,
    AuditLogEntry,
    Cart,
    CartItem,
    ConversationMessage,
    Customer,
    CustomerAddress,
    Invoice,
    Notification,
    OrderConsultation,
    OrderEvent,
    OrderStatus,
    OrderType,
    Product,
    ShippingMethod,
    ShopBot,
    ShopOwner,
    WalletCharge,
    WalletTransaction,
)  # noqa: E402
from app.database.session import session_scope  # noqa: E402

# شناسه‌هایِ «واقعی»: هر دو از آستانه‌هایِ قدیمیِ دمو بزرگ‌ترند ⇒ نسخهٔ باگ‌دار این‌ها را دمو می‌شمرد.
REAL_OWNER_TG = 7_169_064_445
REAL_BOT_TG = 9_139_561_191
REAL_CUSTOMER_TG = 8_111_222_333


async def _count(model, *criteria) -> int:
    async with session_scope() as session:
        return int((await session.execute(select(func.count()).select_from(model).where(*criteria))).scalar_one())


async def _demo_bot_id() -> int:
    async with session_scope() as session:
        return int(
            (await session.execute(select(ShopBot.id).where(ShopBot.bot_telegram_id == seed_demo.DEMO_BOT_TG))).scalar_one()
        )


async def _cart_id(bot_id: int) -> int:
    async with session_scope() as session:
        return int((await session.execute(select(Cart.id).where(Cart.shop_bot_id == bot_id))).scalar_one())


async def _build_real_shop() -> dict:
    """فروشگاهِ واقعیِ کامل: محصول، مشتری، سفارشِ تأییدشده + خط‌زمان + فاکتور + اعلان + دفترچه‌آدرس + سبد."""
    bot_id = await seed_usable_shop(REAL_OWNER_TG, REAL_BOT_TG)
    async with session_scope() as session:
        owner = (await session.execute(select(ShopOwner).where(ShopOwner.telegram_id == REAL_OWNER_TG))).scalar_one()
        product = Product(shop_bot_id=bot_id, name="مداد", price_toman=1_000, stock_quantity=5, kind="physical")
        customer = Customer(shop_bot_id=bot_id, telegram_id=REAL_CUSTOMER_TG, platform="telegram", first_name="مشتریِ واقعی")
        session.add_all([product, customer])
        await session.flush()
        order = OrderConsultation(
            shop_bot_id=bot_id,
            customer_id=customer.id,
            product_id=product.id,
            type=OrderType.ORDER,
            summary="مداد",
            status=OrderStatus.CONFIRMED,
            quantity=2,
            estimated_value_toman=2_000,
        )
        session.add(order)
        await session.flush()
        cart = Cart(shop_bot_id=bot_id, customer_id=customer.id)
        session.add(cart)
        await session.flush()
        session.add_all(
            [
                OrderEvent(order_id=order.id, to_status="confirmed", actor_type="owner"),
                Invoice(shop_bot_id=bot_id, group_id=f"real-group-{order.id}", number="INV-REAL-1", data_json="{}"),
                Notification(chat_id=REAL_CUSTOMER_TG, text="سفارشت تأیید شد", shop_bot_id=bot_id, owner_id=owner.id, dedupe_key="real-1"),
                CustomerAddress(customer_id=customer.id, address="تهران، خیابانِ TEST، پلاکِ ۱", is_default=True),
                CartItem(cart_id=cart.id, product_id=product.id, quantity=1),
                ConversationMessage(customer_id=customer.id, role="user", content="سلام"),
            ]
        )
        await session.flush()
        return {"bot_id": bot_id, "owner_id": owner.id, "product_id": product.id, "customer_id": customer.id, "order_id": order.id}


# ============================================================================= ۱ — دادهٔ واقعی نمی‌میرد
async def test_real_accounts_survive_demo_cleanup() -> None:
    await reset_database()
    real = await _build_real_shop()
    await seed_demo._seed(500_000)
    demo_bot = await _demo_bot_id()
    assert await _count(Product, Product.shop_bot_id == demo_bot) == len(seed_demo.PRODUCTS), "دمو ساخته نشد؟"

    result = await seed_demo._cleanup()

    # فروشگاهِ واقعی باید کِامِل سرِ جایش باشد — این همان چیزی است که باگِ قدیمی پاک می‌کرد
    assert await _count(ShopOwner, ShopOwner.telegram_id == REAL_OWNER_TG) == 1
    assert await _count(ShopBot, ShopBot.bot_telegram_id == REAL_BOT_TG) == 1
    assert await _count(Product, Product.shop_bot_id == real["bot_id"]) == 1
    assert await _count(Customer, Customer.shop_bot_id == real["bot_id"]) == 1
    assert await _count(OrderConsultation, OrderConsultation.shop_bot_id == real["bot_id"]) == 1
    assert await _count(OrderEvent, OrderEvent.order_id == real["order_id"]) == 1
    assert await _count(Invoice, Invoice.shop_bot_id == real["bot_id"]) == 1
    assert await _count(Notification, Notification.shop_bot_id == real["bot_id"]) == 1
    assert await _count(CustomerAddress, CustomerAddress.customer_id == real["customer_id"]) == 1
    assert await _count(CartItem, CartItem.cart_id == (await _cart_id(real["bot_id"]))) == 1
    assert await _count(WalletTransaction, WalletTransaction.shop_owner_id == real["owner_id"]) > 0, "دفترِ کیف‌پولِ واقعی پاک شد"

    # محتوایِ دمو رفته است
    assert result["products_left"] == 0, result
    assert await _count(Product, Product.shop_bot_id == demo_bot) == 0
    assert await _count(Customer, Customer.shop_bot_id == demo_bot) == 0
    assert await _count(OrderConsultation, OrderConsultation.shop_bot_id == demo_bot) == 0
    assert await _count(ShippingMethod, ShippingMethod.shop_bot_id == demo_bot) == 0
    assert await _count(WalletCharge, WalletCharge.shop_owner_id == real["owner_id"]) > 0
    print("✅ test_real_accounts_survive_demo_cleanup PASSED")


# ============================================================================= ۲ — پوسته می‌ماند، ممیزی نمی‌شکند
async def test_shell_and_audit_are_kept_and_reseed_is_idempotent() -> None:
    await reset_database()
    await seed_demo._seed(500_000)
    demo_bot = await _demo_bot_id()
    async with session_scope() as session:
        session.add(Notification(chat_id=1, text="تست", shop_bot_id=demo_bot, dedupe_key="demo-keep"))
    # رویدادِ ممیزیِ وصل به رباتِ دمو ⇒ پاک‌کردنِ ربات هم کلیدِ خارجی را می‌شکند و هم زنجیرهٔ هش را
    async with session_scope() as session:
        from app.services import audit_log_service

        await audit_log_service.log(session, AuditEventType.SHOP_SUSPENDED, shop_bot_id=demo_bot, details="دمو")

    result = await seed_demo._cleanup()
    assert result["shell_kept"] is True, result
    assert await _count(ShopBot, ShopBot.bot_telegram_id == seed_demo.DEMO_BOT_TG) == 1, "پوستهٔ دمو حذف شد ⇒ ممیزی بی‌ربط می‌ماند"
    assert await _count(AuditLogEntry, AuditLogEntry.shop_bot_id == demo_bot) == 1, "ردیفِ ممیزی پاک شد (زنجیرهٔ هش می‌شکند)"
    assert await _count(Notification, Notification.shop_bot_id == demo_bot) == 0
    async with session_scope() as session:
        owner = (await session.execute(select(ShopOwner).where(ShopOwner.telegram_id == seed_demo.DEMO_OWNER_TG))).scalar_one()
        assert owner.wallet_balance_toman == 0, owner.wallet_balance_toman
        assert await _count(WalletTransaction, WalletTransaction.shop_owner_id == owner.id) == 0

    # اجرایِ دوباره از همان پوسته استفاده می‌کند، نه رباتِ دموِ دوم
    await seed_demo._seed(500_000)
    assert await _count(ShopBot, ShopBot.bot_telegram_id == seed_demo.DEMO_BOT_TG) == 1
    assert await _count(ShopOwner, ShopOwner.telegram_id == seed_demo.DEMO_OWNER_TG) == 1
    assert await _count(Product, Product.shop_bot_id == demo_bot) == len(seed_demo.PRODUCTS)
    assert await _count(ShippingMethod, ShippingMethod.shop_bot_id == demo_bot) == len(seed_demo.SHIPPING_METHODS)
    print("✅ test_shell_and_audit_are_kept_and_reseed_is_idempotent PASSED")


# ============================================================================= ۳ — دامنهٔ جست‌وجو
async def test_demo_lookup_is_exact_not_a_range() -> None:
    """رجرشنِ اصلی: ربات/فروشگاه‌دارِ واقعی هرگز به‌عنوانِ دمو برگردانده نمی‌شوند."""
    await reset_database()
    real = await _build_real_shop()
    async with session_scope() as session:
        owner, bot = await seed_demo._find_demo(session)
    assert owner is None and bot is None, "فروشگاهِ واقعی با شناسهٔ درشت «دمو» شناخته شد"
    assert real["bot_id"] > 0
    # حتی اگر یکِ فروشگاه‌دارِ واقعی از آستانهٔ قدیمی بزرگ‌تر باشد، `_cleanup` نباید به او دست بزند
    await seed_demo._cleanup()
    assert await _count(ShopOwner, ShopOwner.telegram_id == REAL_OWNER_TG) == 1
    assert await _count(ShopBot, ShopBot.id == real["bot_id"]) == 1
    print("✅ test_demo_lookup_is_exact_not_a_range PASSED")


async def main() -> None:
    await test_real_accounts_survive_demo_cleanup()
    await test_shell_and_audit_are_kept_and_reseed_is_idempotent()
    await test_demo_lookup_is_exact_not_a_range()


if __name__ == "__main__":
    asyncio.run(main())
