"""اسکریپتِ بارِ ایزوله رویِ مسیرهایِ گرمِ مالی (PHASE 12).

چرا این شکل: مسیرِ HTTP در این پروژه فقط در حالتِ webhook فعال است و فعال‌کردنش رویِ
میزبانِ توسعه، `set_webhook` را رویِ توکن‌هایِ **واقعی** می‌نویسد و ترافیکِ زندهٔ رباتِ کاربر
را عوض می‌کند. پس به‌جایِ HTTP، خودِ همان سرویسِ گرمِ مالی (کسرِ کیف‌پول با FIFO و
`SELECT … FOR UPDATE`، و همسنجیِ دفتر) را با همزمانیِ بالا می‌سنجیم — یعنی همان کاری که
هر پیامِ مشتری و هر تسویهٔ کمیسیون انجام می‌دهد، بدونِ هیچ اثرِ بیرونی.

ایمنی (عمدی و سخت):
- تا `LOADTEST_DB_CONFIRM=1` ست نشود اصلاً اجرا نمی‌شود؛ `DATABASE_URL` هم باید صریحاً به
  دیتابیسِ جدا اشاره کند. هرگز رویِ دیتابیسِ اصلی اجرا نکن.
- هیچ سرویسِ پرداخت، پیامک یا پیامِ تلگرامی واقعی ندارد.
- ردیف‌هایِ بار با `telegram_id >= 9_000_000` ساخته و در پایانِ اجرا پاک می‌شوند.

دستور:
    docker compose exec -T db createdb -U postgres kasbokar_load
    docker compose run --rm -e DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/kasbokar_load bot alembic upgrade head
    docker compose run --rm -e DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/kasbokar_load \
                    -e LOADTEST_DB_CONFIRM=1 bot python scripts/loadtest_wallet_paths.py --levels 10,50,100,250
"""
from __future__ import annotations

import argparse
import asyncio
import datetime
import os
import statistics
import sys
import time

sys.path.insert(0, ".")

from sqlalchemy import delete, func, select  # noqa: E402

from app.config import settings  # noqa: E402
from app.database.models import ShopOwner, WalletCharge, WalletTransaction, WalletTransactionReason  # noqa: E402
from app.database.session import engine, session_scope  # noqa: E402
from app.services import wallet_service  # noqa: E402

SEED_PREFIX = 9_000_000  # آیدی‌هایِ ساختگی، دور از دادهٔ واقعی


def _guard() -> None:
    if os.environ.get("LOADTEST_DB_CONFIRM") != "1":
        raise SystemExit(
            "LOADTEST_DB_CONFIRM=1 لازم است: این اسکریپت دیتابیس را می‌نویسد و پاک می‌کند. "
            f"DATABASE_URL فعلی: {settings.database_url}"
        )


async def _seed(owners_count: int) -> list[int]:
    """چند فروشگاه‌دارِ مستقل با یک بستهٔ ۱٬۰۰۰٬۰۰۰ تومانی؛ استقلال یعنی قفلِ سطرِ یکی،
    گلوگاهِ همه نمی‌شود (تأثیرِ صفِ pool و قفلِ سطری هرچه باشد جدا دیده می‌شود)."""
    ids: list[int] = []
    async with session_scope() as session:
        for index in range(owners_count):
            owner = ShopOwner(
                telegram_id=SEED_PREFIX + index,
                first_name=f"load-{index}",
                referral_code=f"L{index:08d}",
                registration_completed=True,
                wallet_balance_toman=0,
            )
            session.add(owner)
            await session.flush()
            # عمداً از خودِ سرویس استفاده می‌شود تا حالتِ «سالم» ساخته شود:
            # بسته + ردیفِ دفتر + موجودیِ کش‌شده هر سه با هم ⇒ همسنجی باید صفر اختلاف بدهد.
            await wallet_service.add_charge(session, owner, 1_000_000, reason=WalletTransactionReason.TOPUP, reference=f"load-seed:{index}")
            ids.append(owner.id)
    return ids


async def _cleanup() -> int:
    async with session_scope() as session:
        owner_ids = list((await session.execute(select(ShopOwner.id).where(ShopOwner.telegram_id >= SEED_PREFIX))).scalars().all())
        if owner_ids:
            await session.execute(delete(WalletTransaction).where(WalletTransaction.shop_owner_id.in_(owner_ids)))
            await session.execute(delete(WalletCharge).where(WalletCharge.shop_owner_id.in_(owner_ids)))
            await session.execute(delete(ShopOwner).where(ShopOwner.id.in_(owner_ids)))
        left = (await session.execute(select(func.count()).select_from(ShopOwner).where(ShopOwner.telegram_id >= SEED_PREFIX))).scalar_one()
    return int(left)


async def _one_spend(owner_id: int, amount: int) -> tuple[bool, float]:
    started = time.perf_counter()
    async with session_scope() as session:
        owner = (
            await session.execute(select(ShopOwner).where(ShopOwner.id == owner_id).with_for_update())
        ).scalar_one()
        ok = await wallet_service.deduct(session, owner, amount, WalletTransactionReason.CHAT_MESSAGE, reference=f"load:{owner_id}")
    return bool(ok), (time.perf_counter() - started) * 1000.0


async def _one_reconcile(limit: int) -> tuple[float, int]:
    started = time.perf_counter()
    async with session_scope() as session:
        gaps = await wallet_service.reconcile_balances(session, limit=limit)
    return (time.perf_counter() - started) * 1000.0, len(gaps)


def _percentile(values: list[float], share: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round(share * (len(ordered) - 1)))))
    return ordered[index]


async def _wave(concurrency: int, owner_ids: list[int], requests: int) -> dict:
    latencies: list[float] = []
    errors = 0
    started = time.perf_counter()
    for offset in range(0, requests, concurrency):
        batch = [_one_spend(owner_ids[(offset + i) % len(owner_ids)], 1_000) for i in range(min(concurrency, requests - offset))]
        for ok, ms in await asyncio.gather(*batch):
            latencies.append(ms)
            errors += 0 if ok else 1
    elapsed = time.perf_counter() - started
    return {
        "concurrency": concurrency,
        "requests": len(latencies),
        "rps": round(len(latencies) / elapsed, 1) if elapsed > 0 else 0.0,
        "p50_ms": round(_percentile(latencies, 0.50), 1),
        "p95_ms": round(_percentile(latencies, 0.95), 1),
        "p99_ms": round(_percentile(latencies, 0.99), 1),
        "max_ms": round(max(latencies), 1) if latencies else 0.0,
        "mean_ms": round(statistics.fmean(latencies), 1) if latencies else 0.0,
        "errors": errors,
    }


async def main(levels: list[int], requests: int, owners_count: int) -> None:
    _guard()
    await _cleanup()  # اجرایِ قبلی که نصفه مانده باشد نباید بکشد (referral_code یکتا است)
    owner_ids = await _seed(owners_count)
    pool_size = getattr(engine.pool, "size", lambda: "?")()
    overflow = getattr(engine.pool, "_max_overflow", "?")
    print(f"pool size={pool_size} max_overflow={overflow} owners={owners_count} requests/wave={requests}")
    try:
        ms, gaps = await _one_reconcile(limit=owners_count)
        print(f"reconcile_balances over {owners_count} owners: {ms:.1f}ms, gaps={gaps} (انتظار: 0 ⇒ دادهٔ seed شده سازگار است)")
        for concurrency in levels:
            row = await _wave(concurrency, owner_ids, requests)
            print(
                "concurrency={concurrency:>5} req={requests:>6} rps={rps:>8} p50={p50_ms:>7} "
                "p95={p95_ms:>7} p99={p99_ms:>7} max={max_ms:>8} mean={mean_ms:>7} errors={errors:>3}".format(**row)
            )
    finally:
        left = await _cleanup()
        print(f"پاک‌سازی: {left} ردیفِ بار باقی ماند (باید صفر باشد)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--levels", default="10,50,100,250", help="سطح‌هایِ همزمانی، با کاما")
    parser.add_argument("--requests", type=int, default=2000, help="تعدادِ کلِ کسرها در هر سطح")
    parser.add_argument("--owners", type=int, default=64, help="تعدادِ فروشگاه‌دارهایِ ساختگی")
    args = parser.parse_args()
    asyncio.run(main([int(x) for x in args.levels.split(",") if x.strip()], args.requests, args.owners))
