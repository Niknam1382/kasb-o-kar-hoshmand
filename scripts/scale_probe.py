#!/usr/bin/env python3
"""سنجشِ مقیاسِ ۵۰۰ فروشگاه (P29-A) — ادعا قبل از عدد مجاز نیست.

چرا این اسکریپت هست: «تا ۵۰۰ فروشگاه هم‌زمان» را نمی‌شود با حدس گفت. چهار چیزی که با N
بزرگ می‌شوند را رویِ دیتابیسِ تست (`kasbokar_test`) می‌سنجد و به هیچ سرویسِ بیرونی درخواست
نمی‌زند (همه‌یِ تماس‌هایِ تلگرام از FakeSessionِ خودِ سوئیتِ تست رد می‌شوند):

  ۱) راه‌اندازی: `bot_manager.load_all()` — زمانِ خالصِ کد + زمانِ رسیدنِ همهٔ ربات‌ها به
     اولین delete_webhook + اوجِ درخواست‌هایِ هم‌زمان + تعدادِ درخواستِ تلگرام به‌ازایِ هر ربات
     (RTT شبیه‌سازی‌شده با `--rtt-ms`)
  ۲) رم و فهرستِ فایلِ باز: هزینهٔ خودِ N آبجکتِ `Bot` + session (بدونِ هیچ ترافیکی)
  ۳) مسیرِ یکِ پیامِ مشتری: تعدادِ statement‌هایِ SQL به‌ازایِ هر پیام و آیا با N رشد می‌کند
  ۴) یکِ پاسِ کاملِ جابِ دوره‌ای (سرد = نوبتِ همهٔ ربات‌ها رسیده، گرم = نرسیده)

اجرا (داخلِ کانتینر؛ `bot` باید خاموش باشد که جاب دو نسخه نشود):
    docker compose stop bot
    docker compose run --rm bot python3 scripts/scale_probe.py --sizes 1,50,200,500
"""
from __future__ import annotations

import argparse
import asyncio
import datetime
import gc
import os
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests_manual"))

import db_env  # noqa: E402

os.environ["DATABASE_URL"] = db_env.test_database_url()
os.environ.setdefault("ADMIN_TELEGRAM_IDS", "12345")

from sqlalchemy import delete, event, func, select, text  # noqa: E402

from harness import FakeSession, build_test_dispatchers, reset_database  # noqa: E402

from app.database.models import (  # noqa: E402
    ConversationMessage,
    Customer,
    Product,
    ShopBot,
    ShopOwner,
    WalletCharge,
    WalletTransaction,
    WalletTransactionReason,
)
from app.database.session import engine, session_scope  # noqa: E402
from app.services import (  # noqa: E402
    conversation_service,
    customer_service,
    platform_service,
    shop_bot_service,
    wallet_service,
)
from app.bots.shop_bot import middlewares as shop_middlewares  # noqa: E402
from app.utils.encryption import encrypt_token  # noqa: E402

OWNER_PREFIX = 9_000_000  # همان قاعده‌ای که loadtest_message_path.py برای ردیف‌های بار استفاده می‌کند
BOT_PREFIX = 900_000_000
CUSTOMER_PREFIX = 910_000_000
DEDUCT_TOMAN = 250
SEED_BATCH = 25

_SESSIONS: dict[str, object] = {}


def shared_sessions() -> tuple:
    """`build_test_dispatchers()` فقط یک‌بار در هر پروسه شدنی است (راوترها singleton‌اند)."""
    if "pair" not in _SESSIONS:
        _SESSIONS["pair"] = build_test_dispatchers()
    return _SESSIONS["pair"]


def fake_token(index: int) -> str:
    """تلگرام توکن را با قاعدهٔ `<number>:<32+ نویسه>` می‌سنجد؛ سید باید همان شکل را داشته باشد."""
    return f"{BOT_PREFIX + index}:" + "A" * 35


def rss_mib() -> float:
    try:
        with open("/proc/self/status", encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) / 1024.0
    except OSError:
        pass
    import resource

    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


def open_fds() -> int:
    try:
        return len(os.listdir("/proc/self/fd"))
    except OSError:
        return -1


class SqlCount:
    """شمارشِ statement‌هایِ SQL در یکِ پنجره (برایِ پیداکردنِ N+1 و رشدِ خطی با N)."""

    calls: dict[str, int] = {}
    total = 0
    active = False
    installed = False

    @classmethod
    def _listener(cls, conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001, ARG002
        if not cls.active:
            return
        cls.total += 1
        key = " ".join(statement.split())[:90]
        cls.calls[key] = cls.calls.get(key, 0) + 1

    @classmethod
    def install(cls) -> None:
        if not cls.installed:
            event.listen(engine.sync_engine, "before_cursor_execute", cls._listener)
            cls.installed = True


class Window:
    """`with Window() as w:` ⇒ فقط statement‌هایِ داخلِ پنجره شمرده می‌شوند."""

    def __enter__(self) -> "Window":
        SqlCount.install()
        SqlCount.calls = {}
        SqlCount.total = 0
        SqlCount.active = True
        return self

    def __exit__(self, *exc_info) -> None:
        SqlCount.active = False

    @property
    def statements(self) -> int:
        return SqlCount.total

    def top(self, limit: int = 6) -> list[tuple[int, str]]:
        return sorted(((c, s) for s, c in SqlCount.calls.items()), reverse=True)[:limit]


class ProbeSession(FakeSession):
    """FakeSession + شمارشِ درخواست‌ها + خوابیدن به‌اندازهٔ RTT، تا مدلِ شبکه واقع‌گرایانه بماند.

    هیچ بایتی از این جلسه به بیرون نمی‌رود؛ فقط اسمِ متد، تعداد، اوجِ هم‌زمانی و تأخیرِ شبیه‌سازی‌شده ثبت می‌شود.
    """

    rtt_s = 0.0
    longpoll_s = 0.0
    calls: dict[str, int] = {}
    inflight: dict[str, int] = {}
    peak: dict[str, int] = {}
    ready_bots = 0
    first_at: dict[str, float] = {}

    @classmethod
    def reset(cls) -> None:
        cls.calls = {}
        cls.inflight = {}
        cls.peak = {}
        cls.ready_bots = 0
        cls.first_at = {}

    async def make_request(self, bot, method, timeout=None):  # noqa: ANN001
        name = type(method).__name__
        ProbeSession.calls[name] = ProbeSession.calls.get(name, 0) + 1
        ProbeSession.inflight[name] = ProbeSession.inflight.get(name, 0) + 1
        ProbeSession.peak[name] = max(ProbeSession.peak.get(name, 0), ProbeSession.inflight[name])
        ProbeSession.first_at.setdefault(name, time.perf_counter())
        delay = ProbeSession.rtt_s + (ProbeSession.longpoll_s if name == "GetUpdates" else 0.0)
        try:
            if delay:
                await asyncio.sleep(delay)
            return await super().make_request(bot, method, timeout)
        finally:
            ProbeSession.inflight[name] -= 1
            if name == "DeleteWebhook":
                ProbeSession.ready_bots += 1


async def seed_more(count: int, *, customers_per_shop: int, products_per_shop: int) -> None:
    """count فروشگاهِ تازه (مالک + ربات + مشتری + محصول)؛ موجودی از خودِ add_charge تا دفتر سازگار بماند."""
    async with session_scope() as session:
        already = int(
            (await session.execute(select(func.count(ShopOwner.id)).where(ShopOwner.telegram_id >= OWNER_PREFIX))).scalar_one()
        )
    index = OWNER_PREFIX + already
    for done in range(0, count, SEED_BATCH):
        batch = min(SEED_BATCH, count - done)
        async with session_scope() as session:
            owners = []
            for offset in range(batch):
                owners.append(
                    ShopOwner(
                        telegram_id=index + offset,
                        first_name=f"probe-{index + offset}",
                        referral_code=f"P{index + offset}",
                        registration_completed=True,
                        wallet_balance_toman=0,
                    )
                )
            session.add_all(owners)
            await session.flush()
            bots = []
            for owner in owners:
                await wallet_service.add_charge(
                    session, owner, 5_000_000, reason=WalletTransactionReason.TOPUP, reference=f"probe:{owner.telegram_id}"
                )
                bots.append(
                    ShopBot(
                        shop_owner_id=owner.id,
                        encrypted_token=encrypt_token(fake_token(owner.telegram_id)),
                        bot_telegram_id=BOT_PREFIX + owner.telegram_id,
                        bot_username=f"probe_bot_{owner.telegram_id}",
                        webhook_secret_token="probe-secret",
                    )
                )
            session.add_all(bots)
            await session.flush()
            rows = []
            for position, bot in enumerate(bots):
                base = CUSTOMER_PREFIX + (index + position) * 1000
                for c in range(customers_per_shop):
                    rows.append(Customer(shop_bot_id=bot.id, telegram_id=base + c))
                for p in range(products_per_shop):
                    rows.append(
                        Product(
                            shop_bot_id=bot.id,
                            name=f"محصول {p}",
                            price_toman=100_000 + p,
                            stock_quantity=100,
                            is_active=True,
                        )
                    )
            session.add_all(rows)
        index += batch


async def cleanup_probe_rows() -> int:
    async with session_scope() as session:
        owner_ids = list((await session.execute(select(ShopOwner.id).where(ShopOwner.telegram_id >= OWNER_PREFIX))).scalars().all())
        bot_ids = list((await session.execute(select(ShopBot.id).where(ShopBot.bot_telegram_id >= BOT_PREFIX))).scalars().all())
        customer_ids = (
            list((await session.execute(select(Customer.id).where(Customer.shop_bot_id.in_(bot_ids)))).scalars().all())
            if bot_ids
            else []
        )
        if customer_ids:
            await session.execute(delete(ConversationMessage).where(ConversationMessage.customer_id.in_(customer_ids)))
            await session.execute(delete(Customer).where(Customer.id.in_(customer_ids)))
        if bot_ids:
            await session.execute(delete(ShopBot).where(ShopBot.id.in_(bot_ids)))
        if owner_ids:
            await session.execute(delete(WalletTransaction).where(WalletTransaction.shop_owner_id.in_(owner_ids)))
            await session.execute(delete(WalletCharge).where(WalletCharge.shop_owner_id.in_(owner_ids)))
            await session.execute(delete(ShopOwner).where(ShopOwner.id.in_(owner_ids)))
        left = int(
            (await session.execute(select(func.count()).select_from(ShopOwner).where(ShopOwner.telegram_id >= OWNER_PREFIX))).scalar_one()
        )
    return left


async def load_probe_bots(limit: int) -> list[ShopBot]:
    async with session_scope() as session:
        return list(
            (
                await session.execute(
                    select(ShopBot).where(ShopBot.bot_telegram_id >= BOT_PREFIX).order_by(ShopBot.id).limit(limit)
                )
            ).scalars().all()
        )


async def stop_polling(manager) -> None:  # noqa: ANN001
    for task in list(manager._polling_tasks.values()):
        task.cancel()
    if manager._polling_tasks:
        await asyncio.gather(*manager._polling_tasks.values(), return_exceptions=True)


async def wait_until(predicate, timeout_s: float) -> float:
    started = time.perf_counter()
    while not predicate():
        if time.perf_counter() - started > timeout_s:
            return -1.0
        await asyncio.sleep(0.02)
    return time.perf_counter() - started


async def measure_startup(n: int, *, rtt_ms: float, longpoll_s: float, webhook_sample: int) -> dict:
    """زمانِ load_all، زمانِ آماده‌شدنِ همه، اوجِ هم‌زمانی، درخواست/ربات — + نمونهٔ حالتِ webhook."""
    import app.services.bot_manager as bot_manager_module
    from app.config import RunMode, settings
    from app.services import shop_bot_service
    from app.services.bot_manager import ShopBotManager

    # دقیقاً مثلِ _load_active_shop_bots در app/main.py: خواندنِ همهٔ ربات‌های فعال + بازنگاریِ رازها
    with Window() as boot_window:
        started = time.perf_counter()
        async with session_scope() as session:
            rows = await shop_bot_service.get_all_active(session)
            await shop_bot_service.reencrypt_secrets(session)
        boot_s = time.perf_counter() - started
    if len(rows) < n:
        raise SystemExit(f"فقط {len(rows)} رباتِ فعال در دیتابیس است (منتظرِ {n} بودیم)")
    _main_dispatcher, shop_dispatcher, _manager, _bot = shared_sessions()
    original_bot_class = bot_manager_module.Bot
    ProbeSession.reset()
    ProbeSession.rtt_s = rtt_ms / 1000.0
    ProbeSession.longpoll_s = longpoll_s
    bot_manager_module.Bot = lambda token, **kwargs: original_bot_class(token, session=ProbeSession())
    manager = ShopBotManager(shop_dispatcher)
    out: dict = {"n": n, "rtt_ms": rtt_ms, "boot_sql": boot_window.statements, "boot_s": round(boot_s, 3)}
    try:
        started = time.perf_counter()
        await manager.load_all(rows)
        out["load_all_s"] = round(time.perf_counter() - started, 3)
        out["all_ready_s"] = round(await wait_until(lambda: ProbeSession.ready_bots >= n, 120.0), 3)
        out["first_call_s"] = round(min(ProbeSession.first_at.values()) - started, 3) if ProbeSession.first_at else -1.0
        out["peak"] = dict(ProbeSession.peak)
        out["tasks"] = len(manager._polling_tasks)
        out["calls"] = dict(ProbeSession.calls)
        out["rss_mib"] = round(rss_mib(), 1)
        out["fds"] = open_fds()
        if webhook_sample:
            # در حالتِ webhook هر register قبل از بعدی منتظرِ شبکه می‌ماند ⇒ زمان = N × RTT
            await stop_polling(manager)
            ProbeSession.reset()
            mode_before = settings.run_mode
            manager2 = ShopBotManager(shop_dispatcher)
            try:
                settings.run_mode = RunMode.WEBHOOK
                started = time.perf_counter()
                await manager2.load_all(rows[:webhook_sample])
                out["webhook_sample_n"] = webhook_sample
                out["webhook_load_all_s"] = round(time.perf_counter() - started, 3)
            finally:
                await stop_polling(manager2)
                settings.run_mode = mode_before
    finally:
        await stop_polling(manager)
        bot_manager_module.Bot = original_bot_class
    return out


async def measure_bot_memory(n: int) -> dict:
    """هزینهٔ خودِ N اتصال: آبجکتِ Bot + session واقعیِ aiogram، بدونِ هیچ درخواستِ شبکه."""
    from aiogram import Bot

    gc.collect()
    before = rss_mib()
    fds_before = open_fds()
    objects = [Bot(token=f"{BOT_PREFIX + i}:" + "A" * 35) for i in range(n)]
    after = rss_mib()
    for bot in objects:
        await bot.session.close()
    objects.clear()
    gc.collect()
    return {
        "n": n,
        "delta_mib": round(after - before, 1),
        "per_bot_kib": round((after - before) * 1024 / max(1, n), 1),
        "after_close_mib": round(rss_mib() - before, 1),
        "fds_delta": open_fds() - fds_before,
    }


async def one_message(bot_telegram_id: int, customer_tid: int, note: str) -> tuple[bool, float]:
    started = time.perf_counter()
    async with session_scope() as session:
        shop_bot = await shop_bot_service.get_by_platform_bot_id(session, bot_telegram_id, bale=False)
        if shop_bot is None:
            return False, (time.perf_counter() - started) * 1000.0
        await shop_middlewares.is_blocked(
            session, ShopBot.bot_telegram_id, bot_telegram_id, customer_tid, platform_service.TELEGRAM
        )
        owner = await session.get(ShopOwner, shop_bot.shop_owner_id)
        customer = await customer_service.get_or_create_customer(session, shop_bot.id, customer_tid, None, None)
        await conversation_service.get_recent_history(session, customer.id, limit=20)
        await conversation_service.save_turn(session, customer.id, note, "پاسخِ کوتاهِ آزمایشی")
        await wallet_service.deduct(session, owner, DEDUCT_TOMAN, WalletTransactionReason.CHAT_MESSAGE)
    return True, (time.perf_counter() - started) * 1000.0


def percentile(values: list[float], share: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    index = min(len(ordered) - 1, max(0, int(round(share * (len(ordered) - 1)))))
    return ordered[index]


async def measure_messages(n: int, levels: list[int], per_level: int) -> list[dict]:
    """مسیرِ یکِ پیام با N فروشگاهِ فعال: آیا تعدادِ statement یا تأخیر با N رشد می‌کند؟"""
    bots = await load_probe_bots(n)
    async with session_scope() as session:
        pairs_rows = list(
            (
                await session.execute(
                    select(Customer.shop_bot_id, Customer.telegram_id)
                    .where(Customer.shop_bot_id.in_([b.id for b in bots]))
                    .order_by(Customer.id)
                )
            ).all()
            if bots
            else []
        )
    by_shop: dict[int, int] = {}
    for shop_bot_id, telegram_id in pairs_rows:
        by_shop.setdefault(shop_bot_id, telegram_id)
    pairs = [(bot.bot_telegram_id, by_shop[bot.id]) for bot in bots if bot.id in by_shop]
    results: list[dict] = []
    for concurrency in levels:
        latencies: list[float] = []
        errors = 0
        with Window() as window:
            started = time.perf_counter()
            for offset in range(0, per_level, concurrency):
                batch = []
                for i in range(min(concurrency, per_level - offset)):
                    bot_tid, cust_tid = pairs[(offset + i) % len(pairs)]
                    batch.append(one_message(bot_tid, cust_tid, f"probe-{offset + i}"))
                for ok, ms in await asyncio.gather(*batch):
                    latencies.append(ms)
                    errors += 0 if ok else 1
            elapsed = time.perf_counter() - started
        results.append(
            {
                "n": n,
                "concurrency": concurrency,
                "requests": len(latencies),
                "statements_per_msg": round(window.statements / max(1, len(latencies)), 1),
                "rps": round(len(latencies) / elapsed, 1) if elapsed > 0 else 0.0,
                "p50_ms": round(percentile(latencies, 0.50), 1),
                "p95_ms": round(percentile(latencies, 0.95), 1),
                "max_ms": round(max(latencies), 1) if latencies else 0.0,
                "errors": errors,
                "top": window.top(14),
            }
        )
        if errors:
            print(f"    warning: concurrency={concurrency} ⇒ {errors} پیام خطا گرفت (استخرِ اتصال تمام کرده؟)")
    return results


async def measure_scheduler(n: int, *, cold: bool) -> dict:
    """یکِ پاسِ کاملِ جاب با N رباتِ ثبت‌شده — سرد (نوبتِ بیو همه رسیده) و گرم (نرسیده)."""
    import app.services.bot_manager as bot_manager_module
    from app.services import scheduler

    now = datetime.datetime.now(datetime.timezone.utc)
    async with session_scope() as session:
        if cold:
            await session.execute(
                text("UPDATE shop_bots SET branding_next_check_at = NULL, branding_checked_at = NULL "
                     "WHERE bot_telegram_id >= :p"),
                {"p": BOT_PREFIX},
            )
        else:
            await session.execute(
                text("UPDATE shop_bots SET branding_next_check_at = :t WHERE bot_telegram_id >= :p"),
                {"t": now + datetime.timedelta(days=2), "p": BOT_PREFIX},
            )
    rows = await load_probe_bots(n)
    from app.services.bot_manager import ShopBotManager

    main_dispatcher, shop_dispatcher, _m, main_bot = shared_sessions()
    manager = ShopBotManager(shop_dispatcher)
    main_dispatcher["bot_manager"] = manager
    original_bot_class = bot_manager_module.Bot
    ProbeSession.reset()
    bot_manager_module.Bot = lambda token, **kwargs: original_bot_class(token, session=ProbeSession())
    try:
        await manager.load_all(rows)
        # polling لازم نیست و فقط CPU می‌خورد؛ تسک‌ها را می‌بندیم و ربات‌ها ثبت‌شده می‌مانند
        await stop_polling(manager)
        ProbeSession.reset()
        with Window() as window:
            started = time.perf_counter()
            await scheduler.run_periodic_pass(main_bot, manager)
            elapsed = time.perf_counter() - started
        return {
            "n": n,
            "cold": cold,
            "seconds": round(elapsed, 3),
            "statements": window.statements,
            "per_shop": round(window.statements / max(1, n), 1),
            "telegram_calls": dict(ProbeSession.calls),
            "top": window.top(6),
        }
    finally:
        await stop_polling(manager)
        bot_manager_module.Bot = original_bot_class


def show_startup(row: dict) -> None:
    per_bot = {k: round(v / row["n"], 2) for k, v in row["calls"].items()}
    print(
        f"  boot-sql n={row['n']} statements={row['boot_sql']} seconds={row['boot_s']}s "
        f"(get_all_active + reencrypt_secrets)"
    )
    print(
        f"  startup[polling n={row['n']} rtt={row['rtt_ms']}ms] load_all={row['load_all_s']}s "
        f"all_ready={row['all_ready_s']}s first_call={row['first_call_s']}s peak={row['peak']} "
        f"tasks={row['tasks']} rss={row['rss_mib']}MiB fds={row['fds']}"
    )
    print(f"    telegram_calls_total={row['calls']} per_bot={per_bot}")
    if "webhook_load_all_s" in row:
        print(f"  startup[webhook n={row['webhook_sample_n']}] load_all={row['webhook_load_all_s']}s (sequential per bot)")


def show_messages(rows: list[dict]) -> None:
    for row in rows:
        print(
            f"  msg n={row['n']} conc={row['concurrency']:>4} req={row['requests']:>5} "
            f"stmt/msg={row['statements_per_msg']:>6} rps={row['rps']:>8} p50={row['p50_ms']:>7} "
            f"p95={row['p95_ms']:>7} max={row['max_ms']:>8} errors={row['errors']}"
        )
        for count, statement in row["top"]:
            print(f"      [{count:>5}] {statement}")


def show_scheduler(row: dict) -> None:
    tag = "cold" if row["cold"] else "warm"
    print(
        f"  scheduler[{tag} n={row['n']}] {row['seconds']}s statements={row['statements']} "
        f"per_shop={row['per_shop']} telegram_calls={row['telegram_calls']}"
    )
    for count, statement in row["top"]:
        print(f"      [{count:>5}] {statement}")


async def main(args) -> None:  # noqa: ANN001
    if not db_env.is_test_database(os.environ["DATABASE_URL"]):
        raise SystemExit("DATABASE_URL به دیتابیسِ تست نمی‌رسد؛ اجرا متوقف شد")
    db_env.prepare()
    SqlCount.install()
    await reset_database()
    sizes = [int(x) for x in args.sizes.split(",") if x.strip()]
    levels = [int(x) for x in args.levels.split(",") if x.strip()]
    pool = getattr(engine.pool, "size", lambda: "?")()
    overflow = getattr(engine.pool, "_max_overflow", "?")
    dbname = os.environ["DATABASE_URL"].rsplit("/", 1)[-1]
    print(f"== scale probe | pool={pool} overflow={overflow} db={dbname} customers/shop={args.customers} products/shop={args.products} ==")
    total = 0
    for size in sizes:
        print(f"\n### N={size}")
        if size > total:
            started = time.perf_counter()
            await seed_more(size - total, customers_per_shop=args.customers, products_per_shop=args.products)
            total = size
            print(f"  seed {size} فروشگاه در {time.perf_counter() - started:.2f}s")
        gc.collect()
        show_startup(await measure_startup(size, rtt_ms=args.rtt_ms, longpoll_s=args.longpoll, webhook_sample=args.webhook_sample))
        if args.memory:
            print(f"  bot-memory {await measure_bot_memory(size)}")
        show_messages(await measure_messages(size, levels, args.per_level))
        show_scheduler(await measure_scheduler(size, cold=True))
        show_scheduler(await measure_scheduler(size, cold=False))
    if args.keep:
        print("\n--keep: ردیف‌هایِ سید پاک نشدند")
    else:
        left = await cleanup_probe_rows()
        print(f"\nپاک‌سازی: {left} ردیفِ سید باقی ماند (باید صفر باشد)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--sizes", default="1,50,200,500", help="اندازه‌های N با کاما")
    parser.add_argument("--customers", type=int, default=8, help="مشتریِ ساختگی در هر فروشگاه")
    parser.add_argument("--products", type=int, default=5, help="محصولِ ساختگی در هر فروشگاه")
    parser.add_argument("--rtt-ms", type=float, default=250.0, help="تأخیرِ شبیه‌سازی‌شده برای هر درخواستِ تلگرام")
    parser.add_argument("--longpoll", type=float, default=5.0, help="ثانیه که get_updates در حالتِ بلند بلوکه می‌شود")
    parser.add_argument("--webhook-sample", type=int, default=0, help="چند ربات در حالتِ webhook هم سنجیده شود (۰ = خاموش)")
    parser.add_argument("--levels", default="25,100,300", help="سطح‌هایِ همزمانیِ مسیرِ پیام")
    parser.add_argument("--per-level", type=int, default=300, help="تعدادِ پیام در هر سطح")
    parser.add_argument("--memory", action="store_true", help="هزینهٔ رمِ N اتصالِ واقعی را هم بسنج")
    parser.add_argument("--keep", action="store_true", help="ردیف‌هایِ سید را در پایان پاک نکن")
    asyncio.run(main(parser.parse_args()))
