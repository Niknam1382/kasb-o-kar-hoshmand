"""
تست: افزودن/حذفِ کانال‌های اجباری توسط ادمین. مسیرِ اثباتِ مالکیتِ کانال از طریقِ
فوروارد کردنِ یه پیام از همون کانال شبیه‌سازی می‌شه (نه واردکردنِ @username که
نیازمندِ get_chat واقعیه) — این باعث می‌شه کاملاً از طریقِ FakeSession قابل‌تست باشه.

اجرا: python3 tests_manual/test_admin_channel_management.py
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from aiogram import Bot  # noqa: E402
from aiogram.types import Chat  # noqa: E402
from sqlalchemy import select  # noqa: E402

from harness import FakeSession, build_test_dispatchers, make_callback_update, make_message_update, reset_database  # noqa: E402

from app.database.models import MandatoryChannel  # noqa: E402
from app.database.session import session_scope  # noqa: E402

ADMIN_TG_ID = 12345
CHANNEL_TG_ID = -1001234567890


async def test_admin_adds_primary_channel(main_dp) -> None:
    await reset_database()
    admin_bot = Bot(token="000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS", session=FakeSession())
    session_obj: FakeSession = admin_bot.session  # type: ignore[assignment]

    # آیدیِ bot (که از get_me برمی‌گرده) باید عضوِ ادمینِ کانال باشه تا چکِ عضویت رد بشه
    session_obj.set_chat_member_status(str(CHANNEL_TG_ID), 0, "administrator")

    await main_dp.feed_update(admin_bot, make_callback_update(1, data="admin_channel_add", user_id=ADMIN_TG_ID))
    await main_dp.feed_update(admin_bot, make_message_update(2, text="کانالِ اصلیِ فروشگاه", user_id=ADMIN_TG_ID))

    forward_chat = Chat.model_construct(id=CHANNEL_TG_ID, type="channel", title="کانالِ تست")
    await main_dp.feed_update(admin_bot, make_message_update(3, user_id=ADMIN_TG_ID, forward_from_chat=forward_chat))

    await main_dp.feed_update(admin_bot, make_callback_update(4, data="admin_channel_primary:yes", user_id=ADMIN_TG_ID))

    async with session_scope() as session:
        result = await session.execute(select(MandatoryChannel).where(MandatoryChannel.channel_id == str(CHANNEL_TG_ID)))
        channel = result.scalar_one_or_none()
        assert channel is not None, "کانال باید در دیتابیس ثبت بشه"
        assert channel.name == "کانالِ اصلیِ فروشگاه"
        assert channel.is_primary is True

    print("✅ test_admin_adds_primary_channel PASSED")


async def test_second_primary_channel_unsets_first(main_dp) -> None:
    await reset_database()
    admin_bot = Bot(token="000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS", session=FakeSession())
    session_obj: FakeSession = admin_bot.session  # type: ignore[assignment]

    async with session_scope() as session:
        session.add(MandatoryChannel(channel_id="@old_channel", name="کانالِ قدیمی", is_primary=True))
        await session.commit()

    session_obj.set_chat_member_status(str(CHANNEL_TG_ID + 1), 0, "creator")
    await main_dp.feed_update(admin_bot, make_callback_update(1, data="admin_channel_add", user_id=ADMIN_TG_ID))
    await main_dp.feed_update(admin_bot, make_message_update(2, text="کانالِ جدید", user_id=ADMIN_TG_ID))
    forward_chat = Chat.model_construct(id=CHANNEL_TG_ID + 1, type="channel", title="کانالِ جدید")
    await main_dp.feed_update(admin_bot, make_message_update(3, user_id=ADMIN_TG_ID, forward_from_chat=forward_chat))
    await main_dp.feed_update(admin_bot, make_callback_update(4, data="admin_channel_primary:yes", user_id=ADMIN_TG_ID))

    async with session_scope() as session:
        result = await session.execute(select(MandatoryChannel))
        channels = {c.name: c.is_primary for c in result.scalars().all()}
        assert channels["کانالِ قدیمی"] is False, "کانالِ قدیمی باید دیگه primary نباشه"
        assert channels["کانالِ جدید"] is True

    print("✅ test_second_primary_channel_unsets_first PASSED")


async def test_channel_proof_rejected_without_forward(main_dp) -> None:
    await reset_database()
    admin_bot = Bot(token="000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS", session=FakeSession())
    session_obj: FakeSession = admin_bot.session  # type: ignore[assignment]

    await main_dp.feed_update(admin_bot, make_callback_update(1, data="admin_channel_add", user_id=ADMIN_TG_ID))
    await main_dp.feed_update(admin_bot, make_message_update(2, text="کانالِ بی‌مدرک", user_id=ADMIN_TG_ID))
    # نه فوروارد و نه @username → باید رد بشه
    await main_dp.feed_update(admin_bot, make_message_update(3, text="یه متنِ ساده", user_id=ADMIN_TG_ID))

    async with session_scope() as session:
        result = await session.execute(select(MandatoryChannel))
        assert len(list(result.scalars().all())) == 0, "بدونِ اثباتِ مالکیت نباید کانالی ثبت بشه"

    print("✅ test_channel_proof_rejected_without_forward PASSED")


async def main() -> None:
    main_dp, shop_dp, bot_manager, main_bot = build_test_dispatchers()
    await test_admin_adds_primary_channel(main_dp)
    await test_second_primary_channel_unsets_first(main_dp)
    await test_channel_proof_rejected_without_forward(main_dp)


if __name__ == "__main__":
    asyncio.run(main())
