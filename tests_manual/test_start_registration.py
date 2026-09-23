"""
تست: ثبت‌نامِ کاملِ یه فروشگاه‌دارِ تازه (در AUTH_MODE=test) + گیتِ کانال‌های اجباری
سرِ /start.

اجرا: python3 tests_manual/test_start_registration.py

نکته: چون روترهای aiogram آبجکت‌های سطحِ‌ماژول هستن (فقط یه‌بار قابلِ اتصال به یه
دیسپچرِ پرنت)، دیسپچرها فقط یه‌بار در ابتدای main() ساخته می‌شن و بینِ همه‌ی
تست‌های این فایل به اشتراک گذاشته می‌شن؛ چیزی که بینِ تست‌ها ریست می‌شه فقط
دیتابیسه، نه خودِ دیسپچر (دقیقاً مثلِ اجرای واقعی که یه دیسپچر برای کلِ عمرِ
پروسه ساخته می‌شه).
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from aiogram import Bot  # noqa: E402

from harness import FakeSession, build_test_dispatchers, make_callback_update, make_message_update, reset_database  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.database.session import session_scope  # noqa: E402
from app.database.models import MandatoryChannel, ShopOwner  # noqa: E402

USER_ID = 555001


async def test_registration_without_mandatory_channels(main_dp) -> None:
    await reset_database()
    main_bot = Bot(token="000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS", session=FakeSession())
    session_obj: FakeSession = main_bot.session  # type: ignore[assignment]

    await main_dp.feed_update(main_bot, make_message_update(1, text="/start", user_id=USER_ID))
    assert any("نام" in m["text"] for m in session_obj.sent_messages), "پیامِ درخواستِ نام ارسال نشد"

    await main_dp.feed_update(main_bot, make_message_update(2, text="علی", user_id=USER_ID))
    await main_dp.feed_update(main_bot, make_message_update(3, text="رضایی", user_id=USER_ID))
    await main_dp.feed_update(main_bot, make_message_update(4, text="09123456789", user_id=USER_ID))
    await main_dp.feed_update(main_bot, make_message_update(5, text="ali@example.com", user_id=USER_ID))

    async with session_scope() as session:
        result = await session.execute(select(ShopOwner).where(ShopOwner.telegram_id == USER_ID))
        owner = result.scalar_one_or_none()
        assert owner is not None, "فروشگاه‌دار در دیتابیس ساخته نشد"
        assert owner.registration_completed is True, "ثبت‌نام تکمیل‌شده علامت نخورد"
        assert owner.first_name == "علی"
        assert owner.last_name == "رضایی"
        assert owner.phone_number == "09123456789"
        assert owner.email == "ali@example.com"
        assert owner.phone_verified is True and owner.email_verified is True, "در حالتِ تست باید هر دو تاییدشده باشن"

    assert any(
        "پیشنهاد" in m["text"] or "آزمایشی" in m["text"] or "تریال" in m["text"] for m in session_obj.sent_messages[-3:]
    ), "بعد از ثبت‌نام باید پیشنهادِ دوره‌ی آزمایشی نمایش داده بشه"
    print("✅ test_registration_without_mandatory_channels PASSED")


async def test_phone_normalization_variants(main_dp) -> None:
    await reset_database()
    main_bot = Bot(token="000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS", session=FakeSession())
    session_obj: FakeSession = main_bot.session  # type: ignore[assignment]
    uid = USER_ID + 1

    await main_dp.feed_update(main_bot, make_message_update(10, text="/start", user_id=uid))
    await main_dp.feed_update(main_bot, make_message_update(11, text="سارا", user_id=uid))
    await main_dp.feed_update(main_bot, make_message_update(12, text="احمدی", user_id=uid))
    # فرمتِ بین‌المللی با +98
    await main_dp.feed_update(main_bot, make_message_update(13, text="+989121234567", user_id=uid))

    assert not any("نامعتبر" in m["text"] for m in session_obj.sent_messages[-1:]), "شماره‌ی +98 باید معتبر تشخیص داده بشه"

    await main_dp.feed_update(main_bot, make_message_update(14, text="sara@example.com", user_id=uid))

    async with session_scope() as session:
        result = await session.execute(select(ShopOwner).where(ShopOwner.telegram_id == uid))
        owner = result.scalar_one_or_none()
        assert owner is not None
        assert owner.phone_number == "09121234567", f"نرمالایز نشد، مقدار: {owner.phone_number}"

    print("✅ test_phone_normalization_variants PASSED")


async def test_channel_gate_blocks_start(main_dp) -> None:
    await reset_database()
    session_impl = FakeSession()
    main_bot = Bot(token="000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS", session=session_impl)
    uid = USER_ID + 2

    async with session_scope() as session:
        session.add(MandatoryChannel(channel_id="@testchannel", name="کانال تست", is_primary=True))
        await session.commit()

    # کاربر عضوِ کانال نیست (پیش‌فرضِ FakeSession: status='left')
    await main_dp.feed_update(main_bot, make_message_update(20, text="/start", user_id=uid))
    assert any("عضو" in m["text"] for m in session_impl.sent_messages), "پیامِ گیتِ کانال نمایش داده نشد"

    async with session_scope() as session:
        result = await session.execute(select(ShopOwner).where(ShopOwner.telegram_id == uid))
        assert result.scalar_one_or_none() is None, "نباید قبل از عبور از گیت، فروشگاه‌دار ساخته بشه"

    # حالا کاربر رو عضوِ کانال می‌کنیم و دکمه‌ی «بررسیِ مجدد» رو می‌زنیم
    session_impl.set_chat_member_status("@testchannel", uid, "member")
    await main_dp.feed_update(main_bot, make_callback_update(21, data="check_channels_membership", user_id=uid))

    assert len(session_impl.answered_callbacks) >= 1, "کال‌بک باید answer بشه"
    async with session_scope() as session:
        result = await session.execute(select(ShopOwner).where(ShopOwner.telegram_id == uid))
        assert result.scalar_one_or_none() is not None, "بعد از عبور از گیت باید فروشگاه‌دار ساخته بشه و وارد ثبت‌نام بشه"

    print("✅ test_channel_gate_blocks_start PASSED")


async def main() -> None:
    main_dp, shop_dp, bot_manager, _main_bot = build_test_dispatchers()
    await test_registration_without_mandatory_channels(main_dp)
    await test_phone_normalization_variants(main_dp)
    await test_channel_gate_blocks_start(main_dp)


if __name__ == "__main__":
    asyncio.run(main())
