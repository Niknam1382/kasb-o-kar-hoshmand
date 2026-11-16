"""پ۸۷ · لایهٔ اولِ «پنلِ عملیاتیِ وب»: یکِ مسیرِ فقط‌خواندنیِ JSON رویِ اپِ سلامت/ادمین.

چرا همین‌قدر و نه بیشتر: پنلِ وبِ چندکاناله با ورودِ کاربر و نوشتنِ داده، یکِ فازِ کاملِ مستقل است و
نیمه‌کاره گذاشتنِ آن رویِ لایهٔ HTTP خطرناک‌تر از عقب انداختنش است (قاعدهٔ ۱۶ِ قواعدِ کاری). این لایه:

۱. `/ops/status` را *احرازِ همان* `METRICS_TOKEN` می‌کند (کلیدِ خالی ⇒ ۴۰۴، یعنی مسیر وجود ندارد).
۲. فقط عدد و درصد و کلیدِ یافته‌ها را می‌دهد — نه توکن، نه آدرسِ درگاه، نه متنِ پیامِ مشتری.
۳. اپِ سلامت (حالتِ polling) همچنان فقط سه مسیر دارد؛ هیچ وب‌هوکی از آن سرویس نمی‌شود.
۴. `/docs` و OpenAPI خاموش می‌مانند (ادعایِ پ۲۱ نشکند).

اجرا: python3 tests_manual/run_one.py test_p87_ops_endpoint.py
"""
from __future__ import annotations

import asyncio
import json
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from app import main as app_main  # noqa: E402
from app.config import settings  # noqa: E402
from app.database.session import engine  # noqa: E402
from app.services import http_guard  # noqa: E402
from harness import reset_database  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

OWNER_TG_ID = 998_701
SHOP_BOT_TG_ID = 998_702


async def _call(app, method: str, path: str, headers: list[tuple[bytes, bytes]]):
    scope = {
        "type": "http", "asgi": {"version": "3.0", "spec_version": "2.3"}, "http_version": "1.1",
        "method": method, "scheme": "http", "path": path, "raw_path": path.encode(),
        "query_string": b"", "headers": [(b"host", b"localhost")] + headers,
        "client": ("127.0.0.1", 5555), "server": ("localhost", 80), "root_path": "",
    }

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    status: list[int] = []
    body = bytearray()

    async def send(message):
        if message["type"] == "http.response.start":
            status.append(message["status"])
        elif message["type"] == "http.response.body":
            body.extend(message.get("body", b""))

    await app(scope, receive, send)
    return (status[0] if status else 0), bytes(body)


def _paths_of(routes) -> set[str]:
    """همانِ چیزی که تستِ پ۲۱ استفاده می‌کند: مسیرها گاهی زیرِ Mount/Routerِ تودرتویند."""
    found: set[str] = set()

    def walk(items) -> None:
        for route in items:
            for attr in ("routes", "original_router", "router"):
                nested = getattr(route, attr, None)
                if nested is not None and hasattr(nested, "routes"):
                    walk(nested.routes)
            path = getattr(route, "path", None)
            if path:
                found.add(path)

    walk(routes)
    return found


def _health_paths() -> set[str]:
    return _paths_of(app_main.build_health_app().routes)


async def test_route_is_registered_on_both_apps() -> None:
    paths = _health_paths()
    assert paths == {"/health", "/metrics", "/ops/status", "/panel"}, sorted(paths)
    main_paths = _paths_of(app_main.app.routes)
    assert "/ops/status" in main_paths, sorted(main_paths)
    assert "/webhook/main" not in paths, "وب‌هوک هرگز از اپِ سلامت سرویس نمی‌شود"
    print("PASS test_route_is_registered_on_both_apps")


async def test_auth_is_the_same_token_and_hides_the_route_when_unset() -> None:
    http_guard.reset()
    health_app = app_main.build_health_app()
    previous = settings.metrics_token
    try:
        settings.metrics_token = ""
        status, _ = await _call(health_app, "GET", "/ops/status", [])
        assert status == 404, status
        settings.metrics_token = "super-secret-metrics-token"
        status, _ = await _call(health_app, "GET", "/ops/status", [])
        assert status in (401, 403), status
        status, _ = await _call(health_app, "GET", "/ops/status", [(b"x-metrics-token", b"wrong")])
        assert status in (401, 403), status
        assert (await _call(health_app, "GET", "/docs", [(b"x-metrics-token", b"super-secret-metrics-token")]))[0] == 404
    finally:
        settings.metrics_token = previous
    print("PASS test_auth_is_the_same_token_and_hides_the_route_when_unset")


async def test_payload_is_machine_readable_and_secret_free() -> None:
    await reset_database()
    await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID, initial_balance_toman=100_000)
    health_app = app_main.build_health_app()
    previous = settings.metrics_token
    try:
        settings.metrics_token = "tok-for-p87"
        status, raw = await _call(health_app, "GET", "/ops/status", [(b"x-metrics-token", b"tok-for-p87")])
    finally:
        settings.metrics_token = previous
    assert status == 200, (status, raw[:400])
    data = json.loads(raw)
    for key in ("ok", "processes", "stale_processes", "counters", "db_pool", "system", "ai", "thresholds", "findings"):
        assert key in data, sorted(data)
    assert isinstance(data["processes"], int) and data["processes"] >= 1, data["processes"]
    assert isinstance(data["findings"], list), data["findings"]
    assert all(set(item) == {"key", "severity", "title"} for item in data["findings"]), data["findings"][:2]
    text = raw.decode("utf-8", errors="replace")
    for banned in ("encrypted_token", "webhook_secret", "merchant_id", "api_key", "sk-", "gAAAAA"):
        assert banned not in text, f"نامِ راز در پاسخ ظاهر شد: {banned}"
    assert "tok-for-p87" not in text, "کلیدِ متریک نباید در پاسخِ JSON برگردد"
    print(f"MEASURED payload: {len(raw)} بایت · {len(data['findings'])} یافته · counters={len(data['counters'])}")
    print("PASS test_payload_is_machine_readable_and_secret_free")


async def main() -> None:
    await engine.dispose()  # پ۹۶: بی‌صدا کردنِ نویزِ بستنِ استخر در پایانِ پروسه
    await test_route_is_registered_on_both_apps()
    await test_auth_is_the_same_token_and_hides_the_route_when_unset()
    await test_payload_is_machine_readable_and_secret_free()


if __name__ == "__main__":
    asyncio.run(main())
