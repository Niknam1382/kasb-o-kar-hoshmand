"""
تست: P37 — چهار بهینه‌سازی/رفعِ باگِ کم‌ریسکِ داخلِ همین کد

پوشش:
۱. نشتِ توکن به لاگ و به پیامِ ادمین (یافتهٔ بازرسیِ امنیتی): آدرسِ بله توکنِ ربات را در خودش
   دارد و متنِ خطاهایِ aiohttp آن آدرس را چاپ می‌کند ⇒ حالا هر پیامِ خطا از `sanitize` عبور
   می‌کند و الگویِ `/bot<token>/` هم صریح ماسک می‌شود.
۲. پاسخِ غیرJSON (صفحهٔ ۵۰۰ِ HTML) دیگر `ContentTypeError` با آدرسِ توکندار نمی‌سازد، چون
   وضعیت/نوعِ محتوا پیش ازِ `resp.json()` بررسی می‌شود.
۳. کشِ `photo_shop_file_id` پلتفرم‌مبنا شد: file_idِ بله برایِ تلگرام استفاده نمی‌شود و برعکس؛
   ردیف‌هایِ قدیمیِ دونسخه‌ای «تلگرام» خوانده می‌شوند.
۴. `apply_discount` با `Decimal`: مرزِ «۲٫۹٪ از ۱۰۰٬۰۰۰» که با float یکِ تومان اشتباه می‌داد.
۵. SSRFِ آدرسِ سرویس AI: شکل‌هایِ مبدّلِ همان آدرسِ داخلی (`2130706433`، `0177.0.0.1`،
   `0x7f.0.0.1`، `127.1`، IPv6ِ کاملِ لوپ‌بک) رد می‌شوند و میزبانِ بیرونی پذیرفته می‌شود.
۶. باگِ «ساعتِ بوت»: `time.monotonic()` از بوتِ ماشین می‌شمارد، پس مقایسه با ۰.۰ باعث می‌شد
   اولین هشدارِ ادمین (هر نوع) تا ۳۰ دقیقه و اولین همسنجیِ دفتر تا یک ساعتِ اول بعد ازِ بوت
   خاموش بماند. هر دو با «هنوز ارسال/اجرا نشده = None» رفع شدند و با ساعتِ ۹ و ۱۲ ثانیه سنجیده‌اند.

اجرا: python3 tests_manual/run_one.py test_p37_hardening.py
"""
from __future__ import annotations

import asyncio
import sys
from decimal import Decimal
from types import SimpleNamespace

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from harness import reset_database  # noqa: E402

from app.bots.main_bot.handlers import admin as admin_handlers  # noqa: E402
from app.database.models import DiscountType  # noqa: E402
from app.services import (  # noqa: E402
    admin_alert_service,
    bale_service,
    discount_service,
    payment_event_service,
    platform_service,
    product_photo_service,
    scheduler,
    wallet_service,
)

FAKE_TOKEN = "924123:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdef"
LEAKY = f"Cannot connect to host tapi.bale.ai:443 ssl:default [Connect call failed] url='https://tapi.bale.ai/bot{FAKE_TOKEN}/getUpdates'"


# ============================================================================= ۱ — ماسکِ توکن در مسیرِ خطا
def test_sanitizer_masks_bot_url() -> None:
    out = payment_event_service.sanitize({"error": LEAKY})
    assert FAKE_TOKEN not in out, out
    assert "/bot***/" in out, out
    # الگوهایِ قدیمی هم همچنان ماسک می‌شوند (شمارهٔ کارت و توکنِ خارج از URL)
    mixed = payment_event_service.sanitize("token 123456:abcdefghijklmnopqrstuv و کارت 6104331234567890")
    assert "abcdefghijklmnopqrstuv" not in mixed and "6104331234567890" not in mixed, mixed
    print("✅ test_sanitizer_masks_bot_url PASSED")


async def test_call_never_raises_token_bearing_message() -> None:
    """جایِ `_http`: هر تماسی با بله خطایِ شبکه‌ایِ «توکندار» می‌دهد ⇒ پیامِ BaleError باید ماسک باشد."""
    await reset_database()

    class _Boom:
        def post(self, url, json=None, timeout=None):
            class _Ctx:
                async def __aenter__(self):
                    raise RuntimeError(LEAKY)

                async def __aexit__(self, *exc):
                    return False

            return _Ctx()

    async def fake_http(timeout=None):
        return _Boom()

    real = bale_service._http
    bale_service._http = fake_http
    try:
        raised = None
        try:
            await bale_service._call(FAKE_TOKEN, "getUpdates", {})
        except bale_service.BaleError as exc:
            raised = str(exc)
        assert raised is not None, "خطایِ شبکه باید به BaleError تبدیل می‌شد"
        assert FAKE_TOKEN not in raised, raised
        assert "/bot***/" in raised, raised
    finally:
        bale_service._http = real
    print("✅ test_call_never_raises_token_bearing_message PASSED")


# ============================================================================= ۲ — پاسخِ غیرJSON
async def test_read_json_rejects_html_without_leaking() -> None:
    body = f"<html>500 Bad Gateway — backend https://tapi.bale.ai/bot{FAKE_TOKEN}/sendMessage</html>"

    class _HtmlResp:
        status = 500
        content_type = "text/html; charset=utf-8"

        async def text(self):
            return body

    raised = None
    try:
        await bale_service._read_json(_HtmlResp(), "sendMessage")
    except bale_service.BaleError as exc:
        raised = str(exc)
    assert raised is not None and FAKE_TOKEN not in raised, raised
    assert "HTTP 500" in raised, raised

    payload = {"ok": True, "result": [{"id": 1}]}

    class _JsonResp:
        status = 200
        content_type = "application/json"

        async def json(self):
            return payload

    data = await bale_service._read_json(_JsonResp(), "getUpdates")
    assert data == payload, data
    print("✅ test_read_json_rejects_html_without_leaking PASSED")


# ============================================================================= ۳ — کشِ پلتفرم‌مبنایِ عکس
def test_photo_cache_is_platform_scoped() -> None:
    product = SimpleNamespace(photo_file_id="main_photo_1", photo_shop_file_id=None)
    tag = product_photo_service.source_tag("main_photo_1")

    assert product_photo_service.cached_shop_file_id(product, platform_service.TELEGRAM) is None

    # ردیفِ قدیمیِ دونسخه‌ای ⇒ تلگرام خوانده می‌شود
    product.photo_shop_file_id = f"{tag}|legacy-shop-id"
    assert product_photo_service.cached_shop_file_id(product, platform_service.TELEGRAM) == "legacy-shop-id"
    assert product_photo_service.cached_shop_file_id(product, platform_service.BALE) is None, (
        "file_idِ تلگرام نباید به رباتِ بله داده شود"
    )

    # کشِ سه‌بخشیِ تازه
    product.photo_shop_file_id = f"{tag}|bale|bale-shop-id"
    assert product_photo_service.cached_shop_file_id(product, platform_service.BALE) == "bale-shop-id"
    assert product_photo_service.cached_shop_file_id(product, platform_service.TELEGRAM) is None, (
        "file_idِ بله نباید به رباتِ تلگرام داده شود"
    )
    # خوانشِ سازگارِ قدیمی (بی‌پلتفرم) همچنان کار می‌کند
    assert product_photo_service.cached_shop_file_id(product) == "bale-shop-id"

    # عوض‌شدنِ عکس ⇒ هر دو کش باطل
    product.photo_file_id = "main_photo_2"
    assert product_photo_service.cached_shop_file_id(product, platform_service.BALE) is None
    assert product_photo_service.cached_shop_file_id(product, platform_service.TELEGRAM) is None
    print("✅ test_photo_cache_is_platform_scoped PASSED")


# ============================================================================= ۴ — تخفیفِ درصدی با Decimal
def test_discount_uses_decimal_not_float() -> None:
    percent = SimpleNamespace(type=DiscountType.PERCENT, value=Decimal("2.90"))
    # با float: 100000*2.9 = 289999.99999999994 → int → 2899 → مبلغِ نهایی ۹۷٬۱۰۱ (یکِ تومان گران‌تر)
    assert discount_service.apply_discount(100_000, percent) == 97_100, discount_service.apply_discount(100_000, percent)

    twelve = SimpleNamespace(type=DiscountType.PERCENT, value=Decimal("12.50"))
    assert discount_service.apply_discount(100_000, twelve) == 87_500
    fixed = SimpleNamespace(type=DiscountType.FIXED, value=Decimal("1500.50"))
    assert discount_service.apply_discount(10_000, fixed) == 8_500, "کسرِ مبلغِ ثابت هم با Decimal و رو‌به‌پایین"
    zero = SimpleNamespace(type=DiscountType.PERCENT, value=Decimal("0"))
    assert discount_service.apply_discount(10_000, zero) == 10_000
    huge = SimpleNamespace(type=DiscountType.PERCENT, value=Decimal("150"))
    assert discount_service.apply_discount(10_000, huge) == 0, "تخفیفِ بیشتر ازِ مبلغ ⇒ صفر، نه منفی"
    print("✅ test_discount_uses_decimal_not_float PASSED")


# ============================================================================= ۵ — SSRF با شکل‌هایِ مبدّلِ آدرس
def test_internal_host_forms_are_rejected() -> None:
    blocked = [
        "http://api.example.test/v1",      # httpِ خالص
        "https://127.0.0.1:11434/v1",      # دایرکت
        "https://169.254.169.254/latest",  # متادیتایِ ابر
        "https://2130706433/v1",           # همان ۱۲۷.۰.۰.۱ به دسیمال
        "https://0x7f.0.0.1/v1",           # هگز
        "https://0177.0.0.1/v1",           # octal
        "https://127.1/v1",                # کوتاه‌شده
        "https://[0:0:0:0:0:0:0:1]/v1",    # IPv6 لوپ‌بکِ کامل
        "https://10.255.255.1/v1",
        "https://172.31.0.9/v1",
        "https://0.0.0.0/v1",
    ]
    for bad in blocked:
        assert admin_handlers._url_value_error(bad) is not None, bad
    for good in ("https://api.example.test/v1", "https://api.openai.com/v1", "https://tapi.bale.ai/bot"):
        assert admin_handlers._url_value_error(good) is None, good
    print("✅ test_internal_host_forms_are_rejected PASSED")


# ============================================================================= ۶ — باگِ ساعتِ بوت (هشدار و همسنجی)
async def test_boot_clock_does_not_suppress_the_first_alert() -> None:
    """`time.monotonic()` رویِ لینوکس از بوتِ ماشین می‌شمارد.

    مقایسه با ۰.۰ یعنی «آخرین هشدار در مبدأ زمان زده شده» ⇒ رویِ سرور/کانتینرِ تازه‌بوت‌شده
    اولین هشدارِ هر نوع تا `ALERT_COOLDOWN_SECONDS` (سی دقیقه) خاموش می‌ماند. تست با ساعتِ ۱۲ ثانیه
    همان وضعیتِ بوت را بازسازی می‌کند.
    """
    real_module = admin_alert_service.time
    admin_alert_service.time = SimpleNamespace(monotonic=lambda: 12.0)  # type: ignore[assignment]
    try:
        admin_alert_service.reset()
        detail = "یکِ خطایِ آزمونِ payment"
        threshold = admin_alert_service.THRESHOLDS[admin_alert_service.KIND_PAYMENT]
        results = [admin_alert_service.record_event(admin_alert_service.KIND_PAYMENT, detail) for _ in range(threshold)]
        assert results[: threshold - 1] == [False] * (threshold - 1), results
        assert results[-1] is True, f"اولین هشدار رویِ ساعتِ تازه‌بوت‌شده نباید خاموش شود: {results}"

        # و خنک‌شدنِ واقعی همچنان کار می‌کند: همان کلید در ثانیه‌های بعد دوباره ارسال نمی‌کند
        clock = {"now": 20.0}
        admin_alert_service.time = SimpleNamespace(monotonic=lambda: clock["now"])  # type: ignore[assignment]
        assert admin_alert_service.record_event(admin_alert_service.KIND_PAYMENT, detail) is False
    finally:
        admin_alert_service.time = real_module  # type: ignore[assignment]
        admin_alert_service.reset()
    print("✅ test_boot_clock_does_not_suppress_the_first_alert PASSED")


async def test_reconcile_runs_on_the_first_tick_after_boot() -> None:
    """همسنجیِ دفتر (نگهبانِ اختلافِ حسابداری) هم نباید به «ساعتِ بوت» گرو بماند."""
    real_module = scheduler.time
    real_reconcile = wallet_service.reconcile_balances
    scheduler.time = SimpleNamespace(monotonic=lambda: 9.0)  # type: ignore[assignment]
    wallet_service.reconcile_balances = lambda session: _one_gap(session)  # type: ignore[assignment]
    try:
        scheduler.reset_reconcile_clock_for_tests()
        assert await scheduler.reconcile_wallet_ledgers() == 1, "اولین دور بعد ازِ بوت باید اجرا شود"
        assert await scheduler.reconcile_wallet_ledgers() == 0, "دورِ دوم در همان ساعت مجاز نیست"
    finally:
        scheduler.time = real_module  # type: ignore[assignment]
        wallet_service.reconcile_balances = real_reconcile  # type: ignore[assignment]
        scheduler.reset_reconcile_clock_for_tests()
    print("✅ test_reconcile_runs_on_the_first_tick_after_boot PASSED")


async def _one_gap(session):
    return [{"owner_id": 7, "cached_toman": 999, "ledger_toman": 100_000, "lots_toman": 100_000, "ledger_delta_toman": 99_001}]


async def main() -> None:
    test_sanitizer_masks_bot_url()
    await test_call_never_raises_token_bearing_message()
    await test_read_json_rejects_html_without_leaking()
    test_photo_cache_is_platform_scoped()
    test_discount_uses_decimal_not_float()
    test_internal_host_forms_are_rejected()
    await test_boot_clock_does_not_suppress_the_first_alert()
    await test_reconcile_runs_on_the_first_tick_after_boot()


if __name__ == "__main__":
    asyncio.run(main())
