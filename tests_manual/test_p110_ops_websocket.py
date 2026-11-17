"""پ۱۱۰ · نگاهِ زندهٔ پنلِ عملیاتی (`/ws/ops`): WebSocket به‌جایِ رفرشِ ۳۰ ثانیه‌ای.

ادعاها (همه در همین فایل سنجیده می‌شوند):
۱. بی‌`METRICS_TOKEN` اتصال با کد ۴۴۰۴ بسته می‌شود؛ با کوکیِ بی‌امضا/جعلی/قدیمی ۴۴۰۱؛ با نشانهٔ
   درست پذیرفته می‌شود و پیامِ اول *فوری* است (بی‌صبرِ OPS_PUSH_SECONDS).
۲. محتوایِ پیام همان تکهٔ escape‌شدهٔ صفحه است و هیچ رازی (خودِ `METRICS_TOKEN`، توکنِ ربات) ندارد.
۳. `onclose` فقط وقتی meta-refresh را برمی‌گرداند که آن را از HTML حذف کنیم: یعنی HTML هر دو را دارد
   (پ۹۱ نمی‌شکند: هنوز `http-equiv=refresh` در صفحه هست).
۴. عمرِ اتصال سقف دارد (`OPS_WS_MAX_LIFETIME_SECONDS`) ⇒ تسکِ بی‌پایان باز نمی‌ماند.
۵. مسیرِ زنده اتصالِ «idle in transaction» نمی‌سازد (همان باگی که پ۱۰۴ در `/ops/status` بست).

اجرا: python3 tests_manual/run_one.py test_p110_ops_websocket.py
"""
from __future__ import annotations

import asyncio
import json
import sys
import time

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from app import main as app_main  # noqa: E402
from app.config import settings  # noqa: E402
from app.database.session import engine, session_scope  # noqa: E402
from harness import reset_database  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

OWNER_TG_ID = 11_100_000_001
SHOP_BOT_TG_ID = 11_100_000_002
TOKEN = "p110-metrics-token"


async def _ws_roundtrip(app, *, cookie: str | None, want_pushes: int = 1, wait_for_close: bool = False):
    """یکِ گفت‌وگویِ خامِ WebSocket با اپِ ASGI (بدونِ وابستگیِ تازه به TestClient/httpx)."""
    headers = [(b"sec-websocket-version", b"13")]
    if cookie is not None:
        headers.append((b"cookie", f"{app_main.OPS_WS_COOKIE}={cookie}".encode()))
    scope = {
        "type": "websocket", "asgi": {"version": "3.0", "spec_version": "2.3"}, "http_version": "1.1",
        "scheme": "ws", "path": "/ws/ops", "raw_path": b"/ws/ops", "query_string": b"",
        "headers": [(b"host", b"localhost")] + headers,
        "client": ("127.0.0.1", 5555), "server": ("localhost", 80), "root_path": "", "subprotocols": [],
    }
    inbox: asyncio.Queue = asyncio.Queue()
    await inbox.put({"type": "websocket.connect"})
    sent: list[dict] = []

    async def receive():
        return await inbox.get()

    async def send(message):
        sent.append(message)

    task = asyncio.create_task(app(scope, receive, send))
    pushes = [m for m in sent if m["type"] == "websocket.send"]
    deadline = time.monotonic() + 5.0
    while len(pushes) < want_pushes and time.monotonic() < deadline:
        await asyncio.sleep(0.01)
        pushes = [m for m in sent if m["type"] == "websocket.send"]
    await inbox.put({"type": "websocket.disconnect", "code": 1000})
    if wait_for_close:
        try:
            await asyncio.wait_for(task, timeout=5.0)
        except (asyncio.TimeoutError, asyncio.CancelledError, Exception):  # noqa: BLE001
            task.cancel()
    else:
        task.cancel()
    try:
        await task
    except (asyncio.CancelledError, Exception):  # noqa: BLE001
        pass
    return sent


def _close_code(sent: list[dict]) -> int | None:
    for message in sent:
        if message["type"] == "websocket.close":
            return int(message.get("code", 0))
    return None


# ============================================================================= ۱
async def test_handshake_requires_metrics_token_and_ticket() -> None:
    app = app_main.build_health_app()
    previous = settings.metrics_token
    try:
        settings.metrics_token = ""
        sent = await _ws_roundtrip(app, cookie="1.x")
        assert _close_code(sent) == 4404, sent
        assert not any(m["type"] == "websocket.accept" for m in sent)

        settings.metrics_token = TOKEN
        for bad in (None, "", "abc", "999." + "0" * 24, f"{int(time.time() // app_main.OPS_WS_TICKET_WINDOW_SECONDS) - 3}.deadbeef"):
            sent = await _ws_roundtrip(app, cookie=bad)
            assert _close_code(sent) == 4401, (bad, sent)
            assert not any(m["type"] == "websocket.accept" for m in sent), bad

        sent = await _ws_roundtrip(app, cookie=app_main._ops_ws_ticket(), want_pushes=1)
        assert any(m["type"] == "websocket.accept" for m in sent), sent
        assert any(m["type"] == "websocket.send" for m in sent), "اولینِ پیام باید فوری باشد"
    finally:
        settings.metrics_token = previous
    print("PASS test_handshake_requires_metrics_token_and_ticket")


def test_ticket_window_is_rolled() -> None:
    previous = settings.metrics_token
    settings.metrics_token = TOKEN
    try:
        current = int(time.time() // app_main.OPS_WS_TICKET_WINDOW_SECONDS)
        assert app_main._ops_ws_ticket_ok(app_main._ops_ws_ticket())
        assert app_main._ops_ws_ticket_ok(f"{current}.{app_main._ops_ws_sig(current)}")
        assert app_main._ops_ws_ticket_ok(f"{current - 1}.{app_main._ops_ws_sig(current - 1)}"), "پنجرهٔ قبل باید بخشوده شود"
        assert not app_main._ops_ws_ticket_ok(f"{current - 2}.{app_main._ops_ws_sig(current - 2)}")
        assert not app_main._ops_ws_ticket_ok(f"{current}.{app_main._ops_ws_sig(current - 1)}")
        assert not app_main._ops_ws_ticket_ok(f"x.{app_main._ops_ws_sig(current)}")
        other_sig = app_main._ops_ws_sig(current)
        settings.metrics_token = "another-token"
        assert not app_main._ops_ws_ticket_ok(f"{current}.{other_sig}"), "با کلیدِ دیگر نشانه نمی‌خواند"
        assert app_main._ops_ws_ticket_ok(app_main._ops_ws_ticket()), "با کلیدِ تازه، نشانهٔ تازه می‌خواند"
    finally:
        settings.metrics_token = previous
    print("PASS test_ticket_window_is_rolled")


# ============================================================================= ۲ و ۳
async def test_page_carries_both_live_and_fallback_and_payload_is_secret_free() -> None:
    await reset_database()
    await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID, initial_balance_toman=50_000)
    app = app_main.build_health_app()
    previous = settings.metrics_token
    settings.metrics_token = TOKEN
    try:
        from test_p91_ops_panel import _basic, _call  # noqa: PLC0415

        status, headers, body = await _call(app, "/panel", [(b"authorization", f"Basic {_basic(TOKEN)}".encode())])
        text = body.decode("utf-8")
        assert status == 200, status
        assert "http-equiv=refresh" in text, "رفرشِ ۳۰ ثانیه‌ای باید بماند (افتِ ظریف)"
        assert "id=ops-body" in text and "id=live" in text, text[:400]
        assert "/ws/ops" in text and "new WebSocket" in text, "اسکریپتِ نگاهِ زنده نیست"
        assert "<form" not in text and "<button" not in text, "پنلِ فقط‌خواندنی"
        cookie_header = headers.get(b"set-cookie", b"")
        assert app_main.OPS_WS_COOKIE.encode() in cookie_header and b"HttpOnly" in cookie_header, cookie_header
        assert b"samesite=strict" in cookie_header.lower(), cookie_header
        assert TOKEN not in text and TOKEN.encode() not in cookie_header.split(b"=", 1)[1], "کلید در HTML"

        ticket = cookie_header.decode().split(app_main.OPS_WS_COOKIE + "=", 1)[1].split(";")[0]
        sent = await _ws_roundtrip(app, cookie=ticket, want_pushes=1)
        payload = next(m for m in sent if m["type"] == "websocket.send")
        raw = payload.get("text", "").encode("utf-8", errors="replace")
        data = json.loads(payload["text"])
        assert set(data) == {"html"}, sorted(data)
        assert "پروسه" in data["html"] and "<h2" in data["html"]
        for banned in (TOKEN, "encrypted_token", "webhook_secret", "gAAAAA", "sk-"):
            assert banned not in data["html"], banned
        print(f"MEASURED پیامِ زنده: {len(data['html'])} نویسه · {len(raw)} بایت")
    finally:
        settings.metrics_token = previous
    print("PASS test_page_carries_both_live_and_fallback_and_payload_is_secret_free")


# ============================================================================= ۴
async def test_connection_lifetime_is_capped() -> None:
    app = app_main.build_health_app()
    previous_token = settings.metrics_token
    previous_push = app_main.OPS_PUSH_SECONDS
    previous_life = app_main.OPS_WS_MAX_LIFETIME_SECONDS
    settings.metrics_token = TOKEN
    app_main.OPS_PUSH_SECONDS = 0.01
    app_main.OPS_WS_MAX_LIFETIME_SECONDS = 0.05
    try:
        sent = await _ws_roundtrip(app, cookie=app_main._ops_ws_ticket(), want_pushes=3, wait_for_close=True)
        pushes = [m for m in sent if m["type"] == "websocket.send"]
        assert len(pushes) >= 2, len(pushes)
        assert any(m["type"] == "websocket.close" for m in sent), "اتصال باید با سقفِ عمر بسته شود"
    finally:
        settings.metrics_token = previous_token
        app_main.OPS_PUSH_SECONDS = previous_push
        app_main.OPS_WS_MAX_LIFETIME_SECONDS = previous_life
    print("PASS test_connection_lifetime_is_capped")


# ============================================================================= ۵
async def test_live_pushes_leave_no_idle_in_transaction_connection() -> None:
    from sqlalchemy import text as sql_text  # noqa: PLC0415

    await reset_database()
    await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    app = app_main.build_health_app()
    previous_token = settings.metrics_token
    previous_push = app_main.OPS_PUSH_SECONDS
    previous_life = app_main.OPS_WS_MAX_LIFETIME_SECONDS
    settings.metrics_token = TOKEN
    app_main.OPS_PUSH_SECONDS = 0.01
    app_main.OPS_WS_MAX_LIFETIME_SECONDS = 0.3
    try:
        sent = await _ws_roundtrip(app, cookie=app_main._ops_ws_ticket(), want_pushes=4, wait_for_close=True)
        assert len([m for m in sent if m["type"] == "websocket.send"]) >= 4, sent
        async with session_scope() as session:
            leaked = (
                await session.execute(
                    sql_text(
                        "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database() "
                        "AND pid <> pg_backend_pid() AND state = 'idle in transaction'"
                    )
                )
            ).scalar_one()
        assert int(leaked) == 0, f"اتصالِ نشتی با تراکنشِ باز بعد ازِ جریانِ زنده: {leaked}"
    finally:
        settings.metrics_token = previous_token
        app_main.OPS_PUSH_SECONDS = previous_push
        app_main.OPS_WS_MAX_LIFETIME_SECONDS = previous_life
    print("PASS test_live_pushes_leave_no_idle_in_transaction_connection")


async def main() -> None:
    await test_handshake_requires_metrics_token_and_ticket()
    test_ticket_window_is_rolled()
    await test_page_carries_both_live_and_fallback_and_payload_is_secret_free()
    await test_connection_lifetime_is_capped()
    await test_live_pushes_leave_no_idle_in_transaction_connection()
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
