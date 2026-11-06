"""
تست: P18 · A1 + B11 — اعتبارهایِ بله‌پی از یک منبعِ واحد.

پوشش:
۱. توکنِ رباتِ بله از پنلِ ادمین اولویت بر `.env` دارد و بدونِ ری‌استارت اعمال می‌شود.
۲. توکنِ درگاه: اولِ فروشگاه، بعدِ پنلِ ادمین به‌عنوانِ پشتیبانِ سراسری.
۳. `shop_status` هر علتِ ناقص‌بودن را جدا گزارش می‌کند.
۴. **رگرسیونِ B11:** «دکمه‌یِ بله‌پی به مشتری» و «پرداختِ واقعاً ممکن» در هر پیکربندی هم‌ارزش‌اند.
۵. مشتری هرگز پیامِ فنی نمی‌بیند؛ فروشگاه‌دار راهنمایِ عملی می‌گیرد.
۶. منویِ «💳 روش‌هایِ پرداختِ مشتری» وضعیتِ واقعی را نشان می‌دهد (نه «✅ روشن»ِ دروغین).
۷. رازِ وب‌هوک فقط در حالتِ webhook و خودکار ساخته می‌شود؛ هرگز پرسیده نمی‌شود.
۸. حلقه‌یِ getUpdates توکنِ تازه را برمی‌دارد و offset را صفر می‌کند.
۹. اعتبارسنجیِ فرمتِ توکنِ ورودی.

اجرا: python3 tests_manual/test_p18_bale_credentials.py
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from harness import build_test_dispatchers, reset_database  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402
from test_orders_w2 import _Env, _seed  # noqa: E402

from app import main as app_main  # noqa: E402
from app.bots.main_bot import texts as main_texts  # noqa: E402
from app.bots.shop_bot import texts as shop_texts  # noqa: E402
from app.bots.shop_bot.handlers import payments as shop_payments  # noqa: E402
from app.config import settings  # noqa: E402
from app.database.models import ShopBot  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import (  # noqa: E402
    bale_credentials_service as creds,
    bale_service,
    bale_updates_service,
    payment_settings_service,
)
from app.services.admin_settings_service import get_admin_settings, update_setting  # noqa: E402

VALID_CARD = "4111111111111111"
SHOP_TOKEN = "SHOP-OWN-PROVIDER-TOKEN"
GLOBAL_TOKEN = "GLOBAL-ADMIN-PROVIDER-TOKEN"
ENV_BOT_TOKEN = "123456:ENV-BALE-BOT-TOKEN"
PANEL_BOT_TOKEN = "654321:PANEL-BALE-BOT-TOKEN"
# P41: جفتِ خودِ فروشگاه — تنها سطحی که پرداختِ سفارش با آن ساخته می‌شود.
OWN_BOT_TOKEN = "222222:SHOP-OWN-BALE-BOT-TOKEN-P18"
OWN_PAY_BOT = "shop_own_bale_bot_p18"
# P26: لینکِ پرداخت یعنی چتِ رباتِ پرداخت (`https://ble.ir/<username>?start=<payload>`)؛ نامِ
# کاربری در حالتِ عادی از getMe خوانده می‌شود و در تست از `remember_pay_bot_username` (بی‌شبکه).
PLATFORM_PAY_BOT = "platform_pay_bot"

_created: list[dict] = []
_sent_invoices: list[dict] = []


async def _fake_create_invoice_link(bot_token, provider_token, title, description, payload, amount_rial):
    _created.append({"bot_token": bot_token, "provider_token": provider_token, "payload": payload, "amount_rial": amount_rial})
    return f"invoice_id=fake-{payload}"


async def _fake_send_invoice(bot_token, chat_id, provider_token, *, title, description, payload, amount_rial):
    """جایِ `bale_service.send_invoice` — همان چیزی که P26 در مسیرِ `/start` می‌فرستد."""
    _sent_invoices.append(
        {"bot_token": bot_token, "chat_id": chat_id, "provider_token": provider_token, "payload": payload, "amount_rial": amount_rial}
    )


def _datas(markup) -> list[str]:
    return [b.callback_data for row in markup.inline_keyboard for b in row if b.callback_data] if markup else []


class _Cfg:
    """پیکربندیِ موقتِ settings که بعدِ هر تست به حالتِ اول برمی‌گردد."""

    def __init__(self, **values) -> None:
        self._values = values
        self._saved: dict = {}

    def __enter__(self):
        for key, value in self._values.items():
            self._saved[key] = getattr(settings, key)
            setattr(settings, key, value)
        creds.reset_cache()
        # P26: لینکِ پرداخت = چتِ رباتِ بله، پس نامِ کاربری (در حالتِ عادی از getMe) لازم است.
        # توکن که باشد، همان نامِ کاربری را می‌گذاریم تا تست به شبکه نزند؛ توکنِ خالی ⇒ کش خالی.
        if getattr(settings, "bale_bot_token", ""):
            creds.remember_pay_bot_username(PLATFORM_PAY_BOT)
        return self

    def __exit__(self, *_exc) -> None:
        for key, value in self._saved.items():
            setattr(settings, key, value)
        creds.reset_cache()


async def _configure(
    shop_bot_id: int, *, shop_token: bool, global_token: bool, admin_enabled: bool, card: bool = True, own_bot: bool = False
) -> None:
    async with session_scope() as session:
        row = await payment_settings_service.get_or_create(session, shop_bot_id)
        if card:
            payment_settings_service.set_card(row, VALID_CARD, "علی رضایی", "ملی")
            row.card_enabled = True
        row.bale_enabled = True
        if shop_token:
            (await session.get(ShopBot, shop_bot_id)).bale_provider_token = SHOP_TOKEN
        if global_token:
            await update_setting(session, "bale_provider_token", GLOBAL_TOKEN)
        await update_setting(session, "bale_pay_enabled", admin_enabled)
        if own_bot:
            # P41: پرداختِ سفارش با جفتِ «رباتِ بلهٔ خودش + درگاهِ خودش» است، نه سطحِ پلتفرم.
            shop_bot = await session.get(ShopBot, shop_bot_id)
            shop_bot.bale_encrypted_token = OWN_BOT_TOKEN
            shop_bot.bale_bot_id = 222222
            shop_bot.bale_bot_username = OWN_PAY_BOT
            shop_bot.bale_bot_enabled = True
        await session.commit()


# ============================================================================= ۱ و ۲ و ۳ و ۹ — سرویس
async def test_token_precedence_and_validation() -> None:
    await reset_database()
    with _Cfg(bale_bot_token=ENV_BOT_TOKEN, bale_updates_mode="polling", bale_webhook_secret=""):
        assert creds.bot_token() == ENV_BOT_TOKEN, "بدونِ مقدارِ پنل ⇒ .env"
        assert creds.valid_token_input(PANEL_BOT_TOKEN) and creds.valid_token_input(SHOP_TOKEN)
        for bad in ("", None, "کوتاه", "a" * 19, "دو تکه با فاصله در توکنِ بلند", "x" * 513):
            assert not creds.valid_token_input(bad), repr(bad)

        async with session_scope() as session:
            await update_setting(session, "bale_bot_token", PANEL_BOT_TOKEN)
        # بدونِ ری‌استارت: فقط یک refresh (که خودِ پنل و حلقه‌یِ getUpdates صدا می‌زنند)
        async with session_scope() as session:
            assert await creds.refresh(session) == PANEL_BOT_TOKEN
        assert creds.bot_token() == PANEL_BOT_TOKEN, "مقدارِ پنل بر .env اولویت دارد"

        async with session_scope() as session:
            await update_setting(session, "bale_bot_token", None)
            await creds.refresh(session)
        assert creds.bot_token() == ENV_BOT_TOKEN, "پاک‌کردنِ مقدارِ پنل ⇒ برگشت به .env"
    print("✅ test_token_precedence_and_validation PASSED")


async def test_provider_token_shop_first_then_global() -> None:
    await reset_database()
    shop_bot_id = await _seed_shop_only()
    with _Cfg(bale_bot_token=ENV_BOT_TOKEN):
        async with session_scope() as session:
            shop_bot = await session.get(ShopBot, shop_bot_id)
            assert await creds.provider_token(session, shop_bot) is None, "هیچ توکنی ⇒ None"
            await update_setting(session, "bale_provider_token", GLOBAL_TOKEN)
            assert await creds.provider_token(session, shop_bot) == GLOBAL_TOKEN, "پشتیبانِ سراسری"
            shop_bot.bale_provider_token = SHOP_TOKEN
            await session.flush()
            assert await creds.provider_token(session, shop_bot) == SHOP_TOKEN, "توکنِ فروشگاه اولویت دارد"
            assert await creds.provider_token(session, None) == GLOBAL_TOKEN, "بدونِ فروشگاه ⇒ سراسری"
    print("✅ test_provider_token_shop_first_then_global PASSED")


async def test_shop_status_reports_every_reason() -> None:
    await reset_database()
    shop_bot_id = await _seed_shop_only()
    own_bot_token = "222222:SHOP-OWN-BALE-BOT-P18-UPDATED"
    own_bot_username = "shop_p18_bot"
    with _Cfg(bale_bot_token=""):
        async with session_scope() as session:
            shop_bot = await session.get(ShopBot, shop_bot_id)
            row = await payment_settings_service.get_or_create(session, shop_bot_id)
            status = await creds.shop_status(session, shop_bot, row)
            # P41: ملاکِ پرداختِ سفارش، خودِ فروشگاه است ⇒ علت‌ها هم «خودش»‌اند. توکنِ رباتِ
            # پلتفرم و نامِ کاربریِ رباتِ پرداخت در این حالت دیگر شمارده نمی‌شوند، چون صورتحسابِ
            # سفارش با آن‌ها ساخته **نمی‌شود**.
            assert set(status.missing) == {
                creds.MISSING_SHOP_BOT_TOKEN,
                creds.MISSING_SHOP_PROVIDER_TOKEN,
                creds.ADMIN_DISABLED,
            }, status.missing
            assert not status.available
            # فروشگاه‌دار کلیدِ خودش را خاموش کرده ⇒ علتِ چهارم هم اضافه می‌شود
            row.bale_enabled = False
            status = await creds.shop_status(session, shop_bot, row)
            assert creds.SHOP_DISABLED in status.missing and len(status.missing) == 4, status.missing
            row.bale_enabled = True
            shop_bot.bale_provider_token = SHOP_TOKEN
            await update_setting(session, "bale_pay_enabled", True)
            await session.commit()

    with _Cfg(bale_bot_token=ENV_BOT_TOKEN):
        # P26: لینکِ پرداخت = چتِ ربات ⇒ نامِ کاربری (که در حالتِ عادی از getMe می‌آید) لازم است
        creds.remember_pay_bot_username(PLATFORM_PAY_BOT)
        async with session_scope() as session:
            shop_bot = await session.get(ShopBot, shop_bot_id)
            row = await payment_settings_service.get(session, shop_bot_id)
            status = await creds.shop_status(session, shop_bot, row)
            assert not status.available, "فقط توکنِ درگاه ⇒ پرداخت با ربات/درگاهِ پلتفرم ساخته نمی‌شود"
            assert creds.MISSING_SHOP_BOT_TOKEN in status.missing
            # جفتِ کاملِ خودش ⇒ فعال، و با ربات و درگاهِ **خودش** (پلتفرم دیگر مصرف نمی‌شود)
            shop_bot.bale_encrypted_token = own_bot_token
            shop_bot.bale_bot_id = 222222
            shop_bot.bale_bot_username = own_bot_username
            shop_bot.bale_bot_enabled = True
            await session.commit()

        async with session_scope() as session:
            shop_bot = await session.get(ShopBot, shop_bot_id)
            row = await payment_settings_service.get(session, shop_bot_id)
            status = await creds.shop_status(session, shop_bot, row)
            assert status.available and status.missing == (), status.missing
            assert status.bot_token == own_bot_token and status.provider_token == SHOP_TOKEN
            assert status.username == own_bot_username and status.uses_own_bot is True
            assert payment_settings_service.METHOD_BALE in await creds.methods(session, shop_bot, row)
    print("✅ test_shop_status_reports_every_reason PASSED")


# ============================================================================= ۴ و ۵ — رگرسیونِ B11
async def _payment_keyboard(env: _Env, group: str) -> list[str]:
    await env.cust_cb(f"pm_menu:{group}")
    return _datas(env.shop_bot.session.edited_texts[-1]["reply_markup"])


async def _run_matrix_case(
    dispatchers, *, shop_token: bool, global_token: bool, admin_enabled: bool, bot_token: str, own_bot: bool = False
) -> tuple[bool, bool, list[dict]]:
    """یک پیکربندیِ کامل را از چک‌اوت تا pm_bale می‌راند و برمی‌گرداند:
    (دکمه به مشتری نشان داده شد؟, پرداخت واقعاً لینک ساخت؟, لینک‌هایِ ساخته‌شده)."""
    _main_dp, shop_dp, bot_manager, main_bot = dispatchers
    shop_bot_id, p1, p2 = await _seed()
    await _configure(
        shop_bot_id, shop_token=shop_token, global_token=global_token, admin_enabled=admin_enabled, own_bot=own_bot
    )
    _created.clear()
    _sent_invoices.clear()
    with _Cfg(bale_bot_token=bot_token):
        shop_payments._last_owner_misconfig_alert.clear()  # محدودیتِ نرخِ هشدار بینِ تست‌ها نشت نکند
        env = _Env(shop_dp, _main_dp, bot_manager, main_bot, shop_bot_id, p1, p2)
        app_main._state["bot_manager"], app_main._state["main_bot"] = bot_manager, main_bot
        group = await env.checkout([p1, p2])
        shown = f"pm_bale:{group}" in await _payment_keyboard(env, group)
        await env.cust_cb(f"pm_bale:{group}")
        # P26: «پرداختِ واقعاً ممکن» یعنی مشتری لینکِ چتِ بله را گرفت **و** `/start`ِ همان لینک
        # صورتحساب را با توکنِ درگاهِ درست ساخت (تطبیقِ پولِ همان فروشگاه).
        link = _last_bale_link(env)
        worked = link is not None
        if worked:
            payload = link.split("start=", 1)[1]
            # P41: لینکِ فروشگاه با جفتِ کامل، در چتِ رباتِ *خودش* باز می‌شود ⇒ آپدیت هم با
            # توکنِ همان ربات می‌رسد (در واقعیت `bot_manager` این کار را می‌کند).
            await app_main._dispatch_bale_update(
                {"update_id": 1, "message": {"chat": {"id": 777001}, "text": f"/start {payload}"}},
                token=OWN_BOT_TOKEN if own_bot else None,
            )
        alert_texts = [a.get("text") or "" for a in env.cust_alerts()]
        assert shown == worked, (
            f"دکمه‌یِ بله‌پی و پرداختِ واقعی باید هم‌ارزش باشند (shown={shown}, worked={worked}) — "
            f"shop_token={shop_token} global_token={global_token} admin_enabled={admin_enabled} bot_token={bot_token!r}"
        )
        if not worked:
            assert shop_texts.PAY_METHOD_UNAVAILABLE in alert_texts, f"مشتری باید پیامِ مودبانه ببیند: {alert_texts}"
            assert not any("provider" in t.lower() or "BALE_BOT_TOKEN" in t for t in alert_texts), "پیامِ فنی به مشتری نرسد"
        return shown, worked, list(_sent_invoices)


def _last_bale_link(env) -> str | None:
    """آخرین لینکِ `ble.ir` که به مشتری نشان داده شده (از edit_text یا answer)."""
    session_obj = env.shop_bot.session
    for record in reversed(list(session_obj.edited_texts) + list(session_obj.sent_messages)):
        markup = record.get("reply_markup")
        for row in getattr(markup, "inline_keyboard", []) or []:
            for btn in row:
                url = getattr(btn, "url", None)
                if url and url.startswith("https://ble.ir/"):
                    return url
    return None


async def test_button_and_payment_never_disagree(shop_dp, main_dp, bot_manager, main_bot) -> None:
    dispatchers = (main_dp, shop_dp, bot_manager, main_bot)
    bale_service.create_invoice_link = _fake_create_invoice_link
    bale_service.send_invoice = _fake_send_invoice

    # ۱) جفتِ کاملِ خودِ فروشگاه ⇒ دکمه هست، لینک با درگاهِ خودش
    shown, worked, made = await _run_matrix_case(
        dispatchers, shop_token=True, global_token=False, admin_enabled=True, bot_token=ENV_BOT_TOKEN, own_bot=True
    )
    assert shown and worked and made[0]["provider_token"] == SHOP_TOKEN and made[0]["bot_token"] == OWN_BOT_TOKEN

    # ۲) توکنِ رباتِ پلتفرم از پنل باشد ⇒ بدونِ ری‌استارت خوانده می‌شود و اثری بر پرداختِ سفارش ندارد
    shown, worked, made = await _run_matrix_case(
        dispatchers, shop_token=True, global_token=False, admin_enabled=True, bot_token=PANEL_BOT_TOKEN, own_bot=True
    )
    assert shown and worked and made[0]["bot_token"] == OWN_BOT_TOKEN, "صورتحسابِ سفارش با رباتِ پلتفرم ساخته نشود"

    # ۳) **باگِ گزارش‌شده:** فروشگاه‌دار توکن را گذاشته ولی کلیدِ سراسریِ ادمین خاموش است
    shown, worked, _ = await _run_matrix_case(
        dispatchers, shop_token=True, global_token=False, admin_enabled=False, bot_token=ENV_BOT_TOKEN, own_bot=True
    )
    assert not shown and not worked, "بدونِ کلیدِ ادمین، دکمه اصلاً نباید به مشتری نشان داده شود"

    # ۴) P41: درگاهِ سراسری هست ولی فروشگاه درگاهِ خودش را ندارد ⇒ هیچ‌کدام.
    #    (پیش از این همین حالت پولِ مشتری را به کیف‌پولِ پلتفرم می‌ریخت.)
    shown, worked, _ = await _run_matrix_case(
        dispatchers, shop_token=False, global_token=True, admin_enabled=True, bot_token=ENV_BOT_TOKEN, own_bot=True
    )
    assert not shown and not worked, "پرداختِ سفارش با درگاهِ پلتفرم ساخته نمی‌شود"

    # ۵) هیچ توکنِ درگاهی نیست ⇒ نه دکمه، نه پرداخت
    shown, worked, _ = await _run_matrix_case(
        dispatchers, shop_token=False, global_token=False, admin_enabled=True, bot_token=ENV_BOT_TOKEN, own_bot=True
    )
    assert not shown and not worked

    # ۶) P41: توکنِ رباتِ *پلتفرم* نیست ولی جفتِ خودش کامل است ⇒ پرداختِ سفارش کار می‌کند
    shown, worked, made = await _run_matrix_case(
        dispatchers, shop_token=True, global_token=False, admin_enabled=True, bot_token="", own_bot=True
    )
    assert shown and worked and made[0]["bot_token"] == OWN_BOT_TOKEN

    # ۷) P41: فقط توکنِ درگاه، بدونِ رباتِ بلهٔ خودش (حالتی که مالکِ محصول دید) ⇒ هیچ‌کدام
    shown, worked, _ = await _run_matrix_case(
        dispatchers, shop_token=True, global_token=True, admin_enabled=True, bot_token=ENV_BOT_TOKEN, own_bot=False
    )
    assert not shown and not worked, "با جفتِ ناقص پولِ مشتری هرگز به کیف‌پولِ پلتفرم نمی‌نشیند"
    print("✅ test_button_and_payment_never_disagree PASSED")


async def test_owner_gets_actionable_notice_not_customer(shop_dp, main_dp, bot_manager, main_bot) -> None:
    """کیبوردِ کهنه: مشتری بله‌پی را می‌زند در حالی که پیکربندی ناقص است ⇒ پیامِ مودبانه به مشتری
    و راهنمایِ عملی به فروشگاه‌دار (با محدودیتِ نرخ)."""
    shop_bot_id, p1, p2 = await _seed()
    await _configure(shop_bot_id, shop_token=True, global_token=False, admin_enabled=True, own_bot=True)
    bale_service.create_invoice_link = _fake_create_invoice_link
    _created.clear()
    with _Cfg(bale_bot_token=ENV_BOT_TOKEN):
        shop_payments._last_owner_misconfig_alert.clear()
        env = _Env(shop_dp, main_dp, bot_manager, main_bot, shop_bot_id, p1, p2)
        app_main._state["bot_manager"], app_main._state["main_bot"] = bot_manager, main_bot
        group = await env.checkout([p1, p2])
        assert f"pm_bale:{group}" in await _payment_keyboard(env, group)
        # پیکربندی بعد از ساختِ کیبورد ناقص می‌شود (کلیدِ سراسری خاموش)
        async with session_scope() as session:
            await update_setting(session, "bale_pay_enabled", False)
        owner_before = len(main_bot.session.sent_messages)
        await env.cust_cb(f"pm_bale:{group}")
        assert not _created, "پرداختِ ناقص نباید لینک بسازد"
        assert shop_texts.PAY_METHOD_UNAVAILABLE in [a.get("text") or "" for a in env.cust_alerts()]
        notices = [m["text"] for m in main_bot.session.sent_messages[owner_before:]]
        assert len(notices) == 1 and main_texts.bale_misconfigured_notice((creds.ADMIN_DISABLED,)) == notices[0]
        # محدودیتِ نرخ: دابل‌تپ پیامِ دوم نمی‌سازد
        await env.cust_cb(f"pm_bale:{group}")
        assert len(main_bot.session.sent_messages) == owner_before + 1, "هشدارِ تکراری به فروشگاه‌دار نرود"
    print("✅ test_owner_gets_actionable_notice_not_customer PASSED")


async def test_owner_menu_reports_true_state(shop_dp, main_dp, bot_manager, main_bot) -> None:
    shop_bot_id, _p1, _p2 = await _seed()
    await _configure(shop_bot_id, shop_token=True, global_token=False, admin_enabled=False)
    with _Cfg(bale_bot_token=ENV_BOT_TOKEN):
        async with session_scope() as session:
            shop_bot = await session.get(ShopBot, shop_bot_id)
            row = await payment_settings_service.get(session, shop_bot_id)
            status = await creds.shop_status(session, shop_bot, row)
        text = main_texts.payments_menu_text(row, shop_bot, status.missing)
        assert "بله‌پی: ⛔️ خاموش" in text, text
        assert "⚠️ بله‌پی برایِ مشتری فعال نیست" in text and "کلیدِ سراسریِ بله‌پی خاموش است" in text, text
        # P41: درگاهِ سراسریِ مدیر دیگر پولِ سفارش را به پلتفرم نمی‌برد، پس ادعایِ «استفاده می‌شود»
        # نباید باشد و وضعیت هم تا جفتِ خودش کامل نشده «روشن» نمی‌شود.
        async with session_scope() as session:
            await update_setting(session, "bale_pay_enabled", True)
            await update_setting(session, "bale_provider_token", GLOBAL_TOKEN)
            shop_bot = await session.get(ShopBot, shop_bot_id)
            shop_bot.bale_provider_token = None
            await session.flush()
            row = await payment_settings_service.get(session, shop_bot_id)
            status = await creds.shop_status(session, shop_bot, row)
        text = main_texts.payments_menu_text(row, shop_bot, status.missing)
        assert "بله‌پی: ⛔️ خاموش" in text, text
        assert "توکنِ سراسریِ مدیر استفاده می‌شود" not in text, text
        assert "درگاهِ سراسری برایِ پرداختِ سفارش استفاده نمی‌شود" in text, text

        # جفتِ کاملِ خودِ فروشگاه ⇒ ✅ روشن (بدونِ هیچ درگاهِ سراسری)
        async with session_scope() as session:
            await update_setting(session, "bale_provider_token", "")
            shop_bot = await session.get(ShopBot, shop_bot_id)
            shop_bot.bale_provider_token = SHOP_TOKEN
            shop_bot.bale_encrypted_token = OWN_BOT_TOKEN
            shop_bot.bale_bot_id = 222222
            shop_bot.bale_bot_username = OWN_PAY_BOT
            shop_bot.bale_bot_enabled = True
            await session.flush()
            row = await payment_settings_service.get(session, shop_bot_id)
            status = await creds.shop_status(session, shop_bot, row)
        text = main_texts.payments_menu_text(row, shop_bot, status.missing)
        assert "بله‌پی: ✅ روشن" in text and not status.missing, text
        assert "درگاهِ سراسری" not in text, text
    print("✅ test_owner_menu_reports_true_state PASSED")


# ============================================================================= ۷ و ۸ — رازِ وب‌هوک و حلقه
async def test_webhook_secret_auto_generated_only_in_webhook_mode() -> None:
    await reset_database()
    with _Cfg(bale_bot_token=ENV_BOT_TOKEN, bale_updates_mode="polling", bale_webhook_secret=""):
        async with session_scope() as session:
            await creds.refresh(session)
        assert creds.webhook_secret() == "", "در polling هیچ رازی ساخته نمی‌شود"
        async with session_scope() as session:
            assert (await get_admin_settings(session)).bale_webhook_secret_auto in (None, "")

    with _Cfg(bale_bot_token=ENV_BOT_TOKEN, bale_updates_mode="webhook", bale_webhook_secret=""):
        async with session_scope() as session:
            await creds.refresh(session)
            generated = creds.webhook_secret()
            stored = (await get_admin_settings(session)).bale_webhook_secret_auto
        assert len(generated) >= 32 and generated == stored, "رازِ تصادفی خودکار ساخته و ذخیره می‌شود"
        async with session_scope() as session:
            await creds.refresh(session)
            assert creds.webhook_secret() == generated, "پایدار است؛ هر بار یکیِ تازه ساخته نمی‌شود"

    with _Cfg(bale_bot_token=ENV_BOT_TOKEN, bale_updates_mode="webhook", bale_webhook_secret="ENV-SECRET"):
        async with session_scope() as session:
            await creds.refresh(session)
        assert creds.webhook_secret() == "ENV-SECRET", ".env اولویت دارد"
    print("✅ test_webhook_secret_auto_generated_only_in_webhook_mode PASSED")


async def test_run_loop_picks_up_new_token_and_resets_offset() -> None:
    seen: list[tuple[str, int | None]] = []

    async def fetch(token, offset):
        seen.append((token, offset))
        return [{"update_id": 10}] if token == "TOKEN-A" else []

    async def handler(update) -> None:
        return None

    async def token_provider() -> str:
        # دو گردشِ اول با توکنِ .env، بعد پنل توکنِ تازه می‌گیرد (بدونِ ری‌استارت)
        return "TOKEN-B" if len(seen) >= 2 else "TOKEN-A"

    old_idle = bale_updates_service.IDLE_SLEEP_SECONDS
    bale_updates_service.IDLE_SLEEP_SECONDS = 0.01
    stop = asyncio.Event()
    try:
        loop = asyncio.create_task(bale_updates_service.run_loop("TOKEN-A", handler, stop, fetch, token_provider))
        await asyncio.sleep(0.3)
        stop.set()
        await asyncio.wait_for(loop, timeout=3)
    finally:
        bale_updates_service.IDLE_SLEEP_SECONDS = old_idle
    assert seen and seen[0] == ("TOKEN-A", None), seen
    assert ("TOKEN-A", 11) in seen, "offsetِ رباتِ فعلی جلو می‌رود"
    assert ("TOKEN-B", None) in seen, "با عوض‌شدنِ توکن، offset باید صفر شود"
    print("✅ test_run_loop_picks_up_new_token_and_resets_offset PASSED")


# ============================================================================= کمکی
async def _seed_shop_only() -> int:
    """فقط فروشگاه (بدونِ محصول) — برایِ تست‌هایِ سطحِ سرویس."""
    await reset_database()
    return await seed_usable_shop(7_200_000_001, 7_200_000_002)


async def main() -> None:
    _main_dp, shop_dp, bot_manager, main_bot = build_test_dispatchers()
    await test_token_precedence_and_validation()
    await test_provider_token_shop_first_then_global()
    await test_shop_status_reports_every_reason()
    await test_button_and_payment_never_disagree(shop_dp, _main_dp, bot_manager, main_bot)
    await test_owner_gets_actionable_notice_not_customer(shop_dp, _main_dp, bot_manager, main_bot)
    await test_owner_menu_reports_true_state(shop_dp, _main_dp, bot_manager, main_bot)
    await test_webhook_secret_auto_generated_only_in_webhook_mode()
    await test_run_loop_picks_up_new_token_and_resets_offset()


if __name__ == "__main__":
    asyncio.run(main())
