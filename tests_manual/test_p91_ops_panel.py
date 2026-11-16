"""پ۹۱ · پنلِ وبِ فقط‌خواندنیِ عملیاتی (`GET /panel`) — HTML راست‌به‌چپ با احرازِ HTTP Basic.

ادعاها (همه سنجیدنی):
۱. بدونِ `METRICS_TOKEN` مسیر ۴۰۴ است؛ با رمزِ غلط ۴۰۱ + چالشِ Basic (مرورگر دوباره می‌پرسد).
۲. با رمزِ درست، صفحه‌ای فارسی/RTL برمی‌گردد که فقط وضعیتِ عملیاتی را نشان می‌دهد: پروسه‌ها، سیستم،
   استخرِ دیتابیس، هوشِ مصنوعی، یافته‌ها، آستانه‌ها و شمارنده‌ها — و **هیچ فرم یا دکمهٔ نوشتنی** ندارد.
۳. هیچ رازی در HTML نیست: نه توکنِ ربات، نه کلیدِ AI، نه merchant_id، نه خودِ `METRICS_TOKEN`.
۴. این مسیر هم مثلِ `/metrics` فقط‌خواندنی است: statementهایِ آن همانِ `/ops/status` (پرس‌وجوهایِ خودِ
   عیب‌یاب) و هیچ نوشتنی انجام نمی‌شود.

اجرا: python3 tests_manual/run_one.py test_p91_ops_panel.py
"""
from __future__ import annotations

import asyncio
import base64
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from app import main as app_main  # noqa: E402
from app.database.session import engine  # noqa: E402
from app.services import http_guard  # noqa: E402
from app.config import settings  # noqa: E402
from harness import reset_database  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

OWNER_TG_ID = 999_951
SHOP_BOT_TG_ID = 999_952
TOKEN = "panel-secret-token"


async def _call(app, path: str, headers: list[tuple[bytes, bytes]]):
    scope = {
        "type": "http", "asgi": {"version": "3.0", "spec_version": "2.3"}, "http_version": "1.1",
        "method": "GET", "scheme": "http", "path": path, "raw_path": path.encode(),
        "query_string": b"", "headers": [(b"host", b"localhost")] + headers,
        "client": ("127.0.0.1", 5555), "server": ("localhost", 80), "root_path": "",
    }

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    status: list[int] = []
    response_headers: list[tuple[bytes, bytes]] = []
    body = bytearray()

    async def send(message):
        if message["type"] == "http.response.start":
            status.append(message["status"])
            response_headers.extend(message.get("headers", []))
        elif message["type"] == "http.response.body":
            body.extend(message.get("body", b""))

    await app(scope, receive, send)
    return (status[0] if status else 0), dict(response_headers), bytes(body)


def _basic(secret: str) -> bytes:
    return base64.b64encode(f"ops:{secret}".encode()).decode()


async def test_auth_gate() -> None:
    http_guard.reset()
    app = app_main.build_health_app()
    previous = settings.metrics_token
    try:
        settings.metrics_token = ""
        status, _, _ = await _call(app, "/panel", [])
        assert status == 404, status
        settings.metrics_token = TOKEN
        status, headers, body = await _call(app, "/panel", [])
        assert status == 401, status
        assert b"www-authenticate" in {k.lower() for k in headers}, headers
        assert "METRICS_TOKEN" in body.decode("utf-8"), body[:120]
        status, _, _ = await _call(app, "/panel", [(b"authorization", f"Basic {_basic('wrong')}".encode())])
        assert status == 401, status
        status, _, _ = await _call(app, "/panel", [(b"authorization", b"Basic !!!not-base64!!!")])
        assert status == 401, status
    finally:
        settings.metrics_token = previous
    print("PASS test_auth_gate")


async def test_panel_is_readonly_persian_and_secret_free() -> None:
    http_guard.reset()
    await reset_database()
    await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID, initial_balance_toman=50_000)
    app = app_main.build_health_app()
    previous = settings.metrics_token
    try:
        settings.metrics_token = TOKEN
        status, headers, body = await _call(app, "/panel", [(b"authorization", f"Basic {_basic(TOKEN)}".encode())])
    finally:
        settings.metrics_token = previous
    assert status == 200, status
    text = body.decode("utf-8")
    assert 'dir=rtl' in text and "پنلِ عملیاتی" in text, text[:200]
    for section in ("پروسه‌ها", "سیستم", "دیتابیس", "هوشِ مصنوعی", "یافته‌ها", "آستانه‌هایِ موثر", "شمارنده‌ها"):
        assert section in text, section
    assert "<form" not in text and "<button" not in text and "input" not in text.split("<style")[0], "پنلِ فقط‌خواندنی"
    assert "http-equiv=refresh" in text, "تازه‌سازیِ خودکار دارد"
    for banned in ("panel-secret-token", "encrypted_token", "webhook_secret", "merchant_id", "sk-", "gAAAAA"):
        assert banned not in text, banned
    assert "main_bot_token" not in text.lower()
    print(f"MEASURED پنل: {len(body)} بایت · content-type={headers.get(b'content-type', b'?').decode(errors='replace')}")
    print("PASS test_panel_is_readonly_persian_and_secret_free")


async def test_brute_force_is_rate_limited() -> None:
    """پ۹۶ · تلاشِ ناموفقِ بی‌پایانِ رمز، صفحه را باز نمی‌کند: بعد ازِ سقف ⇒ ۴۲۹ + Retry-After."""
    http_guard.reset()
    app = app_main.build_health_app()
    previous = settings.metrics_token
    limit = app_main.OPS_AUTH_FAIL_LIMIT_PER_MINUTE
    try:
        settings.metrics_token = TOKEN
        bad = (b"authorization", f"Basic {_basic('guessed')}".encode())
        for _ in range(limit):
            assert (await _call(app, "/panel", [bad]))[0] == 401
        status, headers, _ = await _call(app, "/panel", [bad])
        assert status == 429, status
        assert b"retry-after" in {k.lower() for k in headers}, headers
        # رمزِ درست حتی در همان دقیقه کار می‌کند (سقف مالِ تلاشِ *ناموفق* است، نه موفق)
        good = (b"authorization", f"Basic {_basic(TOKEN)}".encode())
        assert (await _call(app, "/panel", [good]))[0] == 200, "سقفِ تلاشِ ناموفق نباید رمزِ درست را هم بخورد"
    finally:
        settings.metrics_token = previous
        http_guard.reset()
    print("PASS test_brute_force_is_rate_limited")


async def main() -> None:
    await test_auth_gate()
    await test_panel_is_readonly_persian_and_secret_free()
    await test_brute_force_is_rate_limited()
    await engine.dispose()  # پ۹۶: اتصال‌ها قبلِ بسته‌شدنِ loop برگردند تا warningِ greenlet ساخته نشود


if __name__ == "__main__":
    asyncio.run(main())
