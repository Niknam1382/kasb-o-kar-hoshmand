"""پ۶۴ · نگهبانِ رفتاریِ هارنس + جارویِ پاک‌کردنِ FSM در ناوبریِ «📊 مصرفِ کاربران».

دو کلاسِ باگ که در این پروژه *سه بار* برگشتند (P19 رفع کرد، پ۴۹ و پ۵۶ دوباره ساختند):

۱. پاسخِ دوباره به یکِ `callback_query` — در تلگرام خطایِ واقعی می‌سازد و دکمه بی‌جواب می‌ماند،
   ولی هارنسِ پیشین آن را بی‌صدا رد می‌کرد. از این فاز `FakeSession` برایِ دومینِ پاسخِ *موفق*
   همان شناسه `DuplicateCallbackAnswer` می‌دهد (از `BaseException`، تا هندلرِ خطایِ aiogram
   آن را نبلعد و تست بلند شکست بخورد).
۲. ناوبریِ داخلِ یکِ صفحه، حالتِ «در انتظارِ ورودی» را پاک نمی‌کرد ⇒ عددی که ادمین بعد ازِ آن
   می‌نوشت به‌جایِ کارِ جدید، ورودیِ پرسشِ قدیمی ذخیره می‌شد. چهار هندلرِ «📊 مصرفِ کاربران»
   (پنجره/صفحه، جزئیات، توقف، بلاک) حالا `state.clear()` دارند و آزمونِ ۳ تا ۵ همین را با
   «عددِ بعدی هیچ ستونی را عوض نمی‌کند» می‌سنجد، نه با خواندنِ متنِ پیام.

۶. پاسخِ ناموفق در حالتِ `fail_answer_callbacks` (تستِ P27) در نگهبان ثبت نمی‌شود ⇒ تلاشِ دوباره
   مثلِ قبل مجاز است (آزمونِ ۲).
"""
from __future__ import annotations

import asyncio
import datetime as dt
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from aiogram import Bot  # noqa: E402
from aiogram.exceptions import TelegramBadRequest  # noqa: E402
from sqlalchemy import select  # noqa: E402

import harness  # noqa: E402
from harness import FakeSession, build_test_dispatchers, reset_database  # noqa: E402
from phase4_helpers import Chat  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from app.bots.main_bot import texts as main_texts  # noqa: E402
from app.database.models import Customer, ShopBot, WalletTransaction, WalletTransactionReason  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import customer_service  # noqa: E402

ADMIN_TG_ID = 12345
OWNER_TG_ID = 996_401
SHOP_BOT_TG_ID = 996_402
MAIN_TOKEN = "550000:FAKE_MAIN_BOT_TOKEN_FOR_P64_TESTING"
NOW = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)


async def _seed_one_customer() -> int:
    await reset_database()
    shop_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    async with session_scope() as session:
        shop_bot = await session.get(ShopBot, shop_id)
        customer = await customer_service.get_or_create_customer(
            session, shop_id, 996_410, "مشتریِ آزمونی", None, platform="telegram"
        )
        session.add(
            WalletTransaction(
                shop_owner_id=shop_bot.shop_owner_id, customer_id=customer.id, amount_toman=-700,
                reason=WalletTransactionReason.CHAT_MESSAGE, created_at=NOW - dt.timedelta(minutes=5),
            )
        )
        await session.commit()
        return customer.id


async def _customer_flags(customer_id: int) -> tuple[int | None, dt.datetime | None, bool]:
    async with session_scope() as session:
        row = (await session.execute(select(Customer).where(Customer.id == customer_id))).scalar_one()
        return row.ai_daily_limit_toman, row.ai_paused_until, bool(row.is_blocked)


async def test_harness_guard_fires_on_second_successful_answer() -> None:
    session = FakeSession()
    session.strict_callback_answers = True
    bot = Bot(token=MAIN_TOKEN, session=session)
    await bot.answer_callback_query("q-64-a", text="اول")
    assert len(session.answered_callbacks) == 1, session.answered_callbacks
    raised = False
    try:
        await bot.answer_callback_query("q-64-a", text="دوم")
    except harness.DuplicateCallbackAnswer:
        raised = True
    assert raised, "نگهبانِ پاسخِ دوباره عمل نکرد"
    assert len(session.answered_callbacks) == 1, "پاسخِ ردشده نباید در شمارِ پاسخ‌ها برود"
    print("PASS test_harness_guard_fires_on_second_successful_answer")


async def test_guard_uses_base_exception_and_ignores_failed_answers() -> None:
    assert issubclass(harness.DuplicateCallbackAnswer, BaseException)
    assert not issubclass(harness.DuplicateCallbackAnswer, Exception), (
        "اگر از Exception برثبد، هندلرِ خطایِ aiogram آن را می‌بلعد و تست بی‌صدا سبز می‌ماند"
    )
    session = FakeSession()
    session.strict_callback_answers = True
    session.fail_answer_callbacks = True
    bot = Bot(token=MAIN_TOKEN, session=session)
    try:
        await bot.answer_callback_query("q-64-b")
        raise AssertionError("حالتِ query-is-too-old باید خطایِ واقعی بسازد")
    except TelegramBadRequest:
        pass
    session.fail_answer_callbacks = False
    await bot.answer_callback_query("q-64-b")  # تلاشِ دوباره ⇒ مجاز (پاسخِ اول موفق نبود)
    assert len(session.answered_callbacks) == 2, session.answered_callbacks
    print("PASS test_guard_uses_base_exception_and_ignores_failed_answers")


async def test_window_and_page_navigation_clears_the_pending_limit(main_dp) -> None:
    customer_id = await _seed_one_customer()
    admin = Chat(main_dp, ADMIN_TG_ID)
    await admin.say(main_texts.AI_USAGE_BUTTON)
    await admin.tap(f"ai_usage_limit:{customer_id}:24h:0")
    assert main_texts.AI_USAGE_LIMIT_ASK in admin.sent[-1]["text"], admin.sent[-1]
    await admin.tap("ai_usage:7d:0")
    assert "۷ روز" in admin.last_edit_text, admin.last_edit_text
    await admin.say("۵۰۰۰۰")
    assert await _customer_flags(customer_id) == (None, None, False), (
        "عددِ بعدی نباید سقفِ کاربرِ پرسشِ رهاشده را پر کند"
    )
    print("PASS test_window_and_page_navigation_clears_the_pending_limit")


async def test_detail_navigation_clears_the_pending_limit(main_dp) -> None:
    customer_id = await _seed_one_customer()
    admin = Chat(main_dp, ADMIN_TG_ID)
    await admin.say(main_texts.AI_USAGE_BUTTON)
    await admin.tap(f"ai_usage_limit:{customer_id}:24h:0")
    await admin.tap(f"ai_usage_view:24h:0:{customer_id}")
    await admin.say("۹۰۰۰۰")
    assert (await _customer_flags(customer_id))[0] is None, "رفتن به جزئیات هم پرسش را رها می‌کند"
    print("PASS test_detail_navigation_clears_the_pending_limit")


async def test_pause_and_block_actions_clear_the_pending_limit(main_dp) -> None:
    customer_id = await _seed_one_customer()
    admin = Chat(main_dp, ADMIN_TG_ID)
    await admin.say(main_texts.AI_USAGE_BUTTON)
    await admin.tap(f"ai_usage_limit:{customer_id}:24h:0")
    await admin.tap(f"ai_usage_pause:{customer_id}:24:24h:0")
    limit, paused, blocked = await _customer_flags(customer_id)
    assert limit is None, "توقفِ موقت نباید همزمان سقف هم بگذارد"
    assert paused is not None, "خودِ فعلِ توقف باید اعمال شده باشد"
    assert not blocked
    await admin.say("۳۰۰۰۰")
    assert (await _customer_flags(customer_id))[0] is None, "عددِ بعدی ورودیِ پرسشِ رهاشده نیست"

    await admin.tap(f"ai_usage_limit:{customer_id}:24h:0")
    await admin.tap(f"ai_usage_block:{customer_id}:1:24h:0")
    limit, _paused, blocked = await _customer_flags(customer_id)
    assert blocked and limit is None, "بلاک اعمال شود و پرسش رها شود"
    await admin.say("۴۰۰۰۰")
    assert (await _customer_flags(customer_id))[0] is None
    print("PASS test_pause_and_block_actions_clear_the_pending_limit")


async def test_limit_flow_still_works_when_not_interrupted(main_dp) -> None:
    """ضدِ رگرسیونِ خودِ فیچر: اگر پرسش را قطع نکنیم، عددِ جلالی همان‌جا ذخیره می‌شود."""
    customer_id = await _seed_one_customer()
    admin = Chat(main_dp, ADMIN_TG_ID)
    await admin.say(main_texts.AI_USAGE_BUTTON)
    await admin.tap(f"ai_usage_limit:{customer_id}:24h:0")
    await admin.say("۵۰۰۰۰")
    assert (await _customer_flags(customer_id))[0] == 50_000, "جریانِ عادی دست‌نخورده ماند"
    print("PASS test_limit_flow_still_works_when_not_interrupted")


async def test_bale_entry_answers_exactly_once(main_dp) -> None:
    """باگِ واقعیِ پیدا‌شده توسطِ همین نگهبان: `tok_bale` اول answer می‌داد و بعد
    `_own_shop_bot_cb` هم answer می‌کرد ⇒ اخطارِ «رباتِ فروشگاهی تنظیم نشده» در تلگرام رد می‌شد."""
    await reset_database()
    owner = Chat(main_dp, 996_420)
    await owner.tap("tok_bale")
    assert len(owner.session.answered_callbacks) == 1, owner.session.answered_callbacks
    assert owner.sent, "یکِ پیامِ روشن باید به کاربر برسد"
    print("PASS test_bale_entry_answers_exactly_once")


async def main() -> None:
    main_dp, _shop_dp, _bot_manager, _main_bot = build_test_dispatchers()
    await test_harness_guard_fires_on_second_successful_answer()
    await test_guard_uses_base_exception_and_ignores_failed_answers()
    await test_window_and_page_navigation_clears_the_pending_limit(main_dp)
    await test_detail_navigation_clears_the_pending_limit(main_dp)
    await test_pause_and_block_actions_clear_the_pending_limit(main_dp)
    await test_limit_flow_still_works_when_not_interrupted(main_dp)
    await test_bale_entry_answers_exactly_once(main_dp)
    print("📊 نتیجه: ۷ تستِ پ۶۴ (نگهبانِ پاسخِ دوباره + پاک‌سازیِ FSM در ناوبری) پاس شد")


if __name__ == "__main__":
    asyncio.run(main())
