"""
تست: پیامِ فروشگاه‌دار به مشتری‌هایِ خودش (فازِ ۳، اولین زیربخش) — عمداً جدا
از پیامِ همگانیِ ادمین به فروشگاه‌دارها که از قبل هست (همون شکلِ ظاهری، ولی
گیرنده/فرستنده/رباتِ ارسال‌کننده‌ش کاملاً فرق داره).

پوشش:
۱. مسیرِ کامل: دکمه → نوشتنِ متن → پیش‌نمایش با تعدادِ درستِ مشتری → تایید →
   ارسال به همه‌ی مشتری‌هایِ همون فروشگاه از طریقِ ربات خودِ فروشگاه (نه ربات
   اصلی، که پیامِ همگانیِ ادمین ازش استفاده می‌کنه) → یه پیامِ خلاصه به خودِ
   فروشگاه‌دار (از طریقِ ربات اصلی) بعدِ اتمامِ تسکِ پس‌زمینه.
۲. ایزوله‌بودنِ چندمستاجری: مشتریِ یه فروشگاهِ دیگه هیچ‌وقت این پیام رو نمی‌گیره.
۳. لغو در مرحله‌ی تایید → هیچ پیامی برایِ هیچ مشتری‌ای فرستاده نمی‌شه.
۴. فروشگاهِ بدونِ مشتری → پیامِ «مشتری‌ای نیست»، اصلاً وارد مرحله‌ی نوشتنِ متن نمی‌شه.

اجرا: python3 tests_manual/test_customer_broadcast.py
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from aiogram import Bot  # noqa: E402

from harness import (  # noqa: E402
    FakeSession,
    build_test_dispatchers,
    make_callback_update,
    make_message_update,
    register_fake_shop_bot,
    reset_database,
)
from shop_setup import seed_usable_shop  # noqa: E402

from app.bots.main_bot import texts  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import customer_service  # noqa: E402

OWNER_TG_ID = 999701
SHOP_BOT_TG_ID = 999702
CUSTOMER_1_TG_ID = 999703
CUSTOMER_2_TG_ID = 999704

OTHER_OWNER_TG_ID = 999711
OTHER_SHOP_BOT_TG_ID = 999712
OTHER_CUSTOMER_TG_ID = 999713

BROADCAST_TEXT = "فردا ۲۰٪ تخفیف داریم!"


def _new_owner_bot() -> Bot:
    return Bot(token="000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS", session=FakeSession())


async def test_full_broadcast_flow_sends_via_shop_bot_and_notifies_owner(main_dp, bot_manager) -> None:
    await reset_database()
    owner_bot = _new_owner_bot()
    shop_bot_instance = Bot(token=f"{SHOP_BOT_TG_ID}:FAKE", session=FakeSession())

    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    register_fake_shop_bot(bot_manager, shop_bot_id, shop_bot_instance)

    async with session_scope() as session:
        await customer_service.get_or_create_customer(session, shop_bot_id, CUSTOMER_1_TG_ID, "مشتری یک", None)
        await customer_service.get_or_create_customer(session, shop_bot_id, CUSTOMER_2_TG_ID, "مشتری دو", None)

    await main_dp.feed_update(owner_bot, make_message_update(1, text="📣 پیام به مشتری‌ها", user_id=OWNER_TG_ID))
    await main_dp.feed_update(owner_bot, make_message_update(2, text=BROADCAST_TEXT, user_id=OWNER_TG_ID))
    await main_dp.feed_update(owner_bot, make_callback_update(3, data="customer_broadcast_confirm", user_id=OWNER_TG_ID))
    await asyncio.sleep(0.5)  # صبر برای اتمامِ تسکِ پس‌زمینه‌ی ارسال

    shop_session: FakeSession = shop_bot_instance.session  # type: ignore[assignment]
    assert len(shop_session.sent_messages) == 2, f"باید دقیقاً برایِ هر دو مشتری فرستاده بشه، شد {len(shop_session.sent_messages)}"
    recipients = {m["chat_id"] for m in shop_session.sent_messages}
    assert recipients == {CUSTOMER_1_TG_ID, CUSTOMER_2_TG_ID}, "باید دقیقاً همون دو مشتری گیرنده باشن"
    assert all(m["text"] == BROADCAST_TEXT for m in shop_session.sent_messages), "متنِ فرستاده‌شده باید دقیقاً همونی باشه که فروشگاه‌دار نوشت"

    owner_session: FakeSession = owner_bot.session  # type: ignore[assignment]
    # ترتیب: سوالِ متن، پیش‌نمایش، خلاصه‌ی نهایی (پیامِ «شروع شد» با edit_text
    # می‌ره، نه send_message، پس اینجا حساب نمی‌شه).
    assert len(owner_session.sent_messages) == 3, f"باید ۳ پیام باشه (سوال، پیش‌نمایش، خلاصه)، شد {len(owner_session.sent_messages)}"
    assert owner_session.sent_messages[-1]["text"] == texts.customer_broadcast_sent_confirmation(2, 2)

    print("✅ test_full_broadcast_flow_sends_via_shop_bot_and_notifies_owner PASSED")


async def test_broadcast_never_reaches_another_shops_customers(main_dp, bot_manager) -> None:
    await reset_database()
    owner_bot = _new_owner_bot()
    shop_bot_instance = Bot(token=f"{SHOP_BOT_TG_ID}:FAKE", session=FakeSession())
    other_shop_bot_instance = Bot(token=f"{OTHER_SHOP_BOT_TG_ID}:FAKE", session=FakeSession())

    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    other_shop_bot_id = await seed_usable_shop(OTHER_OWNER_TG_ID, OTHER_SHOP_BOT_TG_ID)
    register_fake_shop_bot(bot_manager, shop_bot_id, shop_bot_instance)
    register_fake_shop_bot(bot_manager, other_shop_bot_id, other_shop_bot_instance)

    async with session_scope() as session:
        await customer_service.get_or_create_customer(session, shop_bot_id, CUSTOMER_1_TG_ID, "مشتریِ فروشگاهِ اول", None)
        await customer_service.get_or_create_customer(session, other_shop_bot_id, OTHER_CUSTOMER_TG_ID, "مشتریِ فروشگاهِ دوم", None)

    await main_dp.feed_update(owner_bot, make_message_update(1, text="📣 پیام به مشتری‌ها", user_id=OWNER_TG_ID))
    await main_dp.feed_update(owner_bot, make_message_update(2, text=BROADCAST_TEXT, user_id=OWNER_TG_ID))
    await main_dp.feed_update(owner_bot, make_callback_update(3, data="customer_broadcast_confirm", user_id=OWNER_TG_ID))
    await asyncio.sleep(0.5)

    shop_session: FakeSession = shop_bot_instance.session  # type: ignore[assignment]
    assert len(shop_session.sent_messages) == 1
    assert shop_session.sent_messages[0]["chat_id"] == CUSTOMER_1_TG_ID

    other_session: FakeSession = other_shop_bot_instance.session  # type: ignore[assignment]
    assert len(other_session.sent_messages) == 0, "مشتریِ فروشگاهِ دیگه نباید هیچ‌وقت این پیام رو بگیره"

    print("✅ test_broadcast_never_reaches_another_shops_customers PASSED")


async def test_cancel_sends_nothing_to_customers(main_dp, bot_manager) -> None:
    await reset_database()
    owner_bot = _new_owner_bot()
    shop_bot_instance = Bot(token=f"{SHOP_BOT_TG_ID}:FAKE", session=FakeSession())

    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    register_fake_shop_bot(bot_manager, shop_bot_id, shop_bot_instance)

    async with session_scope() as session:
        await customer_service.get_or_create_customer(session, shop_bot_id, CUSTOMER_1_TG_ID, "مشتری یک", None)

    await main_dp.feed_update(owner_bot, make_message_update(1, text="📣 پیام به مشتری‌ها", user_id=OWNER_TG_ID))
    await main_dp.feed_update(owner_bot, make_message_update(2, text=BROADCAST_TEXT, user_id=OWNER_TG_ID))
    await main_dp.feed_update(owner_bot, make_callback_update(3, data="customer_broadcast_cancel", user_id=OWNER_TG_ID))
    await asyncio.sleep(0.2)

    shop_session: FakeSession = shop_bot_instance.session  # type: ignore[assignment]
    assert len(shop_session.sent_messages) == 0, "بعدِ لغو نباید هیچ پیامی فرستاده بشه"

    print("✅ test_cancel_sends_nothing_to_customers PASSED")


async def test_no_customers_guard_skips_composing(main_dp) -> None:
    await reset_database()
    owner_bot = _new_owner_bot()
    await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)

    await main_dp.feed_update(owner_bot, make_message_update(1, text="📣 پیام به مشتری‌ها", user_id=OWNER_TG_ID))

    owner_session: FakeSession = owner_bot.session  # type: ignore[assignment]
    assert len(owner_session.sent_messages) == 1
    assert owner_session.sent_messages[0]["text"] == texts.CUSTOMER_BROADCAST_NO_CUSTOMERS

    # چون هیچ‌وقت وارد حالتِ waiting_message نشد، این پیامِ بعدی نباید به‌عنوانِ
    # متنِ پیام همگانی تفسیر بشه (یعنی نباید پیش‌نمایشی ساخته بشه).
    await main_dp.feed_update(owner_bot, make_message_update(2, text="یه متنِ رندوم", user_id=OWNER_TG_ID))
    assert not any("پیش‌نمایشِ پیام" in m["text"] for m in owner_session.sent_messages), "نباید هیچ پیش‌نمایشی ساخته بشه"

    print("✅ test_no_customers_guard_skips_composing PASSED")


async def main() -> None:
    main_dp, _shop_dp, bot_manager, _main_bot = build_test_dispatchers()
    await test_full_broadcast_flow_sends_via_shop_bot_and_notifies_owner(main_dp, bot_manager)
    await test_broadcast_never_reaches_another_shops_customers(main_dp, bot_manager)
    await test_cancel_sends_nothing_to_customers(main_dp, bot_manager)
    await test_no_customers_guard_skips_composing(main_dp)


if __name__ == "__main__":
    asyncio.run(main())
