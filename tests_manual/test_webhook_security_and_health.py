"""
تست: امنیتِ وب‌هوکِ ربات اصلی (webhook_secret_token) و اندپوینتِ /health
(فازِ ۱ - بازیابی، مسترپرامپتِ جدید).

اجرا: python3 tests_manual/test_webhook_security_and_health.py
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from harness import reset_database  # noqa: E402

from app import main as app_main  # noqa: E402
from app.config import settings  # noqa: E402


def test_no_secret_configured_allows_any_value() -> None:
    """اگه ادمین هنوز main_bot_webhook_secret رو ست نکرده، رفتارِ قبلی (بدونِ چک) حفظ می‌شه."""
    original = settings.main_bot_webhook_secret
    settings.main_bot_webhook_secret = ""
    try:
        assert app_main._is_valid_webhook_secret(None) is True
        assert app_main._is_valid_webhook_secret("هرچیزیِ دیگه") is True
    finally:
        settings.main_bot_webhook_secret = original
    print("✅ test_no_secret_configured_allows_any_value PASSED")


def test_secret_configured_requires_exact_match() -> None:
    original = settings.main_bot_webhook_secret
    settings.main_bot_webhook_secret = "یه-رمز-تصادفیِ-بلند"
    try:
        assert app_main._is_valid_webhook_secret("یه-رمز-تصادفیِ-بلند") is True
        assert app_main._is_valid_webhook_secret("رمزِ-اشتباه") is False
        assert app_main._is_valid_webhook_secret(None) is False, "بدونِ هدر هم نباید رد بشه"
    finally:
        settings.main_bot_webhook_secret = original
    print("✅ test_secret_configured_requires_exact_match PASSED")


async def test_health_check_reports_ok_when_db_and_bot_are_up() -> None:
    await reset_database()
    original_state = dict(app_main._state)
    app_main._state["main_bot"] = object()  # فقط برای شبیه‌سازیِ "بات مقداردهی شده"
    try:
        response = await app_main.health_check()
        assert response.status_code == 200, "با دیتابیسِ سالم و باتِ مقداردهی‌شده باید ۲۰۰ برگردونه"
    finally:
        app_main._state.clear()
        app_main._state.update(original_state)
    print("✅ test_health_check_reports_ok_when_db_and_bot_are_up PASSED")


async def test_health_check_reports_unhealthy_when_bot_not_initialized() -> None:
    await reset_database()
    original_state = dict(app_main._state)
    app_main._state.pop("main_bot", None)
    try:
        response = await app_main.health_check()
        assert response.status_code == 503, "اگه bot هنوز مقداردهی نشده باید ۵۰۳ برگردونه"
    finally:
        app_main._state.clear()
        app_main._state.update(original_state)
    print("✅ test_health_check_reports_unhealthy_when_bot_not_initialized PASSED")


async def async_main() -> None:
    await test_health_check_reports_ok_when_db_and_bot_are_up()
    await test_health_check_reports_unhealthy_when_bot_not_initialized()


def main() -> None:
    test_no_secret_configured_allows_any_value()
    test_secret_configured_requires_exact_match()
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
