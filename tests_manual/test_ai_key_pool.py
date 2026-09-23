"""
تست: استخرِ کلیدهایِ AI + مدارِ قطعِ هوشمند + جداسازیِ قابلیتِ چت/vision (فازِ ۲).

اجرا: python3 tests_manual/test_ai_key_pool.py
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from harness import build_test_dispatchers, make_callback_update, make_message_update, reset_database  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402
from aiogram import Bot  # noqa: E402
from harness import FakeSession  # noqa: E402

from app.database.session import session_scope  # noqa: E402
from app.services import ai_pool_service, ai_service  # noqa: E402
from app.services.admin_settings_service import get_admin_settings  # noqa: E402
from app.services.ai_service import AiCallResult, AiServiceError, PooledAiService  # noqa: E402

ADMIN_TG_ID = 12345


class _AlwaysFail:
    def __init__(self) -> None:
        self.call_count = 0

    async def get_reply(self, system_prompt, history, user_message):
        self.call_count += 1
        raise AiServiceError("همیشه شکست")

    async def analyze_image(self, prompt, image_bytes, mime_type="image/jpeg"):
        raise AiServiceError("همیشه شکست")

    async def transcribe_audio(self, audio_bytes, filename="voice.ogg"):
        raise AiServiceError("همیشه شکست")


class _AlwaysSucceed:
    def __init__(self) -> None:
        self.call_count = 0

    async def get_reply(self, system_prompt, history, user_message):
        self.call_count += 1
        return AiCallResult(text="پاسخِ موفق", total_tokens=10)

    async def analyze_image(self, prompt, image_bytes, mime_type="image/jpeg"):
        raise NotImplementedError

    async def transcribe_audio(self, audio_bytes, filename="voice.ogg"):
        raise NotImplementedError


async def test_pooled_service_succeeds_if_any_key_works() -> None:
    ai_service.reset_all_circuits_for_tests()
    bad = _AlwaysFail()
    good = _AlwaysSucceed()
    pool = PooledAiService([(101, bad), (102, good)])

    result = await pool.get_reply("sys", [], "سلام")
    assert result.text == "پاسخِ موفق", "حتی اگه یه کلید شکست بخوره، باید از کلیدِ بعدی جواب بگیره"
    print("✅ test_pooled_service_succeeds_if_any_key_works PASSED")


async def test_pooled_service_raises_when_all_fail() -> None:
    ai_service.reset_all_circuits_for_tests()
    pool = PooledAiService([(201, _AlwaysFail()), (202, _AlwaysFail())])
    try:
        await pool.get_reply("sys", [], "سلام")
        raise AssertionError("باید وقتی همه‌ی کلیدها شکست می‌خورن، خطا بده")
    except AiServiceError:
        pass
    print("✅ test_pooled_service_raises_when_all_fail PASSED")


async def test_circuit_opens_after_threshold_and_skips_key() -> None:
    ai_service.reset_all_circuits_for_tests()
    bad = _AlwaysFail()
    good = _AlwaysSucceed()

    # ۵ بار پشتِ‌سرِهم صدا بزنیم تا مدارِ کلیدِ bad باز بشه (آستانه=۵)
    for _ in range(5):
        pool = PooledAiService([(301, bad)])
        try:
            await pool.get_reply("sys", [], "x")
        except AiServiceError:
            pass

    assert ai_service._circuit_is_open(301), "بعدِ ۵ شکستِ پیاپی، مدار باید باز شده باشه"

    # حالا یه استخرِ ۲تایی با همون کلیدِ خراب + یه کلیدِ سالم — نباید اصلاً
    # سراغِ کلیدِ bad بره (چون مدارش بازه)، مستقیم بره سراغِ good
    calls_before = bad.call_count
    pool = PooledAiService([(301, bad), (302, good)])
    result = await pool.get_reply("sys", [], "x")
    assert result.text == "پاسخِ موفق"
    assert bad.call_count == calls_before, "کلیدی که مدارش بازه، اصلاً نباید صدا زده بشه"
    print("✅ test_circuit_opens_after_threshold_and_skips_key PASSED")


async def test_circuit_resets_on_success() -> None:
    ai_service.reset_all_circuits_for_tests()
    good = _AlwaysSucceed()
    pool = PooledAiService([(401, good)])
    await pool.get_reply("sys", [], "x")
    assert not ai_service._circuit_is_open(401)
    print("✅ test_circuit_resets_on_success PASSED")


async def test_build_service_falls_back_to_legacy_fields_when_pool_empty() -> None:
    await reset_database()
    async with session_scope() as session:
        admin_settings = await get_admin_settings(session)
        admin_settings.ai_api_key = "legacy-key-123"
        admin_settings.ai_model = "legacy-model"
        admin_settings.ai_base_url = "https://legacy.example.com/v1/chat/completions"

        service = await ai_pool_service.build_ai_service(session, admin_settings, "chat")
        assert service is not None
        assert isinstance(service, ai_service.OpenAiCompatibleAiService), "با استخرِ خالی، باید مستقیم از کلیدِ قدیمی استفاده بشه"
    print("✅ test_build_service_falls_back_to_legacy_fields_when_pool_empty PASSED")


async def test_build_service_returns_none_when_nothing_configured() -> None:
    await reset_database()
    async with session_scope() as session:
        admin_settings = await get_admin_settings(session)
        admin_settings.ai_api_key = None
        service = await ai_pool_service.build_ai_service(session, admin_settings, "chat")
        assert service is None
    print("✅ test_build_service_returns_none_when_nothing_configured PASSED")


async def test_capability_filtering_separates_vision_from_chat() -> None:
    await reset_database()
    async with session_scope() as session:
        admin_settings = await get_admin_settings(session)
        admin_settings.ai_api_key = None  # مطمئن بشیم فقط از استخر میاد، نه fallbackِ قدیمی

        await ai_pool_service.add_entry(session, "چت‌فقط", "key-chat", "glm-4-flash", "https://x/v1", "chat")
        await ai_pool_service.add_entry(session, "ویژن‌فقط", "key-vision", "deepseek-vision", "https://x/v1", "vision")
        await ai_pool_service.add_entry(session, "هردو", "key-both", "some-model", "https://x/v1", "both")

        chat_entries = await ai_pool_service.get_active_entries_for_capability(session, "chat")
        assert {e.label for e in chat_entries} == {"چت‌فقط", "هردو"}, "برای چت فقط باید chat+both بیاد"

        vision_entries = await ai_pool_service.get_active_entries_for_capability(session, "vision")
        assert {e.label for e in vision_entries} == {"ویژن‌فقط", "هردو"}, "برای vision فقط باید vision+both بیاد"
    print("✅ test_capability_filtering_separates_vision_from_chat PASSED")


async def test_inactive_entry_excluded_from_pool() -> None:
    await reset_database()
    async with session_scope() as session:
        entry = await ai_pool_service.add_entry(session, "غیرفعال", "key-x", "model-x", "https://x/v1", "chat")
        await ai_pool_service.toggle_active(session, entry)  # خاموشش کن

        chat_entries = await ai_pool_service.get_active_entries_for_capability(session, "chat")
        assert entry.id not in [e.id for e in chat_entries], "کلیدِ غیرفعال نباید توی استخرِ فعال باشه"
    print("✅ test_inactive_entry_excluded_from_pool PASSED")


async def test_admin_add_entry_via_five_line_message(main_dp) -> None:
    await reset_database()
    await seed_usable_shop(999601, 999602)
    main_bot = Bot(token="000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS", session=FakeSession())

    await main_dp.feed_update(main_bot, make_callback_update(1, data="ai_pool_add", user_id=ADMIN_TG_ID))
    message_text = "GapGPT کلید ۱\nsk-test-abc\nglm-4-flash\nhttps://api.gapgpt.app/v1/chat/completions\nchat"
    await main_dp.feed_update(main_bot, make_message_update(2, text=message_text, user_id=ADMIN_TG_ID))

    async with session_scope() as session:
        entries = await ai_pool_service.get_all_entries(session)
        assert len(entries) == 1
        assert entries[0].label == "GapGPT کلید ۱"
        assert entries[0].model == "glm-4-flash"
        cap_value = entries[0].capability.value if hasattr(entries[0].capability, "value") else entries[0].capability
        assert cap_value == "chat"
    print("✅ test_admin_add_entry_via_five_line_message PASSED")


async def test_admin_add_entry_rejects_bad_format(main_dp) -> None:
    await reset_database()
    await seed_usable_shop(999603, 999604)
    main_bot = Bot(token="000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS", session=FakeSession())

    await main_dp.feed_update(main_bot, make_callback_update(1, data="ai_pool_add", user_id=ADMIN_TG_ID))
    await main_dp.feed_update(main_bot, make_message_update(2, text="فقط یه خط", user_id=ADMIN_TG_ID))

    async with session_scope() as session:
        entries = await ai_pool_service.get_all_entries(session)
        assert len(entries) == 0, "فرمتِ نادرست نباید چیزی ذخیره کنه"
    print("✅ test_admin_add_entry_rejects_bad_format PASSED")


async def main() -> None:
    await test_pooled_service_succeeds_if_any_key_works()
    await test_pooled_service_raises_when_all_fail()
    await test_circuit_opens_after_threshold_and_skips_key()
    await test_circuit_resets_on_success()
    await test_build_service_falls_back_to_legacy_fields_when_pool_empty()
    await test_build_service_returns_none_when_nothing_configured()
    await test_capability_filtering_separates_vision_from_chat()
    await test_inactive_entry_excluded_from_pool()

    main_dp, _shop_dp, _bot_manager, _main_bot = build_test_dispatchers()
    await test_admin_add_entry_via_five_line_message(main_dp)
    await test_admin_add_entry_rejects_bad_format(main_dp)


if __name__ == "__main__":
    asyncio.run(main())
