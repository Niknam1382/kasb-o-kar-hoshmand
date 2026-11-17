"""
تست: P1-S2 — کیبوردِ رباتِ مشتریِ مود-آگاه (C1/A4)، دکمه‌یِ پشتیبانی (D1-direct)، دکمه‌یِ کهنه، خروج از FSM با دکمه‌یِ منو،
ترتیبِ تصمیمِ دستورِ سراسریِ AI + پیش‌فرضِ حرفه‌ای + «ابزارهایِ ربات» (J1–J3) و پیش‌فرضِ ۸ثانیه + typing (E2).

اجرا: python3 tests_manual/test_customer_menu_and_prompts.py
"""
from __future__ import annotations

import asyncio
import sys
import types

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from aiogram import Bot  # noqa: E402
from aiogram.fsm.context import FSMContext  # noqa: E402
from aiogram.fsm.storage.base import StorageKey  # noqa: E402
from sqlalchemy import select  # noqa: E402

from harness import FakeSession, build_test_dispatchers, make_message_update, reset_database  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from app.bots.main_bot import keyboards as main_keyboards  # noqa: E402
from app.bots.shop_bot import keyboards, texts  # noqa: E402
from app.bots.shop_bot.handlers import customer as customer_handlers  # noqa: E402
from app.bots.shop_bot.states import CheckoutStates  # noqa: E402
from app.database.models import ShopBot, TenantMode  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import ai_context, product_service, prompt_defaults, shop_bot_service  # noqa: E402

OWNER_TG_ID = 7_600_000_001
SHOP_BOT_TG_ID = 7_600_000_002
CUSTOMER_TG_ID = 7_600_000_003

S = types.SimpleNamespace


def _labels(markup) -> list[str]:
    # P24: «هیچ دکمه‌ای نه» هم یک پاسخِ معتبر است (ReplyKeyboardRemove کیبوردِ مرده را برمیدارد)
    rows = getattr(markup, "keyboard", None) or getattr(markup, "inline_keyboard", None) or []
    return [b.text for row in rows for b in row]


# =============================================================================
# J1–J3 — منطقِ خالص
# =============================================================================
def test_prompt_resolution_order_and_defaults() -> None:
    nothing = S(global_ai_prompt_sales=None, global_ai_prompt_consultation=None, global_ai_system_prompt=None)
    assert prompt_defaults.resolve_global_prompt(nothing, TenantMode.SALES) == prompt_defaults.DEFAULT_GLOBAL_PROMPT_SALES
    assert prompt_defaults.resolve_global_prompt(nothing, "consultation") == prompt_defaults.DEFAULT_GLOBAL_PROMPT_CONSULTATION, "بدونِ هیچ تنظیمی: پیش‌فرضِ حرفه‌ایِ همون مود"

    legacy = S(global_ai_prompt_sales=None, global_ai_prompt_consultation="  ", global_ai_system_prompt="قدیمی")
    assert prompt_defaults.resolve_global_prompt(legacy, TenantMode.SALES) == "قدیمی"
    assert prompt_defaults.resolve_global_prompt(legacy, TenantMode.CONSULTATION) == "قدیمی", "نسخه‌یِ فقط‌فاصله = خالی"

    both = S(global_ai_prompt_sales="فروش", global_ai_prompt_consultation="مشاوره", global_ai_system_prompt="قدیمی")
    assert prompt_defaults.resolve_global_prompt(both, TenantMode.SALES) == "فروش"
    assert prompt_defaults.resolve_global_prompt(both, TenantMode.CONSULTATION) == "مشاوره", "نسخه‌یِ مود بر قدیمی غلبه داره"

    sales, consult = prompt_defaults.DEFAULT_GLOBAL_PROMPT_SALES, prompt_defaults.DEFAULT_GLOBAL_PROMPT_CONSULTATION
    assert "«ابزارهایِ ربات»" in sales and "سفارش ثبت نمی‌کنی" in sales and "هرگز نگو «سفارشت ثبت شد»" in sales
    assert "فروشِ کالا و پرداختِ آنلاین ندارد" in consult and "هرگز خرید، سبد، پرداخت" in consult
    assert "افزودن به سبد" not in consult, "پرامپتِ مشاوره‌ای نباید دکمه‌یِ سبد پیشنهاد بده"
    print("✅ test_prompt_resolution_order_and_defaults PASSED")


def test_bot_tools_section_is_dynamic_and_optional() -> None:
    sales_tools = prompt_defaults.build_bot_tools(TenantMode.SALES, False, texts)
    # پ۱۰۸: «📦 سفارش‌هایِ من» هم در منو هست ⇒ باید در فهرستِ ابزارها باشد (تستِ همسانیِ پ۱۰۸).
    assert sales_tools == [
        f"«{texts.BTN_PRODUCTS}» — دیدنِ کاتالوگ",
        f"«{texts.BTN_CART}» — مرورِ سبد و تسویه‌حساب",
        f"«{texts.BTN_MY_ORDERS}» — سفارش‌هایِ خودت",
    ]
    assert any(texts.BTN_SUPPORT in line for line in prompt_defaults.build_bot_tools(TenantMode.SALES, True, texts))
    # P24: در مودِ مشاوره دکمه‌ای برایِ «خدمات» وجود ندارد (کاتالوگ بسته است) ⇒ AI هم نباید
    # به دکمه‌یِ غیرموجود ارجاع بدهد؛ تنها ابزارِ این مود پشتیبانی است.
    assert prompt_defaults.build_bot_tools(TenantMode.CONSULTATION, False, texts) == []
    assert prompt_defaults.build_bot_tools(TenantMode.CONSULTATION, True, texts) == [f"«{texts.BTN_SUPPORT}» — ارتباط با فروشگاه"]
    consult_tools = prompt_defaults.build_bot_tools(TenantMode.CONSULTATION, False, texts)
    assert not any("سبد" in line or "محصولات" in line for line in consult_tools), "مشاوره بدونِ هیچ اشاره به سبد/خرید"

    shop_bot = S(tenant_mode=TenantMode.SALES, ai_instructions=None)
    baseline = ai_context.build_system_prompt(shop_bot, [], None, "G")
    assert ai_context.build_system_prompt(shop_bot, [], None, "G", bot_tools=None) == baseline, "بدونِ ابزار، خروجی بایت‌به‌بایت مثلِ قبل"
    with_tools = ai_context.build_system_prompt(shop_bot, [], None, "G", bot_tools=sales_tools)
    assert with_tools.startswith(baseline.split("\n\nتوجه:")[0]) and "ابزارهایِ ربات" in with_tools and f"- «{texts.BTN_CART}»" in with_tools
    print("✅ test_bot_tools_section_is_dynamic_and_optional PASSED")


def test_customer_keyboard_per_mode_pure() -> None:
    assert _labels(keyboards.customer_main_keyboard(TenantMode.SALES, False)) == [texts.BTN_PRODUCTS, texts.BTN_CART, texts.BTN_MY_ORDERS]
    assert _labels(keyboards.customer_main_keyboard("sales", True)) == [texts.BTN_PRODUCTS, texts.BTN_CART, texts.BTN_MY_ORDERS, texts.BTN_SUPPORT]
    # P24: دو دکمهٔ مرده از منویِ مشاوره حذف شدند («خدمات» هیچ‌وقت پر نمی‌شد، «سفارش‌هایِ من»
    # فقط OrderType.ORDER را می‌خواند). بی‌پشتیبانی = کیبورد برداشته می‌شود.
    removed = keyboards.customer_main_keyboard(TenantMode.CONSULTATION, False)
    assert getattr(removed, "remove_keyboard", None) is True, "مشاوره بی‌پشتیبانی ⇒ هیچ دکمه‌ای نه"
    assert _labels(keyboards.customer_main_keyboard("consultation", True)) == [texts.BTN_SUPPORT]
    assert _labels(keyboards.customer_main_keyboard()) == [texts.BTN_PRODUCTS, texts.BTN_CART, texts.BTN_MY_ORDERS], "بدونِ آرگومان = فروشگاهی (سازگاری)"
    every = {b for mode in ("sales", "consultation") for flag in (True, False) for b in _labels(keyboards.customer_main_keyboard(mode, flag))}
    assert every <= texts.CUSTOMER_MENU_BUTTONS and texts.CUSTOMER_MENU_BUTTONS == {texts.BTN_PRODUCTS, texts.BTN_CART, texts.BTN_SERVICES, texts.BTN_SUPPORT, texts.BTN_MY_ORDERS}, "هر برچسب در مجموعه‌یِ escape هست"

    # منویِ فروشگاه‌دار (A4): مشاوره‌ای بدونِ چیزهایِ مخصوصِ فروش، «📞 پشتیبانی» در هر دو
    sales_owner = {b for row in main_keyboards.shop_owner_panel_keyboard(TenantMode.SALES).keyboard for b in map(lambda x: x.text, row)}
    consult_owner = {b for row in main_keyboards.shop_owner_panel_keyboard(TenantMode.CONSULTATION).keyboard for b in map(lambda x: x.text, row)}
    sales_only = {"💳 پرداختِ آنلاینِ سفارش‌ها", "📝 سوال‌هایِ چک‌اوتِ سبد", "🎯 کمپین‌ها"}
    assert sales_only <= sales_owner and not (sales_only & consult_owner)
    assert "📞 پشتیبانی" in sales_owner and "📞 پشتیبانی" in consult_owner and "🔀 نوعِ کسب‌وکار" not in sales_owner | consult_owner
    print("✅ test_customer_keyboard_per_mode_pure PASSED")


# =============================================================================
# E2 — پیش‌فرضِ ۸ثانیه + typing
# =============================================================================
async def test_default_window_and_typing_indicator() -> None:
    assert shop_bot_service.DEFAULT_MESSAGE_BATCH_SECONDS == 8
    calls: list[tuple[int, str]] = []

    class _Bot:
        async def send_chat_action(self, chat_id: int, action: str) -> None:
            calls.append((chat_id, action))

    await customer_handlers._sleep_with_typing(_Bot(), 11, 1.0)
    assert calls == [], "پنجره‌یِ کوتاه (<۲ث): typing نمی‌فرسته"
    await customer_handlers._sleep_with_typing(_Bot(), 11, 2.5)
    assert calls == [(11, "typing")], "پنجره‌یِ بلندتر: typing حینِ انتظار"

    class _FailingBot:
        async def send_chat_action(self, chat_id: int, action: str) -> None:
            raise RuntimeError("شبکه")

    await customer_handlers._sleep_with_typing(_FailingBot(), 11, 2.0)  # خطایِ typing نباید پردازش رو بشکنه
    print("✅ test_default_window_and_typing_indicator PASSED")


# =============================================================================
# C1 / D1 — رباتِ مشتری
# =============================================================================
async def test_customer_menu_support_stale_and_escape(shop_dp) -> None:
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    bot = Bot(token=f"{SHOP_BOT_TG_ID}:FAKE", session=FakeSession())
    session: FakeSession = bot.session  # type: ignore[assignment]
    n = 0

    async def say(text: str) -> dict:
        nonlocal n
        n += 1
        await shop_dp.feed_update(bot, make_message_update(n, text=text, user_id=CUSTOMER_TG_ID))
        return session.sent_messages[-1]

    async def update_shop(**fields) -> None:
        async with session_scope() as s:
            row = (await s.execute(select(ShopBot).where(ShopBot.id == shop_bot_id))).scalar_one()
            for key, value in fields.items():
                setattr(row, key, value)

    # فروشگاهی، بدونِ پشتیبانی
    msg = await say("/start")
    assert msg["text"] == texts.SHOP_WELCOME and _labels(msg["reply_markup"]) == [texts.BTN_PRODUCTS, texts.BTN_CART, texts.BTN_MY_ORDERS]
    assert (await say(texts.BTN_SUPPORT))["text"] == texts.SUPPORT_UNAVAILABLE, "دکمه‌یِ کهنه/غیرفعال: پیامِ مودبانه"

    # فعال‌سازیِ پشتیبانی (direct)
    await update_shop(support_enabled=True, support_contact_username="shop_help", support_contact_phone="+989123334444", support_contact_text="۹ تا ۱۷")
    msg = await say("/menu")
    assert msg["text"] == texts.MENU_REPLY and _labels(msg["reply_markup"]) == [texts.BTN_PRODUCTS, texts.BTN_CART, texts.BTN_MY_ORDERS, texts.BTN_SUPPORT]
    msg = await say(texts.BTN_SUPPORT)
    assert "@shop_help" in msg["text"] and "+989123334444" in msg["text"] and "۹ تا ۱۷" in msg["text"]
    assert msg["reply_markup"].inline_keyboard[0][0].url == "https://t.me/shop_help"

    # مشاوره‌ای (P24): هیچ دکمهٔ فروش/پیگیریِ مرده‌ای نیست؛ فقط پشتیبانی
    async with session_scope() as s:
        await product_service.create_product(s, shop_bot_id, "جلسه‌یِ مشاوره", None, 500_000, None, None)
    await update_shop(tenant_mode=TenantMode.CONSULTATION)
    msg = await say("/start")
    # P26: خوشامدِ مشاوره‌ای هیچ دکمه‌ای را وعده نمی‌دهد؛ فقط «پشتیبانی» (که این‌جا روشن است)
    assert msg["text"] == texts.shop_welcome_consultation(support_enabled=True)
    assert _labels(msg["reply_markup"]) == [texts.BTN_SUPPORT]
    assert "دکمه" not in texts.SHOP_WELCOME_CONSULTATION, "متنِ پایه نباید به دکمه‌ای اشاره کند"
    for stale in (texts.BTN_PRODUCTS, texts.BTN_CART, texts.BTN_SERVICES, texts.BTN_MY_ORDERS):
        msg = await say(stale)
        assert msg["text"] == texts.STALE_BUTTON_REPLY and _labels(msg["reply_markup"]) == [texts.BTN_SUPPORT]
    # (P24) قبلاً اینجا «فهرستِ خدمات» انتظار می‌رفت؛ آن فهرست در مودِ مشاوره همیشه خالی بود و
    # دکمه‌اش از منو حذف شده ⇒ همان تپِ کهنه به منویِ پشتیبانی برمی‌گردد (تکرارِ حلقهٔ بالا).

    # برگشت به فروشگاهی: دکمه‌یِ مشاوره کهنه می‌شه
    await update_shop(tenant_mode=TenantMode.SALES)
    msg = await say(texts.BTN_SERVICES)
    assert msg["text"] == texts.STALE_BUTTON_REPLY and _labels(msg["reply_markup"]) == [texts.BTN_PRODUCTS, texts.BTN_CART, texts.BTN_MY_ORDERS, texts.BTN_SUPPORT]

    # زدنِ دکمه‌یِ منو وسطِ FSMِ چک‌اوت: state پاک می‌شه و دکمه به هندلرِ خودش می‌رسه
    ctx = FSMContext(storage=shop_dp.storage, key=StorageKey(bot_id=SHOP_BOT_TG_ID, chat_id=CUSTOMER_TG_ID, user_id=CUSTOMER_TG_ID))
    await ctx.set_state(CheckoutStates.answering_questions)
    msg = await say(texts.BTN_PRODUCTS)
    assert await ctx.get_state() is None, "state باید پاک شده باشه"
    assert msg["text"] in (texts.PRODUCTS_BROWSE_TITLE, texts.NO_PRODUCTS_AVAILABLE), "جوابِ چک‌اوت نباید به‌جایِ دکمه بیاد"

    print("✅ test_customer_menu_support_stale_and_escape PASSED")


async def main() -> None:
    test_prompt_resolution_order_and_defaults()
    test_bot_tools_section_is_dynamic_and_optional()
    test_customer_keyboard_per_mode_pure()
    await test_default_window_and_typing_indicator()
    _main_dp, shop_dp, _bot_manager, _main_bot = build_test_dispatchers()
    await test_customer_menu_support_stale_and_escape(shop_dp)


if __name__ == "__main__":
    asyncio.run(main())
