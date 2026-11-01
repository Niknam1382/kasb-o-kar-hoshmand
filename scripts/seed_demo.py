"""دادهٔ نمایشی برایِ تستِ دستی (P21-D · F6).

چرا لازم بود: بعد از ریستِ دیتابیس، پنلِ ادمین و پنلِ فروشگاه‌دار «خالی» است و برایِ دیدنِ
هر صفحه باید دستی محصول/مشتری/سفارش ساخت. این اسکریپت همان‌ها را می‌سازد تا مسیرهایِ واقعی
(لیستِ محصول، آمار، CRM، اخطارِ موجودی، پیگیریِ سفارشِ مشتری) یک‌باره دیده شوند.

ایمنی (عمدی):
- تا `SEED_DEMO_CONFIRM=1` ست نشود اجرا نمی‌شود.
- رباتِ دمو `is_active=False` است ⇒ هرگز با توکنِ جعلی به تلگرام وصل نمی‌شود و ترافیکِ
  واقعیِ رباتِ تو را نمی‌دزدد.
- هیچ فراخوانیِ شبکه‌ای (AI/تلگرام/بله/پرداخت/پیامک) ندارد.
- ردیف‌ها با شناسه‌هایِ ساختگیِ دمو ساخته می‌شوند و `--cleanup` همان‌ها را *با تساویِ دقیقِ همان شناسه‌ها* پاک می‌کند (نه «بزرگ‌تر از»): شناسهٔ تلگرامِ واقعی ۷ تا ۹ میلیارده و مقایسهٔ «≥» یعنی پاک‌کردنِ همهٔ فروشگاه‌دارهایِ واقعی. پوستهٔ دمو و ردیف‌هایِ ممیزی می‌مانند (زنجیرهٔ هشِ ممیزی پاک‌شدنی نیست) و `_seed` همان پوسته را دوباره پر می‌کند.

دستور:
    docker compose run --rm -e SEED_DEMO_CONFIRM=1 bot python scripts/seed_demo.py
    docker compose run --rm -e SEED_DEMO_CONFIRM=1 bot python scripts/seed_demo.py --cleanup
"""
from __future__ import annotations

import argparse
import asyncio
import datetime
import os
import sys

sys.path.insert(0, ".")

from sqlalchemy import delete, func, select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from app.database.models import (  # noqa: E402
    AdminCreditBatchItem,
    BotErrorEvent,
    Campaign,
    Cart,
    CartAiProposal,
    CartItem,
    ChannelKnowledge,
    CommissionReceivable,
    ConversationMessage,
    Customer,
    CustomerAddress,
    DigitalCode,
    DirectMessage,
    DiscountCodeUsage,
    Invoice,
    InvoiceCounter,
    KnowledgeGap,
    LearnedAnswer,
    Notification,
    OrderConsultation,
    OrderEvent,
    OrderPayment,
    OrderStatus,
    OrderType,
    OtpCode,
    Payment,
    PaymentEventLog,
    Product,
    Referral,
    ScheduledBroadcast,
    ShippingMethod,
    ShopBot,
    ShopOwner,
    ShopPaymentSettings,
    Subscription,
    TimeFreeze,
    WalletCharge,
    WalletTransaction,
    WalletTransactionReason,
)  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import shipping_service, wallet_service  # noqa: E402

DEMO_PREFIX = 9_600_000  # دور از دادهٔ واقعی و دور از ردیف‌هایِ بارسنجی (≥ 9_000_000)
DEMO_BOT_PREFIX = 960_000_000
# پوستهٔ دمو با این دو شناسهٔ *دقیق* شناخته می‌شود. هرگز به‌صورت «≥ DEMO_PREFIX» جست‌وجو نکن:
DEMO_OWNER_TG = DEMO_PREFIX + 1
DEMO_BOT_TG = DEMO_BOT_PREFIX + 1


def _guard() -> None:
    if os.environ.get("SEED_DEMO_CONFIRM") != "1":
        # P21-F: رشتهٔ اتصال چاپ نمی‌شود — داخلِ آن رمزِ دیتابیس است و این پیام به stdout
        # (و لاگِ CI) می‌رود. نامِ میزبان/دیتابیس هم برایِ تشخیصِ «کجا می‌نویسم» کافی بود،
        # ولی ریسکش به آن ارزش را نداشت؛ اسکریپت خودش را با DEPLOY_ENV/سرویسِ داکر مشخص می‌کند.
        raise SystemExit(
            "SEED_DEMO_CONFIRM=1 لازم است: این اسکریپت رویِ دیتابیسِ پیکربندی‌شده می‌نویسد. "
            "رویِ دیتابیسِ اصلی اجرایِ واقعی مشکلی ندارد چون فقط ردیف‌هایِ نمایشیِ شناسا می‌سازد و پاک‌سازی هم تساویِ دقیق است، "
            "ولی با --cleanup هم پاک‌شدنی است."
        )


async def _find_demo(session: AsyncSession) -> tuple[ShopOwner | None, ShopBot | None]:
    """پوستهٔ دمو (فروشگاه‌دار/ربات) را فقط با شناسهٔ ساختگیِ *دقیق* پیدا می‌کند.

    چرا این‌قدر وسواس: نسخهٔ اولِ این اسکریپت ردیف‌ها را با `telegram_id >= DEMO_PREFIX` می‌شمرد.
    شناسهٔ تلگرامِ آدم‌هایِ واقعی ۷ تا ۹ میلیارده ⇒ هر سه فروشگاه‌دار، رباتِ فعالِ آن‌ها،
    محصول‌ها و سفارش‌هایشان داخلِ «ردیف‌هایِ نمایشی» جا می‌رفت و `--cleanup` همان‌ها را
    پاک می‌کرد. این اسکریپت فقط با مقایسهٔ تساویِ شناسهٔ ساختگی کار می‌کند و تستِ
    `test_p22_seed_cleanup_safety.py` همان دام را می‌بندد.
    """
    owner = (await session.execute(select(ShopOwner).where(ShopOwner.telegram_id == DEMO_OWNER_TG))).scalar_one_or_none()
    bot = (await session.execute(select(ShopBot).where(ShopBot.bot_telegram_id == DEMO_BOT_TG))).scalar_one_or_none()
    if bot is not None and bot.shop_owner_id != (owner.id if owner else None):
        raise SystemExit("⛔ پوستهٔ دمو سازگار نیست (ربات هست، ولی فروشگاه‌دارِ دمو نه یا مالکِ دیگری دارد)؛ خودت دستی درست کن، من دست نمی‌زنم.")
    return owner, bot


async def _cleanup() -> dict:
    """محتوایِ دمو را پاک می‌کند.

    دو چیز را *عمداً* نمی‌کند:
    - ردیف‌هایِ `audit_log_entries`: زنجیرهٔ هشِ ممیزی با حذفِ ردیفِ میانی می‌شکند و
      `verify_audit_chain.py` بعداً «شکستِ هش» گزارش می‌دهد.
    - پوستهٔ دمو (فروشگاه‌دار/ربات): همان ردیف‌هایِ ممیزی به ربات ارجاع می‌دهند، پس پوسته می‌ماند
      و `_seed` دوباره از همان پوسته استفاده می‌کند (ساختِ رباتِ دمؤ دوم ⇒ دادهٔ تکراری).
    """
    async with session_scope() as session:
        owner, bot = await _find_demo(session)
        if bot is not None:
            bot_ids = [bot.id]
            order_ids = select(OrderConsultation.id).where(OrderConsultation.shop_bot_id.in_(bot_ids))
            customer_ids = select(Customer.id).where(Customer.shop_bot_id.in_(bot_ids))
            cart_ids = select(Cart.id).where(Cart.shop_bot_id.in_(bot_ids))
            # پاک‌سازیِ لانه‌ای: وابسته‌هایِ سفارش، وابسته‌هایِ سبد، وابسته‌هایِ مشتری — بعد خودِ آن سه
            dependent_rows = [
                (DigitalCode, DigitalCode.order_id, order_ids),
                (DirectMessage, DirectMessage.order_id, order_ids),
                (OrderEvent, OrderEvent.order_id, order_ids),
                (WalletTransaction, WalletTransaction.order_id, order_ids),
                (CartItem, CartItem.cart_id, cart_ids),
                (CartAiProposal, CartAiProposal.cart_id, cart_ids),
                (ConversationMessage, ConversationMessage.customer_id, customer_ids),
                (CustomerAddress, CustomerAddress.customer_id, customer_ids),
                (DirectMessage, DirectMessage.customer_id, customer_ids),
                (Cart, Cart.customer_id, customer_ids),
                (OrderConsultation, OrderConsultation.customer_id, customer_ids),
            ]
            for model, column, source in dependent_rows:
                await session.execute(delete(model).where(column.in_(source)))
            # باقیِ ردیف‌هایِ سطحِ ربات (به‌جزِ ممیزی، که دست‌نخورده می‌ماند)
            for model in (
                PaymentEventLog, Invoice, InvoiceCounter, OrderPayment, ShopPaymentSettings, ChannelKnowledge,
                KnowledgeGap, LearnedAnswer, Campaign, BotErrorEvent, ScheduledBroadcast, Notification,
                ShippingMethod, Product, Customer, OrderConsultation, Cart,
            ):
                await session.execute(delete(model).where(model.shop_bot_id.in_(bot_ids)))
        if owner is not None:
            owner_ids = [owner.id]
            for model, column in (
                (WalletTransaction, WalletTransaction.shop_owner_id),
                (WalletCharge, WalletCharge.shop_owner_id),
                (CommissionReceivable, CommissionReceivable.shop_owner_id),
                (DiscountCodeUsage, DiscountCodeUsage.shop_owner_id),
                (AdminCreditBatchItem, AdminCreditBatchItem.shop_owner_id),
                (OtpCode, OtpCode.shop_owner_id),
                (Payment, Payment.shop_owner_id),
                (Subscription, Subscription.shop_owner_id),
                (TimeFreeze, TimeFreeze.shop_owner_id),
                (Notification, Notification.owner_id),
                (ScheduledBroadcast, ScheduledBroadcast.owner_id),
            ):
                await session.execute(delete(model).where(column.in_(owner_ids)))
            # referralsِ دمو فقط وقتی پاک می‌شوند که دو سرشان دمو باشد؛ اگر آدمِ واقعی با کدِ
            # دعوتِ دمو ثبت‌نام کرده باشد، آن ردیف تاریخچهٔ واقعی است و می‌ماند.
            await session.execute(delete(Referral).where(Referral.referrer_id.in_(owner_ids), Referral.referred_id.in_(owner_ids)))
            # کیف‌پولِ پوسته صفر می‌شود تا ردیف‌هایِ دفترِ پاک‌شده با موجودیِ ناسازگار نمانند.
            owner.wallet_balance_toman = 0
            owner.commission_reserved_toman = 0
        left = int(
            (await session.execute(select(func.count()).select_from(Product).where(Product.shop_bot_id == (bot.id if bot else -1)))).scalar_one()
        )
    return {"products_left": left, "shell_kept": bot is not None}


PRODUCTS = [
    ("کیفِ چرمیِ دستِ‌دوز", 1_850_000, 6, "physical"),
    ("کمربندِ چرمی", 620_000, 2, "physical"),
    ("کیفِ دوشیِ کوچک", 1_250_000, 0, "physical"),
    ("کدِ تخفیفِ ۲۰٪ (دیجیتال)", 150_000, None, "digital"),
    ("ساکِ پارچه‌ای", 240_000, 14, "physical"),
    ("خدماتِ تعمیرات (مشاوره)", 400_000, None, "physical"),
]

CUSTOMERS = [("مریم", "maryam_d", "رضایی"), ("سینا", "sina_k", "کریمی"), ("زهرا", None, "احمدی"), ("امیر", "amir_p", None), ("ناشناس", None, None)]

# (نام، هزینه، رایگانِ بالایِ، متنِ زمانِ تحویل) — روش‌هایِ ارسالِ فروشگاهِ دمو
SHIPPING_METHODS = [
    ("پستِ پیشتاز", 40_000, 2_000_000, "۳ تا ۵ روزِ کاری"),
    ("پیکِ داخلِ شهر", 25_000, None, "همان روز"),
]


async def _seed(credit_toman: int) -> dict:
    counts = {}
    async with session_scope() as session:
        # پوسته را دوباره استفاده می‌کند (اگر --cleanup آن را نگه داشته باشد) تا رباتِ دموِ
        # دومی ساخته نشود؛ محتوایش پاک شده و از نو پر می‌شود.
        owner, shop_bot = await _find_demo(session)
        if owner is None:
            owner = ShopOwner(
                telegram_id=DEMO_OWNER_TG,
                first_name="فروشگاهِ نمایشی",
                last_name="دمو",
                referral_code="DEMO0001",
                registration_completed=True,
                wallet_balance_toman=0,
            )
            session.add(owner)
            await session.flush()
        if shop_bot is None:
            shop_bot = ShopBot(
                shop_owner_id=owner.id,
                encrypted_token=f"{DEMO_BOT_PREFIX}:DEMO_TOKEN_NOT_A_REAL_TOKEN",
                bot_telegram_id=DEMO_BOT_TG,
                bot_username="demo_shop_bot",
                webhook_secret_token="demo-secret-not-real",
                is_active=False,  # به‌توکنِ جعلی هرگز وصل نمی‌شود؛ ترافیکِ واقعیِ تو دست‌نخورده می‌ماند
                ai_instructions="تو دستیارِ یکِ فروشگاهِ کیف/کمربندِ چرمی هستی؛ کوتاه و مؤدب جواب بده.",
                low_stock_alert_threshold=3,
            )
            session.add(shop_bot)
            await session.flush()
        if owner.wallet_balance_toman == 0:
            await wallet_service.add_charge(
                session, owner, credit_toman, reason=WalletTransactionReason.TOPUP, reference="demo-seed-credit"
            )

        products = []
        for name, price, stock, kind in PRODUCTS:
            product = Product(shop_bot_id=shop_bot.id, name=name, price_toman=price, stock_quantity=stock, kind=kind)
            session.add(product)
            products.append(product)
        await session.flush()

        # P22 (مشکل ۵): فروشگاهِ دمو دو روشِ ارسالِ فعال دارد تا گامِ «🚚 روشِ ارسال» در
        # چک‌اوتِ واقعی پرسیده شود و هزینه‌اش رویِ جمعِ کل بنشیند؛ بی‌این، چک‌اوت فقط
        # «هماهنگی با فروشگاه» را پیشنهاد می‌دهد و مسیرِ پولیِ ارسال هرگز دیده نمی‌شود.
        shipping = []
        for name, fee, free_over, eta in SHIPPING_METHODS:
            method = await shipping_service.create_method(session, shop_bot.id, name, fee, free_over, eta)
            if method is not None:
                shipping.append(method)
        await session.flush()

        customers = []
        for index, (first, username, last) in enumerate(CUSTOMERS):
            customer = Customer(
                shop_bot_id=shop_bot.id,
                telegram_id=DEMO_PREFIX + 100 + index,
                platform="telegram",
                first_name=first,
                username=username,
                last_name=last,
                last_message_at=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=index),
            )
            session.add(customer)
            customers.append(customer)
        await session.flush()

        session.add_all(
            [
                ConversationMessage(customer_id=customers[0].id, role="user", content="سلام، این کیفِ چرمی رنگِ قهوه‌ای هم داره؟"),
                ConversationMessage(customer_id=customers[0].id, role="assistant", content="سلام! بله، قهوه‌ای موجود است 🙂"),
                ConversationMessage(customer_id=customers[1].id, role="user", content="ارسال به شهرستان چند است؟"),
                ConversationMessage(customer_id=customers[1].id, role="assistant", content="ارسال به شهرستان ۴۵٬۰۰۰ تومان است."),
            ]
        )

        # سفارش‌ها با وضعیت‌هایِ مختلف تا صفحه‌هایِ «مدیریتِ سفارش‌ها» و «پیگیریِ مشتری» پر باشند
        statuses = [
            (OrderStatus.PENDING, customers[0], products[0], 2, "physical"),
            (OrderStatus.AWAITING_PAYMENT, customers[1], products[2], 1, "physical"),
            (OrderStatus.CONFIRMED, customers[2], products[4], 3, "physical"),
            (OrderStatus.REJECTED, customers[3], products[1], 1, "physical"),
            (OrderStatus.PENDING, customers[4], products[5], 1, "consultation"),
        ]
        for status, customer, product, quantity, kind in statuses:
            session.add(
                OrderConsultation(
                    shop_bot_id=shop_bot.id,
                    customer_id=customer.id,
                    product_id=product.id,
                    type=OrderType.CONSULTATION if kind == "consultation" else OrderType.ORDER,
                    summary=product.name,
                    status=status,
                    quantity=quantity,
                    estimated_value_toman=product.price_toman * quantity,
                    customer_phone=customer.phone_number,
                )
            )
        await session.flush()
        counts = {
            "owner_telegram_id": owner.telegram_id,
            "products": len(products),
            "shipping": len(shipping),
            "customers": len(customers),
            "orders": len(statuses),
            "credit_toman": credit_toman,
            "shop_bot_id": shop_bot.id,
        }
    return counts


async def main(credit_toman: int) -> None:
    _guard()
    result = await _cleanup()  # اجرایِ قبلی اگر مانده باشد، تکراری نمی‌سازد
    if result["products_left"]:
        raise SystemExit(f"{result['products_left']} محصولِ دمو پاک نشد؛ از ادامه دست کشیدم (دادهٔ ساختگی تکراری نشود).")
    counts = await _seed(credit_toman)
    print(
        "✅ دادهٔ نمایشی ساخته شد:\n"
        f"   فروشگاه‌دارِ دمو (شناسهٔ تلگرامِ ساختگی): {counts['owner_telegram_id']}\n"
        f"   رباتِ فروشگاه (غیرفعال، توکنِ جعلی): shop_bot_id={counts['shop_bot_id']}\n"
        f"   {counts['products']} محصول · {counts['shipping']} روشِ ارسال · {counts['customers']} مشتری · "
        f"{counts['orders']} سفارش · اعتبار {counts['credit_toman']:,} تومان\n"
        "   آستانهٔ اخطارِ موجودی رویِ ۳ تنظیم شده (دو کالا زیرِ آن است).\n"
        "   روش‌هایِ ارسال فعال‌اند ⇒ در چک‌اوت، گامِ «🚚 روشِ ارسال» پرسیده می‌شود و هزینه‌اش به جمعِ کل می‌آید.\n"
        "   برایِ پاک کردن: python scripts/seed_demo.py --cleanup"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--cleanup", action="store_true", help="فقط ردیف‌هایِ نمایشی را پاک کن")
    parser.add_argument("--credit", type=int, default=750_000, help="اعتبارِ اولیهٔ کیف‌پولِ دمو (تومان)")
    args = parser.parse_args()
    if args.cleanup:
        _guard()
        result = asyncio.run(_cleanup())
        if not result["shell_kept"]:
            print("🧹 پاک‌سازی: هیچِ ردیفِ نمایشیِ دیگری پیدا نشد.")
        else:
            print(
                "🧹 پاک‌سازی: محتوایِ دمو حذف شد و کیف‌پولش صفر شد.\n"
                "   پوستهٔ دمو (فروشگاه‌دار/ربات) و ردیف‌هایِ ممیزی عمداً مانده‌اند: زنجیرهٔ هشِ ممیزی با حذفِ"
                " ردیفِ میانی می‌شکند. اگر دیتابیسِ تست است و پوسته هم لازم نداری، با `DROP`/ریستِ کامل پاکش کن."
            )
    else:
        asyncio.run(main(args.credit))
