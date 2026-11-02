"""
تست: P23 — لینکِ پرداختِ بله‌پی و پایانِ «دکمهٔ بی‌صدا»

دو باگِ واقعی که از لاگِ زنده و `payment_event_logs`ِ محیطِ توسعه گرفته شد:

۱. بله از `createInvoiceLink` با `ok: true` یکِ **شناسه** برمی‌گرداند
   («invoice_id=M6dm2AJsfX32GuWpmlCX»)، نه آدرس. کد همان را داخلِ `InlineKeyboardButton(url=…)`
   می‌گذاشت و تلگرام ردش می‌کرد:
   «Bad Request: inline keyboard button URL 'invoice_id=…' is invalid: Wrong HTTP URL»
   ⇒ پیامِ پرداخت هیچ‌وقت ارسال نمی‌شد و کاربر «دکمه هیچ کاری نمی‌کند» را تجربه می‌کرد.
۲. سه هندلرِ «روشِ پرداخت» `data["base_amount"]` را بدونِ بررسی می‌خواندند؛ با کیبوردِ کهنه یا
   ری‌استارتِ ربات (FSM در `MemoryStorage` است) `KeyError` *پیش ازِ* `callback.answer()`
   می‌افتاد ⇒ همان سکوت، حتی برایِ کارت‌به‌کارت که هیچ ربطی به بله ندارد.

اجرا: python3 tests_manual/run_one.py test_p23_bale_payment_link.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests_manual"))

from sqlalchemy import func, select  # noqa: E402

from harness import build_test_dispatchers, reset_database  # noqa: E402
from phase4_helpers import Chat  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from app.bots.main_bot import texts as main_texts  # noqa: E402
from app.database.models import Payment  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import bale_credentials_service, bale_service  # noqa: E402
from app.services.admin_settings_service import get_admin_settings  # noqa: E402

OWNER_TG_ID = 999_901
SHOP_BOT_TG_ID = 999_902
# رشتهٔ واقعیِ اندازه‌گیری‌شده از payment_event_logs همین محیط:
BALE_RAW_ID = "invoice_id=M6dm2AJsfX32GuWpmlCX"
TEMPLATE = "https://gateway.invalid/bale/pay?invoice_id={invoice_id}"
TEMPLATE_LINK = "https://gateway.invalid/bale/pay?invoice_id=M6dm2AJsfX32GuWpmlCX"


async def _payment_count() -> int:
    async with session_scope() as session:
        return int((await session.execute(select(func.count()).select_from(Payment))).scalar_one())


async def _configure_bale(*, template: str | None, provider: str = "provider-token-77") -> None:
    """همان چهار مقداری که پنلِ ادمین پر می‌کند: توکنِ ربات، توکنِ درگاه، سوییچ و قالبِ لینک."""
    async with session_scope() as session:
        admin = await get_admin_settings(session)
        admin.bale_bot_token = "111111:fake-bale-bot-token-for-tests"
        admin.bale_provider_token = provider
        admin.bale_pay_enabled = True
        admin.bale_pay_link_template = template
        await session.flush()
        await bale_credentials_service.refresh(session)


async def _run_to_payment_methods(chat: Chat) -> list[str]:
    """مسیرِ واقعیِ شارژ: کیف‌پول ← مبلغ ← ردِ کدِ تخفیف ← صفحهٔ «روش پرداخت»."""
    await chat.tap("topup_start")
    await chat.tap("topup_amount:100000")
    await chat.tap("skip_discount")
    return [btn.text for row in chat.last_markup.inline_keyboard for btn in row]


# ============================================================================= ۱ — تبدیلِ شناسه به لینک
def test_resolve_payment_link() -> None:
    assert bale_service.resolve_payment_link(BALE_RAW_ID, TEMPLATE) == TEMPLATE_LINK
    # خودِ رشتهٔ خام هم قابلِ passing است (اگر بله روزی فرمتِ دیگری خواست)
    raw_template = "https://gateway.invalid/bale/pay?params={invoice_params}"
    assert bale_service.resolve_payment_link(BALE_RAW_ID, raw_template) == (
        "https://gateway.invalid/bale/pay?params=invoice_id=M6dm2AJsfX32GuWpmlCX"
    )
    # اگر بله روزی آدرسِ کامل بدهد، همان رد می‌شود و قالب بی‌اثر است
    assert bale_service.resolve_payment_link("https://pay.example/abc", TEMPLATE) == "https://pay.example/abc"
    # P25: بدونِ قالبِ قابلِ‌استفاده، پیش‌فرضِ مستندِ بله ساخته می‌شود (نه None، نه لینکِ بی‌اعتبار)
    default_link = "https://bale.ai/pay/M6dm2AJsfX32GuWpmlCX"
    assert bale_service.resolve_payment_link(BALE_RAW_ID, None) == default_link
    assert bale_service.resolve_payment_link(BALE_RAW_ID, "") == default_link
    assert bale_service.resolve_payment_link(BALE_RAW_ID, "https://gateway.invalid/bale/pay") == default_link
    # P25: مقدارِ نمونهٔ داکیومنت (میزبانِ جعلی) همان باگی بود که دکمه را می‌کشت ⇒ نادیده گرفته می‌شود
    assert bale_service.resolve_payment_link(BALE_RAW_ID, "https://YOUR_BALE_PAYMENT_BASE_URL?invoice_id={invoice_id}") == default_link
    assert bale_service.usable_link_template("https://YOUR_BALE_PAYMENT_BASE_URL?invoice_id={invoice_id}") is False
    assert bale_service.usable_link_template(TEMPLATE) is True
    assert bale_service.usable_link_template("") is False  # خالی = «استفاده نکن»، نه «قابلِ استفاده»
    # پاسخِ بی‌شکل از بله هیچ‌وقت لینک نمی‌سازد
    assert bale_service.resolve_payment_link("not-a-link-and-no-equals", TEMPLATE) is None
    assert bale_service.resolve_payment_link("", TEMPLATE) is None
    print("✅ test_resolve_payment_link PASSED")


def test_valid_link_template() -> None:
    assert bale_service.valid_link_template(TEMPLATE) is True
    assert bale_service.valid_link_template("https://gateway.invalid/x?i={invoice_params}") is True
    assert bale_service.valid_link_template(None) is True  # «خالی» = پاک‌کردن، مجاز است
    assert bale_service.valid_link_template("gateway.invalid/x?i={invoice_id}") is False  # بدونِ پروتکل
    assert bale_service.valid_link_template("https://gateway.invalid/x") is False  # بدونِ جای‌نگهدار
    assert bale_service.valid_link_template("https://gateway.invalid/x?a=1 b={invoice_id}") is False  # فاصله
    print("✅ test_valid_link_template PASSED")


# ============================================================================= ۲ — پایانِ سکوت
async def test_stale_keyboard_answers_instead_of_crashing(main_dp) -> None:
    """بدونِ هیچ state‌ای (کیبوردِ کهنه/ری‌استارت) هر سه دکمه باید *جوابِ* دیدنی بدهند."""
    await reset_database()
    await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    await _configure_bale(template=TEMPLATE)
    async with session_scope() as session:
        admin = await get_admin_settings(session)
        admin.zarinpal_enabled = True
        admin.zarinpal_merchant_id = "00000000-0000-0000-0000-000000000000"
        await session.flush()

    chat = Chat(main_dp, OWNER_TG_ID)
    before = await _payment_count()
    for data in ("payment_method:card", "payment_method:zarinpal", "payment_method:bale"):
        await chat.tap(data)
        assert chat.last_toast["text"] == main_texts.PAYMENT_FLOW_STALE, (data, chat.last_toast)
        assert not chat.sent, f"با کیبوردِ کهنه نباید پیامی برود: {data} → {[m['text'][:40] for m in chat.sent]}"
    assert await _payment_count() == before, "ردیفِ پرداختِ بی‌سرانجام ساخته نمی‌شود"
    print("✅ test_stale_keyboard_answers_instead_of_crashing PASSED")


# ============================================================================= ۳ — نمایش = توانایی (بدونِ «قالبِ لازم»)
async def test_bale_button_follows_the_template(main_dp) -> None:
    """P25: دکمه به «قالبِ لینک» وابسته نیست؛ با توکن/درگاه/کلیدِ کامل ساخته می‌شود — قالبِ
    ناقصِ ادمین فقط نادیده گرفته می‌شود و پیش‌فرضِ مستندِ بله لینک را می‌سازد."""
    await reset_database()
    await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)

    await _configure_bale(template=None)
    chat = Chat(main_dp, OWNER_TG_ID)
    labels = await _run_to_payment_methods(chat)
    assert any("کارت‌به‌کارت" in label for label in labels), labels
    assert any("بله‌پی" in label for label in labels), f"قالبِ تنظیم‌نشده نباید دکمه را حذف کند: {labels}"

    # با همان پیکربندی، لینکِ ارسالی باید پیش‌فرضِ بله باشد و شناسه در آن نشسته باشد
    async def fake_invoice_link(*args, **kwargs):
        return BALE_RAW_ID

    original = bale_service.create_invoice_link
    bale_service.create_invoice_link = fake_invoice_link
    try:
        await chat.tap("payment_method:bale")
    finally:
        bale_service.create_invoice_link = original
    buttons = [btn for row in chat.last_markup.inline_keyboard for btn in row]
    assert buttons and buttons[0].url == "https://bale.ai/pay/M6dm2AJsfX32GuWpmlCX", [b.url for b in buttons]

    # و با قالبِ پنل، همان قالب برنده است
    await _configure_bale(template=TEMPLATE)
    chat2 = Chat(main_dp, OWNER_TG_ID)
    labels = await _run_to_payment_methods(chat2)
    assert any("بله‌پی" in label for label in labels), labels
    print("✅ test_bale_button_follows_the_template PASSED")


# ============================================================================= ۴ — لینکِ واقعی
async def test_bale_topup_sends_a_clickable_link(main_dp) -> None:
    await reset_database()
    await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    await _configure_bale(template=TEMPLATE)

    calls: list[tuple] = []

    async def fake_invoice_link(bot_token, provider_token, *, title, description, payload, amount_rial):
        calls.append((bot_token, provider_token, payload, amount_rial))
        return BALE_RAW_ID  # همان چیزی که بله واقعاً برمی‌گرداند

    original = bale_service.create_invoice_link
    bale_service.create_invoice_link = fake_invoice_link
    try:
        chat = Chat(main_dp, OWNER_TG_ID)
        await _run_to_payment_methods(chat)
        await chat.tap("payment_method:bale")
    finally:
        bale_service.create_invoice_link = original

    assert len(calls) == 1, calls
    assert calls[0][3] == 1_000_000, "۱۰۰٬۰۰۰ تومان باید ۱٬۰۰۰٬۰۰۰ ریال شود"
    assert chat.last_text == main_texts.BALE_PAY_REDIRECT_TEXT, chat.last_text
    buttons = [btn for row in chat.last_markup.inline_keyboard for btn in row]
    assert len(buttons) == 1 and buttons[0].url == TEMPLATE_LINK, [b.url for b in buttons]
    assert buttons[0].url.startswith("https://"), "لینک باید برایِ تلگرام قابل‌قبول باشد"
    assert await _payment_count() == 1, "ردیفِ پرداخت فقط وقتی لینک سالم بود ساخته می‌شود"
    print("✅ test_bale_topup_sends_a_clickable_link PASSED")


# ============================================================================= ۵ — پاسخِ غیرقابل‌استفاده
async def test_unresolvable_response_creates_nothing(main_dp) -> None:
    """اگر بله روزی چیزی بدهد که نه آدرس است نه «کلید=مقدار»: سکوت نه، لینکِ خراب نه."""
    await reset_database()
    await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    await _configure_bale(template=TEMPLATE)

    async def weird_response(*args, **kwargs):
        return "ok"

    original = bale_service.create_invoice_link
    bale_service.create_invoice_link = weird_response
    try:
        chat = Chat(main_dp, OWNER_TG_ID)
        await _run_to_payment_methods(chat)
        await chat.tap("payment_method:bale")
    finally:
        bale_service.create_invoice_link = original

    assert chat.last_text == main_texts.BALE_LINK_UNRESOLVED, chat.last_text
    assert chat.last_markup is None or all(
        btn.url is None for row in chat.last_markup.inline_keyboard for btn in row
    ), "هیچ دکمهٔ لینک‌دارِ بی‌اعتباری ارسال نمی‌شود"
    assert await _payment_count() == 0, "بدونِ لینکِ قابل‌کلیک هیچ ردیفِ پرداختی نمی‌ماند"
    print("✅ test_unresolvable_response_creates_nothing PASSED")


async def main() -> None:
    main_dp, _shop_dp, _bot_manager, _main_bot = build_test_dispatchers()
    test_resolve_payment_link()
    test_valid_link_template()
    try:
        await test_stale_keyboard_answers_instead_of_crashing(main_dp)
        await test_bale_button_follows_the_template(main_dp)
        await test_bale_topup_sends_a_clickable_link(main_dp)
        await test_unresolvable_response_creates_nothing(main_dp)
    finally:
        bale_credentials_service.reset_cache()


if __name__ == "__main__":
    asyncio.run(main())
