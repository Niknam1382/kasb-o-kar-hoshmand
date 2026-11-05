"""
تست: P22 — ثبتِ توکنِ درگاهِ بله‌پی از *همان* صفحهٔ «روش‌هایِ پرداختِ مشتری» (مشکلِ ۳ کاربر)

تا پیشِ این، داخلِ صفحهٔ تنظیماتِ پرداخت برایِ زرین‌پال دکمهٔ «🔑 مرچنتِ زرین‌پال» بود ولی برایِ
بله‌پی هیچِ ورودی نبود؛ فروشگاه‌دار باید دکمهٔ «💳 پرداختِ آنلاینِ سفارش‌ها» را در منویِ اصلی
پیدا می‌کرد — یعنی عملاً «قسمتِ ثبتِ بله‌پی وجود ندارد». حالا هر دو راهِ ورود به یکِ مسیرِ
ذخیره می‌رسند؛ این تست همان را (بدونِ هیچ تماسِ شبکه‌ای) می‌سنجد.

اجرا: python3 tests_manual/run_one.py test_p22_bale_token_in_panel.py
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from harness import build_test_dispatchers, reset_database  # noqa: E402
from phase4_helpers import Chat  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from app.bots.main_bot import keyboards, texts  # noqa: E402
from app.database.models import ShopBot  # noqa: E402
from app.database.session import session_scope  # noqa: E402

OWNER_TG_ID = 999_881
SHOP_BOT_TG_ID = 999_882


def _callbacks(markup) -> list[str]:
    return [b.callback_data for row in markup.inline_keyboard for b in row if b.callback_data]


async def _shop_bot_id() -> int:
    async with session_scope() as session:
        from sqlalchemy import select

        return int((await session.execute(select(ShopBot.id))).scalar_one())


async def test_payments_screen_offers_the_provider_token_button() -> None:
    """ساختارِ کیبورد: دکمهٔ تازه هست، کنارِ توکنِ زرین‌پال، و ترتیبِ بقیه دست‌نخورده است."""
    class _Row:
        card_enabled = True
        bale_enabled = False
        zarinpal_enabled = False
        manual_enabled = True
        auto_accept_online = False

    class _Bot:
        id = 1

    codes = _callbacks(keyboards.payments_menu_keyboard(_Row(), _Bot()))
    assert "pays_bale_token" in codes, codes
    assert codes.index("pays_bale_token") > codes.index("pays_tog:bale"), "بلافاصله بعدِ کلیدِ خودِ بله‌پی"
    assert codes[:6] == ["pays_card", "pays_tog:card", "pays_tog:bale", "pays_tog:zarinpal", "pays_tog:manual", "pays_tog:auto"], codes
    assert "pays_zp" in codes, "دکمهٔ مرچنتِ زرین‌پال هم سرِ جایش باشد"
    print("✅ test_payments_screen_offers_the_provider_token_button PASSED")


async def test_owner_can_store_and_remove_token_from_the_payments_screen(main_dp) -> None:
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    # P39: این صفحه *هر دو* توکن را می‌گیرد و اول آنچه کم است را می‌پرسد. رباتِ بله را از پیش
    # ثبت می‌کنیم تا مسیرِ توکنِ درگاه (ورودیِ نامعتبر + «حذف») سنجیده شود.
    async with session_scope() as session:
        shop_bot = await session.get(ShopBot, shop_bot_id)
        shop_bot.bale_encrypted_token = "777777:BALEFAKETOKENFORTHEPANELTEST00"
        await session.commit()
    owner = Chat(main_dp, OWNER_TG_ID)

    await owner.tap("pays_menu")
    # «پays_menu» همان پیام را ویرایش می‌کند (نه پیامِ تازه) ⇒ markup از edited_texts خوانده می‌شود
    markup = owner.last_edit_markup if owner.edits else owner.last_markup
    assert "pays_bale_token" in _callbacks(markup), _callbacks(markup)

    # ۱) ورودیِ تازه: همان صفحه را نشان می‌دهد (وضعیت + آنچه کم است) و منتظرِ توکن می‌نشیند
    await owner.tap("pays_bale_token")
    screen = owner.last_text
    # P39: «🏦 توکنِ درگاهِ بله‌پی» (سرتیترِ P35) به صفحهٔ دوورودیِ «پرداختِ آنلاینِ سفارش‌ها با
    # بله‌پی» تبدیل شد؛ دکمهٔ منو همان نامِ قبلی را نگه داشته است.
    assert "پرداختِ آنلاینِ سفارش‌ها با بله‌پی" in screen, screen
    assert "۱) توکنِ رباتِ بله" in screen and "۲) توکنِ درگاهِ بله‌پی" in screen, screen
    assert "توکنِ درگاهِ خودت را بفرست" in screen, "راهنمایِ صریحِ مرحلهٔ بعد"

    # ۲) ورودیِ نامعتبر: رد می‌شود و state می‌ماند (هیچ تماسِ شبکه‌ای هم لازم ندارد)
    await owner.say("xyz")
    assert texts.BALE_PROVIDER_TOKEN_INVALID in owner.last_text, owner.last_text

    # ۳) «حذف» از همین مسیر هم کار می‌کند (بدونِ شبکه) و توکنِ ثبت‌شده را برمی‌دارد
    async with session_scope() as session:
        from sqlalchemy import update

        await session.execute(update(ShopBot).values(bale_provider_token="PROVIDER-TOKEN-FOR-TEST-0001"))
        await session.commit()
    await owner.tap("pays_bale_token")
    await owner.say("حذف")
    assert texts.BALE_PROVIDER_TOKEN_REMOVED in owner.last_text, owner.last_text
    async with session_scope() as session:
        shop_bot = (await session.get(ShopBot, await _shop_bot_id())).bale_provider_token
    assert shop_bot in (None, ""), "توکن حذف شد"

    # ۴) راهنمایِ قدیمی که کاربر را به منویِ اصلی می‌فرستاد، به همین دکمه اشاره می‌کند
    shop_id = await _shop_bot_id()
    async with session_scope() as session:
        from app.services import payment_settings_service

        settings_row = await payment_settings_service.get_or_create(session, shop_id)
        settings_row.bale_enabled = False  # کلیدِ بله‌پی خاموش + توکنِ خالی ⇒ نگهبان باید حرف بزند
        await session.commit()
    await owner.tap("pays_tog:bale")
    toast = (owner.last_toast.get("text") or "") if owner.session.answered_callbacks else ""
    assert "pays_bale_token" not in toast and "توکنِ درگاهِ بله‌پی" in toast, repr(toast)
    print("✅ test_owner_can_store_and_remove_token_from_the_payments_screen PASSED")


async def main() -> None:
    main_dp, _shop_dp, _bot_manager, _main_bot = build_test_dispatchers()
    await test_payments_screen_offers_the_provider_token_button()
    await test_owner_can_store_and_remove_token_from_the_payments_screen(main_dp)


if __name__ == "__main__":
    asyncio.run(main())
