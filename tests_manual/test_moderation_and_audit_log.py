"""
تست: نگهبانِ محتوا (Moderation) و گزارشِ ممیزی (Audit Log) — بخشِ ۲ مسترپرامپت.

اجرا: python3 tests_manual/test_moderation_and_audit_log.py
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from harness import FakeSession, build_test_dispatchers, make_callback_update, make_message_update, reset_database  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from aiogram import Bot  # noqa: E402

from app.database.models import AuditEventType, ModerationRule  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import ai_service, audit_log_service, moderation_service  # noqa: E402
from app.services.ai_service import AiCallResult  # noqa: E402

OWNER_TG_ID = 999501
SHOP_BOT_TG_ID = 999502
CUSTOMER_TG_ID = 999503
ADMIN_TG_ID = 12345


class _FakeAiService:
    def __init__(self) -> None:
        self.call_count = 0

    async def get_reply(self, system_prompt, history, user_message) -> AiCallResult:
        self.call_count += 1
        return AiCallResult(text="سلام، چطور می‌تونم کمکتون کنم؟", total_tokens=50)


async def _add_rule(pattern: str, action: str) -> None:
    async with session_scope() as session:
        session.add(ModerationRule(pattern=pattern, is_regex=False, action=action))
        await session.flush()


async def test_block_rule_prevents_ai_call_and_logs(shop_dp) -> None:
    await reset_database()
    await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    await _add_rule("ممنوعه‌واژه", "block")

    fake_ai = _FakeAiService()
    original = ai_service.get_ai_service
    ai_service.get_ai_service = lambda api_key, model, base_url=None, fallback_api_key=None, fallback_model=None, fallback_base_url=None: fake_ai
    try:
        shop_bot_instance = Bot(token=f"{SHOP_BOT_TG_ID}:FAKE", session=FakeSession())
        session_obj: FakeSession = shop_bot_instance.session  # type: ignore[assignment]
        await shop_dp.feed_update(shop_bot_instance, make_message_update(1, text="یه ممنوعه‌واژه اینجاست", user_id=CUSTOMER_TG_ID))
        await asyncio.sleep(4.5)  # عبور از پنجره‌ی debounce (DEBOUNCE_SECONDS=3.0)

        assert fake_ai.call_count == 0, "نباید هوش‌مصنوعی صدا زده بشه"
        assert any(texts_contains(m, "متاسفانه") for m in session_obj.sent_messages), "باید پیامِ مسدودشده دیده بشه"

        async with session_scope() as session:
            entries = await audit_log_service.get_recent(session, limit=5)
            assert any(e.event_type == AuditEventType.MODERATION_MATCH for e in entries), "باید یه رویدادِ moderation_match ثبت بشه"
    finally:
        ai_service.get_ai_service = original

    print("✅ test_block_rule_prevents_ai_call_and_logs PASSED")


async def test_review_rule_notifies_owner(shop_dp, main_bot) -> None:
    await reset_database()
    await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    await _add_rule("نیازبررسی", "review")

    fake_ai = _FakeAiService()
    original = ai_service.get_ai_service
    ai_service.get_ai_service = lambda api_key, model, base_url=None, fallback_api_key=None, fallback_model=None, fallback_base_url=None: fake_ai
    try:
        shop_bot_instance = Bot(token=f"{SHOP_BOT_TG_ID}:FAKE", session=FakeSession())
        main_session_obj: FakeSession = main_bot.session  # type: ignore[assignment]
        main_session_obj.sent_messages.clear()

        await shop_dp.feed_update(shop_bot_instance, make_message_update(1, text="این نیازبررسی داره", user_id=CUSTOMER_TG_ID))
        await asyncio.sleep(4.5)

        assert fake_ai.call_count == 0
        assert any(texts_contains(m, "بررسی") for m in main_session_obj.sent_messages), "فروشگاه‌دار باید از طریقِ main_bot خبردار بشه"
    finally:
        ai_service.get_ai_service = original

    print("✅ test_review_rule_notifies_owner PASSED")


async def test_warn_rule_allows_ai_call(shop_dp) -> None:
    await reset_database()
    await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    await _add_rule("فقط‌هشدار", "warn")

    fake_ai = _FakeAiService()
    original = ai_service.get_ai_service
    ai_service.get_ai_service = lambda api_key, model, base_url=None, fallback_api_key=None, fallback_model=None, fallback_base_url=None: fake_ai
    try:
        shop_bot_instance = Bot(token=f"{SHOP_BOT_TG_ID}:FAKE", session=FakeSession())
        await shop_dp.feed_update(shop_bot_instance, make_message_update(1, text="این فقط‌هشدار داره", user_id=CUSTOMER_TG_ID))
        await asyncio.sleep(4.5)

        assert fake_ai.call_count >= 1, "برای WARN باید هوش‌مصنوعی بازم صدا زده بشه (مکالمه مسدود نشه)"

        async with session_scope() as session:
            entries = await audit_log_service.get_recent(session, limit=5)
            assert any(e.event_type == AuditEventType.MODERATION_MATCH for e in entries), "بازم باید ثبت بشه، فقط مکالمه بلاک نشه"
    finally:
        ai_service.get_ai_service = original

    print("✅ test_warn_rule_allows_ai_call PASSED")


async def test_unrelated_message_no_match(shop_dp) -> None:
    await reset_database()
    await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    await _add_rule("ممنوعه‌واژه", "block")

    fake_ai = _FakeAiService()
    original = ai_service.get_ai_service
    ai_service.get_ai_service = lambda api_key, model, base_url=None, fallback_api_key=None, fallback_model=None, fallback_base_url=None: fake_ai
    try:
        shop_bot_instance = Bot(token=f"{SHOP_BOT_TG_ID}:FAKE", session=FakeSession())
        await shop_dp.feed_update(shop_bot_instance, make_message_update(1, text="سلام، قیمتِ محصول چنده؟", user_id=CUSTOMER_TG_ID))
        await asyncio.sleep(4.5)

        assert fake_ai.call_count >= 1, "پیامِ بی‌ربط نباید مسدود بشه"
    finally:
        ai_service.get_ai_service = original

    print("✅ test_unrelated_message_no_match PASSED")


async def test_admin_add_and_toggle_rule_handlers(main_dp) -> None:
    await reset_database()
    await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)

    main_bot = Bot(token="000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS", session=FakeSession())
    await main_dp.feed_update(main_bot, make_callback_update(1, data="mod_rule_add", user_id=ADMIN_TG_ID))
    await main_dp.feed_update(main_bot, make_message_update(2, text="کلیدواژه‌ی‌تستی", user_id=ADMIN_TG_ID))
    await main_dp.feed_update(main_bot, make_callback_update(3, data="mod_rule_action:block", user_id=ADMIN_TG_ID))

    async with session_scope() as session:
        rules = await moderation_service.get_all_rules(session)
        assert len(rules) == 1
        assert rules[0].pattern == "کلیدواژه‌ی‌تستی"
        assert rules[0].action == "block"
        rule_id = rules[0].id

    await main_dp.feed_update(main_bot, make_callback_update(4, data=f"mod_rule_toggle:{rule_id}", user_id=ADMIN_TG_ID))
    async with session_scope() as session:
        rule = await moderation_service.get_by_id(session, rule_id)
        assert rule.is_active is False, "بعدِ toggle باید غیرفعال بشه"

    await main_dp.feed_update(main_bot, make_callback_update(5, data=f"mod_rule_delete:{rule_id}", user_id=ADMIN_TG_ID))
    async with session_scope() as session:
        rules = await moderation_service.get_all_rules(session)
        assert len(rules) == 0, "بعدِ حذف نباید هیچ قانونی بمونه"

    print("✅ test_admin_add_and_toggle_rule_handlers PASSED")


async def test_audit_log_records_kill_switch_toggle(main_dp) -> None:
    await reset_database()
    await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)

    main_bot = Bot(token="000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS", session=FakeSession())
    await main_dp.feed_update(main_bot, make_callback_update(1, data="admin_toggle_maintenance", user_id=ADMIN_TG_ID))

    async with session_scope() as session:
        entries = await audit_log_service.get_recent(session, limit=5)
        assert any(e.event_type == AuditEventType.KILL_SWITCH_TOGGLED for e in entries)
        assert any("maintenance_mode" in (e.details or "") for e in entries)

    print("✅ test_audit_log_records_kill_switch_toggle PASSED")


def texts_contains(sent_message: dict, needle: str) -> bool:
    return needle in sent_message.get("text", "")


async def main() -> None:
    main_dp, shop_dp, bot_manager, main_bot = build_test_dispatchers()
    await test_block_rule_prevents_ai_call_and_logs(shop_dp)
    await test_review_rule_notifies_owner(shop_dp, main_bot)
    await test_warn_rule_allows_ai_call(shop_dp)
    await test_unrelated_message_no_match(shop_dp)
    await test_admin_add_and_toggle_rule_handlers(main_dp)
    await test_audit_log_records_kill_switch_toggle(main_dp)


if __name__ == "__main__":
    asyncio.run(main())
