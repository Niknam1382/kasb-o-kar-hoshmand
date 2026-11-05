"""
تست: P34 — پرداختِ سفارش با «رباتِ بله + توکنِ درگاهِ خودِ فروشگاه»

پوشش:
۱. قاعدهٔ جفت: فقط توکنِ درگاه ⇒ پرداخت با رباتِ پلتفرم و یکِ هشدارِ روشن؛ هر دو ورودی ⇒
   جفتِ خودِ فروشگاه (رباتِ او + درگاهِ او).
۲. لینکِ پرداخت به چتِ همان ربات می‌رود (نه همیشه رباتِ پلتفرم).
۳. `/start`ِ صورتحساب: با رباتِ درست با توکنِ همان فروشگاه ساخته می‌شود؛ با رباتِ نادرست
   ساخته نمی‌شود و پیامِ «لینکِ کهنه» می‌رود. مبلغِ سفارشِ تکی هم دیگر AttributeError نمی‌دهد.
۴. پلِ `bot_manager`: آپدیتِ پرداختِ بله در رباتِ فروشگاه مصرف می‌شود و با توکنِ همان ربات به
   هندلرِ پرداخت می‌رود؛ آپدیتِ گفت‌وگو و `payment-` مصرف نمی‌شوند.
۵. پنلِ فروشگاه‌دار (P39): «💳 پرداختِ آنلاینِ سفارش‌ها» هر دو توکن را می‌گیرد (اول ربات، بعد
   درگاه) و صفحهٔ هوشمندسازیِ بله فقط توکنِ ربات را دارد.
۶. با کلیدِ رونماییِ خاموش، همان صفحه فقط توکنِ درگاه را می‌پرسد (اتصالِ بله که ساخته نشود،
   توکنِ ربات هم لازم نیست).

اجرا: python3 tests_manual/run_one.py test_p34_bale_own_payment_surface.py
"""
from __future__ import annotations

import asyncio
import sys
from types import SimpleNamespace

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from sqlalchemy import select  # noqa: E402

from harness import build_test_dispatchers, reset_database  # noqa: E402
from phase4_helpers import Chat  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from app import main as app_main  # noqa: E402
from app.bots.main_bot import texts as main_texts  # noqa: E402
from app.config import settings  # noqa: E402
from app.database.models import OrderConsultation, OrderStatus, OrderType, ShopBot  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import (  # noqa: E402
    bale_bot_service,
    bale_credentials_service as creds,
    bale_service,
    customer_service,
    payment_settings_service,
)
from app.services.admin_settings_service import update_setting  # noqa: E402

OWNER_TG_ID = 7_200_000_041
SHOP_BOT_TG_ID = 7_200_000_042
CUSTOMER_TG_ID = 7_200_000_043
PLATFORM_BOT_TOKEN = "111111:PLATFORM-BALE-BOT-TOKEN"
SHOP_BALE_TOKEN = "222222:SHOP-OWN-BALE-BOT-TOKEN"
SHOP_PROVIDER = "SHOP-OWN-PROVIDER-TOKEN-0123456789"
PLATFORM_PROVIDER = "PLATFORM-PROVIDER-TOKEN-0123456789"
SHOP_PAY_BOT = "shop_own_bale_bot"
PLATFORM_PAY_BOT = "platform_pay_bot"

_invoices: list[dict] = []
_texts: list[dict] = []


class _Cfg:
    """توکنِ رباتِ پلتفرم + نامِ کاربریِ رباتِ پرداخت، بدونِ شبکه؛ بعد برمی‌گردد."""

    def __enter__(self):
        self._saved_token = settings.bale_bot_token
        settings.bale_bot_token = PLATFORM_BOT_TOKEN
        creds.reset_cache()
        creds.remember_pay_bot_username(PLATFORM_PAY_BOT)
        return self

    def __exit__(self, *_exc):
        settings.bale_bot_token = self._saved_token
        creds.reset_cache()


async def _fake_send_invoice(bot_token, chat_id, provider_token, *, title, description, payload, amount_rial):
    _invoices.append(
        {"bot_token": bot_token, "chat_id": chat_id, "provider_token": provider_token, "payload": payload, "amount_rial": amount_rial}
    )


async def _fake_send_text(bot_token, chat_id, text, **kwargs):
    _texts.append({"bot_token": bot_token, "chat_id": chat_id, "text": text})


async def _configure_platform(*, provider: bool = True, pay_enabled: bool = True) -> None:
    async with session_scope() as session:
        await update_setting(session, "bale_provider_token", PLATFORM_PROVIDER if provider else "")
        await update_setting(session, "bale_pay_enabled", pay_enabled)


async def _set_shop_provider(shop_bot_id: int, value: str | None) -> None:
    async with session_scope() as session:
        shop_bot = await session.get(ShopBot, shop_bot_id)
        shop_bot.bale_provider_token = value
        await session.flush()


async def _connect_shop_bale_bot(shop_bot_id: int) -> None:
    """همان چیزی که «🔑 توکنِ ربات بله» در پنل می‌نویسد (رمزنگاری‌شده + شناسه + نامِ کاربری)."""
    async with session_scope() as session:
        shop_bot = await session.get(ShopBot, shop_bot_id)
        shop_bot.bale_encrypted_token = SHOP_BALE_TOKEN
        shop_bot.bale_bot_id = 987_654
        shop_bot.bale_bot_username = SHOP_PAY_BOT
        shop_bot.bale_bot_enabled = True
        await session.flush()


async def _status(shop_bot_id: int):
    async with session_scope() as session:
        shop_bot = await session.get(ShopBot, shop_bot_id)
        row = await payment_settings_service.get(session, shop_bot_id)
        return await creds.shop_status(session, shop_bot, row)


# ============================================================================= ۱ و ۲ — قاعدهٔ جفت و لینک
async def test_pair_rule_and_link_target() -> None:
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    await _configure_platform()
    with _Cfg():
        # الف) هیچ درگاهی نه از فروشگاه نه از پلتفرم ⇒ بله‌پی فعال نیست
        await _configure_platform(provider=False)
        status = await _status(shop_bot_id)
        assert not status.available and creds.MISSING_PROVIDER_TOKEN in status.missing, status.missing
        assert status.uses_own_bot is False and status.shop_bot_id is None

        # ب) فقط توکنِ درگاهِ فروشگاه ⇒ پرداخت با رباتِ پلتفرم، و هشدارِ روشن (باگِ گزارش‌شده)
        await _configure_platform(provider=True)
        await _set_shop_provider(shop_bot_id, SHOP_PROVIDER)
        status = await _status(shop_bot_id)
        assert status.available, status.missing
        assert status.bot_token == PLATFORM_BOT_TOKEN and status.provider_token == SHOP_PROVIDER
        assert status.username == PLATFORM_PAY_BOT and status.uses_own_bot is False
        assert creds.SHOP_HAS_PROVIDER_WITHOUT_BOT in status.warnings, status.warnings

        # ج) رباتِ بله را هم ثبت کرد ⇒ جفتِ خودِ فروشگاه: رباتِ او، درگاهِ او، چتِ او
        await _connect_shop_bale_bot(shop_bot_id)
        status = await _status(shop_bot_id)
        assert status.available and status.warnings == (), (status.missing, status.warnings)
        assert status.bot_token == SHOP_BALE_TOKEN and status.provider_token == SHOP_PROVIDER
        assert status.username == SHOP_PAY_BOT and status.uses_own_bot is True
        assert status.shop_bot_id == shop_bot_id

        link = creds.pay_link_for("order-1-aabbccddee", status.username)
        assert link and f"ble.ir/{SHOP_PAY_BOT}" in link and "start=order-1-aabbccddee" in link, link
        old_link = creds.pay_link_for("order-1-aabbccddee")
        assert old_link and f"ble.ir/{PLATFORM_PAY_BOT}" in old_link, old_link

        # د) رباتِ بله هست ولی درگاه ندارد ⇒ هشدارِِ دوم، و پرداخت با درگاهِ سراسری
        await _set_shop_provider(shop_bot_id, None)
        status = await _status(shop_bot_id)
        assert creds.SHOP_HAS_BOT_WITHOUT_PROVIDER in status.warnings, status.warnings
        assert status.provider_token == PLATFORM_PROVIDER and status.uses_own_bot is False
    print("✅ test_pair_rule_and_link_target PASSED")


# ============================================================================= ۳ — `/start` و صورتحساب
async def _make_order_with_payload(shop_bot_id: int) -> tuple[str, int]:
    async with session_scope() as session:
        customer = await customer_service.get_or_create_customer(session, shop_bot_id, CUSTOMER_TG_ID, "مشتری", None)
        order = OrderConsultation(
            shop_bot_id=shop_bot_id,
            customer_id=customer.id,
            type=OrderType.ORDER,
            summary="یکِ سفارشِ آزمون",
            estimated_value_toman=250_000,
            status=OrderStatus.AWAITING_PAYMENT,
            bale_invoice_payload="order-1-aabbccddee112233",
        )
        session.add(order)
        await session.flush()
        return order.bale_invoice_payload, order.estimated_value_toman


async def test_handoff_uses_matching_surface() -> None:
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    await _configure_platform()
    await _set_shop_provider(shop_bot_id, SHOP_PROVIDER)
    await _connect_shop_bale_bot(shop_bot_id)
    payload, amount = await _make_order_with_payload(shop_bot_id)

    real_create, real_text = bale_service.send_invoice, bale_service.send_text
    bale_service.send_invoice = _fake_send_invoice
    bale_service.send_text = _fake_send_text
    _invoices.clear()
    _texts.clear()
    try:
        with _Cfg():
            start = {"update_id": 1, "message": {"chat": {"id": CUSTOMER_TG_ID}, "text": f"/start {payload}"}}
            # رباتِ خودِ فروشگاه آپدیت را خوانده ⇒ صورتحساب با توکنِ همان فروشگاه و درگاهِ همان فروشگاه
            await app_main._dispatch_bale_update(dict(start), token=SHOP_BALE_TOKEN)
            assert len(_invoices) == 1, _invoices
            assert _invoices[0]["bot_token"] == SHOP_BALE_TOKEN, _invoices[0]
            assert _invoices[0]["provider_token"] == SHOP_PROVIDER, _invoices[0]
            assert _invoices[0]["amount_rial"] == amount * 10, _invoices[0]

            # همان لینک اگر به رباتِ پلتفرم برسد ⇒ جفت قاطی می‌شود ⇒ صورتحساب ساخته نمی‌شود
            _invoices.clear()
            await app_main._dispatch_bale_update({"update_id": 2, "message": {"chat": {"id": CUSTOMER_TG_ID}, "text": f"/start {payload}"}}, token=PLATFORM_BOT_TOKEN)
            assert not _invoices, "رباتِ نادرست نباید صورتحساب بسازد"
            assert any(main_texts.BALE_PAY_LINK_STALE in t["text"] for t in _texts), _texts
    finally:
        bale_service.send_invoice = real_create
        bale_service.send_text = real_text
    print("✅ test_handoff_uses_matching_surface PASSED")


# ============================================================================= ۴ — پلِ bot_manager
class _Update:
    """جایِ aiogram.Update — فقط همان چیزی که `_handle_bale_payment_update` مصرف می‌کند."""

    def __init__(self, raw: dict) -> None:
        self._raw = raw

    def model_dump(self, **kwargs) -> dict:
        return self._raw


async def test_bale_payment_bridge_consumes_only_payment_updates(bot_manager) -> None:
    await reset_database()
    calls: list[tuple[dict, str | None]] = []
    real = app_main._dispatch_bale_update

    async def fake_dispatch(data: dict, token: str | None = None) -> None:
        calls.append((data, token))

    app_main._dispatch_bale_update = fake_dispatch  # type: ignore[assignment]
    bot = SimpleNamespace(token=SHOP_BALE_TOKEN)
    try:
        pre_checkout = {"update_id": 1, "pre_checkout_query": {"id": "q1", "invoice_payload": "order-5-aabb"}}
        paid = {"update_id": 2, "message": {"successful_payment": {"invoice_payload": "cartgroup-7-aabb", "telegram_payment_charge_id": "t1"}}}
        start = {"update_id": 3, "message": {"chat": {"id": 5}, "text": "/start order-5-aabb"}}
        chat = {"update_id": 4, "message": {"chat": {"id": 5}, "text": "سلام، قیمت چنده؟"}}
        topup = {"update_id": 5, "message": {"chat": {"id": 5}, "text": "/start payment-9-aabbcc"}}

        for raw in (pre_checkout, paid, start):
            assert await bot_manager._handle_bale_payment_update(bot, _Update(raw)), raw
        for raw in (chat, topup):
            assert not await bot_manager._handle_bale_payment_update(bot, _Update(raw)), raw

        assert len(calls) == 3, calls
        assert all(token == SHOP_BALE_TOKEN for _, token in calls), calls
    finally:
        app_main._dispatch_bale_update = real  # type: ignore[assignment]
    print("✅ test_bale_payment_bridge_consumes_only_payment_updates PASSED")


# ============================================================================= ۵ — پنلِ دو ورودی
async def _reveal_bale_bots(shop_bot_id: int) -> None:
    async with session_scope() as session:
        await update_setting(session, "bale_shop_bots_enabled", True)
        shop_bot = await session.get(ShopBot, shop_bot_id)
        shop_bot.bale_bot_enabled = True


async def test_payment_screen_takes_both_inputs(main_dp, bot_manager) -> None:
    """P39: «💳 پرداختِ آنلاینِ سفارش‌ها» هر دو توکن را می‌گیرد (اول ربات، بعد درگاه) و
    صفحهٔ هوشمندسازیِ بله دیگر دکمهٔ توکنِ درگاه ندارد."""
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    await _configure_platform()
    await _reveal_bale_bots(shop_bot_id)

    bot_manager.register_bale = lambda shop_bot: asyncio.sleep(0)  # type: ignore[assignment] — بی‌شبکه
    owner = Chat(main_dp, OWNER_TG_ID)
    with _Cfg():
        await owner.say("💳 پرداختِ آنلاینِ سفارش‌ها")
        screen = owner.last_text
        assert "۱) توکنِ رباتِ بله" in screen and "۲) توکنِ درگاهِ بله‌پی" in screen, screen
        assert "تنظیم‌نشده" in screen, screen
        assert "اول توکنِ رباتِ بله" in screen, "چون رباتِ بله ثبت نشده، همان اول پرسیده می‌شود"

        await owner.say("کوتاه")
        assert owner.last_text == main_texts.BALE_SHOP_BOT_TOKEN_INVALID_FORMAT, owner.last_text

        real_fetch = bale_bot_service.fetch_identity

        async def fake_fetch(_token: str) -> dict:
            return {"id": 987_654, "username": SHOP_PAY_BOT}

        bale_bot_service.fetch_identity = fake_fetch  # type: ignore[assignment]
        try:
            await owner.say(SHOP_BALE_TOKEN)
        finally:
            bale_bot_service.fetch_identity = real_fetch  # type: ignore[assignment]
        assert owner.sent[-2]["text"] == main_texts.BALE_SHOP_BOT_SAVED, owner.sent[-2]["text"]
        assert "توکنِ درگاهِ خودت را بفرست" in owner.last_text, owner.last_text

        await owner.say("کوتاه")
        assert owner.last_text == main_texts.BALE_PROVIDER_TOKEN_INVALID, owner.last_text

        # جفتِ کامل ⇒ پیامِ ذخیره باید بگوید صورتحساب در چتِ رباتِ خودت می‌آید
        await owner.say(SHOP_PROVIDER)
        saved = owner.sent[-2]["text"]
        assert "رباتِ بله‌ات هم ثبت است" in saved, saved
        assert "همین دکمه را دوباره بزن" in owner.last_text, owner.last_text
        async with session_scope() as session:
            shop_bot = await session.get(ShopBot, shop_bot_id)
            assert shop_bot.bale_provider_token == SHOP_PROVIDER
            assert shop_bot.bale_bot_username == SHOP_PAY_BOT

        # «حذف» از همان صفحه کار می‌کند
        await owner.say("💳 پرداختِ آنلاینِ سفارش‌ها")
        await owner.say("حذف")
        assert main_texts.BALE_PROVIDER_TOKEN_REMOVED in owner.last_text, owner.last_text
        async with session_scope() as session:
            shop_bot = await session.get(ShopBot, shop_bot_id)
            assert shop_bot.bale_provider_token is None

        # صفحهٔ هوشمندسازیِ بله: فقط توکنِ ربات (دکمهٔ درگاه حذف شده است)
        await owner.say(main_texts.BALE_SHOP_BOT_BUTTON)
        datas = [b.callback_data for row in owner.last_markup.inline_keyboard for b in row]
        assert "bale_edit" in datas, datas
        assert "bale_provider_edit" not in datas, datas
        assert "۲)" not in owner.last_text, owner.last_text
    print("✅ test_payment_screen_takes_both_inputs PASSED")


async def test_payment_screen_asks_bot_token_only_when_revealed(main_dp) -> None:
    """کلیدِ رونماییِ ادمین خاموش ⇒ اتصالِ بله ساخته نمی‌شود، پس صفحهٔ پرداخت هم توکنِ ربات
    نمی‌پرسد و سراغِ همان توکنِ درگاه می‌رود (رفتارِ پیش از P39 برایِ نصب‌هایِ پنهان)."""
    await reset_database()
    await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    await _configure_platform()
    owner = Chat(main_dp, OWNER_TG_ID)
    with _Cfg():
        await owner.say("💳 پرداختِ آنلاینِ سفارش‌ها")
        screen = owner.last_text
        assert "اول توکنِ رباتِ بله" not in screen, screen
        assert "توکنِ درگاهِ خودت را بفرست" in screen, screen
        await owner.say(SHOP_PROVIDER)
        async with session_scope() as session:
            shop_bot = (await session.execute(select(ShopBot))).scalars().first()
            assert shop_bot.bale_provider_token == SHOP_PROVIDER
    print("✅ test_payment_screen_asks_bot_token_only_when_revealed PASSED")


async def main() -> None:
    main_dp, _shop_dp, bot_manager, _main_bot = build_test_dispatchers()
    await test_pair_rule_and_link_target()
    await test_handoff_uses_matching_surface()
    await test_bale_payment_bridge_consumes_only_payment_updates(bot_manager)
    await test_payment_screen_takes_both_inputs(main_dp, bot_manager)
    await test_payment_screen_asks_bot_token_only_when_revealed(main_dp)


if __name__ == "__main__":
    asyncio.run(main())
