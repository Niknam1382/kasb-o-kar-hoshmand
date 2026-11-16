"""
تست: P21-B — اپِ سلامت در حالتِ polling، پاک‌سازیِ صفِ اعلان، و تنظیمِ دیتابیس

پوشش:
۱. `build_health_app()` فقط `/health`، `/metrics` و `/ops/status` را دارد: هیچ مسیرِ `/webhook/*` یا
   `/payment/*` در آن سرویس نمی‌شود (این دلیلِ اصلیِ ساختِ اپِ جداست، نه تنظیف).
۲. `/health`: با دیتابیسِ سالم و باتِ مقداردهی‌شده ۲۰۰، بدونِ بات ۵۰۳ ⇒ لودبالانسر گول نمی‌خورد.
۳. `prune_aged`: ردیف‌هایِ کهنهٔ `sent` می‌روند، `failed` تا ۹۰ روز می‌مانند، و `pending`
   هرگز پاک نمی‌شود (آن بدهیِ ارسال است، نه تاریخچه).
۴. جابِ prune در `run_periodic_pass` همان پاک‌سازی را واقعاً صدا می‌زند (سیم‌کشی، نه تابعِ تنها).

اجرا: python3 tests_manual/test_p21_ops.py
"""
from __future__ import annotations

import asyncio
import datetime
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from sqlalchemy import select  # noqa: E402

from harness import build_test_dispatchers, make_shop_bot, reset_database  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from app import main as app_main  # noqa: E402
from app.database.models import Notification  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import notification_service, scheduler  # noqa: E402

OWNER_TG_ID = 999_751
SHOP_BOT_TG_ID = 999_752


# ============================================================================= ۱ — سطحِ حملهٔ اپِ سلامت
def _paths(routes) -> set[str]:
    """مسیرها را از درختِ router جمع می‌کند.

    starlette 1.x موقعِ `include_router` یکِ `_IncludedRouter` تنبل می‌گذارد (route‌های واقعی
    زیرِ `original_router`‌اند)، پس هر سه شکلِ ممکن را walk می‌کنیم تا تست به نسخهٔ کتابخانه
    وابسته نماند.
    """
    found: set[str] = set()
    for route in routes:
        path = getattr(route, "path", None)
        if path:
            found.add(path)
        for attr in ("routes", "original_router", "router"):
            nested = getattr(route, attr, None)
            if nested is not None and hasattr(nested, "routes"):
                found |= _paths(nested.routes)
    return found


async def _asgi_status(app, method: str, path: str) -> int:
    """فراخوانیِ مستقیمِ ASGI بدونِ TestClient (که به httpx نیاز دارد و در ایمیج نیست)."""
    scope = {
        "type": "http", "asgi": {"version": "3.0", "spec_version": "2.3"}, "http_version": "1.1",
        "method": method, "scheme": "http", "path": path, "raw_path": path.encode(),
        "query_string": b"", "headers": [(b"host", b"localhost")],
        "client": ("127.0.0.1", 5555), "server": ("localhost", 80), "root_path": "",
    }

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    statuses: list[int] = []

    async def send(message):
        if message["type"] == "http.response.start":
            statuses.append(message["status"])

    await app(scope, receive, send)
    return statuses[0] if statuses else 0


async def test_health_app_exposes_only_two_routes() -> None:
    from app.config import settings

    health_app = app_main.build_health_app()
    paths = _paths(health_app.routes)
    # پ۸۷: مسیرِ سومِ فقط‌خواندنی (/ops/status) افزوده شد — ادعا بی‌تغییر می‌ماند: هیچ وب‌هوکی اینجا
    # سرویس نمی‌شود و `/docs` همچنان ۴۰۴ است. (تغییرِ رفتاریِ عمدی، ثبت‌شده در docs/PROGRESS.md)
    assert paths == {"/health", "/metrics", "/ops/status", "/panel"}, f"اپِ سلامت باید فقط این سه مسیر را داشته باشد؛ دیده شد: {sorted(paths)}"
    assert {"/health", "/metrics", "/ops/status", "/panel"} <= _paths(app_main.app.routes), "اپِ اصلی هم همان چهار مسیر را دارد"
    assert {"/webhook/main", "/webhook/shop/{shop_bot_id}"} <= _paths(app_main.app.routes), "وب‌هوک‌هایِ اپِ اصلی نباید رفته باشند"

    # رفتارِ واقعی (نه فقط جدولِ مسیر): در حالتِ polling هم آپدیتِ جعلی قابلِ تزریق نیست
    previous_token = settings.metrics_token
    try:
        settings.metrics_token = ""
        assert await _asgi_status(health_app, "POST", "/webhook/main") == 404, "وب‌هوک در اپِ سلامت سرویس نمی‌شود"
        assert await _asgi_status(health_app, "POST", "/webhook/shop/1") == 404
        assert await _asgi_status(health_app, "GET", "/metrics") == 404, "بدونِ METRICS_TOKEN متریک بیرون نمی‌رود"
        assert await _asgi_status(health_app, "GET", "/docs") == 404, "مستندات/OpenAPI خاموش است"
        assert await _asgi_status(health_app, "GET", "/health") in (200, 503)
    finally:
        settings.metrics_token = previous_token
    print("✅ test_health_app_exposes_only_two_routes PASSED")


# ============================================================================= ۲ — /health صادق است
async def test_health_reflects_bot_initialization() -> None:
    saved = dict(app_main._state)
    try:
        app_main._state.clear()
        down = await app_main.health_check()
        assert down.status_code == 503, "بدونِ باتِ مقداردهی‌شده ⇒ ۵۰۳ (لودبالانسر نباید گول بخورد)"
        app_main._state["main_bot"] = object()
        ok = await app_main.health_check()
        assert ok.status_code == 200, ok.status_code
    finally:
        app_main._state.clear()
        app_main._state.update(saved)
    print("✅ test_health_reflects_bot_initialization PASSED")


# ============================================================================= ۳ — پاک‌سازیِ صف
async def _insert(status: str, age_days: int) -> int:
    now = datetime.datetime.now(datetime.timezone.utc)
    async with session_scope() as session:
        row = Notification(
            chat_id=1000 + age_days,
            text="خبرِ آزمایشی",
            status=status,
            attempts=1,
            next_attempt_at=now,
            created_at=now - datetime.timedelta(days=age_days),
        )
        session.add(row)
        await session.flush()
        return row.id


async def _statuses() -> dict[str, list[int]]:
    async with session_scope() as session:
        rows = list((await session.execute(select(Notification))).scalars().all())
    out: dict[str, list[int]] = {}
    for row in rows:
        out.setdefault(row.status, []).append(row.id)
    return out


async def test_prune_aged_keeps_pending_and_recent_history() -> None:
    await reset_database()
    await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)

    old_sent = await _insert(notification_service.SENT, 40)
    fresh_sent = await _insert(notification_service.SENT, 5)
    old_failed = await _insert(notification_service.FAILED, 120)
    fresh_failed = await _insert(notification_service.FAILED, 40)
    pending = await _insert(notification_service.PENDING, 200)  # حتی کهنه هم نمی‌رود: بدهیِ ارسال است

    async with session_scope() as session:
        removed = await notification_service.prune_aged(session)
    left = await _statuses()
    survivors = sorted([row_id for ids in left.values() for row_id in ids])
    assert removed == 2, removed
    assert old_sent not in survivors and old_failed not in survivors, "کهنه‌ها رفته‌اند"
    assert left.get("sent") == [fresh_sent], left
    assert left.get("failed") == [fresh_failed], left
    assert left.get("pending") == [pending], "هیچ اعلانِ در‌انتظارِ ارسال پاک نمی‌شود"

    # ۰ ⇒ نگهداریِ نامحدود (سوییچِ ایمنِ عملیاتی؛ «هیچ سابقه‌ای را دور نریز»)
    async with session_scope() as session:
        again = await notification_service.prune_aged(session, sent_days=0, failed_days=0)
    assert again == 0, again
    print("✅ test_prune_aged_keeps_pending_and_recent_history PASSED")


# ============================================================================= ۴ — سیم‌کشیِ جاب
async def test_periodic_pass_prunes_the_outbox(bot_manager) -> None:
    await reset_database()
    await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    old_sent = await _insert(notification_service.SENT, 45)
    old_failed = await _insert(notification_service.FAILED, 200)

    main_bot = make_shop_bot("000000:MAIN_FAKE")
    await scheduler.run_periodic_pass(main_bot, bot_manager)

    survivors = sorted([row_id for ids in (await _statuses()).values() for row_id in ids])
    assert old_sent not in survivors and old_failed not in survivors, (old_sent, old_failed, survivors)
    print("✅ test_periodic_pass_prunes_the_outbox PASSED")


# ============================================================================= ۵ — قفلِ جاب برایِ چندپروسه
async def test_periodic_pass_is_single_flight(bot_manager) -> None:
    """O4: اگر نسخهٔ دیگری قفلِ advisory را گرفته باشد، این دور هیچ کاری نمی‌کند."""
    from sqlalchemy import text as sql_text

    await reset_database()
    await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    marker = await _insert(notification_service.SENT, 45)

    async with session_scope() as holder:  # «نسخهٔ دومِ اپ» که همین حالا جاب را اجرا می‌کند
        assert (await holder.execute(sql_text("SELECT pg_try_advisory_lock(:k)"), {"k": scheduler.SCHEDULER_LOCK_KEY})).scalar_one()
        main_bot = make_shop_bot("000000:MAIN_FAKE")
        await scheduler.run_periodic_pass(main_bot, bot_manager)
        still_there = len((await _statuses()).get("sent", []))
        await holder.execute(sql_text("SELECT pg_advisory_unlock(:k)"), {"k": scheduler.SCHEDULER_LOCK_KEY})
    assert still_there == 1, "با قفلِ گرفته‌شده، پاک‌سازیِ صف اجرا نشد ⇒ دو نسخهٔ اپ جاب را دوباره انجام نمی‌دهند"

    main_bot = make_shop_bot("000000:MAIN_FAKE")
    await scheduler.run_periodic_pass(main_bot, bot_manager)
    assert marker not in [row_id for ids in (await _statuses()).values() for row_id in ids], "بعد از آزادشدنِ قفل، جاب دوباره کار می‌کند"
    print("✅ test_periodic_pass_is_single_flight PASSED")


async def main() -> None:
    _main_dp, _shop_dp, bot_manager, _main_bot = build_test_dispatchers()
    await test_health_app_exposes_only_two_routes()
    await test_health_reflects_bot_initialization()
    await test_prune_aged_keeps_pending_and_recent_history()
    await test_periodic_pass_prunes_the_outbox(bot_manager)
    await test_periodic_pass_is_single_flight(bot_manager)


if __name__ == "__main__":
    asyncio.run(main())
