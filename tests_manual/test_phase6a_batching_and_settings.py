"""
تست: فازِ ۶-الف — اصلاحِ «چند پیامِ پشتِ‌هم = چند جواب»، مدتِ تجمیعِ پیام‌ها (تنظیمِ فروشگاه‌دار)، محافظ‌هایِ ظرفیت،
فهرستِ فروشگاه‌دارها در پنلِ ادمین و دکمه‌یِ «⏭ رد کردن» برایِ مرحله‌هایِ اختیاریِ محصول.

ریشه‌یِ باگِ چند جواب: debounce فقط تا شروعِ پردازش جلویِ پیام‌ها رو می‌گرفت؛ پیامی که وسطِ فراخوانیِ AIِ دسته‌یِ قبلی
می‌رسید یه چرخه‌یِ جدا شروع می‌کرد و هم‌زمان جواب می‌داد. حالا برایِ هر (فروشگاه، مشتری) فقط یه پردازش هم‌زمان اجرا
می‌شه و پیام‌هایِ این فاصله بعدِ اتمامِ پردازشِ قبلی با هم و با یه جواب پردازش می‌شن.

پوشش:
۱. منطقِ خالص: parse_batch_seconds (ارقامِ فارسی، مرزها)، _batch_window (تنظیمِ فروشگاه یا پیش‌فرض)، برچسبِ فهرستِ ادمین.
۲. پیام‌هایِ وسطِ پردازش → دقیقاً یه دسته‌یِ بعدی؛ هیچ‌وقت دو فراخوانیِ هم‌زمانِ AI برایِ یه مشتری.
۳. پنجره‌یِ هر فروشگاه (۲..۶۰ ثانیه) اعمال می‌شه؛ بدونِ تنظیم همون پیش‌فرض.
۴. اتصالِ دیتابیس قبل از انتظارِ AI آزاد می‌شه (ظرفیت: با ۱۵ اتصال نباید فقط ۱۵ مشتریِ هم‌زمان سقف باشه).
۵. سقفِ فراخوانیِ هم‌زمانِ AI (semaphore).
۶. صفحه‌یِ «⚙️ تنظیماتِ ربات فروشگاه»: پیش‌تنظیم‌ها، مقدارِ دلخواه، اعتبارسنجی، بازگشت به پیش‌فرض، ایزولاسیون.
۷. فهرستِ فروشگاه‌دارها: «✅/⛔️ نام — @ربات»، «بدونِ ربات»، صفحه‌بندی با شمارِ کل.
۸. دکمه‌یِ «⏭ رد کردن» برایِ توضیح/عکس/موجودیِ محصول + دکمه‌یِ کهنه.

اجرا: python3 tests_manual/test_phase6a_batching_and_settings.py
"""
from __future__ import annotations

import asyncio
import sys
import types

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from aiogram import Bot  # noqa: E402
from sqlalchemy import select  # noqa: E402

from harness import FakeSession, build_test_dispatchers, make_message_update, reset_database  # noqa: E402
from phase4_helpers import Chat, FakeAi, callbacks, patched_ai, set_ai, wallet_transactions  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from app.bots.main_bot import texts  # noqa: E402
from app.bots.main_bot.handlers import owner_common  # noqa: E402
from app.bots.shop_bot.handlers import customer as customer_handlers  # noqa: E402
from app.config import settings  # noqa: E402
from app.database.models import ShopBot, WalletTransactionReason  # noqa: E402
from app.database.session import engine, session_scope  # noqa: E402
from app.services import ai_service, product_service, shop_bot_service, shop_owner_service  # noqa: E402
from app.services.order_detection_service import _CLASSIFIER_USER_PROMPT  # noqa: E402
from app.utils import validators  # noqa: E402

ADMIN_TG_ID = 12345  # باید با ADMIN_TELEGRAM_IDS توی .env یکی باشه
OWNER_TG_ID = 997001
SHOP_BOT_TG_ID = 997002
CUSTOMER_TG_ID = 997003
CUSTOMER2_TG_ID = 997004
OTHER_OWNER_TG_ID = 997011
OTHER_SHOP_BOT_TG_ID = 997012
STRANGER_TG_ID = 997021


class _TrackedAi(FakeAi):
    """FakeAi ـی که بیشینه‌یِ فراخوانی‌هایِ هم‌زمانِ «چت» رو هم ثبت می‌کنه (کلاسیفایرِ سفارش جدا می‌مونه)."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.active = 0
        self.max_active = 0

    async def get_reply(self, system_prompt, history, user_message):
        if user_message == _CLASSIFIER_USER_PROMPT:
            return await super().get_reply(system_prompt, history, user_message)
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        try:
            return await super().get_reply(system_prompt, history, user_message)
        finally:
            self.active -= 1


async def _wait_for(predicate, timeout: float = 10.0, step: float = 0.05) -> bool:
    waited = 0.0
    while waited < timeout:
        if predicate():
            return True
        await asyncio.sleep(step)
        waited += step
    return predicate()


def _new_shop_bot_instance() -> tuple[Bot, FakeSession]:
    bot = Bot(token=f"{SHOP_BOT_TG_ID}:FAKE", session=FakeSession())
    return bot, bot.session  # type: ignore[return-value]


async def _say(shop_dp, bot: Bot, update_id: int, text: str, user_id: int = CUSTOMER_TG_ID) -> None:
    await shop_dp.feed_update(bot, make_message_update(update_id, text=text, user_id=user_id))


# =============================================================================
# ۱. منطقِ خالص
# =============================================================================
def test_pure_batch_seconds_parsing_and_window_fallback() -> None:
    parse = shop_bot_service.parse_batch_seconds
    assert parse(2) == 2 and parse(60) == 60 and parse("15") == 15 and parse("  30 ") == 30
    assert parse("۱۵") == 15 and parse("٢٠") == 20, "ارقامِ فارسی/عربی هم پذیرفته می‌شه"
    for bad in (None, "", "abc", "1", 1, 0, -5, "61", 61, "12.5", "۱۵ ثانیه", "²", "①", "¹⁰", "-²"):
        assert parse(bad) is None, bad
    # «ارقامِ غیرِ اعشاری» (²، ①) از isdigit() رد می‌شن ولی int() روشون ValueError می‌ده؛ ورودیِ آزادِ کاربر نباید exception بده
    for odd in ("²", "①", "¹⁰", "-²"):
        assert owner_common.parse_suffix_int(f"bs_batch:{odd}", "bs_batch:") is None, odd
        assert validators.parse_price_toman(odd) is None and validators.parse_signed_toman_amount(odd) is None, odd
    suffix = owner_common.parse_suffix_int
    assert suffix("bs_batch:15", "bs_batch:") == 15 and suffix("bs_batch:", "bs_batch:") is None
    assert validators.parse_price_toman("۵۰,۰۰۰") == 50_000, "رفتارِ قبلی حفظ می‌شه"
    assert validators.parse_signed_toman_amount("-۱۲۰۰") == -1200, "رفتارِ قبلی حفظ می‌شه"
    assert shop_bot_service.DEFAULT_MESSAGE_BATCH_SECONDS == 8 and customer_handlers.DEBOUNCE_SECONDS == 8.0, "E2: پیش‌فرضِ ۳ ← ۸"

    window = customer_handlers._batch_window
    assert window(types.SimpleNamespace(message_batch_seconds=None)) == customer_handlers.DEBOUNCE_SECONDS
    assert window(types.SimpleNamespace(message_batch_seconds=15)) == 15.0
    assert window(types.SimpleNamespace(message_batch_seconds=1)) == customer_handlers.DEBOUNCE_SECONDS, "خارج از بازه نادیده گرفته می‌شه"
    assert window(types.SimpleNamespace(message_batch_seconds=999)) == customer_handlers.DEBOUNCE_SECONDS
    assert window(types.SimpleNamespace()) == customer_handlers.DEBOUNCE_SECONDS

    print("✅ test_pure_batch_seconds_parsing_and_window_fallback PASSED")


def test_owner_list_label_formats_pure() -> None:
    owner = types.SimpleNamespace(first_name="علی", last_name="رضایی", telegram_id=123456)
    nameless = types.SimpleNamespace(first_name=None, last_name=None, telegram_id=987654)
    active_bot = types.SimpleNamespace(bot_username="ali_shop_bot", is_active=True)
    suspended_bot = types.SimpleNamespace(bot_username="ali_shop_bot", is_active=False)

    label = texts.admin_owner_list_item_label
    assert label(owner) == "علی رضایی", "بدونِ اطلاعاتِ ربات رفتارِ قبلی (فقط نام)"
    assert label(owner, active_bot) == "✅ علی رضایی — @ali_shop_bot"
    assert label(owner, suspended_bot) == "⛔️ علی رضایی — @ali_shop_bot"
    assert label(owner, None) == "علی رضایی — بدونِ ربات"
    assert label(nameless, None) == "کاربرِ بی‌نام — بدونِ ربات", "بدونِ نام، هرگز آیدیِ عددی نمایش داده نمی‌شه (H2)"
    long_owner = types.SimpleNamespace(first_name="ن" * 80, last_name="", telegram_id=1)
    assert len(label(long_owner, active_bot)) <= texts.OWNER_LABEL_MAX_LEN and label(long_owner, active_bot).endswith("…")

    intro = texts.admin_shop_owners_intro(23, 1, 3)
    assert "23 نفر" in intro and "صفحه‌یِ 2 از 3" in intro and "✅" in intro and "⛔️" in intro

    print("✅ test_owner_list_label_formats_pure PASSED")


# =============================================================================
# ۲ و ۳. دسته‌بندیِ پیام‌ها
# =============================================================================
async def test_messages_during_processing_form_one_followup_batch(shop_dp) -> None:
    await reset_database()
    await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    fake = set_ai(_TrackedAi(chat_reply=lambda system_prompt, history, user_message: f"پاسخ به «{user_message}»", delay=1.0))
    bot, shop_session = _new_shop_bot_instance()

    original_debounce = customer_handlers.DEBOUNCE_SECONDS
    customer_handlers.DEBOUNCE_SECONDS = 0.3
    try:
        await _say(shop_dp, bot, 1, "پیامِ اول")
        # صبر تا پردازشِ دسته‌یِ اول واقعاً شروع بشه (AI ۱ ثانیه مشغوله)؛ بعدش پیام‌هایِ دوم و سوم وسطِ پردازش می‌رسن
        assert await _wait_for(lambda: len(fake.chat_calls) == 1, timeout=6.0)
        assert fake.chat_calls[0][2] == "پیامِ اول"
        await _say(shop_dp, bot, 2, "پیامِ دوم")
        await asyncio.sleep(0.3)
        await _say(shop_dp, bot, 3, "پیامِ سوم")  # هنوز وسطِ پردازشِ دسته‌یِ اول (AI تا ~۱ ثانیه‌یِ بعدی مشغوله)

        assert await _wait_for(lambda: len(fake.chat_calls) >= 2 and len(shop_session.sent_messages) >= 2, timeout=12.0)
        await asyncio.sleep(1.5)  # اگه باگ بود، دسته‌یِ سوم/جوابِ اضافه تا اینجا پیدا می‌شد

        assert [call[2] for call in fake.chat_calls] == ["پیامِ اول", "پیامِ دوم\nپیامِ سوم"], (
            "پیام‌هایِ وسطِ پردازش باید با هم و فقط یه‌بار (بعدِ اتمامِ دسته‌یِ اول) برن"
        )
        assert fake.max_active == 1, "هیچ‌وقت نباید دو فراخوانیِ هم‌زمانِ چت برایِ یه مشتری اجرا بشه"
        replies = [m["text"] for m in shop_session.sent_messages]
        assert replies == ["پاسخ به «پیامِ اول»", "پاسخ به «پیامِ دوم\nپیامِ سوم»"], "دقیقاً دو جواب، به ترتیب"
        assert len(await wallet_transactions(WalletTransactionReason.CHAT_MESSAGE)) == 2, "فقط دو بار هزینه"
        assert not customer_handlers._pending_buffers and not customer_handlers._pending_tasks, "هیچ بافر/تسکِ باقی‌مونده‌ای نمی‌مونه"
    finally:
        customer_handlers.DEBOUNCE_SECONDS = original_debounce

    print("✅ test_messages_during_processing_form_one_followup_batch PASSED")


async def test_per_shop_window_is_respected_and_default_unchanged(shop_dp) -> None:
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    fake = set_ai(FakeAi(chat_reply="باشه"))
    bot, _ = _new_shop_bot_instance()
    async with session_scope() as session:
        shop_bot = await shop_bot_service.get_by_id(session, shop_bot_id)
        await shop_bot_service.set_message_batch_seconds(session, shop_bot, 2)

    original_debounce = customer_handlers.DEBOUNCE_SECONDS
    customer_handlers.DEBOUNCE_SECONDS = 0.3
    try:
        # پنجره‌یِ ۲ ثانیه‌ای: فاصله‌یِ ۱٫۲ ثانیه‌یِ بینِ دو پیام جدا حساب نمی‌شه
        await _say(shop_dp, bot, 1, "الف۱", CUSTOMER_TG_ID)
        await asyncio.sleep(1.2)
        assert fake.chat_calls == [], "با پنجره‌یِ ۲ ثانیه‌ای هنوز نباید پردازشی شروع شده باشه (پیش‌فرضِ ۰٫۳ ثانیه بود)"
        await _say(shop_dp, bot, 2, "الف۲", CUSTOMER_TG_ID)
        assert await _wait_for(lambda: len(fake.chat_calls) >= 1, timeout=8.0)
        await asyncio.sleep(0.5)
        assert [call[2] for call in fake.chat_calls] == ["الف۱\nالف۲"], "هر دو پیام یه‌جا و یه‌بار"

        # بدونِ تنظیم → پیش‌فرض: همون فاصله دو دسته‌یِ جدا می‌شه
        async with session_scope() as session:
            shop_bot = await shop_bot_service.get_by_id(session, shop_bot_id)
            await shop_bot_service.set_message_batch_seconds(session, shop_bot, None)
        await _say(shop_dp, bot, 3, "ب۱", CUSTOMER2_TG_ID)
        await asyncio.sleep(1.2)
        await _say(shop_dp, bot, 4, "ب۲", CUSTOMER2_TG_ID)
        assert await _wait_for(lambda: len(fake.chat_calls) >= 3, timeout=8.0)
        await asyncio.sleep(0.8)
        assert [call[2] for call in fake.chat_calls][1:] == ["ب۱", "ب۲"], "پیش‌فرض (بدونِ تنظیم) رفتارِ قبلی رو حفظ می‌کنه"
    finally:
        customer_handlers.DEBOUNCE_SECONDS = original_debounce

    print("✅ test_per_shop_window_is_respected_and_default_unchanged PASSED")


# =============================================================================
# ۴ و ۵. ظرفیت
# =============================================================================
async def test_db_connection_is_released_before_ai_call(main_bot) -> None:
    shop_bot_id = await _seed_basic()
    checked_out_during_ai: list[int] = []

    class _ProbeAi(FakeAi):
        async def get_reply(self, system_prompt, history, user_message):
            if user_message != _CLASSIFIER_USER_PROMPT:
                checked_out_during_ai.append(engine.pool.checkedout())
            return await super().get_reply(system_prompt, history, user_message)

    set_ai(_ProbeAi(chat_reply="جواب"))
    bot, _ = _new_shop_bot_instance()
    async with session_scope() as session:
        await customer_handlers._generate_and_send_reply(session, shop_bot_id, CUSTOMER_TG_ID, "سلام", bot, main_bot)
    await asyncio.sleep(0.3)

    assert checked_out_during_ai == [0], (
        f"موقعِ انتظارِ AI نباید هیچ اتصالِ دیتابیسی گرفته بمونه؛ checked_out={checked_out_during_ai} "
        "(قبلاً هر مشتریِ منتظرِ AI یه اتصال از استخرِ محدود رو می‌بست)"
    )

    print("✅ test_db_connection_is_released_before_ai_call PASSED")


async def test_ai_concurrency_limiter_caps_parallel_calls() -> None:
    original_limit = settings.ai_max_concurrent_calls
    settings.ai_max_concurrent_calls = 3
    ai_service._ai_semaphores.clear()
    active = 0
    max_active = 0

    async def one_call() -> None:
        nonlocal active, max_active
        async with ai_service._ai_semaphore():
            active += 1
            max_active = max(max_active, active)
            await asyncio.sleep(0.05)
            active -= 1

    try:
        await asyncio.gather(*[one_call() for _ in range(15)])
        assert max_active == 3, f"سقفِ فراخوانیِ هم‌زمان باید ۳ باشه، نه {max_active}"
        assert settings.db_pool_size >= 5 and settings.db_max_overflow >= 0 and original_limit >= 1
        assert engine.pool.size() == settings.db_pool_size, "استخرِ دیتابیس از تنظیمات (DB_POOL_SIZE) خونده می‌شه"
    finally:
        settings.ai_max_concurrent_calls = original_limit
        ai_service._ai_semaphores.clear()

    print("✅ test_ai_concurrency_limiter_caps_parallel_calls PASSED")


async def _seed_basic() -> int:
    await reset_database()
    return await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)


# =============================================================================
# ۶. صفحه‌یِ تنظیماتِ فروشگاه‌دار
# =============================================================================
async def test_owner_settings_screen_for_batch_window(main_dp) -> None:
    shop_bot_id = await _seed_basic()
    await seed_usable_shop(OTHER_OWNER_TG_ID, OTHER_SHOP_BOT_TG_ID)
    owner = Chat(main_dp, OWNER_TG_ID)

    async def stored(bot_id: int = shop_bot_id) -> int | None:
        async with session_scope() as session:
            return (await session.execute(select(ShopBot.message_batch_seconds).where(ShopBot.id == bot_id))).scalar_one()

    await owner.say("⚙️ تنظیماتِ ربات فروشگاه")
    assert "8 ثانیه (پیش‌فرضِ سیستم)" in owner.last_text
    assert callbacks(owner.last_markup) == ["bs_batch:3", "bs_batch:8", "bs_batch:15", "bs_batch:30", "bs_batch_custom", "bs_batch_reset", "rp_open", "sp_prefs_open", "sp_open"]

    await owner.tap("bs_batch:15")
    assert await stored() == 15 and owner.last_toast["text"] == texts.BATCH_SECONDS_SAVED
    assert "مدتِ تجمیعِ پیام‌ها: 15 ثانیه" in owner.last_edit_text
    labels = [button.text for row in owner.last_edit_markup.inline_keyboard for button in row]
    assert "✅ 💰 ۱۵ ثانیه" in labels and "⚡ ۳ ثانیه" in labels, "مقدارِ فعلی علامت می‌خوره"

    # مقدارِ دلخواه: اعتبارسنجی، ارقامِ فارسی، ماندنِ state بعد از ورودیِ نامعتبر
    await owner.tap("bs_batch_custom")
    assert owner.last_text == texts.BATCH_SECONDS_ASK
    for bad in ("1", "100", "abc", "۰"):
        await owner.say(bad)
        assert owner.last_text == texts.BATCH_SECONDS_INVALID, bad
    assert await stored() == 15, "ورودیِ نامعتبر چیزی رو عوض نمی‌کنه"
    await owner.say("۲۰")
    assert await stored() == 20
    assert owner.sent[-2]["text"] == texts.BATCH_SECONDS_SAVED and "20 ثانیه" in owner.last_text

    await owner.tap("bs_batch_reset")
    assert await stored() is None and owner.last_toast["text"] == texts.BATCH_SECONDS_RESET
    assert "(پیش‌فرضِ سیستم)" in owner.last_edit_text

    # callbackِ جعلی/خارج از بازه
    for forged in ("bs_batch:99", "bs_batch:abc", "bs_batch:"):
        await owner.tap(forged)
        assert owner.last_toast["text"] == texts.SHOP_SETTINGS_STALE and owner.last_toast["show_alert"], forged
    assert await stored() is None

    # دکمه‌یِ منو وسطِ ورودیِ دلخواه
    await owner.tap("bs_batch_custom")
    await owner.say("🧮 حسابداری")
    assert owner.last_text.startswith("🧮 حسابداری — امروز"), "دکمه‌یِ منو باید از حالتِ ورودی خارج کنه"
    await owner.say("40")
    assert await stored() is None, "بعد از خروج، «40» دیگه تنظیمِ ثانیه حساب نمی‌شه"

    # ایزوله‌سازی: تنظیمِ این فروشگاه‌دار به فروشگاهِ دیگه نمی‌رسه؛ غیرفروشگاه‌دار ورود نداره
    await owner.tap("bs_batch:8")
    async with session_scope() as session:
        other_shop_bot = await shop_bot_service.get_by_bot_telegram_id(session, OTHER_SHOP_BOT_TG_ID)
        other_id = other_shop_bot.id
    assert await stored() == 8 and await stored(other_id) is None
    stranger = Chat(main_dp, STRANGER_TG_ID)
    await stranger.say("⚙️ تنظیماتِ ربات فروشگاه")
    assert stranger.last_text == texts.SHOP_BOT_NOT_SET_UP
    await stranger.tap("bs_batch:30")
    assert stranger.last_toast["show_alert"] and await stored() == 8

    print("✅ test_owner_settings_screen_for_batch_window PASSED")


# =============================================================================
# ۷. فهرستِ فروشگاه‌دارها (ادمین)
# =============================================================================
async def test_admin_owners_list_shows_shop_status_and_pages(main_dp) -> None:
    await reset_database()
    bot_ids = []
    for index in range(11):
        bot_ids.append(await seed_usable_shop(998100 + index, 998200 + index))
    async with session_scope() as session:
        suspended = await shop_bot_service.get_by_bot_telegram_id(session, 998201)
        suspended.is_active = False
        owner = await shop_owner_service.get_or_create_shop_owner(session, 998300)
        await shop_owner_service.complete_registration(session, owner, "بدونِ", "ربات", "09120000000", "x@example.com", True, True)

    admin = Chat(main_dp, ADMIN_TG_ID)
    await admin.say("👥 مدیریت فروشگاه‌دارها")
    assert admin.last_text == texts.admin_shop_owners_intro(12, 0, 2)
    page0 = [button.text for row in admin.last_markup.inline_keyboard for button in row if button.callback_data.startswith("admin_owner_view:")]
    assert len(page0) == 10
    assert page0[0] == "✅ فروشنده فعال — @shop_998200", "اسمِ فروشگاه‌دار + @ربات + وضعیت"
    assert page0[1] == "⛔️ فروشنده فعال — @shop_998201", "رباتِ معلق با ⛔️"
    assert "admin_owners_list:1" in callbacks(admin.last_markup)

    await admin.tap("admin_owners_list:1")
    assert admin.last_edit_text == texts.admin_shop_owners_intro(12, 1, 2)
    page1 = [button.text for row in admin.last_edit_markup.inline_keyboard for button in row if button.callback_data.startswith("admin_owner_view:")]
    assert page1 == ["✅ فروشنده فعال — @shop_998210", "بدونِ ربات — بدونِ ربات"], page1

    await admin.tap("admin_owners_list:99")  # صفحه‌یِ خارج از بازه به آخرین صفحه snap می‌شه
    assert admin.last_edit_text == texts.admin_shop_owners_intro(12, 1, 2)
    assert bot_ids

    print("✅ test_admin_owners_list_shows_shop_status_and_pages PASSED")


# =============================================================================
# ۸. دکمه‌یِ «رد کردن» برایِ محصول
# =============================================================================
async def test_product_skip_buttons_cover_all_optional_steps(main_dp) -> None:
    shop_bot_id = await _seed_basic()
    owner = Chat(main_dp, OWNER_TG_ID)

    await owner.tap("product_add")
    assert owner.last_text == texts.ASK_PRODUCT_NAME
    await owner.say("چایِ ممتاز")
    assert owner.last_text == texts.ASK_PRODUCT_DESCRIPTION and callbacks(owner.last_markup) == ["product_skip:description"]
    await owner.tap("product_skip:description")
    assert owner.last_text == texts.ASK_PRODUCT_PRICE
    await owner.say("50000")
    assert owner.last_text == texts.ASK_PRODUCT_PHOTO and callbacks(owner.last_markup) == ["product_skip:photo"]
    await owner.tap("product_skip:photo")
    assert owner.last_text == texts.ASK_PRODUCT_STOCK and callbacks(owner.last_markup) == ["product_skip:stock"]
    await owner.tap("product_skip:stock")
    assert texts.product_added_confirmation("چایِ ممتاز") in [m["text"] for m in owner.sent]

    async with session_scope() as session:
        products = await product_service.get_active_by_shop_bot(session, shop_bot_id)
    assert len(products) == 1
    assert products[0].name == "چایِ ممتاز" and products[0].description is None and products[0].photo_file_id is None
    assert products[0].price_toman == 50_000 and products[0].stock_quantity is None, "رد کردنِ موجودی = نامحدود"

    # دکمه‌یِ کهنه (بدونِ state) بی‌خطر رد می‌شه و چیزی نمی‌سازه
    for step in ("description", "photo", "stock"):
        await owner.tap(f"product_skip:{step}")
        assert owner.last_toast["text"] == texts.PRODUCT_SKIP_STALE and owner.last_toast["show_alert"], step
    async with session_scope() as session:
        assert len(await product_service.get_active_by_shop_bot(session, shop_bot_id)) == 1

    # مسیرِ متنیِ «رد شدن» همچنان کار می‌کنه (سازگاری با رفتارِ قبلی) و دکمه‌هایِ مراحل هم با متن قاطی نمی‌شن
    await owner.tap("product_add")
    await owner.say("قهوه")
    await owner.say("رد شدن")
    await owner.say("80000")
    await owner.say("رد شدن")
    await owner.say("5")
    async with session_scope() as session:
        names = sorted(p.name for p in await product_service.get_active_by_shop_bot(session, shop_bot_id))
    assert names == sorted(["قهوه", "چایِ ممتاز"]), names

    print("✅ test_product_skip_buttons_cover_all_optional_steps PASSED")


async def main() -> None:
    test_pure_batch_seconds_parsing_and_window_fallback()
    test_owner_list_label_formats_pure()
    main_dp, shop_dp, _bot_manager, main_bot = build_test_dispatchers()
    with patched_ai():
        await test_messages_during_processing_form_one_followup_batch(shop_dp)
        await test_per_shop_window_is_respected_and_default_unchanged(shop_dp)
        await test_db_connection_is_released_before_ai_call(main_bot)
        await test_ai_concurrency_limiter_caps_parallel_calls()
        await test_owner_settings_screen_for_batch_window(main_dp)
        await test_admin_owners_list_shows_shop_status_and_pages(main_dp)
        await test_product_skip_buttons_cover_all_optional_steps(main_dp)


if __name__ == "__main__":
    asyncio.run(main())
