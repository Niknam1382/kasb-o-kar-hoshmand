"""پ۹۰ · سنجش‌هایِ بازِ عملیاتی (MEASURED) — هزینهٔ واقعیِ مسیرهایِ تازه زیرِ بار.

سه چیزی که قبلاً فقط ادعا یا EXTRAPOLATED بود اینجا عدد می‌شود (رویِ دیتابیسِ تست، بدونِ شبکه):
۱. جمعِ شمارنده‌ها با ۲۰۰ پروسهٔ زنده ⇒ چند statement و چند میلی‌ثانیه (ادعایِ پ۷۹: «کوئریِ ثابت»).
۲. درِ «به این حساب جواب نده» با فهرستِ پُر (۲۰۰ حساب) ⇒ هزینهٔ هرِ کامنت چقدر است.
۳. دسته‌بندیِ محصولات با ۲۰۰ دسته و ۲۰۰ محصول ⇒ گروه‌بندیِ Python چقدر طول می‌کشد و چند statement است.
۴. `/ops/status` و `/metrics` ⇒ بایت، میلی‌ثانیه و اینکه مسیرِ HTTP هیچ کوئریِ اضافه‌ای نمی‌زند.

عددها با خطِ `MEASURED` در خروجِ سوئیت چاپ می‌شوند تا در `SCALABILITY_AND_LOAD_TEST_REPORT.md` قابلِ
ارجاع باشند. کران‌هایِ assert محافظه‌کارانه‌اند (نه عددِ دقیقِ ماشینِ من): اگر سخت‌افزاری کندتر باشد،
تست می‌شکند و عددِ واقعیِ آن ماشین را می‌بینیم ⇒ این «شکستِ مفید» است، نه flaky.

اجرا: python3 tests_manual/run_one.py test_p90_ops_measurements.py
"""
from __future__ import annotations

import asyncio
import datetime as dt
import json
import sys
import time

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from sqlalchemy import select  # noqa: E402

from app import main as app_main  # noqa: E402
from app import observability  # noqa: E402
from app.config import settings  # noqa: E402
from app.database.models import InstagramCommentBlock, Product, RuntimeCounterSnapshot  # noqa: E402
from app.database.session import engine, session_scope  # noqa: E402
from app.services import capacity_service, instagram_service, product_service  # noqa: E402
from harness import reset_database  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

UTC = dt.timezone.utc
OWNER_TG_ID = 999_901
SHOP_BOT_TG_ID = 999_902
WORKERS = 200
BLOCKS = 200
CATEGORIES = 200

_statements: list[str] = []
_attached = False


def _attach_counter() -> None:
    global _attached
    if _attached:
        return
    from sqlalchemy import event

    @event.listens_for(engine.sync_engine, "before_cursor_execute")
    def _count(conn, cursor, statement, parameters, context, executemany):
        _statements.append(statement)

    _attached = True


async def _seed_shop() -> int:
    await reset_database()
    observability.reset_counters()
    return await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID, initial_balance_toman=100_000)


# ============================================================================= ۱ — جمعِ ۲۰۰ پروسه
async def test_aggregation_with_many_workers() -> None:
    shop_bot_id = await _seed_shop()
    _attach_counter()
    now = dt.datetime.now(UTC)
    async with session_scope() as session:
        for index in range(WORKERS):
            session.add(
                RuntimeCounterSnapshot(
                    process_key=f"worker-{index}:1000", hostname=f"worker-{index}",
                    counters=json.dumps({"webhook.shop": index, "wallet.deduct_denied": 1}),
                    updated_at=now,
                )
            )
        await session.commit()
    _statements.clear()
    started = time.perf_counter()
    async with session_scope() as session:
        totals, processes, stale = await capacity_service.aggregate_counters(session)
    elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
    stmts = len(_statements)
    print(f"MEASURED جمعِ {WORKERS} پروسه: {stmts} statement · {elapsed_ms}ms · processes={processes} stale={stale}")
    assert stmts <= 2, f"جمعِ شمارنده‌ها باید کوئریِ ثابت بزند، دیده شد: {stmts}"
    assert processes == WORKERS + 1, processes
    assert totals["wallet.deduct_denied"] >= WORKERS, totals
    # پاک‌سازیِ ۷روزه هم کوئریِ ثابت است
    async with session_scope() as session:
        _statements.clear()
        removed = await capacity_service.prune_counter_snapshots(session)
        await session.commit()
    assert removed == 0, removed  # همه تازه‌اند
    assert len(_statements) <= 2, len(_statements)
    print(f"MEASURED پاک‌سازیِ ردیفِ تازه: {len(_statements)} statement · حذف‌شده={removed}")
    print("PASS test_aggregation_with_many_workers")


# ============================================================================= ۲ — درِ «جواب نده» با فهرستِ پُر
async def test_block_gate_cost_with_full_list() -> None:
    shop_bot_id = await _seed_shop()
    _attach_counter()
    async with session_scope() as session:
        for index in range(BLOCKS):
            session.add(InstagramCommentBlock(shop_bot_id=shop_bot_id, username=f"user{index}"))
        await session.commit()
    _statements.clear()
    started = time.perf_counter()
    async with session_scope() as session:
        blocked = await instagram_service.comment_sender_is_blocked(session, shop_bot_id, "USER150")
        allowed = await instagram_service.comment_sender_is_blocked(session, shop_bot_id, "not-there")
        _ = await session.execute(select(InstagramCommentBlock).where(InstagramCommentBlock.shop_bot_id == shop_bot_id))
    elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
    print(f"MEASURED درِ جواب‌نده با {BLOCKS} حساب: ۲ پرس‌وجو در {len(_statements)} statement · {elapsed_ms}ms · blocked={blocked} allowed={allowed}")
    assert blocked is True and allowed is False
    assert len(_statements) == 3, len(_statements)
    print("PASS test_block_gate_cost_with_full_list")


# ============================================================================= ۳ — ۲۰۰ دسته
async def test_category_grouping_cost() -> None:
    shop_bot_id = await _seed_shop()
    _attach_counter()
    async with session_scope() as session:
        for index in range(CATEGORIES):
            session.add(
                Product(
                    shop_bot_id=shop_bot_id, name=f"محصولِ {index}", price_toman=10_000 * (index + 1),
                    stock_quantity=index, category=f"دسته-{index}", is_active=True,
                )
            )
        await session.commit()
    _statements.clear()
    started = time.perf_counter()
    async with session_scope() as session:
        products = list((await session.execute(select(Product).where(Product.shop_bot_id == shop_bot_id))).scalars().all())
        names, groups, unassigned = product_service.category_view(products)
    elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
    print(f"MEASURED {CATEGORIES} دسته و {len(products)} محصول: {len(_statements)} statement · گروه‌بندیِ Python {elapsed_ms}ms")
    assert len(names) == CATEGORIES and not unassigned, len(names)
    assert sum(len(items) for items in groups.values()) == len(products)
    assert elapsed_ms < 400.0, elapsed_ms
    print("PASS test_category_grouping_cost")


# ============================================================================= ۴ —HTTP
async def _asgi(app, path: str, headers: list[tuple[bytes, bytes]]):
    scope = {
        "type": "http", "asgi": {"version": "3.0", "spec_version": "2.3"}, "http_version": "1.1",
        "method": "GET", "scheme": "http", "path": path, "raw_path": path.encode(),
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


async def test_http_paths_are_cheap_and_secret_free() -> None:
    shop_bot_id = await _seed_shop()
    _attach_counter()
    now = dt.datetime.now(UTC)
    async with session_scope() as session:
        for index in range(60):
            session.add(
                RuntimeCounterSnapshot(
                    process_key=f"panel-worker-{index}:1", hostname="panel",
                    counters=json.dumps({"webhook.shop": index}), updated_at=now,
                )
            )
        await session.commit()
    observability.count("webhook.shop", 3)
    health_app = app_main.build_health_app()
    previous = settings.metrics_token
    try:
        settings.metrics_token = "probe-token"
        _statements.clear()
        started = time.perf_counter()
        status, metrics_body = await _asgi(health_app, "/metrics", [(b"x-metrics-token", b"probe-token")])
        metrics_ms = round((time.perf_counter() - started) * 1000, 1)
        metrics_stmts = len(_statements)

        _statements.clear()
        started = time.perf_counter()
        status2, ops_body = await _asgi(health_app, "/ops/status", [(b"x-metrics-token", b"probe-token")])
        ops_ms = round((time.perf_counter() - started) * 1000, 1)
        ops_stmts = len(_statements)
    finally:
        settings.metrics_token = previous
    assert status == 200 and status2 == 200, (status, status2)
    print(f"MEASURED /metrics: {len(metrics_body)} بایت · {metrics_ms}ms · {metrics_stmts} statement (باید صفر باشد)")
    print(f"MEASURED /ops/status: {len(ops_body)} بایت · {ops_ms}ms · {ops_stmts} statement")
    assert metrics_stmts == 0, metrics_stmts
    assert ops_stmts <= 30, ops_stmts  # snapshot + inspect (پرس‌وجوهایِ ثابتِ خودِ عیب‌یاب)
    for banned in ("encrypted_token", "webhook_secret", "merchant_id", "probe-token"):
        assert banned not in ops_body.decode("utf-8", errors="replace"), banned
    print("PASS test_http_paths_are_cheap_and_secret_free")


async def main() -> None:
    await test_aggregation_with_many_workers()
    await test_block_gate_cost_with_full_list()
    await test_category_grouping_cost()
    await test_http_paths_are_cheap_and_secret_free()


if __name__ == "__main__":
    asyncio.run(main())
