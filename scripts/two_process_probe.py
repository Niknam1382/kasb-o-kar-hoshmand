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


async def run(parts: list[str], processes: int, attempts: int) -> int:
    results = []
    if "lock" in parts:
        results.append(await probe_lock(processes))
    if "counters" in parts:
        results.append(await probe_counters(processes))
    if "money" in parts:
        results.append(await probe_money(processes, attempts))
    if not results:
        print("هیچ بخشی انتخاب نشد (--parts lock,counters,money)")
        return 2
    return 0 if all(results) else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="سنجهٔ دو پروسه‌ایِ واقعی (قفل/شمارنده/رقابتِ مالی)")
    parser.add_argument("--parts", default="lock,counters", help="زیرمجموعه از: lock,counters,money")
    parser.add_argument("--processes", type=int, default=2, help="تعدادِ پروسه (پیش‌فرض ۲)")
    parser.add_argument("--attempts", type=int, default=6, help="تعدادِ تلاشِ مالی در هر پروسه (برایِ --parts money)")
    args = parser.parse_args()
    _guard()
    processes = max(2, min(int(args.processes), 8))
    parts = [part.strip() for part in args.parts.split(",") if part.strip()]
    return asyncio.run(run(parts, processes, max(1, int(args.attempts))))


if __name__ == "__main__":
    raise SystemExit(main())
