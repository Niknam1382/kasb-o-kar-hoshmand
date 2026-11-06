"""
تست: P41 — پرداختِ *سفارش* هیچ‌وقت با سطحِ پلتفرم ساخته نمی‌شود

خواستِ مالکِ محصول (پس ازِ دیدنِ صفحهٔ «پرداختِ آنلاینِ سفارش‌ها» با توکنِ درگاهِ فقط‌نیمه):
«پرداخت نباید در کیف پول پلتفرم بشینه. جلوشو بگیر».

پیش از این قاعدهٔ P34 افزودنی بود: اگر فروشگاه فقط توکنِ درگاه را گذاشته بود، صورتحساب با
رباتِ پلتفرم ساخته می‌شد و پولِ مشتری در کیف‌پولِ پلتفرم می‌نشیند. حالا ملاکِ `shop_status`
سخت است: پرداختِ سفارش فقط با «توکنِ رباتِ بلهٔ خودش + توکنِ درگاهِ خودش».

پوشش:
۱. هر سه حالتِ ناقص (فقط درگاه / فقط ربات / هیچ‌کدام) با درگاهِ سراسریِ روشن ⇒ `available` false
   و هیچ `create_invoice_link` برایِ سفارش ساخته نمی‌شود؛ گزینهٔ بله‌پی هم در فهرستِ پرداخت نیست.
۲. حالتِ کامل ⇒ دقیقاً با توکنِ رباتِ خودش و درگاهِ خودش ساخته می‌شود (نه پلتفرم).
۳. سطحِ پلتفرم برایِ «شارژِ کیف‌پولِ پلتفرم» سرِ جاش می‌ماند (آن پرداخت را صاحبِ فروشگاه به
   سرویس می‌دهد، پس مقصدِ درست همان جاست).
۴. متنِ صفحه‌ها دیگر «پول در کیف‌پولِ پلتفرم می‌نشیند» نمی‌گوید و علت‌ها را به خودِ فروشگاه
   نسبت می‌دهد (نه به پنلِ ادمین).

اجرا: python3 tests_manual/run_one.py test_p41_order_payment_never_platform.py
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from aiogram import Bot  # noqa: E402

from harness import FakeSession, build_test_dispatchers, reset_database  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from app.bots.main_bot import texts as main_texts  # noqa: E402
from app.bots.shop_bot.handlers import customer as customer_handlers  # noqa: E402
from app.config import settings  # noqa: E402
from app.database.models import OrderStatus, OrderType, ShopBot  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import (  # noqa: E402
    bale_credentials_service as creds,
    bale_service,
    customer_service,
    order_service,
    payment_settings_service,
)
from app.services.admin_settings_service import update_setting  # noqa: E402

OWNER_TG_ID = 7_441_000_011
SHOP_BOT_TG_ID = 7_441_000_012
CUSTOMER_TG_ID = 7_441_000_013
PLATFORM_BOT_TOKEN = "111111:PLATFORM-BALE-BOT-TOKEN-P41"
SHOP_BALE_TOKEN = "222222:SHOP-OWN-BALE-BOT-TOKEN-P41"
SHOP_PROVIDER = "SHOP-OWN-PROVIDER-TOKEN-P41-0001"
PLATFORM_PROVIDER = "PLATFORM-PROVIDER-TOKEN-P41-0002"
SHOP_PAY_BOT = "shop_p41_bot"
PLATFORM_PAY_BOT = "platform_p41_pay_bot"

_invoice_calls: list[tuple[str, str]] = []


class _Cfg:
    """توکنِ رباتِ پلتفرم + نامِ کاربریِ رباتِ پرداخت، بدونِ شبکه."""

    def __enter__(self):
        self._token = settings.bale_bot_token
        settings.bale_bot_token = PLATFORM_BOT_TOKEN
        creds.reset_cache()
        creds.remember_pay_bot_username(PLATFORM_PAY_BOT)
        return self

    def __exit__(self, *_exc):
        settings.bale_bot_token = self._token
        creds.reset_cache()


async def _configure_platform(*, provider: bool = True, pay_enabled: bool = True) -> None:
    async with session_scope() as session:
        await update_setting(session, "bale_provider_token", PLATFORM_PROVIDER if provider else "")
        await update_setting(session, "bale_pay_enabled", pay_enabled)
        await session.commit()


async def _set_provider(shop_bot_id: int, value: str | None) -> None:
    async with session_scope() as session:
        shop_bot = await session.get(ShopBot, shop_bot_id)
        shop_bot.bale_provider_token = value
        await session.commit()


async def _set_own_bot(shop_bot_id: int, *, connected: bool) -> None:
    async with session_scope() as session:
        shop_bot = await session.get(ShopBot, shop_bot_id)
        shop_bot.bale_encrypted_token = SHOP_BALE_TOKEN if connected else None
        shop_bot.bale_bot_id = 987_654 if connected else None
        shop_bot.bale_bot_username = SHOP_PAY_BOT if connected else None
        shop_bot.bale_bot_enabled = connected
        await session.commit()


async def _fake_invoice(bot_token: str, provider_token: str, **_kwargs) -> str:
    _invoice_calls.append((bot_token, provider_token or ""))
    return "invoice-id-placeholder"


async def _order_and_offer(shop_bot_id: int) -> int:
    """همان کاری که پایانِ چک‌اوتِ تک‌سفارش می‌کند: پیشنهادِ پرداختِ آنلاین (بدِ شبکه)."""
    shop_bot_instance = Bot(token=f"{SHOP_BOT_TG_ID}:P41FAKETOKENFORTESTS000000000AB", session=FakeSession())
    async with session_scope() as session:
        customer = await customer_service.get_or_create_customer(session, shop_bot_id, CUSTOMER_TG_ID, "مشتری", None)
        order = await order_service.create_order(session, shop_bot_id, customer.id, OrderType.ORDER, "دو کیلو برنج", 400_000)
        order.status = OrderStatus.AWAITING_PAYMENT
        shop_bot = await session.get(ShopBot, shop_bot_id)
        order_id = order.id
        await session.commit()
        await customer_handlers._maybe_offer_online_payment(shop_bot_instance, session, shop_bot, order, CUSTOMER_TG_ID)
    return order_id


async def _methods(shop_bot_id: int) -> list[str]:
    async with session_scope() as session:
        shop_bot = await session.get(ShopBot, shop_bot_id)
        # ردیفِ تنظیماتِ پرداخت عمداً ساخته می‌شود؛ بدونِ آن فهرستِ روش‌ها خالی است و
        # ادعاهایِ «هست/نیست» بی‌معنا می‌شدند.
        row = await payment_settings_service.get_or_create(session, shop_bot_id)
        row.bale_enabled = True
        result = await creds.methods(session, shop_bot, row, include_manual=False)
        await session.commit()
        return result


async def test_incomplete_pair_never_offers_platform_payment() -> None:
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    await _configure_platform(provider=True)  # درگاهِ سراسری روشن — همین قبلاً پول را به پلتفرم می‌برد
    _invoice_calls.clear()
    real = bale_service.create_invoice_link
    bale_service.create_invoice_link = _fake_invoice  # type: ignore[assignment]
    try:
        with _Cfg():
            # الف) هیچ‌کدام
            await _set_provider(shop_bot_id, None)
            await _set_own_bot(shop_bot_id, connected=False)
            assert "bale" not in await _methods(shop_bot_id), "بدونِ جفت، گزینه به مشتری نشان داده نشود"
            await _order_and_offer(shop_bot_id)
            assert _invoice_calls == [], f"با جفتِ ناقص هیچ صورتحسابی نساز: {_invoice_calls}"

            # ب) فقط درگاهِ خودش (همان حالتِ گزارش‌شده توسطِ مالکِ محصول)
            await _set_provider(shop_bot_id, SHOP_PROVIDER)
            assert "bale" not in await _methods(shop_bot_id)
            await _order_and_offer(shop_bot_id)
            assert _invoice_calls == [], f"فقط درگاه کافی نیست: {_invoice_calls}"

            # ج) فقط رباتِ بله
            await _set_provider(shop_bot_id, None)
            await _set_own_bot(shop_bot_id, connected=True)
            assert "bale" not in await _methods(shop_bot_id)
            await _order_and_offer(shop_bot_id)
            assert _invoice_calls == [], f"فقط ربات کافی نیست: {_invoice_calls}"

            # د) جفتِ کامل ⇒ صورتحساب با توکنِ خودش و درگاهِ خودش، نه پلتفرم
            await _set_provider(shop_bot_id, SHOP_PROVIDER)
            assert "bale" in await _methods(shop_bot_id)
            await _order_and_offer(shop_bot_id)
            assert _invoice_calls == [(SHOP_BALE_TOKEN, SHOP_PROVIDER)], _invoice_calls
    finally:
        bale_service.create_invoice_link = real  # type: ignore[assignment]
    print("✅ test_incomplete_pair_never_offers_platform_payment PASSED")


async def test_platform_surface_still_serves_wallet_topup() -> None:
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    await _configure_platform(provider=True)
    with _Cfg():
        await _set_provider(shop_bot_id, None)
        await _set_own_bot(shop_bot_id, connected=False)
        link = creds.pay_link_for("payment-14-25")
        assert link and f"ble.ir/{PLATFORM_PAY_BOT}" in link and "start=payment-14-25" in link, link
        async with session_scope() as session:
            shop_bot = await session.get(ShopBot, shop_bot_id)
            row = await payment_settings_service.get(session, shop_bot_id)
            status = await creds.shop_status(session, shop_bot, row)
        assert not status.available and creds.MISSING_SHOP_BOT_TOKEN in status.missing
    print("✅ test_platform_surface_still_serves_wallet_topup PASSED")


async def test_texts_no_longer_promise_platform_wallet() -> None:
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    await _configure_platform(provider=True)
    with _Cfg():
        await _set_provider(shop_bot_id, SHOP_PROVIDER)  # فقط خانهٔ ۲ پر است
        async with session_scope() as session:
            shop_bot = await session.get(ShopBot, shop_bot_id)
            row = await payment_settings_service.get(session, shop_bot_id)
            status = await creds.shop_status(session, shop_bot, row)
            screen = main_texts.bale_provider_token_current(shop_bot, status.missing, "bot")
            smartening = main_texts.bale_shop_bot_status_text(shop_bot, status)
    for body in (screen, smartening):
        assert "پول در کیف‌پولِ پلتفرم می‌نشیند" not in body and "پول به کیف‌پولِ پلتفرم می‌رود" not in body, body
        assert "نشان داده نمی‌شود" in body or "فعال نیست" in body, body
    assert "خانه‌یِ ۱" in screen or "اول توکنِ رباتِ بله" in screen, screen
    assert "پنلِ توکن‌هایِ بله" not in screen, "علت نباید به پنلِ ادمین نسبت داده شود"
    assert main_texts.BALE_MISSING_HINTS[creds.MISSING_SHOP_PROVIDER_TOKEN].startswith("توکنِ درگاهِ بله‌پیِ خودت")
    assert "پرداخت با بله‌پی همچنان باز است" not in main_texts.BALE_PROVIDER_TOKEN_REMOVED
    assert "پلتفرم می‌نشیند (برایِ دریافتش با پشتیبانی هماهنگ کن)" not in main_texts.BALE_PROVIDER_TOKEN_REMOVED
    print("✅ test_texts_no_longer_promise_platform_wallet PASSED")


async def main() -> None:
    build_test_dispatchers()
    await test_incomplete_pair_never_offers_platform_payment()
    await test_platform_surface_still_serves_wallet_topup()
    await test_texts_no_longer_promise_platform_wallet()


if __name__ == "__main__":
    asyncio.run(main())
