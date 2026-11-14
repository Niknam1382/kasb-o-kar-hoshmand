"""پ۶۹ · موردِ ۳۶: برآوردِ هزینهٔ تمام‌شدهٔ AI از توکن‌هایِ واقعی + صفحهٔ ادمین.

پوششِ داده‌شده:
۱. خالص: `estimate_tokens` و کفِ پرامپتِ سیستمی (فروشگاهی در برابرِ مشاوره‌ای، با و بدونِ پرامپتِ
   سراسریِ ادمین) — برچسبِ ESTIMATED حفظ می‌شود.
۲. خالص: ریاضِ `CostView` رویِ ردیف‌هایِ ساختگی — میانگینِ توکن، «گرفته‌شده به‌ازایِ هر ۱۰۰۰ توکن»،
   هزینهٔ خام، نسبتِ گرفته/هزینه، پوشش، و None وقتی دادهٔ اندازه‌گرفته نداریم.
۳. نوشتن: توکنِ یکِ فراخوانی فقط یک‌بار ثبت می‌شود، حتی وقتی کسر بینِ دو بسته پخش شده باشد.
۴. `observe`: پنجرهٔ زمانی، حذفِ ردیف‌هایِ بی‌AI و ردیف‌هایِ قدیمی، و درستیِ جمع‌ها در دو قابلیت.
۵. پنلِ سوپرادمین: یکِ پیام با ارقامِ جلالی، برچسبِ هر قابلیت، سه عددِ قیمت، تغییرِ بازه، بازگشت،
   و ورودیِ دست‌کاری‌شده ⇒ بازگشت به بازهٔ پیش‌فرض (بدونِ خطا).
۶. دسترسی: ادمینِ عملیاتی ⇒ صفر پیام و صفر ویرایش؛ کیبوردِ منویِ قیمت دکمه را دارد.

اجرا: python3 tests_manual/run_one.py test_p69_ai_cost_estimate.py
"""
from __future__ import annotations

import asyncio
import datetime
import sys
from decimal import Decimal

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from sqlalchemy import select  # noqa: E402

from aiogram import Bot  # noqa: E402

from harness import FakeSession, build_test_dispatchers, make_callback_update, make_message_update, reset_database  # noqa: E402
from phase4_helpers import Chat  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from app.bots.main_bot import keyboards, texts as main_texts  # noqa: E402
from app.database.models import ShopOwner, WalletTransaction, WalletTransactionReason  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import admin_role_service, ai_cost_service, admin_settings_service, wallet_service  # noqa: E402

ADMIN_TG_ID = 12345
OPERATOR_TG_ID = 996655
OWNER_TG_ID = 995511
SHOP_BOT_TG_ID = 995512
def _now() -> datetime.datetime:
    """زمانِ تازه: ردیف‌هایِ تست *بعد ازِ* این فراخوانی نوشته نمی‌شوند، پس پنجره گمشان نمی‌کند."""
    return datetime.datetime.now(datetime.timezone.utc)


def _datas(markup) -> list[str]:
    return [b.callback_data for row in markup.inline_keyboard for b in row if b.callback_data] if markup else []


def _ascii_digits(text: str) -> str:
    return "".join(char for char in text if char.isascii() and char.isdigit())


async def _owner_id(user_id: int) -> int:
    async with session_scope() as session:
        return int(
            (await session.execute(select(ShopOwner.id).where(ShopOwner.telegram_id == user_id))).scalars().one()
        )


async def _rows(user_id: int) -> list[WalletTransaction]:
    owner_id = await _owner_id(user_id)
    async with session_scope() as session:
        return list(
            (
                await session.execute(
                    select(WalletTransaction).where(WalletTransaction.shop_owner_id == owner_id).order_by(WalletTransaction.id)
                )
            ).scalars().all()
        )


async def _set_pricing(usd_per_1m: str, rate: int, per_1k: int, markup: str = "5.00") -> None:
    async with session_scope() as session:
        settings = await admin_settings_service.get_admin_settings(session)
        settings.ai_cost_usd_per_1m_tokens = Decimal(usd_per_1m)
        settings.usd_to_toman_rate = rate
        settings.wallet_cost_per_1k_tokens_toman = per_1k
        settings.wallet_markup_multiplier = Decimal(markup)


async def _charge_twice(user_id: int) -> None:
    """دو بسته‌یِ کوچک ⇒ هر کسرِ بزرگ‌تر از یکِ بسته، بینِ دو ردیف پخش می‌شود."""
    owner_id = await _owner_id(user_id)
    async with session_scope() as session:
        owner = await session.get(ShopOwner, owner_id)
        await wallet_service.add_charge(session, owner, 1_000, reason=WalletTransactionReason.TOPUP)
        await wallet_service.add_charge(session, owner, 1_000, reason=WalletTransactionReason.TOPUP)


# ============================================================================= ۱ — خالصِ پرامپت
def test_prompt_floor_is_estimated_not_measured() -> None:
    assert ai_cost_service.estimate_tokens("") == 0 and ai_cost_service.estimate_tokens(None) == 0
    assert ai_cost_service.estimate_tokens("ا" * 35) == 10

    sales = ai_cost_service.prompt_floor_text(consultation=False)
    consult = ai_cost_service.prompt_floor_text(consultation=True)
    assert "دستورالعمل‌های بالا" in sales and "Markdown" in sales, sales[:200]
    assert "توجه: فعلاً هیچ محصولی" in sales, "با صفر محصول، فروشگاهی خطِ «هیچ محصولی» را می‌گیرد"
    assert "توجه: فعلاً هیچ محصولی" not in consult and sales != consult
    assert ai_cost_service.prompt_floor_tokens(consultation=False) > 0

    with_global = ai_cost_service.prompt_floor_text(consultation=False, global_prompt="قاعدهٔ سراسریِ ادمین")
    assert with_global.startswith("قاعدهٔ سراسریِ ادمین")
    assert ai_cost_service.estimate_tokens(with_global) > ai_cost_service.estimate_tokens(sales)
    print("✅ test_prompt_floor_is_estimated_not_measured PASSED")


# ============================================================================= ۲ — خالصِ ریاض
def _view(rows: tuple[ai_cost_service.FeatureRow, ...]) -> ai_cost_service.CostView:
    return ai_cost_service.CostView(
        since=_now() - datetime.timedelta(days=30),
        until=_now(),
        rows=rows,
        price_per_1k_toman=50,
        raw_cost_per_1m_usd=Decimal("0.020"),
        usd_to_toman_rate=100_000,
        markup_multiplier=Decimal("5.00"),
        suggested_price_per_1k=1_000,
        prompt_floor_sales=400,
        prompt_floor_consultation=300,
    )


def test_cost_view_math() -> None:
    chat = ai_cost_service.FeatureRow("chat_message", calls=10, measured_calls=8, tokens=8_000, charged_toman=900, charged_measured_toman=640)
    voice = ai_cost_service.FeatureRow("voice_transcription", calls=2, measured_calls=0, tokens=0, charged_toman=200, charged_measured_toman=0)
    view = _view((chat, voice))

    assert view.calls == 12 and view.measured_calls == 8
    assert view.tokens == 8_000 and view.charged_toman == 1_100
    assert view.mean_tokens == 1_000 and chat.mean_tokens == 1_000
    assert view.coverage == 8 / 12
    assert view.raw_cost_per_1k_toman == Decimal("2")  # ۰٫۰۲ دلار برایِ هر میلیون ⇒ ۰٫۰۰۰۰۲ دلار برایِ هر هزار ≈ ۲ تومان
    assert view.measured_raw_cost_toman == Decimal("16")  # ۸٬۰۰۰ توکن × ۲ ÷ ۱۰۰۰
    assert view.charged_per_1k == 80 and chat.charged_per_1k == 80
    assert view.margin_ratio() == Decimal("40"), view.margin_ratio()
    assert view.margin_ratio("voice_transcription") is None, "بدونِ توکنِ اندازه‌گرفته ⇒ نسبت نمی‌سازیم"
    assert voice.charged_per_1k == 0 and voice.mean_tokens == 0

    empty = _view(())
    assert empty.margin_ratio() is None and empty.coverage == 0.0 and empty.mean_tokens == 0
    print("✅ test_cost_view_math PASSED")


def test_text_uses_only_jalali_digits() -> None:
    view = _view(
        (ai_cost_service.FeatureRow("chat_message", 10, 8, 8_000, 900, 640),)
    )
    body = main_texts.ai_cost_text(view, 30)
    assert "۳۰ روز گذشته" in body and main_texts.AI_COST_FEATURE_LABELS["chat_message"] in body
    assert _ascii_digits(body) == "", _ascii_digits(body)
    assert "MEASURED" in body and "EXTRAPOLATED" in body and "ESTIMATED" in body

    empty = _view(())
    assert main_texts.AI_COST_NO_DATA in main_texts.ai_cost_text(empty, 7)
    no_measure = _view((ai_cost_service.FeatureRow("cart_edit", 3, 0, 0, 300, 0),))
    assert main_texts.AI_COST_NO_MEASURE in main_texts.ai_cost_text(no_measure, 30)
    print("✅ test_text_uses_only_jalali_digits PASSED")


# ============================================================================= ۳ — نوشتنِ توکن
async def test_deduct_records_tokens_once_across_lots() -> None:
    await reset_database()
    await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID, initial_balance_toman=0)
    await _charge_twice(OWNER_TG_ID)
    owner_id = await _owner_id(OWNER_TG_ID)
    async with session_scope() as session:
        owner = await session.get(ShopOwner, owner_id)
        ok = await wallet_service.deduct(
            session, owner, 1_500, WalletTransactionReason.CHAT_MESSAGE, ai_total_tokens=1_234
        )
        assert ok
    rows = await _rows(OWNER_TG_ID)
    deductions = [row for row in rows if row.amount_toman < 0]
    assert len(deductions) == 2, "کسرِ ۱٬۵۰۰ بینِ دو بسته‌یِ ۱٬۰۰۰ تومنی پخش می‌شود"
    assert sum(row.ai_total_tokens or 0 for row in deductions) == 1_234, "توکن یک‌بار ثبت می‌شود، نه دو بار"
    assert sum(1 for row in deductions if row.ai_total_tokens is not None) == 1
    topups = [row for row in rows if row.amount_toman > 0]
    assert all(row.ai_total_tokens is None for row in topups), "ردیفِ شارژ بی‌AI است"
    print("✅ test_deduct_records_tokens_once_across_lots PASSED")


# ============================================================================= ۴ — observe
async def test_observe_windows_groups_and_skips_non_ai() -> None:
    await reset_database()
    await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID, initial_balance_toman=0)
    await _set_pricing("0.020", 100_000, 50)
    owner_id = await _owner_id(OWNER_TG_ID)
    async with session_scope() as session:
        owner = await session.get(ShopOwner, owner_id)
        await wallet_service.add_charge(session, owner, 10_000, reason=WalletTransactionReason.TOPUP)
        await wallet_service.deduct(session, owner, 600, WalletTransactionReason.CHAT_MESSAGE, ai_total_tokens=3_000)
        await wallet_service.deduct(session, owner, 400, WalletTransactionReason.CHAT_MESSAGE, ai_total_tokens=1_000)
        await wallet_service.deduct(session, owner, 300, WalletTransactionReason.CART_EDIT)  # بی‌usage
        # یکِ ردیفِ قدیمی (۴۰ روز) بیرونِ پنجره، و یکِ ردیفِ بی‌AIِ پولی (کمیسیون)
        session.add(
            WalletTransaction(
                shop_owner_id=owner_id, amount_toman=-500, reason=WalletTransactionReason.CHAT_MESSAGE,
                ai_total_tokens=9_000, created_at=_now() - datetime.timedelta(days=40),
            )
        )
        session.add(
            WalletTransaction(
                shop_owner_id=owner_id, amount_toman=-70, reason=WalletTransactionReason.COMMISSION,
                ai_total_tokens=5_000, created_at=_now(),
            )
        )
        await session.flush()

    settings = None
    async with session_scope() as session:
        settings = await admin_settings_service.get_admin_settings(session)
        view = await ai_cost_service.observe(session, since=_now() - datetime.timedelta(days=30), until=_now(), admin_settings=settings)
    assert [row.reason for row in view.rows] == ["chat_message", "cart_edit"], view.rows
    chat, cart = view.rows
    assert (chat.calls, chat.measured_calls, chat.tokens) == (2, 2, 4_000), chat
    assert (chat.charged_toman, chat.charged_measured_toman) == (1_000, 1_000)
    assert (cart.calls, cart.measured_calls, cart.tokens) == (1, 0, 0), cart
    assert view.calls == 3 and view.measured_calls == 2 and view.mean_tokens == 2_000
    assert view.raw_cost_per_1k_toman == Decimal("2")
    assert view.suggested_price_per_1k == wallet_service.compute_cost_per_1k_tokens_from_formula(settings)
    assert view.prompt_floor_sales > 0 and view.prompt_floor_consultation > 0

    # پنجره‌ای که فقط ردیفِ ۴۰روزه در آن است ⇒ همان یک ردیف، نه صفرِ ساختگی و نه ردیفِ امروز
    async with session_scope() as session:
        old = await ai_cost_service.observe(
            session, since=_now() - datetime.timedelta(days=60), until=_now() - datetime.timedelta(days=35), admin_settings=settings
        )
    assert [row.reason for row in old.rows] == ["chat_message"] and old.calls == 1 and old.tokens == 9_000, old.rows
    assert old.measured_calls == 1 and old.charged_toman == 500
    print("✅ test_observe_windows_groups_and_skips_non_ai PASSED")


# ============================================================================= ۵ و ۶ — پنلِ ادمین
async def test_admin_screen_and_ranges(main_dp) -> None:
    await reset_database()
    await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    await _set_pricing("0.020", 100_000, 50)
    owner_id = await _owner_id(OWNER_TG_ID)
    async with session_scope() as session:
        owner = await session.get(ShopOwner, owner_id)
        await wallet_service.add_charge(session, owner, 10_000, reason=WalletTransactionReason.TOPUP)
        await wallet_service.deduct(session, owner, 600, WalletTransactionReason.CHAT_MESSAGE, ai_total_tokens=3_000)

    admin = Chat(main_dp, ADMIN_TG_ID)
    assert main_texts.AI_COST_BUTTON in [
        b.text for row in keyboards.admin_pricing_menu_keyboard().inline_keyboard for b in row
    ]

    await admin.say("💰 تنظیمات قیمت و تخفیف")
    assert "ai_cost_open" in _datas(admin.last_markup), _datas(admin.last_markup)

    await admin.tap("ai_cost_open")
    body = admin.last_edit_text
    assert "برآوردِ هزینهٔ واقعیِ AI" in body and "۳۰ روز گذشته" in body, body
    assert main_texts.AI_COST_FEATURE_LABELS["chat_message"] in body
    assert "۳٬۰۰۰" in body and "میانگینِ هر فراخوانی: ۳٬۰۰۰ توکن" in body, body
    assert _ascii_digits(body) == "", _ascii_digits(body)
    data = _datas(admin.last_edit_markup)
    assert data[:3] == ["ai_cost_range:7", "ai_cost_range:30", "ai_cost_range:90"], data
    assert data[-1] == "admin_pricing_menu" and "🔄 تازه‌سازی" in [
        b.text for row in admin.last_edit_markup.inline_keyboard for b in row
    ]
    assert len(admin.edits) == 1 and len(admin.session.answered_callbacks) == 1, "یکِ ویرایش و یکِ پاسخِ کال‌بک"

    await admin.tap("ai_cost_range:7")
    assert "۷ روز گذشته" in admin.last_edit_text, admin.last_edit_text
    await admin.tap("ai_cost_range:9999")
    assert "۳۰ روز گذشته" in admin.last_edit_text, "بازهٔ دست‌کاری‌شده ⇒ پیش‌فرض، نه خطا"
    await admin.tap("ai_cost_range:x")
    assert "۳۰ روز گذشته" in admin.last_edit_text

    # بازهٔ بی‌داده هم صفحه را می‌سازد (نه تقسیم بر صفر)
    async with session_scope() as session:
        settings = await admin_settings_service.get_admin_settings(session)
        empty = await ai_cost_service.observe(
            session,
            since=_now() + datetime.timedelta(days=1),
            until=_now() + datetime.timedelta(days=2),
            admin_settings=settings,
        )
    assert empty.rows == () and "در این بازه هیچ مصرفِ AI‌ای ثبت نشده" in main_texts.ai_cost_text(empty, 7)
    print("✅ test_admin_screen_and_ranges PASSED")


async def test_operator_cannot_open_the_estimate(main_dp) -> None:
    await reset_database()
    await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    async with session_scope() as session:
        await admin_role_service.grant_operator(session, OPERATOR_TG_ID, granted_by_telegram_id=ADMIN_TG_ID)

    bot = Bot(token="550000:FAKE_MAIN_BOT_TOKEN_FOR_P69_TESTING", session=FakeSession())
    await main_dp.feed_update(bot, make_callback_update(10, data="ai_cost_open", user_id=OPERATOR_TG_ID))
    await main_dp.feed_update(bot, make_message_update(11, text=main_texts.AI_COST_BUTTON, user_id=OPERATOR_TG_ID))
    assert not bot.session.sent_messages and not bot.session.edited_texts, "صفحهٔ برآورد فقط سوپرادمین است"
    await bot.session.close()

    admin = Chat(main_dp, ADMIN_TG_ID)
    await admin.say(main_texts.AI_COST_BUTTON)
    assert admin.sent and "برآوردِ هزینهٔ واقعیِ AI" in admin.last_text, "سوپرادمین با متن هم صفحه را می‌گیرد"
    assert len("ai_cost_range:90".encode("utf-8")) <= 64
    print("✅ test_operator_cannot_open_the_estimate PASSED")


async def main() -> None:
    main_dp, _shop_dp, _bot_manager, _main_bot = build_test_dispatchers()
    test_prompt_floor_is_estimated_not_measured()
    test_cost_view_math()
    test_text_uses_only_jalali_digits()
    await test_deduct_records_tokens_once_across_lots()
    await test_observe_windows_groups_and_skips_non_ai()
    await test_admin_screen_and_ranges(main_dp)
    await test_operator_cannot_open_the_estimate(main_dp)


if __name__ == "__main__":
    asyncio.run(main())
