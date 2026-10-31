"""
تست: تلاشِ مجددِ خودکار (retry) و سرویسِ پشتیبانِ هوش مصنوعی (fallback).

اجرا: python3 tests_manual/test_ai_retry_and_fallback.py
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")

from app.services.ai_service import AiCallResult, AiServiceError, FallbackAiService, get_ai_service  # noqa: E402


class _FlakyThenSuccessAiService:
    """اولین N تلاش شکست می‌خوره، بعدش موفق می‌شه — برای تستِ retry."""

    def __init__(self, fail_times: int) -> None:
        self.fail_times = fail_times
        self.call_count = 0

    async def get_reply(self, system_prompt, history, user_message) -> AiCallResult:
        self.call_count += 1
        if self.call_count <= self.fail_times:
            raise AiServiceError("خطای موقتیِ شبیه‌سازی‌شده")
        return AiCallResult(text="پاسخِ موفق", total_tokens=42)

    async def analyze_image(self, prompt, image_bytes, mime_type="image/jpeg"):
        raise NotImplementedError

    async def transcribe_audio(self, audio_bytes, filename="voice.ogg"):
        raise NotImplementedError


class _AlwaysFailAiService:
    def __init__(self) -> None:
        self.call_count = 0

    async def get_reply(self, system_prompt, history, user_message) -> AiCallResult:
        self.call_count += 1
        raise AiServiceError("همیشه شکست می‌خوره")

    async def analyze_image(self, prompt, image_bytes, mime_type="image/jpeg"):
        raise NotImplementedError

    async def transcribe_audio(self, audio_bytes, filename="voice.ogg"):
        raise NotImplementedError


class _AlwaysSucceedAiService:
    def __init__(self) -> None:
        self.call_count = 0

    async def get_reply(self, system_prompt, history, user_message) -> AiCallResult:
        self.call_count += 1
        return AiCallResult(text="پاسخِ سرویسِ پشتیبان", total_tokens=10)

    async def analyze_image(self, prompt, image_bytes, mime_type="image/jpeg"):
        raise NotImplementedError

    async def transcribe_audio(self, audio_bytes, filename="voice.ogg"):
        raise NotImplementedError


async def test_fallback_used_when_primary_fails() -> None:
    primary = _AlwaysFailAiService()
    fallback = _AlwaysSucceedAiService()
    wrapper = FallbackAiService(primary, fallback)

    result = await wrapper.get_reply("system", [], "سلام")
    assert result.text == "پاسخِ سرویسِ پشتیبان"
    assert primary.call_count == 1
    assert fallback.call_count == 1

    print("✅ test_fallback_used_when_primary_fails PASSED")


async def test_no_fallback_configured_raises_directly() -> None:
    ai = get_ai_service("fake-key", "fake-model", "https://example.com/v1/chat/completions")
    assert not isinstance(ai, FallbackAiService), "بدونِ تنظیمِ fallback نباید FallbackAiService ساخته بشه"

    print("✅ test_no_fallback_configured_raises_directly PASSED")


async def test_fallback_configured_wraps_service() -> None:
    ai = get_ai_service(
        "fake-key", "fake-model", "https://example.com/v1/chat/completions", "fallback-key", "fallback-model", None
    )
    assert isinstance(ai, FallbackAiService), "با تنظیمِ fallback باید FallbackAiService ساخته بشه"

    print("✅ test_fallback_configured_wraps_service PASSED")


async def test_both_primary_and_fallback_fail_raises() -> None:
    primary = _AlwaysFailAiService()
    fallback = _AlwaysFailAiService()
    wrapper = FallbackAiService(primary, fallback)

    try:
        await wrapper.get_reply("system", [], "سلام")
        assert False, "باید خطا پرتاب بشه"
    except AiServiceError:
        pass

    assert primary.call_count == 1
    assert fallback.call_count == 1

    print("✅ test_both_primary_and_fallback_fail_raises PASSED")


async def test_retry_recovers_from_transient_http_error() -> None:
    """
    Mock می‌کنه که سرویسِ هوش مصنوعی بارِ اول با خطای موقتیِ ۵۰۰ جواب بده و
    بارِ دوم موفق بشه — باید _post_chat بدونِ نیاز به دخالتِ لایه‌ی بالاتر
    (fallback) خودش دوباره امتحان کنه و موفق بشه.
    """
    import app.services.ai_service as ai_service_module
    from app.services.ai_service import OpenAiCompatibleAiService

    call_count = {"n": 0}

    class _FakeResponse:
        def __init__(self, status: int, json_data: dict) -> None:
            self.status = status
            self._json_data = json_data

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def text(self):
            return "خطای موقتیِ شبیه‌سازی‌شده"

        async def json(self):
            return self._json_data

    class _FakeSession:
        def post(self, url, headers=None, json=None, data=None):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return _FakeResponse(500, {})
            return _FakeResponse(200, {"choices": [{"message": {"content": "جواب بعدِ تلاشِ دوم"}}], "usage": {"total_tokens": 7}})

    original_get_session = ai_service_module._get_http_session
    ai_service_module._get_http_session = lambda: _FakeSession()
    original_sleep = asyncio.sleep
    asyncio.sleep = lambda _seconds: original_sleep(0)  # تست رو کند نکنیم
    try:
        service = OpenAiCompatibleAiService("fake-key", "fake-model", "https://example.com/v1/chat/completions")
        result = await service.get_reply("system", [], "سلام")
        assert result.text == "جواب بعدِ تلاشِ دوم"
        assert call_count["n"] == 2, "باید دقیقاً یه‌بار دوباره تلاش کنه"
    finally:
        ai_service_module._get_http_session = original_get_session
        asyncio.sleep = original_sleep

    print("✅ test_retry_recovers_from_transient_http_error PASSED")


async def main() -> None:
    await test_fallback_used_when_primary_fails()
    await test_no_fallback_configured_raises_directly()
    await test_fallback_configured_wraps_service()
    await test_both_primary_and_fallback_fail_raises()
    await test_retry_recovers_from_transient_http_error()


if __name__ == "__main__":
    asyncio.run(main())
