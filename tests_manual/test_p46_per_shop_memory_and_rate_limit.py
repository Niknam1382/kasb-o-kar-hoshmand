"""
تست: P46 · مواردِ ۳۷ و ۱۴ — حافظهٔ هر گفتگو و سقفِ پیام، per-shop

۱. سه تنظیمِ تازه در فهرستِ تنظیماتِ per-shop و برچسبِ فارسی‌شان هست؛ دکمهٔ سراسریِ
   «حافظهٔ مکالمه» و «محدودیتِ پیام» از پنلِ ادمین برداشته شده (ستون‌ها به‌عنوانِ پیش‌فرض می‌مانند).
۲. مقدارِ مؤثر: فروشگاهِ تنظیم‌نکرده = پیش‌فرضِ سراسری؛ تنظیم‌کرده = عددِ خودش؛ و همیشه داخلِ
   بازه‌یِ ایمنی clamp می‌شود (۵۰۰ پیام حافظه ⇒ ۲۰۰).
۳. پنلِ کاربر: صفحهٔ «تنظیماتِ ربات» هر سه را نشان می‌دهد، ذخیره و «بازگشت به پیش‌فرض» کار می‌کند
   و در هر دو مود (فروشگاهی و مشاوره‌ای) دیده می‌شوند.
۴. مایگریشن: سه ستونِ nullable رویِ `shop_bots` و مقدارِ پیش‌فرضِ NULL (هیچ رفتارِ تازه‌ای با نصب
   ایجاد نمی‌شود).

اجرا: python3 tests_manual/run_one.py test_p46_per_shop_memory_and_rate_limit.py
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from sqlalchemy import select  # noqa: E402

from harness import FakeSession, build_test_dispatchers, reset_database  # noqa: E402
from phase4_helpers import Chat, callbacks  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from app.bots.main_bot import texts as main_texts  # noqa: E402
from app.database.models import ShopBot  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import shop_prefs_service  # noqa: E402
from app.services.admin_settings_service import get_admin_settings, update_setting  # noqa: E402

OWNER_TG_ID = 7_446_000_001
OTHER_OWNER_TG_ID = 7_446_000_002
SHOP_BOT_TG_ID = 7_446_100_001
OTHER_SHOP_BOT_TG_ID = 7_446_100_002

NEW_PREFS = (
    shop_prefs_service.HISTORY_LIMIT,
    shop_prefs_service.RATE_LIMIT_MESSAGES,
    shop_prefs_service.RATE_LIMIT_SECONDS,
)


async def _shop_bot_id(owner_tg_id: int) -> int:
    async with session_scope() as session:
        from app.database.models import ShopOwner

        owner = (await session.execute(select(ShopOwner).where(ShopOwner.telegram_id == owner_tg_id))).scalar_one()
        return (await session.execute(select(ShopBot.id).where(ShopBot.shop_owner_id == owner.id))).scalar_one()


async def _patch(shop_bot_id: int, **columns) -> None:
    async with session_scope() as session:
        shop_bot = await session.get(ShopBot, shop_bot_id)
        for column, value in columns.items():
            setattr(shop_bot, column, value)
        await session.flush()


async def _admin_default(column: str, value: int) -> None:
    async with session_scope() as session:
        await update_setting(session, column, value)


# ============================================================================= ۱ — ثبتِ تنظیمات و حذفِ دکمهٔ سراسری
def test_prefs_registered_and_admin_buttons_gone() -> None:
    for pref in NEW_PREFS:
        assert pref.key in shop_prefs_service.BY_KEY, pref.key
        assert pref in shop_prefs_service.ALL_PREFS, pref.key
        assert pref.key in main_texts.SHOP_PREF_LABELS, f"برچسبِ فارسی ندارد: {pref.key}"
        assert pref.admin_key in shop_prefs_service.REMOVED_FROM_ADMIN, pref.admin_key
        assert pref.consultation is True, "در پنلِ مشاوره‌ای هم معنا دارد"
    print("✅ test_prefs_registered_and_admin_buttons_gone PASSED")


async def test_admin_panel_no_longer_offers_them() -> None:
    await reset_database()
    async with session_scope() as session:
        admin_settings = await get_admin_settings(session)
    keys = {key for key, _ in main_texts.admin_settings_button_labels(admin_settings)}
    assert "conversation_history_limit" not in keys, keys
    assert "rate_limit" not in keys, keys
    groups = main_texts.ADMIN_SETTING_GROUP
    assert "conversation_history_limit" not in groups and "rate_limit" not in groups, groups
    # هیچ دکمه‌ای در دسته‌ها به این دو فیلدِ سراسری اشاره نمی‌کند
    for group in main_texts.ADMIN_SETTINGS_GROUP_KEYS:
        row_keys = {key for key, _ in main_texts.admin_settings_button_labels(admin_settings, group=group)}
        assert not row_keys & {"conversation_history_limit", "rate_limit"}, group
    print("✅ test_admin_panel_no_longer_offers_them PASSED")


# ============================================================================= ۲ — مقدارِ مؤثر
async def test_effective_values_default_override_and_clamp() -> None:
    await reset_database()
    await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    shop_bot_id = await _shop_bot_id(OWNER_TG_ID)

    await _admin_default("conversation_history_limit", 20)
    await _admin_default("rate_limit_max_messages", 15)
    await _admin_default("rate_limit_window_seconds", 60)

    async with session_scope() as session:
        admin_settings = await get_admin_settings(session)
        shop_bot = await session.get(ShopBot, shop_bot_id)
        # تنظیم‌نکرده ⇒ دقیقاً رفتارِ قبل (پیش‌فرضِ سراسری)
        assert shop_prefs_service.resolve(shop_prefs_service.HISTORY_LIMIT, shop_bot, admin_settings) == 20
        assert shop_prefs_service.resolve(shop_prefs_service.RATE_LIMIT_MESSAGES, shop_bot, admin_settings) == 15
        assert shop_prefs_service.resolve(shop_prefs_service.RATE_LIMIT_SECONDS, shop_bot, admin_settings) == 60

    await _patch(shop_bot_id, history_limit_messages=5, rate_limit_messages=40, rate_limit_seconds=300)
    async with session_scope() as session:
        admin_settings = await get_admin_settings(session)
        shop_bot = await session.get(ShopBot, shop_bot_id)
        assert shop_prefs_service.resolve(shop_prefs_service.HISTORY_LIMIT, shop_bot, admin_settings) == 5
        assert shop_prefs_service.resolve(shop_prefs_service.RATE_LIMIT_MESSAGES, shop_bot, admin_settings) == 40
        assert shop_prefs_service.resolve(shop_prefs_service.RATE_LIMIT_SECONDS, shop_bot, admin_settings) == 300

    await _patch(shop_bot_id, history_limit_messages=500, rate_limit_seconds=1)
    async with session_scope() as session:
        admin_settings = await get_admin_settings(session)
        shop_bot = await session.get(ShopBot, shop_bot_id)
        assert shop_prefs_service.resolve(shop_prefs_service.HISTORY_LIMIT, shop_bot, admin_settings) == 200, "clampِ سقف"
        assert shop_prefs_service.resolve(shop_prefs_service.RATE_LIMIT_SECONDS, shop_bot, admin_settings) == 5, "clampِ کف"

    # فروشگاهِ دیگر دست‌نخورده می‌ماند (per-shop واقعاً per-shop است)
    await seed_usable_shop(OTHER_OWNER_TG_ID, OTHER_SHOP_BOT_TG_ID)
    other_id = await _shop_bot_id(OTHER_OWNER_TG_ID)
    async with session_scope() as session:
        admin_settings = await get_admin_settings(session)
        other = await session.get(ShopBot, other_id)
        assert shop_prefs_service.resolve(shop_prefs_service.HISTORY_LIMIT, other, admin_settings) == 20
        assert other.history_limit_messages is None, other.history_limit_messages
    print("✅ test_effective_values_default_override_and_clamp PASSED")


# ============================================================================= ۳ — پنلِ کاربر
async def test_owner_panel_shows_saves_and_resets(main_dp) -> None:
    await reset_database()
    await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    shop_bot_id = await _shop_bot_id(OWNER_TG_ID)
    owner = Chat(main_dp, OWNER_TG_ID)

    await owner.tap("sp_prefs_open")
    body = owner.last_edit_text
    assert "💭 حافظه‌ی مکالمه" in body and "🚦 سقفِ پیامِ هر مشتری" in body and "🚦 طولِ پنجره‌یِ سقفِ پیام" in body, body
    page = callbacks(owner.last_edit_markup)
    for pref in NEW_PREFS:
        assert f"sp_pref:{pref.key}" in page, page

    await owner.tap(f"sp_pref:{shop_prefs_service.HISTORY_LIMIT.key}")
    assert "پیش‌فرضِ سراسری" in owner.last_edit_text, owner.last_edit_text
    await owner.tap(f"sp_pref_set:{shop_prefs_service.HISTORY_LIMIT.key}:12")
    assert owner.last_toast["text"] == main_texts.SHOP_PREF_SAVED, owner.last_toast
    async with session_scope() as session:
        shop_bot = await session.get(ShopBot, shop_bot_id)
        assert shop_bot.history_limit_messages == 12, shop_bot.history_limit_messages

    await owner.tap(f"sp_pref_set:{shop_prefs_service.RATE_LIMIT_SECONDS.key}:99999")
    assert owner.last_toast["text"] == main_texts.SHOP_PREFS_STALE, "خارجِ بازه ذخیره نمی‌شود"
    async with session_scope() as session:
        shop_bot = await session.get(ShopBot, shop_bot_id)
        assert shop_bot.rate_limit_seconds is None, shop_bot.rate_limit_seconds

    await owner.tap(f"sp_pref_reset:{shop_prefs_service.HISTORY_LIMIT.key}")
    async with session_scope() as session:
        shop_bot = await session.get(ShopBot, shop_bot_id)
        assert shop_bot.history_limit_messages is None, "بازگشت به پیش‌فرضِ سراسری"

    # مودِ مشاوره‌ای هم همان سه را دارد (موردِ ۲۴/۳۷: دو پنل یکی بمانند)
    async with session_scope() as session:
        from app.database.models import TenantMode

        shop_bot = await session.get(ShopBot, shop_bot_id)
        shop_bot.tenant_mode = TenantMode.CONSULTATION
    await owner.tap("sp_prefs_open")
    page = callbacks(owner.last_edit_markup)
    for pref in NEW_PREFS:
        assert f"sp_pref:{pref.key}" in page, page
    print("✅ test_owner_panel_shows_saves_and_resets PASSED")


# ============================================================================= ۴ — مایگریشن
async def test_columns_exist_and_default_to_null() -> None:
    await reset_database()
    await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    shop_bot_id = await _shop_bot_id(OWNER_TG_ID)
    async with session_scope() as session:
        row = (
            await session.execute(
                select(
                    ShopBot.history_limit_messages,
                    ShopBot.rate_limit_messages,
                    ShopBot.rate_limit_seconds,
                ).where(ShopBot.id == shop_bot_id)
            )
        ).one()
    assert row == (None, None, None), row
    print("✅ test_columns_exist_and_default_to_null PASSED")


async def main() -> None:
    main_dp, _shop_dp, _bot_manager, _main_bot = build_test_dispatchers()
    test_prefs_registered_and_admin_buttons_gone()
    await test_admin_panel_no_longer_offers_them()
    await test_effective_values_default_override_and_clamp()
    await test_owner_panel_shows_saves_and_resets(main_dp)
    await test_columns_exist_and_default_to_null()


if __name__ == "__main__":
    asyncio.run(main())
