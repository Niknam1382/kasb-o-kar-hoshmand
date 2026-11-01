"""دادهٔ نمایشی برایِ تستِ دستی (P21-D · F6).

چرا لازم بود: بعد از ریستِ دیتابیس، پنلِ ادمین و پنلِ فروشگاه‌دار «خالی» است و برایِ دیدنِ
هر صفحه باید دستی محصول/مشتری/سفارش ساخت. این اسکریپت همان‌ها را می‌سازد تا مسیرهایِ واقعی
(لیستِ محصول، آمار، CRM، اخطارِ موجودی، پیگیریِ سفارشِ مشتری) یک‌باره دیده شوند.

ایمنی (عمدی):
- تا `SEED_DEMO_CONFIRM=1` ست نشود اجرا نمی‌شود.
- رباتِ دمو `is_active=False` است ⇒ هرگز با توکنِ جعلی به تلگرام وصل نمی‌شود و ترافیکِ
  واقعیِ رباتِ تو را نمی‌دزدد.
- هیچ فراخوانیِ شبکه‌ای (AI/تلگرام/بله/پرداخت/پیامک) ندارد.
- همه‌یِ ردیف‌ها با `telegram_id >= 9_600_000` ساخته و با `--cleanup` کامل پاک می‌شوند.

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

from app.config import settings  # noqa: E402
from app.database.models import (  # noqa: E402
    ConversationMessage,
    Customer,
    OrderConsultation,
    OrderStatus,
    OrderType,
    Product,
    ScheduledBroadcast,
    ShopBot,
    ShopOwner,
    WalletCharge,
    WalletTransaction,
    WalletTransactionReason,
)  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import wallet_service  # noqa: E402

DEMO_PREFIX = 9_600_000  # دور از دادهٔ واقعی و دور از ردیف‌هایِ بارسنجی (≥ 9_000_000)
DEMO_BOT_PREFIX = 960_000_000


def _guard() -> None:
    if os.environ.get("SEED_DEMO_CONFIRM") != "1":
        raise SystemExit(
            "SEED_DEMO_CONFIRM=1 لازم است: این اسکریپت دیتابیس را می‌نویسد. "
            f"DATABASE_URL فعلی: {settings.database_url} — رویِ دیتابیسِ اصلی اجرایِ واقعی مشکلی ندارد "
            "چون فقط ردیف‌هایِ نمایشیِ شناسا می‌سازد، ولی با --cleanup هم پاک‌شدنی است."
        )


async def _cleanup() -> int:
    async with session_scope() as session:
        owner_ids = list((await session.execute(select(ShopOwner.id).where(ShopOwner.telegram_id >= DEMO_PREFIX))).scalars().all())
        bot_ids = list((await session.execute(select(ShopBot.id).where(ShopBot.bot_telegram_id >= DEMO_BOT_PREFIX))).scalars().all())
        if bot_ids:
            # ترتیبِ حذف با قیدهایِ کلیدِ خارجی: اول وابسته‌ها (سفارش ← گفتگو ← مشتری)، بعد خودِ ردیف‌ها
            await session.execute(delete(OrderConsultation).where(OrderConsultation.shop_bot_id.in_(bot_ids)))
            customer_ids = list((await session.execute(select(Customer.id).where(Customer.shop_bot_id.in_(bot_ids)))).scalars().all())
            if customer_ids:
                await session.execute(delete(ConversationMessage).where(ConversationMessage.customer_id.in_(customer_ids)))
                await session.execute(delete(Customer).where(Customer.id.in_(customer_ids)))
            await session.execute(delete(Product).where(Product.shop_bot_id.in_(bot_ids)))
            await session.execute(delete(ScheduledBroadcast).where(ScheduledBroadcast.shop_bot_id.in_(bot_ids)))
            await session.execute(delete(ShopBot).where(ShopBot.id.in_(bot_ids)))
        if owner_ids:
            await session.execute(delete(WalletTransaction).where(WalletTransaction.shop_owner_id.in_(owner_ids)))
            await session.execute(delete(WalletCharge).where(WalletCharge.shop_owner_id.in_(owner_ids)))
            await session.execute(delete(ShopOwner).where(ShopOwner.id.in_(owner_ids)))
        left = int(
            (await session.execute(select(func.count()).select_from(ShopOwner).where(ShopOwner.telegram_id >= DEMO_PREFIX))).scalar_one()
        )
    return left


PRODUCTS = [
    ("کیفِ چرمیِ دستِ‌دوز", 1_850_000, 6, "physical"),
    ("کمربندِ چرمی", 620_000, 2, "physical"),
    ("کیفِ دوشیِ کوچک", 1_250_000, 0, "physical"),
    ("کدِ تخفیفِ ۲۰٪ (دیجیتال)", 150_000, None, "digital"),
    ("ساکِ پارچه‌ای", 240_000, 14, "physical"),
    ("خدماتِ تعمیرات (مشاوره)", 400_000, None, "physical"),
]

CUSTOMERS = [("مریم", "maryam_d", "رضایی"), ("سینا", "sina_k", "کریمی"), ("زهرا", None, "احمدی"), ("امیر", "amir_p", None), ("ناشناس", None, None)]


async def _seed(credit_toman: int) -> dict:
    counts = {}
    async with session_scope() as session:
        owner = ShopOwner(
            telegram_id=DEMO_PREFIX + 1,
            first_name="فروشگاهِ نمایشی",
            last_name="دمو",
            referral_code="DEMO0001",
            registration_completed=True,
            wallet_balance_toman=0,
        )
        session.add(owner)
        await session.flush()
        await wallet_service.add_charge(
            session, owner, credit_toman, reason=WalletTransactionReason.TOPUP, reference="demo-seed-credit"
        )
        shop_bot = ShopBot(
            shop_owner_id=owner.id,
            encrypted_token=f"{DEMO_BOT_PREFIX}:DEMO_TOKEN_NOT_A_REAL_TOKEN",
            bot_telegram_id=DEMO_BOT_PREFIX + 1,
            bot_username="demo_shop_bot",
            webhook_secret_token="demo-secret-not-real",
            is_active=False,  # به‌توکنِ جعلی هرگز وصل نمی‌شود؛ ترافیکِ واقعیِ تو دست‌نخورده می‌ماند
            ai_instructions="تو دستیارِ یکِ فروشگاهِ کیف/کمربندِ چرمی هستی؛ کوتاه و مؤدب جواب بده.",
            low_stock_alert_threshold=3,
        )
        session.add(shop_bot)
        await session.flush()

        products = []
        for name, price, stock, kind in PRODUCTS:
            product = Product(shop_bot_id=shop_bot.id, name=name, price_toman=price, stock_quantity=stock, kind=kind)
            session.add(product)
            products.append(product)
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
            "customers": len(customers),
            "orders": len(statuses),
            "credit_toman": credit_toman,
            "shop_bot_id": shop_bot.id,
        }
    return counts


async def main(credit_toman: int) -> None:
    _guard()
    left = await _cleanup()  # اجرایِ قبلی اگر مانده باشد، تکراری نمی‌سازد
    if left:
        raise SystemExit(f"{left} ردیفِ نمایشی پاک نشد؛ از ادامه دست کشیدم (دادهٔ ساختگی تکراری نشود).")
    counts = await _seed(credit_toman)
    print(
        "✅ دادهٔ نمایشی ساخته شد:\n"
        f"   فروشگاه‌دارِ دمو (شناسهٔ تلگرامِ ساختگی): {counts['owner_telegram_id']}\n"
        f"   رباتِ فروشگاه (غیرفعال، توکنِ جعلی): shop_bot_id={counts['shop_bot_id']}\n"
        f"   {counts['products']} محصول · {counts['customers']} مشتری · {counts['orders']} سفارش · اعتبار {counts['credit_toman']:,} تومان\n"
        "   آستانهٔ اخطارِ موجودی رویِ ۳ تنظیم شده (دو کالا زیرِ آن است).\n"
        "   برایِ پاک کردن: python scripts/seed_demo.py --cleanup"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--cleanup", action="store_true", help="فقط ردیف‌هایِ نمایشی را پاک کن")
    parser.add_argument("--credit", type=int, default=750_000, help="اعتبارِ اولیهٔ کیف‌پولِ دمو (تومان)")
    args = parser.parse_args()
    if args.cleanup:
        _guard()
        remaining = asyncio.run(_cleanup())
        print(f"🧹 پاک‌سازی: {remaining} ردیفِ نمایشی باقی ماند (باید صفر باشد)")
    else:
        asyncio.run(main(args.credit))
