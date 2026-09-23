"""
تست: پاکسازیِ خودکارِ مکالمات (conversation_retention_days) — فازِ ۱، بازیابی.

اجرا: python3 tests_manual/test_conversation_retention.py
"""
from __future__ import annotations

import asyncio
import datetime
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from harness import FakeSession, build_test_dispatchers, make_callback_update, make_message_update, reset_database  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from aiogram import Bot  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.database.models import Customer, ConversationMessage  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import conversation_service  # noqa: E402
from app.services.admin_settings_service import get_admin_settings  # noqa: E402

OWNER_TG_ID = 999601
SHOP_BOT_TG_ID = 999602
CUSTOMER_TG_ID = 999603
ADMIN_TG_ID = 12345


async def _make_customer(shop_bot_id: int) -> int:
    async with session_scope() as session:
        customer = Customer(shop_bot_id=shop_bot_id, telegram_id=CUSTOMER_TG_ID, first_name="مشتریِ تستی")
        session.add(customer)
        await session.flush()
        return customer.id


async def _add_message(customer_id: int, age_days: float, role: str = "user") -> None:
    created_at = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=age_days)
    async with session_scope() as session:
        session.add(ConversationMessage(customer_id=customer_id, role=role, content="متن تستی", created_at=created_at))
        await session.flush()


async def test_prune_deletes_only_older_than_retention() -> None:
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    customer_id = await _make_customer(shop_bot_id)

    await _add_message(customer_id, age_days=200)  # خیلی قدیمی
    await _add_message(customer_id, age_days=100)  # قدیمی‌تر از حدِ ۹۰ روزه
    await _add_message(customer_id, age_days=10)  # تازه

    async with session_scope() as session:
        deleted = await conversation_service.prune_old_messages(session, retention_days=90)
        assert deleted == 2, f"باید دقیقًا ۲ پیامِ قدیمی حذف بشه، نه {deleted}"

        remaining = (await session.execute(select(ConversationMessage))).scalars().all()
        assert len(remaining) == 1
        assert remaining[0].content == "متن تستی"
        age = datetime.datetime.now(datetime.timezone.utc) - remaining[0].created_at
        assert age.days < 90, "پیامِ باقی‌مونده باید همونِ پیامِ تازه باشه"

    print("✅ test_prune_deletes_only_older_than_retention PASSED")


async def test_zero_retention_disables_pruning() -> None:
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    customer_id = await _make_customer(shop_bot_id)
    await _add_message(customer_id, age_days=1000)

    async with session_scope() as session:
        deleted = await conversation_service.prune_old_messages(session, retention_days=0)
        assert deleted == 0, "retention_days<=0 یعنی پاکسازی غیرفعاله؛ نباید چیزی حذف بشه"

        remaining = (await session.execute(select(ConversationMessage))).scalars().all()
        assert len(remaining) == 1

    print("✅ test_zero_retention_disables_pruning PASSED")


async def test_admin_can_set_retention_days_via_settings_menu(main_dp) -> None:
    """مسیرِ end-to-endِ واقعی: ادمین از منوی «🔑 تنظیمات کلیدها» مقدار رو تغییر می‌ده."""
    await reset_database()
    await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID + 1)

    main_bot = Bot(token="000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS", session=FakeSession())
    await main_dp.feed_update(main_bot, make_callback_update(1, data="admin_setting_edit:conversation_retention_days", user_id=ADMIN_TG_ID))
    await main_dp.feed_update(main_bot, make_message_update(2, text="45", user_id=ADMIN_TG_ID))

    async with session_scope() as session:
        admin_settings = await get_admin_settings(session)
        assert admin_settings.conversation_retention_days == 45

    # صفر هم باید مجاز باشه (برخلافِ بقیه‌ی فیلدهای عددی که باید مثبت باشن)
    await main_dp.feed_update(main_bot, make_callback_update(3, data="admin_setting_edit:conversation_retention_days", user_id=ADMIN_TG_ID))
    await main_dp.feed_update(main_bot, make_message_update(4, text="0", user_id=ADMIN_TG_ID))
    async with session_scope() as session:
        admin_settings = await get_admin_settings(session)
        assert admin_settings.conversation_retention_days == 0

    print("✅ test_admin_can_set_retention_days_via_settings_menu PASSED")


async def main() -> None:
    await test_prune_deletes_only_older_than_retention()
    await test_zero_retention_disables_pruning()
    main_dp, _shop_dp, _bot_manager, _main_bot = build_test_dispatchers()
    await test_admin_can_set_retention_days_via_settings_menu(main_dp)


if __name__ == "__main__":
    asyncio.run(main())
