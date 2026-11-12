"""پ۵۸ · موردِ ۲۴-الف: دروازهٔ مود برایِ صفحه‌هایِ مخصوصِ مودِ فروشگاهی.

چرا این لازم بود: دکمه‌هایِ «👥 مشتری‌ها»، «🧾 مدیریتِ سفارش‌ها»، «🎯 کمپین‌ها»، «🧮 حسابداری»،
«💳 پرداختِ آنلاینِ سفارش‌ها» و «📝 سوال‌هایِ چک‌اوتِ سبد» از منویِ مودِ مشاوره‌ای حذف می‌شدند،
ولی خودِ هندلرها هیچ چکِ مودی نداشتند. کیبوردِ قدیمیِ تلگرام تا یکِ منویِ تازه عوض نشود همان
دکمه‌ها را نگه می‌دارد و متنِ دکمه را می‌شود تایپ هم کرد ⇒ فروشگاه‌دارِ مشاوره‌ای صفحه‌هایِ
ناتمامِ فروشگاهی را می‌دید (کمپین/حسابداری برایِ او هیچ معنایی ندارند).

پوششِ داده‌شده:
۱. هر ششِ ورودیِ متنی: در مودِ مشاوره پیامِ مودبانه، در مودِ فروشگاهی همان صفحهٔ قبلی.
۲. دو کال‌بکِ «سازندهٔ داده/حالت» (`campaign_new`، `bs_stock`): فقط اخطار، بدونِ صفحه و بدونِ
   سلاح‌کردنِ FSM (با کال‌بکِ ساختگی هم همین).
۳. کیبوردِ «⚙️ تنظیماتِ رباتِ فروشگاه»: دکمهٔ «📦 اخطارِ موجودی» در مشاوره نیست، در فروشگاهی هست.
۴. صفحه‌یِ جایگزینِ مشاوره («💬 گفتگوها و کاربران») دست‌نخورده کار می‌کند.

اجرا: python3 tests_manual/run_one.py test_p58_mode_gates.py
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from harness import build_test_dispatchers, reset_database  # noqa: E402
from phase4_helpers import Chat  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from app.bots.main_bot import texts
from app.bots.main_bot.handlers.orders_manage import BTN_ORDERS_MANAGE
from app.database.session import session_scope
from app.services import shop_owner_service

SALES_OWNER_TG = 995841
SALES_SHOP_TG = 995851
CONSULT_OWNER_TG = 995842
CONSULT_SHOP_TG = 995852

# ورودی‌هایِ متنیِ فقط-فروشگاهی + یکِ نشانهٔ مختصِ همان صفحه (برایِ ادعایِ «صفحه باز نشد»)
SALES_ONLY_ENTRIES = (
    ("👥 مشتری‌ها", "مشتری"),
    (BTN_ORDERS_MANAGE, "سفارش"),
    ("🎯 کمپین‌ها", "کمپین"),
    ("🧮 حسابداری", "حسابداری"),
    ("💳 پرداختِ آنلاینِ سفارش‌ها", "پرداخت"),
    ("📝 سوال‌هایِ چک‌اوتِ سبد", "سوال"),
)


async def seed_both_modes() -> None:
    """دو فروشگاهِ قابلِ استفاده: یکی فروشگاهی (پیش‌فرضِ سید)، یکی مشاوره‌ای."""
    await reset_database()
    await seed_usable_shop(SALES_OWNER_TG, SALES_SHOP_TG)
    await seed_usable_shop(CONSULT_OWNER_TG, CONSULT_SHOP_TG)
    async with session_scope() as session:
        owner = await shop_owner_service.get_by_telegram_id(session, CONSULT_OWNER_TG)
        await shop_owner_service.set_business_mode(session, owner, "consultation")


async def test_consultation_owner_gets_polite_gate(main_dp) -> None:
    await seed_both_modes()
    owner = Chat(main_dp, CONSULT_OWNER_TG)
    for label, _marker in SALES_ONLY_ENTRIES:
        before_messages = len(owner.sent)
        before_edits = len(owner.edits)
        await owner.say(label)
        assert owner.last_text == texts.MODE_SALES_ONLY, (label, owner.last_text)
        # دروازه باید *جایِ صفحه* بنشیند: نه صفحه‌یِ تازه، نه ویرایشِ صفحهٔ دیگر
        assert len(owner.sent) == before_messages + 1, (label, owner.sent[before_messages:])
        assert len(owner.edits) == before_edits, (label, owner.edits[before_edits:])
    print("PASS test_consultation_owner_gets_polite_gate")


async def test_sales_owner_still_reaches_every_screen(main_dp) -> None:
    await seed_both_modes()
    owner = Chat(main_dp, SALES_OWNER_TG)
    for label, marker in SALES_ONLY_ENTRIES:
        await owner.say(label)
        assert texts.MODE_SALES_ONLY not in owner.last_text, (label, owner.last_text)
        assert marker in owner.last_text, (label, owner.last_text)
    print("PASS test_sales_owner_still_reaches_every_screen")


async def test_crafted_callbacks_do_not_arm_states(main_dp) -> None:
    await seed_both_modes()
    owner = Chat(main_dp, CONSULT_OWNER_TG)
    for data in ("campaign_new", "bs_stock"):
        before_messages = len(owner.sent)
        await owner.tap(data)
        assert owner.last_toast["text"] == texts.MODE_SALES_ONLY, (data, owner.last_toast)
        assert len(owner.sent) == before_messages, (data, owner.sent[before_messages:])

    # سلاح‌نشدنِ FSM: متنِ بعدیِ او نباید پاسخِ ویزاردِ کمپین یا آستانهٔ موجودی باشد
    # (هیچ پیامی هم نباید ساخته شود؛ پس ادعا رویِ «نبودنِ» متن‌هاست، نه رویِ آخرین پیام)
    await owner.tap("campaign_new")
    await owner.say("کمپینِ پاییزه")
    await owner.tap("bs_stock")
    await owner.say("۵")
    sent = [row["text"] for row in owner.sent]
    assert all(texts.CAMPAIGN_ASK_NAME not in text for text in sent), sent
    assert all(texts.ASK_STOCK_THRESHOLD not in text for text in sent), sent
    assert all("موجودی" not in text for text in sent), sent

    # کنترلِ مثبت: همان دو کال‌بک برایِ فروشگاهِ فروشگاهی کار می‌کنند (پس تفاوت، همان دروازه است)
    sales = Chat(main_dp, SALES_OWNER_TG)
    await sales.tap("campaign_new")
    assert texts.CAMPAIGN_ASK_NAME in sales.last_text, sales.last_text
    await sales.tap("bs_stock")
    assert texts.ASK_STOCK_THRESHOLD in sales.last_text, sales.last_text
    print("PASS test_crafted_callbacks_do_not_arm_states")


async def test_settings_keyboard_hides_stock_alert_in_consultation() -> None:
    from app.bots.main_bot import keyboards
    from app.database.models import TenantMode

    for mode, should_show in ((TenantMode.SALES, True), (TenantMode.CONSULTATION, False)):
        # کیبوردِ تنظیمات فقط این چهار صفت را می‌خواند؛ شیءِ سبک‌تر از یکِ ردیفِ دیتابیس است
        shop_bot = type(
            "SB",
            (),
            {"tenant_mode": mode, "message_batch_seconds": None, "low_stock_alert_threshold": 5, "support_enabled": False},
        )()
        labels = [button.text for row in keyboards.shop_settings_keyboard(shop_bot).inline_keyboard for button in row]
        has_stock = any("اخطارِ موجودی" in label for label in labels)
        assert has_stock is should_show, (mode, labels)
    print("PASS test_settings_keyboard_hides_stock_alert_in_consultation")


async def test_consultation_replacement_screen_still_works(main_dp) -> None:
    await seed_both_modes()
    owner = Chat(main_dp, CONSULT_OWNER_TG)
    await owner.say(texts.CONSULT_CONTACTS_BUTTON)
    assert texts.MODE_SALES_ONLY not in owner.last_text, owner.last_text
    assert texts.CONSULT_CONTACTS_EMPTY in owner.last_text, owner.last_text

    # دروازه‌ها نباید چیزی از منویِ مشاوره کم کنند: «💬 گفتگوها و کاربران» سرِ جایش است و
    # هیچ‌کدام از دکمه‌هایِ فقط-فروشگاهی در منویِ مشاوره نمی‌آید (همان ادعایِ موردِ ۲۴).
    from app.bots.main_bot import keyboards

    consult_labels = {button.text for row in keyboards.shop_owner_panel_keyboard("consultation").keyboard for button in row}
    sales_labels = {button.text for row in keyboards.shop_owner_panel_keyboard("sales").keyboard for button in row}
    assert texts.CONSULT_CONTACTS_BUTTON in consult_labels, consult_labels
    assert texts.CONSULT_CONTACTS_BUTTON not in sales_labels, sales_labels
    for label, _marker in SALES_ONLY_ENTRIES:
        assert label not in consult_labels, (label, consult_labels)
        assert label in sales_labels, (label, sales_labels)
    print("PASS test_consultation_replacement_screen_still_works")


async def main() -> None:
    main_dp, _shop_dp, _bot_manager, _main_bot = build_test_dispatchers()
    await test_consultation_owner_gets_polite_gate(main_dp)
    await test_sales_owner_still_reaches_every_screen(main_dp)
    await test_crafted_callbacks_do_not_arm_states(main_dp)
    await test_settings_keyboard_hides_stock_alert_in_consultation()
    await test_consultation_replacement_screen_still_works(main_dp)
    print("📊 نتیجه: ۵ تستِ پ۵۸ (دروازهٔ مود) پاس شد · ششِ ورودی + دو کال‌بک + کیبورد + صفحهٔ جایگزین")


if __name__ == "__main__":
    asyncio.run(main())
