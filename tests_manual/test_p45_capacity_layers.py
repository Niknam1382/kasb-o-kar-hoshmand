"""
تست: P45 · ظرفیت — نقشِ پروسه، شارد، وب‌هوکِ بی‌حالت و ریاضِ لایه‌ها

۱. تقسیمِ شارد دقیق است (هیچ فروشنده‌ای جا نمی‌ماند و هیچ‌کدام دو پروسه ندارد) و کلیدِ قفلِ
   advisory با `SHARD_COUNT=1` دقیقاً همان عددِ امروز است (قفل‌هایِ موجود عوض نمی‌شوند).
۲. نقش‌ها: `core` جاب‌ها و پنلِ مرکزی را نگه می‌دارد، `poller` فقط ربات‌هایِ شاردِ خودش را،
   و نقشِ ناشناخته به `all` برمی‌گردد (پیکربندیِ غلط نباید سرویس را از کار بیندازد).
۳. `load_all` در حالتِ polling فقط شاردِ خودی را ثبت می‌کند (نه تلگرام، نه بلهِ بقیه).
۴. مسیرِ webhook به ثبتِ اولیه وابسته نیست: ربات و رازِ وب‌هوک از دیتابیس خوانده و در LRU
   می‌نشینند؛ فروشگاهِ غیرفعال یا ناشناخته None می‌دهد و استخرِ HTTP بینِ ربات‌ها مشترک است.
۵. `update_dedupe` همان آپدیت را دو بار «مالک» نمی‌داند و ردیف‌هایِ کهنه پاک می‌شوند.
۶. ریاضِ `scripts/scale_readiness.py` با عددهایِ مستندات می‌خواند (۴۰÷۳ ⇒ ~۴۰۰ کاربر).
۷. فایل‌هایِ `deploy/*.yml` پارس‌شدنی‌اند و جمعِ اتصال‌هایشان از سقفِ همان لایه کمتر است.

اجرا: python3 tests_manual/run_one.py test_p45_capacity_layers.py
"""
from __future__ import annotations

import asyncio
import datetime
import sys
from pathlib import Path

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from sqlalchemy import delete, select  # noqa: E402

from harness import reset_database  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from app.config import RunMode, settings  # noqa: E402
from app.database.models import ShopBot, UpdateDedupe  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import app_roles, shop_bot_service, shop_owner_service  # noqa: E402
from app.services.bot_manager import ShopBotManager  # noqa: E402
from app.services.update_dedupe_service import claim as dedupe_claim, prune as dedupe_prune  # noqa: E402

OWNER_BASE = 7_445_000_000
BOT_BASE = 7_445_100_000
FAKE_TOKEN_TAIL = "P45FAKETOKENTHISISAVALIDTOKENAFTERCOLON"  # ≥۳۰ نویسه بعد از دونقطه (قاعدهٔ aiogram)


def _token(bot_telegram_id: int) -> str:
    return f"{bot_telegram_id}:{FAKE_TOKEN_TAIL}"


async def _make_shop(index: int) -> int:
    """یکِ فروشگاهِ تازه (صاحب + ربات) با توکنِ قابلِ رمزگشایی؛ شناسهٔ ربات را برمی‌گرداند."""
    owner_tg_id = OWNER_BASE + index
    bot_tg_id = BOT_BASE + index
    async with session_scope() as session:
        owner = await shop_owner_service.get_or_create_shop_owner(session, owner_tg_id)
        shop_bot = await shop_bot_service.upsert_shop_bot(session, owner, _token(bot_tg_id), bot_tg_id, f"shop_{index}")
        return shop_bot.id


async def _active_shop_ids() -> list[int]:
    async with session_scope() as session:
        return sorted((await session.execute(select(ShopBot.id))).scalars().all())


async def _set_shard(count: int, index: int, role: str = "poller") -> None:
    settings.shard_count = count
    settings.shard_index = index
    settings.app_role = role


# ============================================================================= ۱ — شارد و قفل
def test_shard_partition_and_lock_keys() -> None:
    ids = list(range(1, 61))
    for count in (1, 2, 4, 6):
        buckets = [{shop_id for shop_id in ids if shop_id % count == slot} for slot in range(count)]
        covered = set().union(*buckets)
        assert covered == set(ids), f"با {count} شارد بعضی فروشگاه‌ها جا می‌مانند"
        for a in range(count):
            for b in range(a + 1, count):
                assert not (buckets[a] & buckets[b]), "یکِ فروشگاه در دو پروسه نباشد"

    settings.shard_count, settings.shard_index = 1, 0
    assert app_roles.lock_key(20261103) == 20261103, "با تک‌پروسه هیچ کلیدی عوض نمی‌شود"
    settings.shard_count, settings.shard_index = 4, 0
    keys = set()
    for slot in range(4):
        settings.shard_index = slot
        keys.add(app_roles.lock_key(20261103))
    assert len(keys) == 4, f"هر شارد قفلِ خودش را دارد: {keys}"
    settings.shard_index = 0
    settings.shard_count = 1
    print("✅ test_shard_partition_and_lock_keys PASSED")


# ============================================================================= ۲ — نقش‌ها
def test_role_gating() -> None:
    settings.shard_count, settings.shard_index = 1, 0
    original_mode = settings.run_mode
    try:
        settings.run_mode = RunMode.POLLING
        settings.app_role = "all"
        assert app_roles.is_core() and app_roles.is_poller() and not app_roles.is_web()
        assert not app_roles.serves_http(), "حالتِ pollingِ تک‌پروسه همان رفتارِ امروز است"
        settings.app_role = "core"
        assert app_roles.is_core() and not app_roles.is_poller()
        settings.app_role = "poller"
        assert app_roles.is_poller() and not app_roles.is_core() and not app_roles.is_web()
        settings.app_role = "web"
        assert app_roles.is_web() and not app_roles.is_core() and not app_roles.is_poller()
        assert app_roles.serves_http(), "پروسهٔ web حتی در حالتِ polling هم اپِ HTTP سرو می‌کند"

        settings.run_mode = RunMode.WEBHOOK
        settings.app_role = "all"
        assert app_roles.serves_http() and app_roles.is_core() and app_roles.is_poller()
        settings.app_role = "core"
        assert app_roles.serves_http() and not app_roles.is_poller(), "پنلِ مرکزی و جاب‌ها رویِ core می‌مانند"

        settings.app_role = "pollo"  # غلطِ تایپی ⇒ رفتارِ امروز، نه خاموش‌شدنِ سرویس
        assert app_roles.role() == "all" and app_roles.is_core() and app_roles.is_poller()
    finally:
        settings.run_mode = original_mode
        settings.app_role = "all"
    print("✅ test_role_gating PASSED")


# ============================================================================= ۳ — ثبتِ فقط شاردِ خودی
async def test_load_all_registers_only_this_shard() -> None:
    await reset_database()
    ids = [await _make_shop(i) for i in range(1, 6)]
    assert len(ids) == 5, ids

    manager = ShopBotManager(None)
    registered_telegram: list[int] = []
    registered_bale: list[int] = []

    async def _fake_register(shop_bot) -> None:
        registered_telegram.append(shop_bot.id)

    async def _fake_register_bale(shop_bot) -> None:
        registered_bale.append(shop_bot.id)

    manager.register = _fake_register  # type: ignore[method-assign]
    manager.register_bale = _fake_register_bale  # type: ignore[method-assign]

    original_mode, original_count, original_index = settings.run_mode, settings.shard_count, settings.shard_index
    try:
        settings.run_mode = RunMode.POLLING
        async with session_scope() as session:
            shop_bots = list((await session.execute(select(ShopBot).order_by(ShopBot.id))).scalars().all())

        settings.shard_count, settings.shard_index = 2, 0
        await manager.load_all(shop_bots, bale_enabled=True)
        even = {shop_bot_id for shop_bot_id in ids if shop_bot_id % 2 == 0}
        assert set(registered_telegram) == even, (registered_telegram, ids)
        assert set(registered_bale) == even, "اتصالِ بله هم شارد می‌شود، وگرنه یکِ مشتری دو بار جواب می‌گیرد"

        registered_telegram.clear()
        registered_bale.clear()
        settings.shard_count, settings.shard_index = 1, 0
        await manager.load_all(shop_bots, bale_enabled=True)
        assert set(registered_telegram) == set(ids), "با SHARD_COUNT=1 رفتارِ امروز مو‌به‌مو می‌ماند"

        registered_telegram.clear()
        settings.run_mode = RunMode.WEBHOOK
        settings.shard_count, settings.shard_index = 2, 0
        await manager.load_all(shop_bots, bale_enabled=False)
        assert set(registered_telegram) == set(ids), "در حالتِ webhook هر پروسه همه را register می‌کند (سوکتی باز نمی‌شود)"
    finally:
        settings.run_mode, settings.shard_count, settings.shard_index = original_mode, original_count, original_index
    print("✅ test_load_all_registers_only_this_shard PASSED")


# ============================================================================= ۴ — webhookِ بی‌حالت
async def test_webhook_entry_is_lazy_cached_and_bounded() -> None:
    await reset_database()
    first = await _make_shop(1)
    second = await _make_shop(2)
    original_cache = settings.webhook_bot_cache_size
    try:
        manager = ShopBotManager(None)
        settings.webhook_bot_cache_size = 400

        entry = await manager.webhook_entry(first)
        assert entry is not None and entry[0] is not None, "ربات از دیتابیس ساخته می‌شود، نه از ثبتِ اولیه"
        async with session_scope() as session:
            shop_bot = await session.get(ShopBot, first)
            secret = shop_bot.webhook_secret_token
        assert entry[1] == secret, "رازِ همان فروشگاه برگردانده می‌شود"
        again = await manager.webhook_entry(first)
        assert again[0] is entry[0], "دوباره همان آبجکت (LRU)، نه ساختِ مجدد"
        assert len(manager._webhook_bots) == 1, manager._webhook_bots

        await manager.webhook_entry(second)
        assert manager._shared_session is not None
        assert manager._shared_session._refs == 2, "استخرِ HTTP بینِ ربات‌ها مشترک است"

        settings.webhook_bot_cache_size = 1
        await manager.webhook_entry(first)
        assert len(manager._webhook_bots) == 1, "سقفِ LRU رعایت می‌شود (رم با فروشگاهِ پرمصرف رشد می‌کند، نه با تعدادِ کل)"

        assert await manager.webhook_entry(9_999_999) is None, "فروشگاهِ نبود ⇒ None (نه خطا)"
        async with session_scope() as session:
            inactive = await session.get(ShopBot, second)
            inactive.is_active = False
        manager._webhook_bots.clear()
        manager._webhook_secrets.clear()
        assert await manager.webhook_entry(second) is None, "فروشگاهِ غیرفعال از این مسیر جواب نمی‌دهد"
    finally:
        settings.webhook_bot_cache_size = original_cache
    print("✅ test_webhook_entry_is_lazy_cached_and_bounded PASSED")


# ============================================================================= ۵ — dedupe
async def test_update_dedupe_claims_once_and_prunes() -> None:
    await reset_database()
    bot_id = 7_445_999_001
    assert await dedupe_claim(bot_id, 555) is True, "اولینِ دیدن مالکیت می‌دهد"
    assert await dedupe_claim(bot_id, 555) is False, "دوباره‌دریافتِ همان update_id نباید دوباره پردازش شود"
    assert await dedupe_claim(bot_id, 556) is True, "آپدیتِ تازه مالکیت می‌دهد"

    old = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=2)
    async with session_scope() as session:
        session.add(UpdateDedupe(bot_id=bot_id, update_id=404, seen_at=old))
    async with session_scope() as session:
        removed = await dedupe_prune(session)
    assert removed == 1, removed
    async with session_scope() as session:
        left = list((await session.execute(select(UpdateDedupe.update_id).where(UpdateDedupe.bot_id == bot_id))).scalars().all())
    assert 404 not in left and 555 in left, left
    async with session_scope() as session:
        await session.execute(delete(UpdateDedupe).where(UpdateDedupe.bot_id == bot_id))
    print("✅ test_update_dedupe_claims_once_and_prunes PASSED")


# ============================================================================= ۶ — ریاضِ لایه‌ها
def test_scale_readiness_math() -> None:
    sys.path.insert(0, "scripts")
    import scale_readiness as sr  # noqa: N817

    assert sr.poller_processes(1500, 250) == 6
    assert sr.poller_processes(249, 250) == 1
    assert abs(sr.ram_for_poller(250) - (sr.BASE_RSS_MB + 250 * sr.MB_PER_BOT)) < 1e-6
    # همان فرمولِ مستندات: سقفِ ۴۰ با تأخیرِ ۳ ثانیه ⇒ ~۱۳ پیام/ثانیه ⇒ ~۴۰۰ کاربرِ هم‌زمان
    assert 380 <= sr.users_supported(40, 3.0) <= 420, sr.users_supported(40, 3.0)
    assert 120 <= sr.ai_concurrency_needed(1000, 4.0) <= 140, sr.ai_concurrency_needed(1000, 4.0)
    assert sr.users_supported(130, 4.0) >= 900, "با سقفِ ~۱۳۰ درخواستِ هم‌زمان، ۱٬۰۰۰ نفر جا می‌شوند"
    print("✅ test_scale_readiness_math PASSED")


# ============================================================================= ۷ — فایل‌هایِ لایه‌ها
def test_deploy_overlays_parse_and_fit_their_connection_budget() -> None:
    import yaml

    root = Path("deploy")
    t2 = yaml.safe_load((root / "docker-compose.t2.yml").read_text(encoding="utf-8"))
    t3 = yaml.safe_load((root / "docker-compose.t3.yml").read_text(encoding="utf-8"))
    web = yaml.safe_load((root / "docker-compose.webhook.yml").read_text(encoding="utf-8"))

    for name, doc in (("t2", t2), ("t3", t3), ("webhook", web)):
        assert "services" in doc and doc["services"], name

    def pollers(doc) -> list[dict]:
        out = []
        for key, service in doc["services"].items():
            env = service.get("environment") or {}
            if env.get("APP_ROLE") == "poller":
                out.append(env)
        return out

    for name, doc, max_connections in (("t2", t2, 100), ("t3", t3, 200)):
        rows = pollers(doc)
        counts = {int(env["SHARD_COUNT"]) for env in rows}
        assert len(counts) == 1, (name, counts)
        count = counts.pop()
        assert len(rows) == count, f"{name}: {len(rows)} پروسه برایِ {count} شارد"
        assert sorted(int(env["SHARD_INDEX"]) for env in rows) == list(range(count)), name
        core_pool = int((doc["services"]["bot"]["environment"] or {})["DB_POOL_SIZE"])
        budget = sum(int(env["DB_POOL_SIZE"]) for env in rows) + core_pool + 15
        assert budget < max_connections, f"{name}: {budget} اتصال > {max_connections}"
        assert all(env.get("SHARD_INDEX") is not None for env in rows)

    assert t3["services"]["db"]["command"].count("max_connections=200") == 1, "لایهٔ ۳ سقفِ اتصال را بالا می‌برد"
    web_services = web["services"]
    assert web_services["bot"]["environment"]["APP_ROLE"] == "core", "وب‌هوک هم فقط یکِ core دارد"
    assert sum(1 for s in web_services.values() if (s.get("environment") or {}).get("APP_ROLE") == "web") == 2
    assert "caddy" in web_services, "پراکسیِ HTTPS در همین لایه تعریف شده"
    print("✅ test_deploy_overlays_parse_and_fit_their_connection_budget PASSED")


async def main() -> None:
    test_shard_partition_and_lock_keys()
    test_role_gating()
    await test_load_all_registers_only_this_shard()
    await test_webhook_entry_is_lazy_cached_and_bounded()
    await test_update_dedupe_claims_once_and_prunes()
    test_scale_readiness_math()
    test_deploy_overlays_parse_and_fit_their_connection_budget()


if __name__ == "__main__":
    asyncio.run(main())
