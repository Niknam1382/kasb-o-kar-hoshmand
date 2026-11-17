"""پ۱۰۴ · سنجهٔ **دو پروسه‌ایِ واقعی** (قطعهٔ کم‌خطرِ باقیِ پ۵۰).

چرا این فایل هست: تا امروز عددهایِ مقیاس این پروژه یا «چند هم‌زمان *داخلِ یکِ پروسه*» بودند
(`loadtest_*` با asyncio.gather) یا فقط *استدلال* دربارهٔ چندپروسه‌ای (پ۷۹ می‌گفت «اگر دو worker
باشند، جمعِ شمارنده‌ها درست است» و آن را در یکِ پروسه ثابت کرد). سه ادعایی که در مستندات آمده و هرگز
بینِ دو پروسهٔ واقعی سنجیده نشده بود:

۱. **انحصارِ قفلِ polling** (`pg_try_advisory_lock`): دو پروسه که هم‌زمان بالا بیایند، دقیقاً یکِ
   پروسه باید قفل را بگیرد؛ وگرنه یکِ پیامِ مشتری دو بار به AI می‌رود و **دو بار از کیف‌پول کم می‌شود**.
۲. **جمعِ شمارنده‌هایِ چندپروسه‌ای** (پ۷۹): هرِ پروسه ضربانِ خودش را می‌نویسد و خواننده باید جمعِ
   هرِ دو را ببیند (نه فقط پروسهٔ خودش).
۳. **رقابتِ مالی بینِ دو پروسه**: کسرِ کیف‌پول با `SELECT … FOR UPDATE` رویِ یکِ فروشگاه از دو پروسهٔ
   جدا ⇒ موجودیِ منفی نمی‌شود، هیچ شارژی دو بار مصرف نمی‌شود و جمعِ برداشت‌ها = مجموعِ موفق‌ها.

ایمنی (مثلِ `loadtest_*`، سخت و عمدی):
- تا `LOADTEST_DB_CONFIRM=1` ست نشود **اجرا نمی‌شود**؛ رویِ دیتابیسِ اصلی هرگز اجراش نکن.
- هیچ پیامِ تلگرامی، هیچ فراخوانِ AI، هیچ پرداختِ واقعی. ردیف‌هایِ بار با
  `telegram_id >= 9_400_000` ساخته و در پایان پاک می‌شوند.

دستور (رویِ دیتابیسِ جدا):
    docker compose exec -T db createdb -U postgres kasbokar_load
    docker compose run --rm -e DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/kasbokar_load bot alembic upgrade head
    docker compose run --rm -e DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/kasbokar_load \\
        -e LOADTEST_DB_CONFIRM=1 bot python3 scripts/two_process_probe.py --parts lock,counters,money --workers 8

خروجی: سه بخشِ برچسب‌دار (MEASURED) + کدِ خروج (۰ = همهٔ ادعاها برقرار · ۲ = قفل ایمنی · ۱ = ادعایی شکست).
"""

from __future__ import annotations

import argparse
import asyncio
import multiprocessing as mp
import os
import statistics
import sys
import time

sys.path.insert(0, ".")

SEED_PREFIX = 9_400_000  # شناسه‌هایِ ساختگی، دور از دادهٔ واقعی
LOCK_HOLD_SECONDS = 1.2


def _guard() -> None:
    if os.environ.get("LOADTEST_DB_CONFIRM") != "1":
        print(
            "LOADTEST_DB_CONFIRM=1 لازم است: این سنجه دیتابیس را می‌نویسد و پاک می‌کند. "
            "رویِ دیتابیسِ اصلی/تولیدی هرگز اجرا نکن (اول `createdb` و `alembic upgrade head` رویِ دیتابیسِ جدا)."
        )
        raise SystemExit(2)
    from app.config import settings

    name = str(settings.database_url).rsplit("/", 1)[-1]
    if name in {"kasbokar", "postgres"}:
        print(f"⛔️ دیتابیسِ «{name}» مجاز نیست — یکِ دیتابیسِ جدا (مثلاً kasbokar_load) بده.")
        raise SystemExit(2)


# ============================================================================= ۱ · قفل
async def _lock_worker(slot: int, out: dict) -> None:
    """سعی برایِ گرفتنِ قفلِ polling؛ نتیجه را در out می‌نویسد (بدونِ هر اثرِ بیرونی)."""
    from app.main import POLLING_LOCK_KEY, acquire_polling_lock, release_polling_lock

    connection = await acquire_polling_lock(POLLING_LOCK_KEY)
    out["slot"] = slot
    out["acquired"] = connection is not None
    if connection is not None:
        await asyncio.sleep(LOCK_HOLD_SECONDS)
        await release_polling_lock(connection, POLLING_LOCK_KEY)
    from app.database.session import engine

    await engine.dispose()


def _lock_process(slot: int, q) -> None:
    result: dict = {"slot": slot, "acquired": False}
    try:
        asyncio.run(_lock_worker(slot, result))
    except BaseException as exc:  # noqa: BLE001
        result["error"] = f"{type(exc).__name__}: {str(exc)[:180]}"
    q.put(result)


async def probe_lock(processes: int) -> bool:
    started = time.perf_counter()
    context = mp.get_context("spawn")
    queue = context.Queue()
    procs = [context.Process(target=_lock_process, args=(index, queue)) for index in range(processes)]
    for proc in procs:
        proc.start()
    for proc in procs:
        proc.join(LOCK_HOLD_SECONDS + 20)
    got = [queue.get(timeout=20) for _ in procs]
    winners = sum(1 for item in got if item.get("acquired"))
    print(
        f"MEASURED قفلِ polling بینِ {processes} پروسه: {winners} برنده · "
        f"برندگان={sorted(item['slot'] for item in got if item.get('acquired'))} · "
        f"{int((time.perf_counter() - started) * 1000)} ms"
    )
    if winners != 1:
        print("❌ ادعایِ انحصار شکست: یا هیچ‌کس قفل نگرفت یا بیش از یکِ پروسه گرفت ⇒ دو polling = دو کسرِ کیف‌پول.")
        return False
    return True


# ============================================================================= ۲ · شمارنده‌ها
async def _publish_worker(slot: int, events: int, out: dict) -> None:
    from app.database.session import engine, session_scope
    from app.observability import count
    from app.services import capacity_service

    count("webhook.messages", events + slot)
    async with session_scope() as session:
        await capacity_service.publish_counters(session)
        await session.commit()
    out["slot"] = slot
    out["value"] = events + slot
    await engine.dispose()


def _publish_process(slot: int, events: int, q) -> None:
    result: dict = {"slot": slot, "value": 0}
    try:
        asyncio.run(_publish_worker(slot, events, result))
    except BaseException as exc:  # noqa: BLE001 — مرگِ بی‌صدای پروسهٔ فرزند بدترین حالتِ یکِ سنجه است
        result["error"] = f"{type(exc).__name__}: {str(exc)[:180]}"
    q.put(result)


async def probe_counters(processes: int) -> bool:
    context = mp.get_context("spawn")
    queue = context.Queue()
    per_process = [10 * (index + 1) for index in range(processes)]
    procs = [context.Process(target=_publish_process, args=(index, per_process[index], queue)) for index in range(processes)]
    for proc in procs:
        proc.start()
    for proc in procs:
        proc.join(30)
    got = [queue.get(timeout=20) for _ in procs]
    for item in got:
        if item.get("error"):
            print("⚠️ پروسهٔ فرزند:", item["slot"], item["error"])
    expected = sum(item["value"] for item in got)
    from app.database.session import session_scope
    from app.services import capacity_service

    async with session_scope() as session:
        totals, live, stale = await capacity_service.aggregate_counters(session)
        await session.commit()
    messages = int(totals.get("webhook.messages", 0))
    print(
        f"MEASURED جمعِ شمارنده‌ها: انتظِار {expected} · خوانده‌شده {messages} · پروسه‌هایِ زنده {live} · "
        f"ردیفِ بی‌ضربان {stale}"
    )
    ok = messages >= expected and live >= processes
    if not ok:
        print("❌ جمعِ چندپروسه‌ای درست نیست (کم‌گوییِ بی‌صدا در پنلِ عملیاتی).")
    from app.database.session import engine

    await engine.dispose()
    return ok


# ============================================================================= ۳ · رقابتِ مالی
async def _money_worker(slot: int, attempts: int, shop_owner_tg: int, out: dict) -> None:
    from sqlalchemy import select

    from app.database.models import ShopOwner, WalletTransactionReason
    from app.database.session import engine, session_scope
    from app.services import wallet_service

    succeeded = 0
    errors: list[str] = []
    latencies: list[int] = []
    async with session_scope() as session:
        owner_id = (
            await session.execute(select(ShopOwner.id).where(ShopOwner.telegram_id == shop_owner_tg))
        ).scalar_one()
        await session.commit()
    for _ in range(attempts):
        started = time.perf_counter()
        try:
            async with session_scope() as session:
                owner = await session.get(ShopOwner, owner_id)
                # نکته: `deduct` برایِ «موجودی کم است» استثنا نمی‌دهد، **False** برمی‌گرداند.
                # شمردنِ «بدونِ استثنا = موفق» خودِ همین سنجه را دروغگو می‌کرد (پ۱۰۴).
                charged = await wallet_service.deduct(
                    session,
                    owner,
                    amount_toman=1_000,
                    reason=WalletTransactionReason.CHAT_MESSAGE,
                    idempotency_key=f"p104-{slot}-{time.time_ns()}",
                )
                if charged:
                    succeeded += 1
                else:
                    errors.append("deduct=False")
                await session.commit()
        except Exception as exc:  # noqa: BLE001 — نامِ خطا گزارش می‌شود، نه بلعیده
            errors.append(type(exc).__name__)
        latencies.append(int((time.perf_counter() - started) * 1000))
    out.update({"slot": slot, "succeeded": succeeded, "errors": errors, "latencies": latencies})
    await engine.dispose()


def _money_process(slot: int, attempts: int, shop_owner_tg: int, q) -> None:
    result: dict = {"slot": slot, "succeeded": 0, "errors": [], "latencies": []}
    try:
        asyncio.run(_money_worker(slot, attempts, shop_owner_tg, result))
    except BaseException as exc:  # noqa: BLE001
        result["errors"].append(f"{type(exc).__name__}: {str(exc)[:120]}")
    q.put(result)


async def probe_money(processes: int, attempts: int) -> bool:
    from sqlalchemy import delete, func, select

    from app.database.models import (
        ShopBot,
        ShopOwner,
        WalletCharge,
        WalletTransaction,
        WalletTransactionReason,
    )
    from app.database.session import engine, session_scope
    from app.services import shop_owner_service, wallet_service

    owner_tg = SEED_PREFIX + int(time.time() % 1000)
    async with session_scope() as session:
        # از همان سازندهٔ پروداکشن استفاده می‌کنیم تا پیش‌فرض‌هایِ ستون‌ها (referral_code و…) نیفتد رویِ سرِ ما
        owner = await shop_owner_service.get_or_create_shop_owner(session, owner_tg)
        await session.flush()
        shop_bot = await session.scalar(select(ShopBot).limit(1))
        await wallet_service.add_charge(
            session, owner, 10_000, reason=WalletTransactionReason.TOPUP, reference=f"p104:{shop_bot.id if shop_bot else 0}"
        )
        owner_id = owner.id
        starting = int(owner.wallet_balance_toman)
        await session.commit()

    context = mp.get_context("spawn")
    queue = context.Queue()
    procs = [context.Process(target=_money_process, args=(index, attempts, owner_tg, queue)) for index in range(processes)]
    for proc in procs:
        proc.start()
    for proc in procs:
        proc.join(180)
    got = [queue.get(timeout=30) for _ in procs]
    succeeded = sum(item["succeeded"] for item in got)
    all_latencies = [value for item in got for value in item["latencies"]]
    rejected: dict[str, int] = {}
    for item in got:
        for name in item["errors"]:
            rejected[name] = rejected.get(name, 0) + 1

    async with session_scope() as session:
        ending = int((await session.scalar(select(ShopOwner.wallet_balance_toman).where(ShopOwner.id == owner_id)) or 0))
        ledger_rows = (
            await session.execute(
                select(func.count()).select_from(WalletTransaction).where(
                    WalletTransaction.shop_owner_id == owner_id,
                    WalletTransaction.reason == WalletTransactionReason.CHAT_MESSAGE,
                )
            )
        ).scalar_one()
        await session.commit()

    p95 = int(sorted(all_latencies)[max(0, (len(all_latencies) * 95) // 100 - 1)]) if all_latencies else 0
    print(
        f"MEASURED رقابتِ مالی: {processes} پروسه × {attempts} تلاش ⇒ موفق {succeeded} · رد {rejected} · "
        f"موجودی {starting} ← {ending} · ردیفِ برداشت در دفتر {ledger_rows} · "
        f"p50 {int(statistics.median(all_latencies)) if all_latencies else 0} ms · p95 {p95} ms"
    )
    ok = (
        ending >= 0
        and int(ledger_rows) == succeeded
        and ending == starting - succeeded * 1_000
        and starting - succeeded * 1_000 >= 0
    )
    if not ok:
        print("❌ یا موجودی منفی شد، یا تعدادِ ردیفِ دفتر با موفق‌ها نمی‌خواند، یا جمعِ کسرها با موجودیِ نهایی فرق دارد.")
    async with session_scope() as session:
        # پاک‌سازیِ ردیف‌هایِ بار: اولِ فرزندان (دفتر/شارژ)، بعدِ خودِ حساب — با DELETE، نه TRUNCATE
        await session.execute(delete(WalletTransaction).where(WalletTransaction.shop_owner_id == owner_id))
        await session.execute(delete(WalletCharge).where(WalletCharge.shop_owner_id == owner_id))
        await session.execute(delete(ShopOwner).where(ShopOwner.id == owner_id))
        await session.commit()
    await engine.dispose()
    return ok


# ============================================================================= ۴ · شارد
async def _shard_worker(slot: int, count: int, forced_index: int | None, out: dict) -> None:
    """فهرستِ شاردِ خودی (از SQL) + قفلِ همین شارد.

    نکته: `settings.shard_*` داخلِ هر پروسهٔ فرزند ست می‌شود (spawn ⇒ حافظهٔ جدا)؛ اگر fork بود
    عددِ والد در همه یکی می‌ماند و سنجه بی‌معنی می‌شد.
    """
    from app.config import settings
    from app.database.session import engine, session_scope
    from app.main import POLLING_LOCK_KEY, acquire_polling_lock, release_polling_lock
    from app.services import app_roles, shop_bot_service

    index = slot if forced_index is None else forced_index
    settings.shard_count = count
    settings.shard_index = index
    settings.app_role = "poller"
    async with session_scope() as session:
        rows = await shop_bot_service.get_all_active(session, shard=(index, count))
        ids = sorted(bot.id for bot in rows)
    key = app_roles.lock_key(POLLING_LOCK_KEY)
    connection = await acquire_polling_lock(key)
    out.update({"slot": slot, "index": index, "key": key, "ids": ids, "acquired": connection is not None})
    if connection is not None:
        await asyncio.sleep(LOCK_HOLD_SECONDS)
        await release_polling_lock(connection, key=key)
    await engine.dispose()


def _shard_process(slot: int, count: int, forced_index: int | None, q) -> None:
    result: dict = {"slot": slot, "index": slot, "ids": [], "acquired": False}
    try:
        asyncio.run(_shard_worker(slot, count, forced_index, result))
    except BaseException as exc:  # noqa: BLE001
        result["error"] = f"{type(exc).__name__}: {str(exc)[:180]}"
    q.put(result)


async def _gather(target, args_list) -> list[dict]:
    context = mp.get_context("spawn")
    queue = context.Queue()
    procs = [context.Process(target=target, args=(*args, queue)) for args in args_list]
    for proc in procs:
        proc.start()
    for proc in procs:
        proc.join(LOCK_HOLD_SECONDS + 30)
    got = [queue.get(timeout=25) for _ in procs]
    for item in got:
        if item.get("error"):
            print("⚠️ پروسهٔ فرزند:", item.get("slot"), item["error"])
    return got


async def _seed_shard_shops(count: int) -> list[int]:
    """فروشگاه‌هایِ ساختگیِ همین سنجه (بی‌هیچ اتصالِ شبکه؛ فقط ردیفِ دیتابیس)."""
    from app.database.models import ShopBot
    from app.database.session import session_scope
    from app.services import shop_owner_service

    stamp = int(time.time() % 100_000)
    owner_tgs = [SEED_PREFIX + 700_000 + stamp * 100 + index for index in range(count)]
    created: list[int] = []
    async with session_scope() as session:
        for index, owner_tg in enumerate(owner_tgs):
            owner = await shop_owner_service.get_or_create_shop_owner(session, owner_tg)
            await session.flush()
            shop_bot = ShopBot(
                shop_owner_id=owner.id,
                bot_telegram_id=owner_tg,
                bot_username=f"probe_shard_{index}",
                encrypted_token="placeholder",
                webhook_secret_token="probe-shard-secret",
                is_active=True,
            )
            session.add(shop_bot)
            await session.flush()
            created.append(shop_bot.id)
        await session.commit()
    return created


async def _clean_shard_shops(ids: list[int]) -> None:
    from sqlalchemy import delete, select

    from app.database.models import ShopBot, ShopOwner
    from app.database.session import engine, session_scope

    async with session_scope() as session:
        await session.execute(delete(ShopBot).where(ShopBot.id.in_(ids)))
        owners = (
            await session.execute(select(ShopOwner.id).where(ShopOwner.telegram_id >= SEED_PREFIX + 700_000))
        ).scalars().all()
        if owners:
            await session.execute(delete(ShopOwner).where(ShopOwner.id.in_(owners)))
        await session.commit()
    await engine.dispose()


async def probe_shard(processes: int, shops: int) -> bool:
    """دو ادعا بینِ پروسه‌هایِ واقعی: تقسیمِ *فایل* و مهارِ *هم‌شارد*.

    الف) با SHARD_COUNT=N، هر فروشگاه دقیقاً در یکِ پروسه می‌نشیند (اجتماعِ N دسته == همهٔ ردیف‌ها و
       اشتراکِ هر دوتایی == خالی). این با *کوئریِ واقعی* سنجیده می‌شود، نه تابعِ خالص.
    ب) دو پروسه با شاردِ *متفاوت* هر دو قفل می‌گیرند (پس N پروسهٔ poller می‌توانند همزمان کار کنند)
       و دو پروسه با شاردِ *یکی* ⇒ دقیقاً یکِ برنده (وگرنه یکِ پیام دو بار به AI و دو بار کسر).
    """
    from sqlalchemy import func, select

    from app.database.models import ShopBot
    from app.database.session import session_scope

    ids = await _seed_shard_shops(shops)
    try:
        async with session_scope() as session:
            mine = (
                await session.execute(select(func.count()).select_from(ShopBot).where(ShopBot.id.in_(ids)))
            ).scalar_one()
        if int(mine) != len(ids):
            print(f"❌ سیدِ شارد ناقص است: {mine} از {len(ids)}")
            return False

        started = time.perf_counter()
        got = await _gather(_shard_process, [(slot, processes, None) for slot in range(processes)])
        winners = sum(1 for item in got if item.get("acquired"))
        buckets = [set(item["ids"]) for item in got]
        covered = set().union(*buckets) if buckets else set()
        overlaps = sum(1 for a in range(len(buckets)) for b in range(a + 1, len(buckets)) if buckets[a] & buckets[b])
        keys = {item["key"] for item in got}
        print(
            f"MEASURED شاردبینیِ {processes} پروسه رویِ {len(ids)} فروشگاه: پوششِ کامل={covered >= set(ids)} · "
            f"همپوشانیِ دوتایی={overlaps} · قفل‌هایِ گرفته‌شده={winners}/{processes} · کلیدهایِ یکتا={len(keys)} · "
            f"{int((time.perf_counter() - started) * 1000)} ms"
        )
        ok_a = covered >= set(ids) and overlaps == 0 and winners == processes and len(keys) == processes

        started = time.perf_counter()
        same = await _gather(_shard_process, [(0, processes, 0), (1, processes, 0)])
        both_winners = sum(1 for item in same if item.get("acquired"))
        print(
            f"MEASURED دو پروسه با *یکِ شارد* (index=0/{processes}): برنده={both_winners} · "
            f"{int((time.perf_counter() - started) * 1000)} ms"
        )
        ok_b = both_winners == 1
        if not ok_a:
            print("❌ یا بعضی فروشگاه‌ها جا مانده‌اند، یا در دو پروسه‌اند، یا قفلِ شارد مهار نکرده است.")
        if not ok_b:
            print("❌ دو پروسهٔ هم‌شارد هم‌زمان قفل گرفتند ⇒ دو polling = دو کسرِ کیف‌پول برایِ یکِ پیام.")
        return ok_a and ok_b
    finally:
        await _clean_shard_shops(ids)


async def run(parts: list[str], processes: int, attempts: int, shops: int = 12) -> int:
    results = []
    if "lock" in parts:
        results.append(await probe_lock(processes))
    if "counters" in parts:
        results.append(await probe_counters(processes))
    if "money" in parts:
        results.append(await probe_money(processes, attempts))
    if "shard" in parts:
        results.append(await probe_shard(processes, shops))
    if not results:
        print("هیچ بخشی انتخاب نشد (--parts lock,counters,money,shard)")
        return 2
    return 0 if all(results) else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="سنجهٔ چندپروسه‌ایِ واقعی (قفل/شمارنده/رقابتِ مالی/شارد)")
    parser.add_argument("--parts", default="lock,counters", help="زیرمجموعه از: lock,counters,money,shard")
    parser.add_argument("--processes", type=int, default=2, help="تعدادِ پروسه (پیش‌فرض ۲)")
    parser.add_argument("--attempts", type=int, default=6, help="تعدادِ تلاشِ مالی در هر پروسه (برایِ --parts money)")
    parser.add_argument("--shops", type=int, default=12, help="تعدادِ فروشگاهِ ساختگی برایِ سنجهٔ شارد")
    args = parser.parse_args()
    _guard()
    processes = max(2, min(int(args.processes), 8))
    parts = [part.strip() for part in args.parts.split(",") if part.strip()]
    return asyncio.run(run(parts, processes, max(1, int(args.attempts)), max(2, int(args.shops))))


if __name__ == "__main__":
    raise SystemExit(main())
