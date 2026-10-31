"""
تست: P18 · د — سخت‌سازیِ امنیتی.

پوشش:
۱. در `RUN_MODE=webhook` بدونِ `MAIN_BOT_WEBHOOK_SECRET` برنامه بالا نمی‌آید؛ در polling مشکلی نیست.
۲. هشدارِ تلگرامیِ ادمین: شمارشِ پنجره‌یِ لغزان، آستانه، خنک‌شدن، سقفِ ساعتی، و *هرگز* نشتِ راز در متنِ هشدار.
۳. ۴۰۳ مکررِ وب‌هوک شمرده می‌شود (و تا نرسیدن به آستانه پیامی ساخته نمی‌شود).
۴. شناسه‌یِ همبستگی (shop_bot_id / group_ref) در `payment_event_logs` ذخیره می‌شود.
۵. `.gitignore`/`.dockerignore` شاملِ `.env` هستند (نگهبانِ ایستایِ متن).

اجرا: python3 tests_manual/test_p18_security.py
"""
from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness import reset_database  # noqa: E402

from app import main as app_main  # noqa: E402
from app.config import RunMode, settings  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import admin_alert_service as alerts  # noqa: E402
from app.services import payment_event_service  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
FAKE_BOT_TOKEN = "123456789:AAHfakefaketokenvaluefortestingonly"
FAKE_PAN = "4111111111111111"


# ============================================================================= ۱ — رازِ وب‌هوک
async def test_webhook_mode_requires_secret() -> None:
    saved_mode, saved_secret = settings.run_mode, settings.main_bot_webhook_secret
    try:
        settings.run_mode = RunMode.POLLING
        settings.main_bot_webhook_secret = ""
        app_main.validate_runtime_config()  # polling بدونِ راز مشکلی ندارد

        settings.run_mode = RunMode.WEBHOOK
        for empty in ("", "   "):
            settings.main_bot_webhook_secret = empty
            try:
                app_main.validate_runtime_config()
            except RuntimeError as exc:
                assert "MAIN_BOT_WEBHOOK_SECRET" in str(exc), str(exc)
            else:
                raise AssertionError(f"با رازِ {empty!r} در حالتِ webhook نباید برنامه بالا بیاید")

        settings.main_bot_webhook_secret = "یه-رمز-تصادفی-بلند"
        app_main.validate_runtime_config()
    finally:
        settings.run_mode, settings.main_bot_webhook_secret = saved_mode, saved_secret
    print("✅ test_webhook_mode_requires_secret PASSED")


# ============================================================================= ۲ — هشدارِ ادمین
async def test_alert_threshold_cooldown_budget_and_no_secret_leak() -> None:
    alerts.reset()
    assert alerts._enabled is False, "بدونِ install() نباید پیامی ارسال شود"

    detail = f"app.bots.x: پرداخت با توکنِ {FAKE_BOT_TOKEN} و کارتِ {FAKE_PAN} شکست خورد"
    for _ in range(alerts.THRESHOLDS[alerts.KIND_PAYMENT] - 1):
        assert not alerts.record_event(alerts.KIND_PAYMENT, detail), "زیرِ آستانه ⇒ بدونِ هشدار"
    assert alerts.record_event(alerts.KIND_PAYMENT, detail), "رسیدن به آستانه ⇒ هشدار"

    reached = alerts.threshold_reached()
    assert len(reached) == 1, reached
    _key, cleaned, count = reached[0]
    assert count == alerts.THRESHOLDS[alerts.KIND_PAYMENT]
    assert FAKE_BOT_TOKEN not in cleaned and FAKE_PAN not in cleaned, f"راز در هشدار نشت کرد: {cleaned}"
    assert "***" in cleaned, cleaned

    # خنک‌شدن: بلافاصله دوباره هشدار نمی‌رود
    for _ in range(alerts.THRESHOLDS[alerts.KIND_PAYMENT] + 2):
        assert not alerts.record_event(alerts.KIND_PAYMENT, detail), "در بازه‌یِ خنک‌شدن نباید هشدارِ دوم برود"

    # سقفِ ساعتی
    alerts.reset()
    sent = 0
    for index in range(alerts.MAX_ALERTS_PER_HOUR + 5):
        for _ in range(alerts.THRESHOLDS[alerts.KIND_ERROR]):
            if alerts.record_event(alerts.KIND_ERROR, f"خطایِ متمایزِ شماره‌یِ {index}"):
                sent += 1
    assert sent == alerts.MAX_ALERTS_PER_HOUR, f"سقفِ ساعتی باید اعمال شود: {sent}"

    # هندلرِ لاگ: ERROR تکراری شمرده می‌شود، WARNING نه
    alerts.reset()
    handler = alerts.AdminAlertHandler()
    logging.getLogger("app.test.alerts").warning("این نباید شمرده شود")
    for _ in range(alerts.THRESHOLDS[alerts.KIND_ERROR]):
        handler.emit(logging.LogRecord("app.test.alerts", logging.ERROR, __file__, 1, "خطایِ تکراری", (), None))
    assert len(alerts.threshold_reached()) == 1, "ERROR باید شمرده شود"
    alerts.reset()
    for _ in range(alerts.THRESHOLDS[alerts.KIND_ERROR] + 1):
        handler.emit(logging.LogRecord("app.test.alerts", logging.WARNING, __file__, 1, "هشدارِ بی‌ضرر", (), None))
    assert alerts.threshold_reached() == [], "WARNING نباید شمرده شود"
    print("✅ test_alert_threshold_cooldown_budget_and_no_secret_leak PASSED")


async def test_payment_failure_status_counts_as_alert() -> None:
    await reset_database()
    alerts.reset()
    for _ in range(alerts.THRESHOLDS[alerts.KIND_PAYMENT] - 1):
        await payment_event_service.log_event("bale", "out", "createInvoiceLink", status="failed", raw={"a": 1})
    assert alerts.threshold_reached() == [], "یک مانده به آستانه ⇒ بدونِ هشدار"
    await payment_event_service.log_event("bale", "out", "createInvoiceLink", status="failed", raw={"a": 1})
    assert len(alerts.threshold_reached()) == 1, "شکستِ پرداختِ تکراری ⇒ هشدار"

    # وضعیتِ موفق/در انتظار هشدار نمی‌سازد
    alerts.reset()
    for status in ("ok", "success", "pending"):
        for _ in range(alerts.THRESHOLDS[alerts.KIND_PAYMENT] + 1):
            await payment_event_service.log_event("bale", "in", "inquire", status=status, raw=None)
        assert alerts.threshold_reached() == [], f"{status} شکست نیست"
    print("✅ test_payment_failure_status_counts_as_alert PASSED")


# ============================================================================= ۳ — ۴۰۳ وب‌هوک
async def test_forbidden_webhook_is_counted() -> None:
    alerts.reset()
    for _ in range(alerts.THRESHOLDS[alerts.KIND_FORBIDDEN] - 1):
        response = app_main._forbidden("webhook/main: رازِ وب‌هوکِ نامعتبر")
        assert response.status_code == 403
    assert alerts.threshold_reached() == [], "زیرِ آستانه ⇒ بدونِ هشدار"
    assert app_main._forbidden("webhook/main: رازِ وب‌هوکِ نامعتبر").status_code == 403
    reached = alerts.threshold_reached()
    assert len(reached) == 1 and reached[0][0].startswith(alerts.KIND_FORBIDDEN), reached
    alerts.reset()
    print("✅ test_forbidden_webhook_is_counted PASSED")


# ============================================================================= ۴ — شناسه‌یِ همبستگی
async def test_payment_event_log_stores_correlation() -> None:
    await reset_database()
    async with session_scope() as session:
        await payment_event_service.log_event(
            "bale", "in", "successful_payment", reference="tx-1", status="success",
            raw={"invoice_payload": "cartgroup-abc"}, shop_bot_id=77, group_ref="abc",
        )
        await payment_event_service.log_event("zarinpal", "in", "verify:order", reference="A-1", status="ok", raw=None)
    async with session_scope() as session:
        rows = await payment_event_service.recent_events(session, limit=10)
    assert len(rows) == 2
    by_method = {row.method: row for row in rows}
    assert by_method["successful_payment"].shop_bot_id == 77 and by_method["successful_payment"].group_ref == "abc"
    assert by_method["verify:order"].shop_bot_id is None and by_method["verify:order"].group_ref is None
    print("✅ test_payment_event_log_stores_correlation PASSED")


# ============================================================================= ۵ — نگهبانِ ایستایِ رازها
def test_env_is_ignored_by_git_and_docker() -> None:
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")
    for name, content in ((".gitignore", gitignore), (".dockerignore", dockerignore)):
        lines = [line.strip() for line in content.splitlines() if line.strip() and not line.strip().startswith("#")]
        assert ".env" in lines, f"{name} باید .env را نادیده بگیرد"
    # backup_*.sql هم نباید به گیت برود
    assert "backup_*.sql" in gitignore
    print("✅ test_env_is_ignored_by_git_and_docker PASSED")


async def main() -> None:
    await test_webhook_mode_requires_secret()
    await test_alert_threshold_cooldown_budget_and_no_secret_leak()
    await test_payment_failure_status_counts_as_alert()
    await test_forbidden_webhook_is_counted()
    await test_payment_event_log_stores_correlation()
    test_env_is_ignored_by_git_and_docker()


if __name__ == "__main__":
    asyncio.run(main())
