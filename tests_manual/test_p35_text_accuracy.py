"""
تست: P35 — متن‌هایی که باید عددِ تنظیمِ ادمین را بگویند، نه عددِ کهنه

پوشش:
۱. کدِ معرف: درصدِ زنده از `AdminSettings.referral_reward_value»، فقط به معرف — و هیچ‌وقت
   «۲۰٬۰۰۰ تومان» یا «هر دوتون» (ستونِ `referral_reward_wallet_toman` مرده است).
۲. صفحهٔ «🎁 کد معرف» در پنل هم همان درصد را نشان می‌دهد (مسیرِ واقعیِ هندلر، نه فقط تابع).
۳. پیامِ پاداش: `_notify_payment_result` با dictِ واقعیِ `referral_service` (که کلیدِ
   `referred_telegram_id` ندارد) دیگر KeyError نمی‌دهد و فقط به معرف خبر می‌دهد.
۴. کدِ تخفیفِ خریدِ اعتبار: درصدِ همان کد و مبلغِ کم‌شده را می‌گوید؛ پیامِ «کد کار نمی‌کند»
   سقفِ تعدادِ استفاده را هم نام می‌برد.
۵. صفحهٔ «توکنِ درگاه»: کوتاه شده و جملهٔ غلطِ «توکنِ ربات اینجا پرسیده نمی‌شود و لازم نیست»
   دیگر در آن نیست (از P34 هر دو ورودی لازم‌اند).

اجرا: python3 tests_manual/run_one.py test_p35_text_accuracy.py
"""
from __future__ import annotations

import asyncio
from decimal import Decimal
from types import SimpleNamespace

import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from aiogram import Bot

from harness import FakeSession, build_test_dispatchers, reset_database  # noqa: E402
from phase4_helpers import Chat  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from app import main as app_main  # noqa: E402
from app.bots.main_bot import texts  # noqa: E402
from app.database.models import DiscountType  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services.admin_settings_service import update_setting  # noqa: E402

OWNER_TG_ID = 7_200_000_061
SHOP_BOT_TG_ID = 7_200_000_062
FAKE_BOT_TOKEN = "000000:TEXTACCURACYFAKETOKENFORTESTS"


# ============================================================================= ۱ — کدِ معرف
def test_referral_text_uses_live_percent() -> None:
    stats = {"total": 3, "rewarded": 1}
    body = texts.referral_code_text("ABC123", stats, "my_main_bot", Decimal("12.50"))
    assert "۱۲" in body and "٪" in body, body
    assert "هر دوتون" not in body, body
    assert "۲۰٬۰۰۰" not in body, body
    assert "فقط به معرف" in body, body

    # درصدِ صفر ⇒ هیچ پاداشی وعده داده نشود
    zero = texts.referral_code_text("ABC123", stats, "my_main_bot", Decimal("0"))
    assert "صفر" in zero and "٪" not in zero.split("پاداشِ معرف")[0], zero

    # مقدارِ خراب/نداشتہ ⇒ متن نمی‌شکند
    broken = texts.referral_code_text("ABC123", stats, "my_main_bot", None)
    assert "صفر" in broken, broken
    print("✅ test_referral_text_uses_live_percent PASSED")


# ============================================================================= ۲ — همان چیز در پنل
async def test_panel_referral_screen_shows_percent(main_dp) -> None:
    await reset_database()
    await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    async with session_scope() as session:
        await update_setting(session, "referral_reward_value", Decimal("7.00"))
    owner = Chat(main_dp, OWNER_TG_ID)
    await owner.say("🎁 کد معرف")
    screen = owner.last_text
    assert "۷" in screen and "٪" in screen, screen
    assert "هر دوتون" not in screen and "۲۰٬۰۰۰" not in screen, screen
    print("✅ test_panel_referral_screen_shows_percent PASSED")


# ============================================================================= ۳ — پاداش فقط به معرف
async def test_reward_notification_does_not_raise_keyerror() -> None:
    """`process_referral_reward` این سه کلید را برمی‌گرداند؛ هیچ‌کدام `referred_telegram_id` نیست."""
    bot = Bot(token=FAKE_BOT_TOKEN, session=FakeSession())
    reward_info = {"referrer_telegram_id": 4242, "amount_toman": 5_000, "percent": "10"}
    await app_main._notify_payment_result(bot, 999, True, 50_000, reward_info)
    sent = [m["text"] for m in bot.session.sent_messages]
    assert len(sent) == 2, sent
    assert "۵٬۰۰۰" in sent[1] and "۱۰" in sent[1], sent[1]
    assert not hasattr(texts, "referred_reward_notification"), "پیامِ دوم به معرفی‌شده باید حذف شده باشد"
    print("✅ test_reward_notification_does_not_raise_keyerror PASSED")


# ============================================================================= ۴ — کدِ تخفیفِ اعتبار
def test_discount_texts_name_the_percent() -> None:
    percent_code = SimpleNamespace(code="YES10", type=DiscountType.PERCENT, value=Decimal("10.00"))
    body = texts.discount_applied_text(percent_code, 90_000, 100_000)
    assert "YES10" in body and "۱۰٪ تخفیف" in body, body
    assert "۱۰٬۰۰۰" in body, body  # مبلغی که واقعاً کم شده
    assert "۹۰٬۰۰۰" in body, body

    fixed_code = SimpleNamespace(code="OLD5", type=DiscountType.FIXED, value=Decimal("5000"))
    fixed_body = texts.discount_applied_text(fixed_code, 95_000, 100_000)
    assert "۵٬۰۰۰ تومان تخفیف" in fixed_body, fixed_body

    assert "سقفِ تعدادِ استفاده" in texts.INVALID_DISCOUNT_CODE, texts.INVALID_DISCOUNT_CODE
    print("✅ test_discount_texts_name_the_percent PASSED")


# ============================================================================= ۵ — صفحهٔ توکنِ درگاه
async def test_bale_provider_screen_is_short_and_correct() -> None:
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    async with session_scope() as session:
        from app.database.models import ShopBot

        shop_bot = await session.get(ShopBot, shop_bot_id)
        shop_bot.bale_provider_token = "SHOP-PROVIDER-TOKEN-0123456789"
        await session.flush()
    async with session_scope() as session:
        from app.database.models import ShopBot

        shop_bot = await session.get(ShopBot, shop_bot_id)
        body = texts.bale_provider_token_current(shop_bot, ())
    assert len(body) < 700, f"متن هنوز {len(body)} نویسه است"
    assert "پرسیده نمی‌شود و لازم نیست" not in body, body
    assert "توکنِ رباتِ بله" in body and "پنلِ پذیرندگان" in body, body
    assert "●●●●" in body, "نمایش فقط ماسک‌شده"
    print("✅ test_bale_provider_screen_is_short_and_correct PASSED")


async def main() -> None:
    main_dp, _shop_dp, _bot_manager, _main_bot = build_test_dispatchers()
    test_referral_text_uses_live_percent()
    await test_panel_referral_screen_shows_percent(main_dp)
    await test_reward_notification_does_not_raise_keyerror()
    test_discount_texts_name_the_percent()
    await test_bale_provider_screen_is_short_and_correct()


if __name__ == "__main__":
    asyncio.run(main())
