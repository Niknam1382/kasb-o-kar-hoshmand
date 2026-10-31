"""
تست: قابلیتِ #8 — پیامِ صوتیِ مشتری باید رونویسی بشه و از همون مسیرِ
debounce/پاسخ‌دهیِ متنی رد بشه (یعنی می‌تونه حتی با یه پیامِ متنیِ بلافاصله‌بعد
ترکیب بشه).

اجرا: python3 tests_manual/test_voice_handling.py
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

OWNER_TG_ID = 999301
SHOP_BOT_TG_ID = 999302
CUSTOMER_TG_ID = 999303

VOICE_BYTES = b"OggS-fake-voice-bytes-for-testing"


class _FakeAiServiceForVoice:
    def __init__(self, transcript: str = "سلام، ساعت کاریتون چیه؟") -> None:
        self.transcript = transcript
        self.chat_prompts: list[str] = []

    async def get_reply(self, system_prompt: str, history, user_message: str) -> AiCallResult:
        if user_message != _CLASSIFIER_USER_PROMPT:
            self.chat_prompts.append(user_message)
        text = '{"status": "none"}' if user_message == _CLASSIFIER_USER_PROMPT else "پاسخِ آزمایشی"
        return AiCallResult(text=text, total_tokens=42)

    async def analyze_image(self, prompt, image_bytes, mime_type="image/jpeg") -> AiCallResult:
        return AiCallResult(text="")

    async def transcribe_audio(self, audio_bytes: bytes, filename: str = "voice.ogg") -> str:
        assert audio_bytes == VOICE_BYTES, "بایت‌های واقعیِ صدا باید به رونویسی‌کننده برسه"
        return self.transcript


async def test_voice_message_transcribed_and_replied(shop_dp, main_bot) -> None:
    await reset_database()
    await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)

    fake_ai = _FakeAiServiceForVoice()
    original_get_ai_service = ai_service.get_ai_service
    ai_service.get_ai_service = lambda api_key, model, base_url=None, fallback_api_key=None, fallback_model=None, fallback_base_url=None: fake_ai

    try:
        shop_bot_instance = Bot(token=f"{SHOP_BOT_TG_ID}:FAKE", session=FakeSession())
        shop_session_obj: FakeSession = shop_bot_instance.session  # type: ignore[assignment]
        shop_session_obj.set_downloaded_file("incoming_voice_id", VOICE_BYTES)

        await shop_dp.feed_update(shop_bot_instance, make_message_update(1, user_id=CUSTOMER_TG_ID, voice=True))
        await asyncio.sleep(4.5)  # صبر برای اتمامِ debounce

        assert len(fake_ai.chat_prompts) == 1, f"باید یه پاسخِ چت رخ بده، نه {len(fake_ai.chat_prompts)}"
        assert fake_ai.chat_prompts[0] == "سلام، ساعت کاریتون چیه؟", "متنِ رونویسی‌شده باید عیناً به‌عنوانِ پیامِ مشتری استفاده بشه"
        assert len(shop_session_obj.sent_messages) == 1, "باید فقط یه پاسخ به مشتری برسه"

        print("✅ test_voice_message_transcribed_and_replied PASSED")
    finally:
        ai_service.get_ai_service = original_get_ai_service


async def test_empty_transcript_shows_error(shop_dp, main_bot) -> None:
    await reset_database()
    await seed_usable_shop(OWNER_TG_ID + 1, SHOP_BOT_TG_ID + 1)

    fake_ai = _FakeAiServiceForVoice(transcript="")
    original_get_ai_service = ai_service.get_ai_service
    ai_service.get_ai_service = lambda api_key, model, base_url=None, fallback_api_key=None, fallback_model=None, fallback_base_url=None: fake_ai

    try:
        shop_bot_instance = Bot(token=f"{SHOP_BOT_TG_ID + 1}:FAKE", session=FakeSession())
        shop_session_obj: FakeSession = shop_bot_instance.session  # type: ignore[assignment]
        shop_session_obj.set_downloaded_file("incoming_voice_id", VOICE_BYTES)

        await shop_dp.feed_update(shop_bot_instance, make_message_update(1, user_id=CUSTOMER_TG_ID + 1, voice=True))
        await asyncio.sleep(0.3)

        assert len(fake_ai.chat_prompts) == 0, "با رونویسیِ خالی نباید اصلاً وارد جریانِ پاسخ‌دهیِ چت بشه"
        assert any(
            "نتونستم" in m["text"] or "متوجه نشدم" in m["text"] or "نوشتاری" in m["text"] for m in shop_session_obj.sent_messages
        ), "باید پیامِ خطای رونویسیِ ناموفق نشون داده بشه"

        print("✅ test_empty_transcript_shows_error PASSED")
    finally:
        ai_service.get_ai_service = original_get_ai_service


async def main() -> None:
    main_dp, shop_dp, bot_manager, main_bot = build_test_dispatchers()
    await test_voice_message_transcribed_and_replied(shop_dp, main_bot)
    await test_empty_transcript_shows_error(shop_dp, main_bot)


if __name__ == "__main__":
    asyncio.run(main())
