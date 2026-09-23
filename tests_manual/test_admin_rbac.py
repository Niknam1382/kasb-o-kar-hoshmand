"""
تست: RBACِ ادمین‌ها — سوپرادمین (ADMIN_TELEGRAM_IDS) در برابرِ ادمینِ عملیاتی
(جدولِ admin_roles). فازِ ۲-ب.

اجرا: python3 tests_manual/test_admin_rbac.py
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from harness import FakeSession, build_test_dispatchers, make_callback_update, make_message_update, reset_database  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402
from aiogram import Bot  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.database.models import AdminRole  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import admin_role_service  # noqa: E402

ADMIN_TG_ID = 12345  # باید با ADMIN_TELEGRAM_IDS توی .env یکی باشه
OPERATOR_TG_ID = 555001
STRANGER_TG_ID = 777001

SUPER_ADMIN_ONLY_BUTTONS = {
    "💰 تنظیمات قیمت و تخفیف",
    "🔑 تنظیمات کلیدها",
    "🔑 استخرِ کلیدهایِ AI",
    "👑 مدیریتِ ادمین‌ها",
}
OPERATOR_VISIBLE_BUTTONS = {
    "📢 مدیریت کانال‌های اجباری",
    "🧾 صف تایید پرداخت‌ها",
    "📊 آمار سراسری",
    "📣 پیام همگانی",
    "👥 مدیریت فروشگاه‌دارها",
    "🛡 نگهبانِ محتوا",
    "📜 گزارشِ ممیزی",
}


def _keyboard_button_texts(sent_message: dict) -> set[str]:
    markup = sent_message["reply_markup"]
    return {btn.text for row in markup.keyboard for btn in row}


async def test_operator_keyboard_hides_super_admin_only_buttons(main_dp) -> None:
    await reset_database()
    await seed_usable_shop(999801, 999802)
    async with session_scope() as session:
        await admin_role_service.grant_operator(session, OPERATOR_TG_ID, granted_by_telegram_id=ADMIN_TG_ID)
    main_bot = Bot(token="000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS", session=FakeSession())

    await main_dp.feed_update(main_bot, make_message_update(1, text="/admin", user_id=OPERATOR_TG_ID))

    sent = main_bot.session.sent_messages
    assert len(sent) == 1, "ادمینِ عملیاتی باید بتونه /admin رو باز کنه"
    buttons = _keyboard_button_texts(sent[-1])
    assert buttons == OPERATOR_VISIBLE_BUTTONS, f"کیبوردِ ادمینِ عملیاتی نباید دکمه‌هایِ سوپرادمین رو داشته باشه؛ دیده شد: {buttons}"
    print("✅ test_operator_keyboard_hides_super_admin_only_buttons PASSED")


async def test_super_admin_keyboard_shows_everything(main_dp) -> None:
    await reset_database()
    await seed_usable_shop(999803, 999804)
    main_bot = Bot(token="000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS", session=FakeSession())

    await main_dp.feed_update(main_bot, make_message_update(1, text="/admin", user_id=ADMIN_TG_ID))

    sent = main_bot.session.sent_messages
    buttons = _keyboard_button_texts(sent[-1])
    assert SUPER_ADMIN_ONLY_BUTTONS <= buttons, "سوپرادمین باید همه‌ی دکمه‌های حساس رو هم ببینه"
    assert OPERATOR_VISIBLE_BUTTONS <= buttons, "سوپرادمین باید دکمه‌های عملیاتی رو هم ببینه"
    print("✅ test_super_admin_keyboard_shows_everything PASSED")


async def test_operator_cannot_trigger_super_only_handler(main_dp) -> None:
    await reset_database()
    await seed_usable_shop(999805, 999806)
    async with session_scope() as session:
        await admin_role_service.grant_operator(session, OPERATOR_TG_ID, granted_by_telegram_id=ADMIN_TG_ID)
    main_bot = Bot(token="000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS", session=FakeSession())

    for update_id, text in enumerate(["🔑 استخرِ کلیدهایِ AI", "💰 تنظیمات قیمت و تخفیف", "👑 مدیریتِ ادمین‌ها"], start=1):
        before = len(main_bot.session.sent_messages)
        await main_dp.feed_update(main_bot, make_message_update(update_id, text=text, user_id=OPERATOR_TG_ID))
        after = len(main_bot.session.sent_messages)
        assert after == before, f"ادمینِ عملیاتی نباید بتونه «{text}» رو باز کنه، ولی پاسخی فرستاده شد"
    print("✅ test_operator_cannot_trigger_super_only_handler PASSED")


async def test_operator_can_trigger_operational_handler(main_dp) -> None:
    await reset_database()
    await seed_usable_shop(999807, 999808)
    async with session_scope() as session:
        await admin_role_service.grant_operator(session, OPERATOR_TG_ID, granted_by_telegram_id=ADMIN_TG_ID)
    main_bot = Bot(token="000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS", session=FakeSession())

    await main_dp.feed_update(main_bot, make_message_update(1, text="📊 آمار سراسری", user_id=OPERATOR_TG_ID))

    assert len(main_bot.session.sent_messages) == 1, "ادمینِ عملیاتی باید بتونه آمارِ سراسری رو ببینه"
    print("✅ test_operator_can_trigger_operational_handler PASSED")


async def test_non_admin_still_fully_blocked(main_dp) -> None:
    await reset_database()
    await seed_usable_shop(999809, 999810)
    main_bot = Bot(token="000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS", session=FakeSession())

    await main_dp.feed_update(main_bot, make_message_update(1, text="/admin", user_id=STRANGER_TG_ID))
    await main_dp.feed_update(main_bot, make_message_update(2, text="📊 آمار سراسری", user_id=STRANGER_TG_ID))

    assert len(main_bot.session.sent_messages) == 0, "کاربرِ غیرِادمین نباید هیچ پاسخی از پنلِ ادمین بگیره — RBAC نباید این رفتار رو شل کنه"
    print("✅ test_non_admin_still_fully_blocked PASSED")


async def test_super_admin_can_grant_and_revoke_operator_via_ui(main_dp) -> None:
    await reset_database()
    await seed_usable_shop(999811, 999812)
    main_bot = Bot(token="000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS", session=FakeSession())

    await main_dp.feed_update(main_bot, make_message_update(1, text="👑 مدیریتِ ادمین‌ها", user_id=ADMIN_TG_ID))
    await main_dp.feed_update(main_bot, make_callback_update(2, data="admin_role_add", user_id=ADMIN_TG_ID))
    await main_dp.feed_update(main_bot, make_message_update(3, text=str(OPERATOR_TG_ID), user_id=ADMIN_TG_ID))

    async with session_scope() as session:
        role = await admin_role_service.get_by_telegram_id(session, OPERATOR_TG_ID)
        assert role is not None, "بعدِ فرستادنِ آیدی، باید ردیفِ ادمینِ عملیاتی ساخته بشه"
        role_id = role.id

    await main_dp.feed_update(main_bot, make_callback_update(4, data=f"admin_role_view:{role_id}", user_id=ADMIN_TG_ID))
    await main_dp.feed_update(main_bot, make_callback_update(5, data=f"admin_role_revoke:{role_id}", user_id=ADMIN_TG_ID))

    async with session_scope() as session:
        assert not await admin_role_service.is_operator(session, OPERATOR_TG_ID), "بعدِ حذف، دیگه نباید ادمینِ عملیاتی باشه"
    print("✅ test_super_admin_can_grant_and_revoke_operator_via_ui PASSED")


async def test_grant_rejects_existing_super_admin(main_dp) -> None:
    await reset_database()
    await seed_usable_shop(999813, 999814)
    main_bot = Bot(token="000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS", session=FakeSession())

    await main_dp.feed_update(main_bot, make_callback_update(1, data="admin_role_add", user_id=ADMIN_TG_ID))
    await main_dp.feed_update(main_bot, make_message_update(2, text=str(ADMIN_TG_ID), user_id=ADMIN_TG_ID))

    async with session_scope() as session:
        role = await admin_role_service.get_by_telegram_id(session, ADMIN_TG_ID)
        assert role is None, "سوپرادمین نباید توی جدولِ admin_roles هم دوباره ثبت بشه"
    print("✅ test_grant_rejects_existing_super_admin PASSED")


async def test_grant_rejects_duplicate_operator(main_dp) -> None:
    await reset_database()
    await seed_usable_shop(999815, 999816)
    async with session_scope() as session:
        await admin_role_service.grant_operator(session, OPERATOR_TG_ID, granted_by_telegram_id=ADMIN_TG_ID)
    main_bot = Bot(token="000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS", session=FakeSession())

    await main_dp.feed_update(main_bot, make_callback_update(1, data="admin_role_add", user_id=ADMIN_TG_ID))
    await main_dp.feed_update(main_bot, make_message_update(2, text=str(OPERATOR_TG_ID), user_id=ADMIN_TG_ID))

    async with session_scope() as session:
        result = await session.execute(select(AdminRole).where(AdminRole.telegram_id == OPERATOR_TG_ID))
        rows = result.scalars().all()
        assert len(rows) == 1, "نباید دو ردیفِ تکراری برای یه آیدی ساخته بشه"
    print("✅ test_grant_rejects_duplicate_operator PASSED")


async def test_grant_rejects_non_numeric_input(main_dp) -> None:
    await reset_database()
    await seed_usable_shop(999817, 999818)
    main_bot = Bot(token="000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS", session=FakeSession())

    await main_dp.feed_update(main_bot, make_callback_update(1, data="admin_role_add", user_id=ADMIN_TG_ID))
    await main_dp.feed_update(main_bot, make_message_update(2, text="این-یه-عدد-نیست", user_id=ADMIN_TG_ID))

    async with session_scope() as session:
        roles = await admin_role_service.get_all(session)
        assert roles == [], "ورودیِ نامعتبر نباید چیزی ذخیره کنه"
    print("✅ test_grant_rejects_non_numeric_input PASSED")


async def main() -> None:
    main_dp, _shop_dp, _bot_manager, _main_bot = build_test_dispatchers()
    await test_operator_keyboard_hides_super_admin_only_buttons(main_dp)
    await test_super_admin_keyboard_shows_everything(main_dp)
    await test_operator_cannot_trigger_super_only_handler(main_dp)
    await test_operator_can_trigger_operational_handler(main_dp)
    await test_non_admin_still_fully_blocked(main_dp)
    await test_super_admin_can_grant_and_revoke_operator_via_ui(main_dp)
    await test_grant_rejects_existing_super_admin(main_dp)
    await test_grant_rejects_duplicate_operator(main_dp)
    await test_grant_rejects_non_numeric_input(main_dp)


if __name__ == "__main__":
    asyncio.run(main())
