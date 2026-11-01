"""بارِ ایزوله رویِ «مسیرِ یک پیامِ مشتری» (P20 · ظرفیتِ کاربرِ هم‌زمان).

چرا این اسکریپت جدا از `loadtest_wallet_paths.py`: آن یکی فقط کسرِ کیف‌پول را می‌سنجد. چیزی که
تعیین می‌کند «چند کاربر هم‌زمان» را همین سرویس‌ها جواب می‌دهند، یک تراکنشِ کاملِ پیام است:

    شناساییِ ربات → بررسیِ بلاک → get_or_create مشتری → ذخیره/خواندنِ تاریخچه → کسرِ کیف‌پول

هیچ فراخوانیِ شبکه‌ای (AI/تلگرام/بله) در آن نیست؛ یعنی عددی که می‌بینیم «سقفِ دیتابیسِ خودِ
برنامه» است، نه سقفِ ارائه‌دهندهٔ AI.

دو سنجه جدا (تفاوتشان مهم است):
  A) فروشگاه‌دارهایِ مختلف ⇒ هیچ رقابتی رویِ قفلِ سطری نیست.
  B) همه روی یکِ فروشگاه‌دار ⇒ `SELECT … FOR UPDATE` رویِ بسته‌هایِ کیف‌پول همان یک نفر، همه را
     پشتِ هم می‌چیند؛ این گلوگاهِ واقعیِ رشدِ ماست (چند فروشگاهِ بزرگ با ترافیکِ زیاد).

ایمنی (سخت، عمداً): تا LOADTEST_DB_CONFIRM=1 ست نشده اجرا نمی‌شود، DATABASE_URL باید دیتابیسِ
جدا باشد، و هیچ درخواستی به سرویسِ بیرونی زده نمی‌شود. ردیف‌هایِ بار با telegram_id >= 9_000_000
ساخته و در پایان پاک می‌شوند.

دستور:
    docker compose exec -T db createdb -U postgres kasbokar_load
    docker compose run --rm -e DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/kasbokar_load bot alembic upgrade head
    docker compose run --rm -e DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/kasbokar_load \\
                    -e LOADTEST_DB_CONFIRM=1 bot python scripts/loadtest_message_path.py --levels 10,50,100,200
"""
from __future__ import annotations

import argparse
import asyncio
import os
import statistics
import sys
import time

sys.path.insert(0, ".")

from sqlalchemy import delete, func, select  # noqa: E402

from app.config import settings  # noqa: E402
from app.database.models import (  # noqa: E402
    ConversationMessage,
    Customer,
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

SEED_PREFIX = 9_000_000
BOT_PREFIX = 900_000_000  # «شناسهٔ رباتِ تلگرام» ساختگی، دور از ربات‌هایِ واقعی
DEDUCT_TOMAN = 250  # اندازهٔ واقعیِ یک پاسخِ متوسطِ AI


def _guard() -> None:
    if os.environ.get("LOADTEST_DB_CONFIRM") != "1":
        raise SystemExit(
            "LOADTEST_DB_CONFIRM=1 لازم است: این اسکریپت دیتابیس را می‌نویسد و پاک می‌کند. "
            f"DATABASE_URL فعلی: {settings.database_url}"
        )


def _percentile(values: list[float], share: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round(share * (len(ordered) - 1)))))
    return ordered[index]


async def _seed(shops: int, customers_per_shop: int) -> list[tuple[int, int, list[tuple[int, int]]]]:
    """(shop_bot_id, bot_telegram_id, [(customer_id, customer_telegram_id)…] برایِ هرِ فروشگاهِ ساختگی.

    موجودیِ هر فروشگاه‌دار از خودِ `add_charge` می‌آید تا بسته + دفتر + کشِ موجودی سازگار بمانند
    (وگرنه قفلِ FIFO رویِ دادهٔ ناسنجیده معنا ندارد)."""
    out: list[tuple[int, int, list[tuple[int, int]]]] = []
    async with session_scope() as session:
        for index in range(shops):
            owner = ShopOwner(
                telegram_id=SEED_PREFIX + index,
                first_name=f"load-{index}",
                referral_code=f"M{index:08d}",
                registration_completed=True,
                wallet_balance_toman=0,
            )
            session.add(owner)
            await session.flush()
            await wallet_service.add_charge(
                session, owner, 5_000_000, reason=WalletTransactionReason.TOPUP, reference=f"load-seed:{index}"
            )
            shop_bot = ShopBot(
                shop_owner_id=owner.id,
                encrypted_token=encrypt_token(f"load-token-{index}"),
                bot_telegram_id=BOT_PREFIX + index,
                bot_username=f"load_bot_{index}",
                webhook_secret_token="load-secret",
            )
            session.add(shop_bot)
            await session.flush()
            customers_list = []
            for c in range(customers_per_shop):
                telegram_id = SEED_PREFIX + 100_000 + index * 1000 + c
                customer = Customer(shop_bot_id=shop_bot.id, telegram_id=telegram_id)
                session.add(customer)
                await session.flush()
                customers_list.append((customer.id, telegram_id))
            out.append((shop_bot.id, shop_bot.bot_telegram_id, customers_list))
    return out


async def _cleanup() -> int:
    async with session_scope() as session:
        owner_ids = list((await session.execute(select(ShopOwner.id).where(ShopOwner.telegram_id >= SEED_PREFIX))).scalars().all())
        bot_ids = list((await session.execute(select(ShopBot.id).where(ShopBot.bot_telegram_id >= BOT_PREFIX))).scalars().all())
        customer_ids = list((await session.execute(select(Customer.id).where(Customer.shop_bot_id.in_(bot_ids)))).scalars().all()) if bot_ids else []
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
            (await session.execute(select(func.count()).select_from(ShopOwner).where(ShopOwner.telegram_id >= SEED_PREFIX))).scalar_one()
        )
    return left


async def _one_message(bot_telegram_id: int, customer_tid: int, text: str) -> tuple[bool, float]:
    """همان ترتیبِ کارِ یکِ آپدیتِ ورودی، بدونِ AI و بدونِ تلگرام."""
    started = time.perf_counter()
    async with session_scope() as session:
        shop_bot = await shop_bot_service.get_by_platform_bot_id(session, bot_telegram_id, bale=False)
        if shop_bot is None:
            return False, (time.perf_counter() - started) * 1000.0
        await shop_middlewares.is_blocked(session, ShopBot.bot_telegram_id, bot_telegram_id, customer_tid, platform_service.TELEGRAM)
        owner = await session.get(ShopOwner, shop_bot.shop_owner_id)
        customer = await customer_service.get_or_create_customer(session, shop_bot.id, customer_tid, None, None)
        await conversation_service.get_recent_history(session, customer.id, limit=20)
        await conversation_service.save_turn(session, customer.id, text, "پاسخِ کوتاهِ آزمایشی")
        await wallet_service.deduct(session, owner, DEDUCT_TOMAN, WalletTransactionReason.CHAT_MESSAGE)
    return True, (time.perf_counter() - started) * 1000.0


async def _wave(concurrency: int, shops: list[tuple[int, int, list[tuple[int, int]]]], requests: int, single_owner: bool) -> dict:
    latencies: list[float] = []
    failures = 0
    started = time.perf_counter()
    for offset in range(0, requests, concurrency):
        batch = []
        for i in range(min(concurrency, requests - offset)):
            index = offset + i
            shop = shops[0] if single_owner else shops[index % len(shops)]
            _shop_bot_id, bot_telegram_id, customers = shop
            # customer_idِ جدول لازم نیست: مسیرِ واقعی هم فقط telegram_id را از تلگرام می‌گیرد
            _customer_id, customer_tid = customers[index % len(customers)]
            batch.append(_one_message(bot_telegram_id, customer_tid, f"msg-{index}"))
        for ok, ms in await asyncio.gather(*batch):
            latencies.append(ms)
            failures += 0 if ok else 1
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
        "errors": failures,
    }


def _report(rows: list[dict], label: str) -> None:
    print(f"\n--- {label} ---")
    for row in rows:
        print(
            "concurrency={concurrency:>5} req={requests:>6} rps={rps:>8} p50={p50_ms:>7} "
            "p95={p95_ms:>7} p99={p99_ms:>7} max={max_ms:>8} mean={mean_ms:>7} errors={errors:>3}".format(**row)
        )


async def main(levels: list[int], requests: int, shops: int, customers: int) -> None:
    _guard()
    await _cleanup()
    seeded = await _seed(shops, customers)
    pool_size = getattr(engine.pool, "size", lambda: "?")()
    overflow = getattr(engine.pool, "_max_overflow", "?")
    print(f"pool size={pool_size} max_overflow={overflow} shops={len(seeded)} customers/shop={customers} پیام/سطح={requests}")
    try:
        spread = []
        hot = []
        for concurrency in levels:
            spread.append(await _wave(concurrency, seeded, requests, single_owner=False))
            hot.append(await _wave(concurrency, seeded, max(300, requests // 5), single_owner=True))
        _report(spread, "الف) فروشگاه‌دارهایِ مختلف (بدونِ رقابت رویِ قفلِ کیف‌پول)")
        _report(hot, "ب) همه روی یکِ فروشگاه‌دار (گلوگاهِ قفلِ FIFO)")
        best_spread = max(row["rps"] for row in spread)
        best_hot = max(row["rps"] for row in hot)
        # هر پیامِ AI یکِ درخواستِ DEDUCT_TOMAN است؛ تبدیلِ rps به «کاربرِ فعالِ هم‌زمان»:
        # کاربرِ فعال ≈ هر ۶۰ ثانیه یک پیام ⇒ capacity_users = rps × 60
        print(
            f"\nسقفِ پیام/ثانیه: پخش‌شده={best_spread} · یک‌فروشگاه={best_hot}\n"
            f"برآوردِ کاربرِ فعالِ هم‌زمان (۱ پیام/دقیقه، فقط دیتابیس، بدونِ AI): "
            f"پخش‌شده≈{int(best_spread * 60):,} · یک‌فروشگاه≈{int(best_hot * 60):,}"
        )
    finally:
        left = await _cleanup()
        print(f"پاک‌سازی: {left} ردیفِ بار باقی ماند (باید صفر باشد)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--levels", default="10,50,100,200", help="سطح‌هایِ همزمانی، با کاما")
    parser.add_argument("--requests", type=int, default=1500, help="تعدادِ پیام در هر سطح (سنجهٔ الف)")
    parser.add_argument("--shops", type=int, default=64, help="تعدادِ فروشگاه‌هایِ ساختگی")
    parser.add_argument("--customers", type=int, default=8, help="مشتریِ ساختگی در هر فروشگاه")
    args = parser.parse_args()
    asyncio.run(main([int(x) for x in args.levels.split(",") if x.strip()], args.requests, args.shops, args.customers))
