"""
تست: P22 — گامِ «روشِ ارسال» همیشه پرسیده می‌شود و هزینه‌اش رویِ مبلغ می‌آید (مشکلِ ۵ کاربر)

دو حالتی که کاربر می‌گفت «پرسیده نمی‌شود و به هزینه اضافه نمی‌شود»:
۱) فروشگاه هیچ روشِ ارسالی ندارد ⇒ قبلاً گام بی‌صدا رد می‌شد و ارسال ۰ ثبت می‌شد. حالا
   گزینهٔ «🤝 هماهنگی ارسال با فروشگاه» پرسیده می‌شود، در پیش‌نمایش و در سفارش ثبت می‌شود،
   و فروشگاه‌دار در اعلانِ سفارش مسیرِ ساختنِ روشِ ارسال را می‌گیرد.
۲) فروشگاه روشِ ارسالی با هزینه دارد ⇒ هزینه باید به جمعِ کل اضافه شود و در فاکتور/سفارش بیاید.

اجرا: python3 tests_manual/run_one.py test_p22_shipping_coordination.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from aiogram import Bot  # noqa: E402
from sqlalchemy import select, update  # noqa: E402

from checkout_helpers import run_checkout  # noqa: E402
from harness import FakeSession, build_test_dispatchers, make_callback_update, make_message_update, reset_database  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from app.database.models import OrderConsultation as Order  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import order_transition_service, product_service, shipping_service  # noqa: E402

OWNER_TG_ID = 999_901
SHOP_BOT_TG_ID = 999_902
_user_counter = 999_910


class _Shopper:
    def __init__(self, shop_dp) -> None:
        global _user_counter
        _user_counter += 1
        self.user_id = _user_counter
        self.dp = shop_dp
        self.bot = Bot(token=f"{SHOP_BOT_TG_ID}:FAKE", session=FakeSession())
        self.session: FakeSession = self.bot.session  # type: ignore[assignment]
        self._n = self.user_id * 1000

    async def say(self, text: str) -> None:
        self._n += 1
        await self.dp.feed_update(self.bot, make_message_update(self._n, text=text, user_id=self.user_id))

    async def tap(self, data: str) -> None:
        self._n += 1
        await self.dp.feed_update(self.bot, make_callback_update(self._n, data=data, user_id=self.user_id))

    @property
    def last_text(self) -> str:
        return self.session.sent_messages[-1]["text"]


async def _seed(*, methods: list[tuple[str, int]] | None = None) -> tuple[int, int]:
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    async with session_scope() as session:
        product = await product_service.create_product(session, shop_bot_id, "برنج", None, 200_000, None, 5)
        for name, fee in methods or []:
            await shipping_service.create_method(session, shop_bot_id, name, fee)
        product_id = product.id
        await session.commit()
    return shop_bot_id, product_id


async def _orders(shop_bot_id: int) -> list[Order]:
    async with session_scope() as session:
        return list((await session.execute(select(Order).where(Order.shop_bot_id == shop_bot_id))).scalars().all())


# ============================================================================= ۱ — بدونِ روشِ ارسال
async def test_coordination_is_asked_and_recorded(shop_dp, main_bot) -> None:
    shop_bot_id, product_id = await _seed()
    main_bot.session.sent_messages.clear()
    shopper = _Shopper(shop_dp)

    await shopper.tap(f"cart_add:{product_id}")
    await shopper.tap("cart_checkout_start")
    await shopper.say("علی رضایی")
    await shopper.say("09120000000")
    await shopper.say("تهران")
    await shopper.say("تهران")
    await shopper.say("خیابانِ آزادی، پلاکِ ۱۰")
    await shopper.tap("ck_skip")  # کدپستی
    assert "هماهنگی" in shopper.last_text, shopper.last_text  # P22: پرسیده می‌شود، رد نمی‌شود

    await shopper.tap("ck_ship:0")
    await shopper.tap("ck_skip")  # توضیح
    preview = shopper.last_text
    assert "هماهنگی ارسال با فروشگاه" in preview, preview
    assert "۲۵۰٬۰۰۰" not in preview and "۲۰۰٬۰۰۰" in preview, "هزینه‌ای اضافه نشده؛ جمع = مبلغِ کالا"

    await shopper.tap("cart_checkout_confirm")
    orders = await _orders(shop_bot_id)
    assert len(orders) == 1, orders
    assert orders[0].shipping_fee_toman == 0 and orders[0].shipping_method_name == "هماهنگی ارسال با فروشگاه"
    owner_text = main_bot.session.sent_messages[0]["text"]
    assert "هماهنگی" in owner_text and "🚚 روش‌هایِ ارسال" in owner_text, owner_text
    print("✅ test_coordination_is_asked_and_recorded PASSED")


# ============================================================================= ۲ — با هزینه‌یِ ارسال
async def test_shipping_fee_is_added_to_the_total(shop_dp, main_bot) -> None:
    shop_bot_id, product_id = await _seed(methods=[("پست", 40_000)])
    main_bot.session.sent_messages.clear()
    async with session_scope() as session:
        method_id = int((await session.execute(select(shipping_service.ShippingMethod.id))).scalar_one())
    shopper = _Shopper(shop_dp)

    await shopper.tap(f"cart_add:{product_id}")
    await run_checkout(shopper.tap, shopper.say, ship_method_id=method_id, postal=None, note=None)
    preview = shopper.last_text
    assert "۴۰٬۰۰۰" in preview, preview
    assert "۲۴۰٬۰۰۰" in preview, f"جمعِ کل باید ۲۰۰٬۰۰۰ + ۴۰٬۰۰۰ باشد: {preview}"

    await shopper.tap("cart_checkout_confirm")
    orders = await _orders(shop_bot_id)
    assert orders[0].shipping_fee_toman == 40_000, orders[0].shipping_fee_toman
    assert orders[0].shipping_method_name == "پست", orders[0].shipping_method_name
    assert orders[0].estimated_value_toman == 200_000, "برآوردِ هر سفارش = مبلغِ اقلامش؛ ارسال جدا نگه داشته می‌شود"
    assert order_transition_service.group_total_toman(orders) == 240_000, "جمعِ گروهِ سفارش = اقلام + ارسال"
    print("✅ test_shipping_fee_is_added_to_the_total PASSED")


# ============================================================================= ۳ — گامِ خاموش‌شدنی
async def test_owner_can_still_turn_the_step_off(shop_dp, main_bot) -> None:
    """B9 دست‌نخورده: اگر خودِ فروشگاه گامِ «ارسال» را خاموش کند، پرسیده نمی‌شود."""
    import json

    shop_bot_id, product_id = await _seed()
    main_bot.session.sent_messages.clear()
    async with session_scope() as session:
        from app.database.models import ShopBot

        config = {"shipping": {"on": False, "q": ""}}
        await session.execute(update(ShopBot).where(ShopBot.id == shop_bot_id).values(checkout_config=json.dumps(config)))
        await session.commit()
        saved = (await session.execute(select(ShopBot.checkout_config).where(ShopBot.id == shop_bot_id))).scalar_one()
    assert saved and json.loads(saved)["shipping"]["on"] is False, saved
    shopper = _Shopper(shop_dp)

    await shopper.tap(f"cart_add:{product_id}")
    await shopper.tap("cart_checkout_start")
    await shopper.say("مریم")
    await shopper.say("09121110000")
    await shopper.say("تهران")
    await shopper.say("تهران")
    await shopper.say("آدرسِ تست")
    await shopper.tap("ck_skip")  # کدپستی
    await shopper.tap("ck_skip")  # توضیح ⇒ بدونِ پرسشِ ارسال
    assert "ثبت بشه؟" in shopper.last_text, [m["text"][:40] for m in shopper.session.sent_messages]
    assert "هماهنگی" not in shopper.last_text, shopper.last_text
    print("✅ test_owner_can_still_turn_the_step_off PASSED")


async def main() -> None:
    _main_dp, shop_dp, _bot_manager, main_bot = build_test_dispatchers()
    await test_coordination_is_asked_and_recorded(shop_dp, main_bot)
    await test_shipping_fee_is_added_to_the_total(shop_dp, main_bot)
    await test_owner_can_still_turn_the_step_off(shop_dp, main_bot)


if __name__ == "__main__":
    asyncio.run(main())
