"""
تست: P1-S5a (بخشِ اجراشده) — پایه‌یِ پرداختِ بله: آدرسِ پایه‌یِ قابل‌تنظیم (B1)، بدونِ currency و با clampِ طول (B2)،
وضعیتِ «succeed» موفق + کنترلِ مبلغ (B3)، toman_to_rial (B4)، رازِ وب‌هوک در مسیر (B5)،
ردِ رویدادهایِ پرداخت (B12) و دکمه‌هایِ ادمین «🧪 آزمایشِ بله‌پی» / «🔎 آخرین رویدادهایِ پرداخت» (B13).

اجرا: python3 tests_manual/test_bale_payment_foundation.py
"""
from __future__ import annotations

import asyncio
import sys
import types

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from sqlalchemy import select  # noqa: E402

from harness import build_test_dispatchers, reset_database  # noqa: E402
from phase4_helpers import Chat  # noqa: E402

from app import main as app_main  # noqa: E402
from app.bots.main_bot import texts  # noqa: E402
from app.config import settings  # noqa: E402
from app.database.models import PaymentEventLog  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import bale_service, payment_event_service  # noqa: E402
from app.services.admin_settings_service import get_admin_settings  # noqa: E402

ADMIN_TG_ID = 12345


async def _events() -> list[PaymentEventLog]:
    async with session_scope() as session:
        return list((await session.execute(select(PaymentEventLog).order_by(PaymentEventLog.id))).scalars().all())


# =============================================================================
# B1–B4 — منطقِ خالص
# =============================================================================
async def test_bale_pure_helpers_and_invoice_body() -> None:
    assert bale_service.toman_to_rial(1500) == 15000 and bale_service.toman_to_rial("20") == 200

    original_base = settings.bale_api_base
    try:
        assert settings.bale_api_base == "https://tapi.bale.ai", "B1: پیش‌فرضِ مستندات"
        assert bale_service._api_url("T0KEN", "getMe") == "https://tapi.bale.ai/botT0KEN/getMe"
        settings.bale_api_base = "https://example.test/"
        assert bale_service._api_url("T", "m") == "https://example.test/botT/m", "از تنظیمات خونده می‌شه، اسلشِ آخر نادیده"
    finally:
        settings.bale_api_base = original_base

    classify = bale_service.classify_transaction_status
    for ok in ("succeed", "Successful", " success ", "paid", "OK"):
        assert classify({"status": ok}) == "success", ok
    assert classify({"status": "pending"}) == "pending"
    for bad in ("failed", "rejected", "timeout"):
        assert classify({"status": bad}) == "failed", bad
    assert classify({"status": "weird"}) == "unknown" and classify({}) == "unknown" and classify(None) == "unknown"

    verify = bale_service.verify_transaction_amount
    assert verify({"amount": 15000}, 15000) is True and verify({"amount": "15000"}, 15000) is True
    assert verify({"amount": 14000}, 15000) is False and verify({"amount": "x"}, 1) is False
    assert verify({}, 15000) is None and verify(None, 1) is None, "مبلغ برنگشت = قابلِ راستی‌آزمایی نیست"

    sent: dict = {}

    async def fake_call(bot_token: str, method: str, payload: dict):
        sent.update(method=method, payload=payload)
        return "https://pay.test/abc"

    original_call = bale_service._call
    bale_service._call = fake_call
    try:
        link = await bale_service.create_invoice_link("BT", "PT", "ع" * 50, "د" * 400, "pay-1", 15000)
        body = sent["payload"]
        assert link == "https://pay.test/abc" and sent["method"] == "createInvoiceLink"
        assert "currency" not in body, "B2: فیلدِ currency حذف شد"
        assert len(body["title"]) == 32 and len(body["description"]) == 255 and body["prices"] == [{"label": body["title"], "amount": 15000}]

        await bale_service.create_invoice_link("BT", "PT", "", "", "pay-2", 10000)
        assert sent["payload"]["title"] == "پرداخت" and sent["payload"]["description"] == "پرداخت", "عنوانِ خالی جایگزین می‌شه"

        for bad_payload in ("", "x" * 129, "ع" * 65):  # ۶۵ حرفِ فارسی = ۱۳۰ بایت
            try:
                await bale_service.create_invoice_link("BT", "PT", "t", "d", bad_payload, 10000)
            except bale_service.BaleError:
                pass
            else:
                raise AssertionError(f"payloadِ نامعتبر باید رد بشه: {bad_payload!r}")
        for bad_amount in (0, -5):
            try:
                await bale_service.create_invoice_link("BT", "PT", "t", "d", "ok", bad_amount)
            except bale_service.BaleError:
                pass
            else:
                raise AssertionError("مبلغِ غیرمثبت باید رد بشه")
    finally:
        bale_service._call = original_call

    print("✅ test_bale_pure_helpers_and_invoice_body PASSED")


# =============================================================================
# B12 — ردِ رویدادها
# =============================================================================
async def test_payment_event_log_sanitizes_and_persists() -> None:
    await reset_database()
    text = payment_event_service.sanitize(
        {"provider_token": "SECRET123", "token": "t", "card": "6037991234567890", "url": "https://x/bot123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw/getMe",
         "nested": {"merchant_id": "m", "ok": 1}}
    )
    for leaked in ("SECRET123", "6037991234567890", "123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw", '"m"'):
        assert leaked not in text, f"نشت: {leaked}"
    assert '"ok": 1' in text and len(payment_event_service.sanitize("ع" * 10_000)) <= payment_event_service.MAX_RAW_LENGTH

    await payment_event_service.log_event("bale", "out", "createInvoiceLink", reference="p-1", status="ok", raw={"provider_token": "S", "x": 1})
    await payment_event_service.log_event("bale", "in", "successful_payment", reference="tx-9", status="success", raw="plain")
    events = await _events()
    assert [(e.provider, e.direction, e.method, e.status) for e in events] == [
        ("bale", "out", "createInvoiceLink", "ok"), ("bale", "in", "successful_payment", "success")
    ]
    assert '"provider_token": "***"' in events[0].raw and '"x": 1' in events[0].raw
    async with session_scope() as session:
        recent = await payment_event_service.recent_events(session, limit=1)
    assert recent[0].method == "successful_payment", "جدیدترین اول"
    print("✅ test_payment_event_log_sanitizes_and_persists PASSED")


async def test_outcome_guard_and_event_trail() -> None:
    await reset_database()
    ok = app_main._bale_outcome_ok
    assert await ok({"status": "succeed", "amount": 15000}, 1500, "t") is True, "succeed + مبلغِ درست"
    assert await ok({"status": "succeed"}, 1500, "t") is True, "مبلغ برنگشته: رد نمی‌شه"
    assert await ok({"status": "pending", "amount": 15000}, 1500, "t") is False
    assert await ok({"status": "failed"}, 1500, "t") is False
    assert await ok({"status": "succeed", "amount": 1000}, 1500, "t") is False, "مبلغِ نامنطبق اعتبار نمی‌ده"
    assert await ok({"status": "succeed", "amount": 15000}, None, "t") is True
    events = await _events()
    assert len(events) == 6 and all(e.method == "inquire_result:t" for e in events)
    assert [e.status for e in events] == ["success", "success", "pending", "failed", "success", "success"]
    print("✅ test_outcome_guard_and_event_trail PASSED")


# =============================================================================
# B5 — رازِ وب‌هوک در مسیر
# =============================================================================
async def test_webhook_secret_in_path() -> None:
    def request(headers: dict | None = None):
        async def _json():
            return {}

        return types.SimpleNamespace(headers=headers or {}, json=_json)

    saved = (settings.bale_bot_token, settings.bale_webhook_secret)
    try:
        settings.bale_bot_token = ""
        assert (await app_main.webhook_bale_with_secret("s3cret", request())).status_code == 404, "بدونِ توکن: غیرفعال"
        settings.bale_bot_token, settings.bale_webhook_secret = "tok", "s3cret"
        assert (await app_main.webhook_bale_with_secret("s3cret", request())).status_code == 200, "رازِ درست در مسیر"
        assert (await app_main.webhook_bale_with_secret("wrong", request())).status_code == 403
        assert (await app_main.webhook_bale(request())).status_code == 403, "مسیرِ قدیمی بدونِ هدر رد"
        assert (await app_main.webhook_bale(request({"X-Telegram-Bot-Api-Secret-Token": "s3cret"}))).status_code == 200, "مسیرِ قدیمی با هدرِ درست هنوز کار می‌کنه"
        settings.bale_webhook_secret = ""
        assert (await app_main.webhook_bale_with_secret("anything", request())).status_code == 403, "رازِ تنظیم‌نشده ← مسیرِ دارایِ راز هیچ‌وقت باز نیست"
        assert (await app_main.webhook_bale(request())).status_code == 200
    finally:
        settings.bale_bot_token, settings.bale_webhook_secret = saved
    print("✅ test_webhook_secret_in_path PASSED")


# =============================================================================
# B13 — دکمه‌هایِ ادمین
# =============================================================================
async def test_admin_selftest_and_events_buttons(main_dp) -> None:
    await reset_database()
    admin = Chat(main_dp, ADMIN_TG_ID)

    await admin.tap("admin_payment_events")
    assert admin.last_text == texts.PAYMENT_EVENTS_EMPTY

    saved_token, original_call = settings.bale_bot_token, bale_service._call
    try:
        settings.bale_bot_token = ""
        await admin.tap("admin_bale_selftest")
        # A1(د): بدونِ توکن، خودتشخیصی هر پیش‌نیاز را جدا و با راهنمایِ عملی نشان می‌دهد و به شبکه نمی‌رود.
        report = admin.last_text
        assert "❌ توکنِ رباتِ بله" in report, report
        assert "🔑 تنظیمات کلیدها" in report, "پیامِ خطا باید عملی باشد و مسیرِ پنل را نشان دهد"
        assert "getMe" not in report, "بدونِ توکن نباید مرحله‌یِ شبکه‌ای اجرا شود"

        settings.bale_bot_token = "123:TEST"

        async def fake_call(token: str, method: str, payload: dict):
            if method == "getMe":
                return {"username": "pay_bot"}
            if method == "getWebhookInfo":
                return {"url": "https://example.test/webhook/bale/xyz"}
            raise bale_service.BaleError("درخواستِ createInvoiceLink به بله ناموفق بود: invalid provider")

        bale_service._call = fake_call
        async with session_scope() as session:
            (await get_admin_settings(session)).bale_provider_token = "PROV-TOKEN"
        await admin.tap("admin_bale_selftest")
        report = admin.last_text
        assert "✅ getMe" in report and "@pay_bot" in report and "✅ getWebhookInfo" in report
        assert "❌ createInvoiceLink" in report and "invalid provider" in report and "PROV-TOKEN" not in report, "خطایِ مرحله‌یِ سوم + توکن نشت نکنه"

        async def ok_call(token: str, method: str, payload: dict):
            return {"username": "pay_bot"} if method == "getMe" else ({"url": ""} if method == "getWebhookInfo" else "https://pay.test/l")

        bale_service._call = ok_call
        await admin.tap("admin_bale_selftest")
        assert "❌" not in admin.last_text and "همه‌یِ مرحله‌ها درسته" in admin.last_text
    finally:
        settings.bale_bot_token, bale_service._call = saved_token, original_call

    await payment_event_service.log_event("bale", "in", "successful_payment", reference="tx-1", status="success", raw={"a": 1})
    await admin.tap("admin_payment_events")
    assert "bale/in" in admin.last_text and "successful_payment" in admin.last_text and "ref=tx-1" in admin.last_text
    print("✅ test_admin_selftest_and_events_buttons PASSED")


async def main() -> None:
    main_dp, _shop_dp, _bot_manager, _main_bot = build_test_dispatchers()
    await test_bale_pure_helpers_and_invoice_body()
    await test_payment_event_log_sanitizes_and_persists()
    await test_outcome_guard_and_event_trail()
    await test_webhook_secret_in_path()
    await test_admin_selftest_and_events_buttons(main_dp)


if __name__ == "__main__":
    asyncio.run(main())
