"""
تست: باگ #10 — وقتی مشتری چند پیامِ پشت‌سرهم (توی چند ثانیه) می‌فرسته، ربات باید
همه رو با هم جمع کنه و فقط یه‌بار جواب بده، نه اینکه به هر پیام جدا جدا (و شاید
با یه «سلام» تکراری) جواب بده.

از اونجایی که خودِ فراخوانیِ هوش مصنوعی نیاز به شبکه‌ی واقعی داره (که توی سندباکس
مجاز نیست)، ai_service.get_ai_service با یه پیاده‌سازیِ جعلی monkeypatch می‌شه که
فقط پیامِ ترکیبی‌ای که بهش رسیده رو ضبط می‌کنه — چیزی که مکانیزمِ debounce (که
خودِ باگ‌فیکسه) رو دقیقاً امتحان می‌کنه.

اجرا: python3 tests_manual/test_message_debounce.py
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from aiogram import Bot  # noqa: E402

from harness import FakeSession, build_test_dispatchers, make_message_update, reset_database  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from app.services import ai_service  # noqa: E402
from app.services.ai_service import AiCallResult  # noqa: E402
from app.services.order_detection_service import _CLASSIFIER_USER_PROMPT  # noqa: E402

OWNER_TG_ID = 999101
SHOP_BOT_TG_ID = 999102
CUSTOMER_TG_ID = 999103


class _FakeAiService:
    def __init__(self) -> None:
        self.received_prompts: list[str] = []
        self.all_calls: list[tuple[str, str]] = []  # (system_prompt[:30], user_message)

    async def get_reply(self, system_prompt: str, history: list[dict[str, str]], user_message: str) -> AiCallResult:
        self.all_calls.append((system_prompt[:30], user_message))
        # فراخوانیِ واقعیِ چت (نه طبقه‌بندی‌کننده‌ی پس‌زمینه‌ی تشخیصِ سفارش که یه
        # پرامپتِ ثابتِ خودشو داره) رو جدا ضبط می‌کنیم، چون همون چیزیه که مکانیزمِ
        # debounce/ترکیبِ پیام‌ها روش اثر می‌ذاره.
        if user_message != _CLASSIFIER_USER_PROMPT:
            self.received_prompts.append(user_message)
        text = '{"completed": false}' if user_message == _CLASSIFIER_USER_PROMPT else "این پاسخِ آزمایشیِ هوشِ مصنوعیه."
        return AiCallResult(text=text, total_tokens=42)

    async def analyze_image(self, prompt: str, image_bytes: bytes, mime_type: str = "image/jpeg") -> AiCallResult:
        return AiCallResult(text="تحلیلِ آزمایشیِ تصویر", total_tokens=42)

    async def transcribe_audio(self, audio_bytes: bytes, filename: str = "voice.ogg") -> str:
        return "متنِ آزمایشیِ رونویسی‌شده"


async def test_rapid_messages_are_combined(shop_dp, main_bot) -> None:
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)

    fake_ai = _FakeAiService()
    original_get_ai_service = ai_service.get_ai_service
    ai_service.get_ai_service = lambda api_key, model, base_url=None, fallback_api_key=None, fallback_model=None, fallback_base_url=None: fake_ai

    try:
        shop_bot_instance = Bot(token=f"{SHOP_BOT_TG_ID}:FAKE", session=FakeSession())
        shop_session_obj: FakeSession = shop_bot_instance.session  # type: ignore[assignment]

        # سه پیامِ جدا رو خیلی سریع (بدونِ فاصله‌ی زمانیِ واقعی) پشتِ‌سرِ هم می‌فرستیم
        await shop_dp.feed_update(shop_bot_instance, make_message_update(1, text="سلام", user_id=CUSTOMER_TG_ID))
        await shop_dp.feed_update(shop_bot_instance, make_message_update(2, text="قیمتِ محصولِ الف چنده؟", user_id=CUSTOMER_TG_ID))
        await shop_dp.feed_update(shop_bot_instance, make_message_update(3, text="ارسال هم دارید؟", user_id=CUSTOMER_TG_ID))

        # صبر می‌کنیم تا تسکِ debounce (که با تاخیر ~3 ثانیه اجرا می‌شه) کامل بشه
        await asyncio.sleep(4.5)

        assert len(fake_ai.received_prompts) == 1, (
            f"باید فقط یه‌بار (پیامِ ترکیبی) به هوش مصنوعی فرستاده بشه، نه {len(fake_ai.received_prompts)} بار"
        )
        combined = fake_ai.received_prompts[0]
        assert "سلام" in combined and "قیمتِ محصولِ الف" in combined and "ارسال" in combined, (
            f"متنِ ترکیبی باید هر سه پیام رو شامل بشه: {combined!r}"
        )

        assert len(shop_session_obj.sent_messages) == 1, (
            f"باید فقط یه پاسخ به مشتری فرستاده بشه، نه {len(shop_session_obj.sent_messages)} پاسخِ جدا"
        )

        print("✅ test_rapid_messages_are_combined PASSED")
    finally:
        ai_service.get_ai_service = original_get_ai_service


async def test_single_message_still_gets_reply(shop_dp, main_bot) -> None:
    await reset_database()
    await seed_usable_shop(OWNER_TG_ID + 1, SHOP_BOT_TG_ID + 1)

    fake_ai = _FakeAiService()
    original_get_ai_service = ai_service.get_ai_service
    ai_service.get_ai_service = lambda api_key, model, base_url=None, fallback_api_key=None, fallback_model=None, fallback_base_url=None: fake_ai

    try:
        shop_bot_instance = Bot(token=f"{SHOP_BOT_TG_ID + 1}:FAKE", session=FakeSession())
        shop_session_obj: FakeSession = shop_bot_instance.session  # type: ignore[assignment]

        await shop_dp.feed_update(shop_bot_instance, make_message_update(1, text="سلام تنها", user_id=CUSTOMER_TG_ID + 1))
        await asyncio.sleep(4.5)

        assert len(fake_ai.received_prompts) == 1
        assert fake_ai.received_prompts[0] == "سلام تنها"
        assert len(shop_session_obj.sent_messages) == 1

        print("✅ test_single_message_still_gets_reply PASSED")
    finally:
        ai_service.get_ai_service = original_get_ai_service


async def main() -> None:
    main_dp, shop_dp, bot_manager, main_bot = build_test_dispatchers()
    await test_rapid_messages_are_combined(shop_dp, main_bot)
    await test_single_message_still_gets_reply(shop_dp, main_bot)


if __name__ == "__main__":
    asyncio.run(main())
