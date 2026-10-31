"""
تست: باگ #2 (عکسِ مشتری هندل نمی‌شد) + قابلیتِ #6 (تحلیلِ هوشمندِ تصویر برای رسید).

این دقیقاً همون هندلریه که در بازسازیِ این پروژه، ground truth نشون داد نیمه‌کاره و
بامشکل بود (یه placeholder با "if False else" و متغیرهای analysis_note/caption_note
که محاسبه می‌شدن ولی هیچ‌جا استفاده نمی‌شدن). این تست تاییدِ نهاییه که نسخه‌ی
تکمیل‌شده درست کار می‌کنه: عکس با bot فروشگاهی دانلود می‌شه، با هوش مصنوعی تحلیل
می‌شه، و از طریقِ main_bot (نه bot فروشگاهی) با یه فایلِ تازه (BufferedInputFile)
برای فروشگاه‌دار فوروارد می‌شه — چون file_id بینِ دو bot instance قابل‌انتقال نیست.

اجرا: python3 tests_manual/test_photo_handling.py
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

OWNER_TG_ID = 999201
SHOP_BOT_TG_ID = 999202
CUSTOMER_TG_ID = 999203

PHOTO_BYTES = b"\xff\xd8\xff\xe0-fake-jpeg-bytes-for-a-receipt-photo"


class _FakeAiServiceForPhoto:
    async def get_reply(self, system_prompt, history, user_message) -> AiCallResult:
        return AiCallResult(text='{"completed": false}', total_tokens=42)

    async def analyze_image(self, prompt: str, image_bytes: bytes, mime_type: str = "image/jpeg") -> AiCallResult:
        assert image_bytes == PHOTO_BYTES, "بایت‌های واقعیِ عکس باید به تحلیل‌گر برسه"
        return AiCallResult(text="مبلغ: ۴۵۰,۰۰۰ تومان — تاریخ: ۱۴۰۴/۰۵/۱۹ — شماره‌ی پیگیری: 123456", total_tokens=120)

    async def transcribe_audio(self, audio_bytes: bytes, filename: str = "voice.ogg") -> str:
        return ""


async def test_customer_photo_forwarded_with_analysis(shop_dp, main_bot) -> None:
    await reset_database()
    await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)

    fake_ai = _FakeAiServiceForPhoto()
    original_get_ai_service = ai_service.get_ai_service
    ai_service.get_ai_service = lambda api_key, model, base_url=None, fallback_api_key=None, fallback_model=None, fallback_base_url=None: fake_ai

    try:
        shop_bot_instance = Bot(token=f"{SHOP_BOT_TG_ID}:FAKE", session=FakeSession())
        shop_session_obj: FakeSession = shop_bot_instance.session  # type: ignore[assignment]
        shop_session_obj.set_downloaded_file("incoming_photo_id", PHOTO_BYTES)

        main_session_obj: FakeSession = main_bot.session  # type: ignore[assignment]
        main_session_obj.sent_photos.clear()

        await shop_dp.feed_update(
            shop_bot_instance,
            make_message_update(1, user_id=CUSTOMER_TG_ID, photo=True, caption="این فیشِ واریزیمه", first_name="مشتریِ تست"),
        )

        # هندلر یه تسکِ پس‌زمینه برای تحلیل/فوروارد نداره (مستقیم await می‌شه)، پس
        # نیازی به sleep نیست؛ فقط برای اطمینانِ کامل یه لحظه صبر می‌کنیم
        await asyncio.sleep(0.2)

        assert len(main_session_obj.sent_photos) == 1, (
            f"عکس باید دقیقاً یه‌بار از طریقِ main_bot به فروشگاه‌دار فوروارد بشه، نه {len(main_session_obj.sent_photos)} بار"
        )
        forwarded = main_session_obj.sent_photos[0]
        assert forwarded["chat_id"] == OWNER_TG_ID, "عکس باید به آیدیِ تلگرامِ فروشگاه‌دار فرستاده بشه"
        assert "مشتریِ تست" in forwarded["caption"], "کپشن باید نامِ مشتری رو داشته باشه"
        assert "این فیشِ واریزیمه" in forwarded["caption"], "کپشنِ همراهِ عکسِ مشتری باید توی کپشنِ فوروارد باشه"
        assert "۴۵۰" in forwarded["caption"] or "450" in forwarded["caption"], (
            "نتیجه‌ی تحلیلِ هوشمندِ تصویر باید توی کپشن باشه (این دقیقاً چیزیه که در نسخه‌ی نیمه‌کاره گم شده بود)"
        )

        assert any("دریافت شد" in m["text"] for m in shop_session_obj.sent_messages), "باید یه تاییدِ دریافت به مشتری نشون داده بشه"

        print("✅ test_customer_photo_forwarded_with_analysis PASSED")
    finally:
        ai_service.get_ai_service = original_get_ai_service


async def test_photo_forward_survives_ai_failure(shop_dp, main_bot) -> None:
    """حتی اگه تحلیلِ هوش مصنوعی fail بشه، خودِ عکس باید همچنان فوروارد بشه."""
    await reset_database()
    await seed_usable_shop(OWNER_TG_ID + 1, SHOP_BOT_TG_ID + 1)

    class _FailingAi(_FakeAiServiceForPhoto):
        async def analyze_image(self, prompt, image_bytes, mime_type="image/jpeg"):
            raise ai_service.AiServiceError("قطعیِ آزمایشی")

    fake_ai = _FailingAi()
    original_get_ai_service = ai_service.get_ai_service
    ai_service.get_ai_service = lambda api_key, model, base_url=None, fallback_api_key=None, fallback_model=None, fallback_base_url=None: fake_ai

    try:
        shop_bot_instance = Bot(token=f"{SHOP_BOT_TG_ID + 1}:FAKE", session=FakeSession())
        shop_session_obj: FakeSession = shop_bot_instance.session  # type: ignore[assignment]
        shop_session_obj.set_downloaded_file("incoming_photo_id", PHOTO_BYTES)

        main_session_obj: FakeSession = main_bot.session  # type: ignore[assignment]
        main_session_obj.sent_photos.clear()

        await shop_dp.feed_update(shop_bot_instance, make_message_update(1, user_id=CUSTOMER_TG_ID + 1, photo=True))
        await asyncio.sleep(0.2)

        assert len(main_session_obj.sent_photos) == 1, "حتی با شکستِ تحلیلِ هوشمند، خودِ عکس باید فوروارد بشه"
        print("✅ test_photo_forward_survives_ai_failure PASSED")
    finally:
        ai_service.get_ai_service = original_get_ai_service


async def main() -> None:
    main_dp, shop_dp, bot_manager, main_bot = build_test_dispatchers()
    await test_customer_photo_forwarded_with_analysis(shop_dp, main_bot)
    await test_photo_forward_survives_ai_failure(shop_dp, main_bot)


if __name__ == "__main__":
    asyncio.run(main())
