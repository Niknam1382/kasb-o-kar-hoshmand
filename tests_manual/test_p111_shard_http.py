"""پ۱۱۱ · شاردبندیِ کاملِ polling + بارسنجیِ HTTPِ واقعی.

ادعاها:
۱. فیلترِ *SQL* شارد با همان تقسیمِ درحافظه یکی است: اجتماعِ دسته‌ها == همهٔ ردیف‌ها، هیچ
   همپوشانیِ دوتایی، و با `SHARD_COUNT=1` خروجی و کوئری دقیقاً مثلِ قبل (هیچ شرطِ تازه نمی‌آید).
۲. لاگِ صادق: `count_active` جمعِ کلِ ردیف‌هایِ فعال را می‌دهد، پس «X از Y» در دیپلویِ شاردشده
   گمراه‌کننده نمی‌شود.
۳. قفل‌هایِ شارد *مستقل*اند: دو شاردِ متفاوت هم‌زمان گرفته می‌شوند (پس N پروسهٔ poller ممکن است)
   و دو درخواستِ یکِ شارد ⇒ دقیقاً یکِ برنده. با `SHARD_COUNT=1` عددِ قفل عوض نمی‌شود.
۴. دو لایهٔ محافظ هم‌راستاند: ورودیِ شاردشدهٔ SQL اگر به `load_all` برود، *همه*اش ثبت می‌شود
   (هیچ ردیفی دو بار فیلتر شدن نمی‌افتد).
۵. سنجه‌هایِ تازه بی‌`LOADTEST_DB_CONFIRM` اجرا نمی‌شوند و اپِ بارسنجیِ HTTP هیچ `/webhook/*` ندارد
   (پس فشارِ HTTP هرگز به تلگرام/AI/پرداخت نمی‌رسد).

اجرا: python3 tests_manual/run_one.py test_p111_shard_http.py
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from sqlalchemy import select  # noqa: E402

from app.config import settings  # noqa: E402
from app.database.session import engine, session_scope  # noqa: E402
from app.main import POLLING_LOCK_KEY, acquire_polling_lock, release_polling_lock  # noqa: E402
from app.services import app_roles, shop_bot_service  # noqa: E402
from harness import reset_database  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

OWNER_BASE = 11_110_000_000
BOT_BASE = 11_110_001_000
SHOPS = 6


async def _seed_shops() -> list[int]:
    await reset_database()
    ids = []
    for index in range(SHOPS):
        ids.append(await seed_usable_shop(OWNER_BASE + index, BOT_BASE + index))
    return ids


# ============================================================================= ۱ و ۲
async def test_sql_shard_partition_and_total_count() -> None:
    ids = await _seed_shops()
    original_count, original_index = settings.shard_count, settings.shard_index
    try:
        async with session_scope() as session:
            unfiltered = sorted(bot.id for bot in await shop_bot_service.get_all_active(session))
            assert unfiltered == sorted(ids), (unfiltered, ids)
            total = await shop_bot_service.count_active(session)
            assert total == len(ids), total

        for count in (1, 2, 3, 4):
            buckets = []
            for index in range(count):
                async with session_scope() as session:
                    rows = await shop_bot_service.get_all_active(session, shard=(index, count))
                buckets.append({bot.id for bot in rows})
            covered = set().union(*buckets)
            assert covered == set(ids), f"با {count} شارد بعضی فروشگاه‌ها جا می‌مانند: {set(ids) - covered}"
            for a in range(count):
                for b in range(a + 1, count):
                    assert not (buckets[a] & buckets[b]), f"یکِ فروشگاه در دو شارد: {buckets[a] & buckets[b]}"
            # همان تقسیمِ درحافظهٔ `bot_manager` (منبعِ حقیقتِ فرمول)
            in_memory = {bot_id for bot_id in ids if bot_id % count == (0 % count)}
            assert buckets[0] == in_memory, (buckets[0], in_memory)

        # با `count<=1` هیچ شرطِ تازه‌ای به کوئری اضافه نمی‌شود ⇒ خروجی مثلِ قبل
        async with session_scope() as session:
            one = sorted(bot.id for bot in await shop_bot_service.get_all_active(session, shard=(0, 1)))
            assert one == unfiltered, "کوئریِ بدونِ شارد عوض شد"
            none = sorted(bot.id for bot in await shop_bot_service.get_all_active(session, shard=None))
            assert none == unfiltered
    finally:
        settings.shard_count, settings.shard_index = original_count, original_index
    print("PASS test_sql_shard_partition_and_total_count")


# ============================================================================= ۳
async def test_per_shard_locks_are_independent() -> None:
    original_count, original_index = settings.shard_count, settings.shard_index
    try:
        settings.shard_count = 4
        keys = set()
        for index in range(4):
            settings.shard_index = index
            keys.add(app_roles.lock_key(POLLING_LOCK_KEY))
        assert len(keys) == 4, keys
        assert POLLING_LOCK_KEY not in keys, "با شاردِ چهارتایی کلیدِ امروز نباید استفاده شود"

        settings.shard_count = 1
        settings.shard_index = 0
        assert app_roles.lock_key(POLLING_LOCK_KEY) == POLLING_LOCK_KEY, "تک‌پروسه ⇒ همان کلیدِ همیشگی"

        settings.shard_count, settings.shard_index = 4, 0
        first_key = app_roles.lock_key(POLLING_LOCK_KEY)
        settings.shard_index = 1
        second_key = app_roles.lock_key(POLLING_LOCK_KEY)
        settings.shard_index = 0

        first = await acquire_polling_lock(first_key)
        assert first is not None, "شاردِ صفر باید قفل بگیرد"
        second = await acquire_polling_lock(second_key)
        assert second is not None, "دو شاردِ متفاوت نباید همدیگر را مهار کنند"
        same_shard = await acquire_polling_lock(first_key)
        assert same_shard is None, "دو پروسهٔ یکِ شارد ⇒ فقط یکِ polling"
        await release_polling_lock(second, second_key)
        await release_polling_lock(first, first_key)
        reopened = await acquire_polling_lock(first_key)
        assert reopened is not None, "بعد ازِ آزادکردن، قفلِ شارد دوباره در دسترس است"
        await release_polling_lock(reopened, first_key)
    finally:
        settings.shard_count, settings.shard_index = original_count, original_index
        await engine.dispose()
    print("PASS test_per_shard_locks_are_independent")


# ============================================================================= ۴
async def test_sql_shard_and_load_all_agree() -> None:
    from app.services.bot_manager import ShopBotManager

    ids = await _seed_shops()
    original_mode, original_count, original_index = settings.run_mode, settings.shard_count, settings.shard_index
    registered: list[int] = []

    async def _fake_register(shop_bot) -> None:
        registered.append(shop_bot.id)

    manager = ShopBotManager(None)
    manager.register = _fake_register  # type: ignore[method-assign]
    manager.register_bale = _fake_register  # type: ignore[method-assign]
    try:
        from app.config import RunMode  # noqa: PLC0415

        settings.run_mode = RunMode.POLLING
        settings.shard_count, settings.shard_index = 2, 0
        async with session_scope() as session:
            rows = await shop_bot_service.get_all_active(session, shard=(0, 2))
        registered.clear()
        await manager.load_all(rows, bale_enabled=False)
        assert sorted(registered) == sorted(bot.id for bot in rows), (
            "دو لایهٔ فیلتر با هم نمی‌خوانند: چیزی که SQL داد، load_all دور ریخت"
        )
        assert registered, "کوئریِ شارد صفر ردیف نداشت"
        assert all(shop_bot_id % 2 == 0 for shop_bot_id in registered), registered
        assert len(registered) < len(ids), "با SHARD_COUNT=2 نباید همه در یکِ پروسه بنشینند"
    finally:
        settings.run_mode, settings.shard_count, settings.shard_index = original_mode, original_count, original_index
    print("PASS test_sql_shard_and_load_all_agree")


# ============================================================================= ۵
async def test_probes_are_guarded_and_http_app_has_no_side_effects() -> None:
    import os

    sys.path.insert(0, "scripts")
    import http_load_probe  # noqa: E402
    import two_process_probe as probe  # noqa: E402

    had = os.environ.pop("LOADTEST_DB_CONFIRM", None)
    try:
        for module in (probe, http_load_probe):
            code = 0
            try:
                module._guard()
            except SystemExit as exc:
                code = int(exc.code or 2)
            assert code == 2, (module.__name__, code)
    finally:
        if had is not None:
            os.environ["LOADTEST_DB_CONFIRM"] = had

    paths = set()

    def _walk(routes) -> None:
        for route in routes:
            path = getattr(route, "path", None)
            if path:
                paths.add(path)
            for attr in ("routes", "original_router", "router"):
                nested = getattr(route, attr, None)
                if nested is not None and hasattr(nested, "routes"):
                    _walk(nested.routes)

    _walk(http_load_probe.build_app().routes)
    assert not any(item.startswith("/webhook") for item in paths), sorted(paths)
    assert paths <= {"/health", "/metrics", "/ops/status", "/panel", "/ws/ops"}, sorted(paths)
    assert "/health" in paths and "/panel" in paths, sorted(paths)

    endpoint_names = [name for name, *_ in http_load_probe._endpoints()]
    for required in ("health", "metrics", "ops/status", "panel", "web/login-bad", "webhook-unsigned"):
        assert required in endpoint_names, required
    print(f"MEASURED مسیرهایِ بارسنجی: {len(endpoint_names)} · مسیرهایِ اپِ سلامت: {len(paths)}")
    print("PASS test_probes_are_guarded_and_http_app_has_no_side_effects")


async def main() -> None:
    await test_sql_shard_partition_and_total_count()
    await test_per_shard_locks_are_independent()
    await test_sql_shard_and_load_all_agree()
    await test_probes_are_guarded_and_http_app_has_no_side_effects()
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
