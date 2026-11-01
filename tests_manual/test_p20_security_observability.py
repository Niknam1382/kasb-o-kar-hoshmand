"""
تست: P20-C — امنیت و قابلیتِ مشاهده (رفعِ بلاکرهایِ B1/B2/B3)

پوشش:
۱. scrubber: توکنِ ربات، کلیدِ `sk-…`، رمزِ Fernet، JWT و شمارهٔ موبایل از متنِ لاگ پاک می‌شوند؛
   متنِ فارسیِ معمولی و شناسه‌هایِ غیرحساس دست‌نخورده می‌مانند.
۲. `install()` واقعاً فیلتر را رویِ handler می‌نشاند (نمونه با یک StringIO handler).
۳. سقفِ نرخِ HTTP: پنجرهٔ یک‌دقیقه‌ای، ردِّ بعد از سقف، بازگشتِ ظرفیت بعد از پنجره، و خاموش با ۰.
۴. `/metrics`: بدونِ راز ⇒ ۴۰۴؛ رازِ غلط ⇒ ۴۰۳ (بدونِ هشدارِ مکرر به ادمین)؛ رازِ درست ⇒ شمارنده‌ها.
۵. correlation-id: در هر دو قالب (متنِ ساده و JSON) در خطِ لاگ می‌آید و هیچ رازی رد نمی‌شود.
۶. زنجیرهٔ هشِ ممیزی: هر ردیف، هشِ ردیفِ قبلی را می‌گیرد و تغییرِ محتوای یک ردیفِ قدیمی
   با همان تابع قابلِ کشف است (پیش ازِ نوشتنِ «سالم» هیچ prev_hash‌ای نبود).
۷. رازِ وب‌هوکِ هر رباتِ فروشگاهی: در دیتابیس رمز است، در حافظه/plaintext خوانده می‌شود، و
   بازنویسیِ یک‌بارهٔ بوت‌آپ ردیف‌هایِ قدیمیِ خام را رمز می‌کند (ایدِمپوتنت).

اجرا: python3 tests_manual/test_p20_security_observability.py
"""
from __future__ import annotations

import asyncio
import io
import json
import logging
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from sqlalchemy import select, text as sql_text  # noqa: E402

from harness import reset_database  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from app import observability  # noqa: E402
from app.database.models import AuditEventType, AuditLogEntry  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.main import _too_many_requests, metrics_endpoint  # noqa: E402
from app.services import http_guard, shop_bot_service  # noqa: E402
from app.utils.encryption import decrypt_token, looks_encrypted  # noqa: E402

OWNER_TG_ID = 999_711
SHOP_BOT_TG_ID = 999_712
FAKE_BOT_TOKEN = "123456789:AAFAKE_FAKE-fake_FAKEfakeFAKE123"
FAKE_API_KEY = "sk-proj-abcdefghijklmnopqrstuvwxyz123456"
FAKER_FERNET = "gAAAAA" + "B" * 60
FAKE_JWT = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abcdefghijklmnopqrstuvwxy"
FAKE_PHONE = "09121234567"


# ============================================================================= ۱ و ۲ — پاک‌سازیِ لاگ
def test_scrubber_masks_every_secret_shape() -> None:
    clean = "سفارشِ ۱۲۳۴ با مبلغِ ۵۰۰٬۰۰۰ تومان ثبت شد (shop_bot=7)"
    assert observability.scrub(clean) == clean, "متنِ عادی نباید تغییر کند"

    for secret in (FAKE_BOT_TOKEN, FAKE_API_KEY, FAKER_FERNET, FAKE_JWT):
        masked = observability.scrub(f"خطا در فراخوانی: {secret}")
        assert secret not in masked, secret[:12]
        assert "●●●●" in masked, masked

    phone_free = observability.scrub(f"درخواستِ OTP برایِ {FAKE_PHONE} رد شد")
    assert FAKE_PHONE not in phone_free, phone_free
    assert "درخواستِ OTP" in phone_free, "فقط راز حذف شود، بقیه‌یِ پیام بماند"

    labelled = observability.scrub(f"تنظیمات: authorization = Bearer {FAKE_API_KEY}")
    assert FAKE_API_KEY not in labelled, labelled
    print("✅ test_scrubber_masks_every_secret_shape PASSED")


def test_install_puts_the_filter_on_root_handlers() -> None:
    buffer = io.StringIO()
    handler = logging.StreamHandler(buffer)
    handler.setFormatter(logging.Formatter("%(levelname)s %(name)s%(corr)s: %(message)s"))
    root = logging.getLogger()
    previous_handlers = list(root.handlers)
    root.addHandler(handler)
    try:
        observability.install(level="INFO", as_json=False)
        token = observability.bind_correlation("wh:main:42")
        logging.getLogger("app.test").warning("توکنِ ربات: %s", FAKE_BOT_TOKEN)
        output = buffer.getvalue()
    finally:
        root.handlers[:] = previous_handlers
        observability.bind_correlation("")

    assert FAKE_BOT_TOKEN not in output, output
    assert "●●●●" in output, output
    assert f"[{token}]" in output, output
    print("✅ test_install_puts_the_filter_on_root_handlers PASSED")


def test_json_logs_format_carries_correlation() -> None:
    buffer = io.StringIO()
    handler = logging.StreamHandler(buffer)
    root = logging.getLogger()
    previous_handlers = list(root.handlers)
    root.addHandler(handler)
    try:
        observability.install(level="INFO", as_json=True)
        observability.bind_correlation("wh:shop:9")
        logging.getLogger("app.test").info("مشتری پیام داد: %s", "سلام")
        line = buffer.getvalue().strip().splitlines()[-1]
    finally:
        root.handlers[:] = previous_handlers
        observability.bind_correlation("")

    payload = json.loads(line)
    assert payload["corr"] == "wh:shop:9" and payload["msg"].startswith("مشتری پیام داد"), payload
    assert "سلام" in payload["msg"]
    print("✅ test_json_logs_format_carries_correlation PASSED")


# ============================================================================= ۳ — سقفِ نرخ
def test_http_guard_window() -> None:
    http_guard.reset()
    key = ("203.0.113.7", "main")
    assert all(http_guard.allow(key, 3, now=100.0 + i) for i in range(3)), "سه درخواستِ اول مجاز"
    assert http_guard.allow(key, 3, now=102.5) is False, "چهارم در همانِ پنجره رد می‌شود"
    assert http_guard.allow(key, 3, now=161.0) is True, "بعد از گذشتِ پنجره دوباره مجاز"
    assert http_guard.allow(("198.51.100.4", "main"), 3) is True, "IP دیگر سقفِ جدا دارد"
    assert http_guard.allow(("203.0.113.7", "shop:3"), 3) is True, "مسیرِ دیگر سقفِ جدا دارد"
    assert all(http_guard.allow(("192.0.2.9", "any"), 0) for _ in range(500)), "سقفِ ۰ ⇒ محدودسازی خاموش"
    http_guard.reset()
    print("✅ test_http_guard_window PASSED")


class _Headers:
    def __init__(self, values: dict[str, str]) -> None:
        self._values = {k.lower(): v for k, v in values.items()}

    def get(self, name: str, default=None):
        return self._values.get(name.lower(), default)


class _Request:
    def __init__(self, ip: str = "203.0.113.5", headers: dict[str, str] | None = None) -> None:
        self.client = type("Client", (), {"host": ip})()
        self.headers = _Headers(headers or {})

    async def json(self) -> dict:
        return {}


def test_endpoint_guard_returns_429_after_the_ceiling() -> None:
    from app.config import settings

    http_guard.reset()
    previous = settings.webhook_rate_limit_per_minute
    settings.webhook_rate_limit_per_minute = 2
    try:
        assert _too_many_requests(_Request(), "main") is None
        assert _too_many_requests(_Request(), "main") is None
        blocked = _too_many_requests(_Request(), "main")
        assert blocked is not None and blocked.status_code == 429, blocked
        assert blocked.headers.get("retry-after") == "60", dict(blocked.headers)
        assert observability.snapshot().get("webhook.rate_limited", 0) >= 1
    finally:
        settings.webhook_rate_limit_per_minute = previous
        http_guard.reset()
    print("✅ test_endpoint_guard_returns_429_after_the_ceiling PASSED")


async def test_metrics_endpoint_is_hidden_or_guarded() -> None:
    from app.config import settings

    observability.reset_counters()
    observability.count("webhook.main", 7)
    previous = settings.metrics_token
    try:
        settings.metrics_token = ""
        assert (await metrics_endpoint(_Request())).status_code == 404, "بدونِ راز، endpoint وجود ندارد"
        settings.metrics_token = "s3cr3t-metrics-token"
        assert (await metrics_endpoint(_Request())).status_code == 403, "بدونِ هدر ⇒ ۴۰۳"
        assert (await metrics_endpoint(_Request(headers={"x-metrics-token": "wrong"}))).status_code == 403, "رازِ غلط ⇒ ۴۰۳"
        ok = await metrics_endpoint(_Request(headers={"x-metrics-token": "s3cr3t-metrics-token"}))
        body = ok.body.decode()
    finally:
        settings.metrics_token = previous
        observability.reset_counters()

    assert ok.status_code == 200, ok.status_code
    assert "kasbokar_webhook_main 7" in body, body
    assert "kasbokar_uptime_seconds" in body, body
    print("✅ test_metrics_endpoint_is_hidden_or_guarded PASSED")


# ============================================================================= ۶ — زنجیرهٔ هشِ ممیزی
async def test_audit_chain_links_and_detects_tampering() -> None:
    from app.services import audit_log_service

    await reset_database()
    async with session_scope() as session:
        first = await audit_log_service.log(session, AuditEventType.KILL_SWITCH_TOGGLED, actor_telegram_id=111, details="الف")
        second = await audit_log_service.log(session, AuditEventType.KILL_SWITCH_TOGGLED, actor_telegram_id=111, details="ب")
        assert first.row_hash and len(first.row_hash) == 64, first.row_hash
        assert first.prev_hash == audit_log_service.GENESIS, "نخستینِ ردیفِ هش‌دار از مقدارِ آغازین شروع می‌کند"
        assert second.prev_hash == first.row_hash, "حلقه باید به هشِ ردیفِ قبلی وصل باشد"
        assert audit_log_service.compute_hash(second.prev_hash, second) == second.row_hash
        await session.commit()

    # تحریف: همان ردیف را با محتوایِ دیگر بخوان، هشِ ذخیره‌شده نمی‌خواند
    async with session_scope() as session:
        rows = list((await session.execute(select(AuditLogEntry).order_by(AuditLogEntry.id))).scalars().all())
        tampered = rows[-1]
        tampered.details = "متنی که بعداً عوض شد"
        assert audit_log_service.compute_hash(tampered.prev_hash, tampered) != tampered.row_hash, (
            "تغییرِ محتوا باید با همان تابع قابلِ کشف باشد"
        )
        await session.rollback()
    print("✅ test_audit_chain_links_and_detects_tampering PASSED")


# ============================================================================= ۷ — رازِ وب‌هوکِ رمزنگاری‌شده
async def test_webhook_secret_is_encrypted_and_legacy_rows_are_rewritten() -> None:
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    async with session_scope() as session:
        shop_bot = await shop_bot_service.get_by_id(session, shop_bot_id)
        secret = shop_bot.webhook_secret_token
        assert len(secret) > 20, "رازِ تازه باید همان چیزی باشد که هندلر مقایسه می‌کند"
        raw = await session.scalar(sql_text("SELECT webhook_secret_token FROM shop_bots WHERE id = :i"), {"i": shop_bot_id})
        assert looks_encrypted(str(raw)), "ردیفِ تازه باید رمزنگاری‌شده ذخیره شود"
        assert decrypt_token(str(raw)) == secret

    # ردیفِ قدیمیِ خام (پیش ازِ این مایگریشن): بوت‌آپ باید یک‌بار بازنویسی‌اش کند
    async with session_scope() as session:
        await session.execute(sql_text("UPDATE shop_bots SET webhook_secret_token = 'plaintext-legacy-secret' WHERE id = :i"), {"i": shop_bot_id})
        await session.commit()
    async with session_scope() as session:
        fixed = await shop_bot_service.reencrypt_secrets(session)
        await session.commit()
    assert fixed == 1, fixed
    async with session_scope() as session:
        shop_bot = await shop_bot_service.get_by_id(session, shop_bot_id)
        raw = await session.scalar(sql_text("SELECT webhook_secret_token FROM shop_bots WHERE id = :i"), {"i": shop_bot_id})
        assert shop_bot.webhook_secret_token == "plaintext-legacy-secret", "خواندنِ مقدارِ رمزنگاری‌شده شفاف است"
        assert looks_encrypted(str(raw)) and decrypt_token(str(raw)) == "plaintext-legacy-secret"
    async with session_scope() as session:
        assert await shop_bot_service.reencrypt_secrets(session) == 0, "دوباره اجرا ⇒ هیچ نوشتنی (ایدِمپوتنت)"
    print("✅ test_webhook_secret_is_encrypted_and_legacy_rows_are_rewritten PASSED")


async def main() -> None:
    test_scrubber_masks_every_secret_shape()
    test_install_puts_the_filter_on_root_handlers()
    test_json_logs_format_carries_correlation()
    test_http_guard_window()
    test_endpoint_guard_returns_429_after_the_ceiling()
    await test_metrics_endpoint_is_hidden_or_guarded()
    await test_audit_chain_links_and_detects_tampering()
    await test_webhook_secret_is_encrypted_and_legacy_rows_are_rewritten()


if __name__ == "__main__":
    asyncio.run(main())
