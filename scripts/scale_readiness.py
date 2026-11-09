#!/usr/bin/env python3
"""P45 · ظرفیت: «آیا این پیکربندی، این تعداد کاربر را می‌کشَد؟» — با عدد، نه با حدس.

سه چیز را کنارِ هم می‌گذارد و می‌گوید کدامِ لایه لازم است:
۱) جمعِ اتصال‌هایِ دیتابیس (پروسه × استخر) در برابرِ `max_connections` واقعیِ postgres.
۲) رم و سوکتِ حالتِ polling (MEASURED: ~۰٫۴–۰٫۷ مگابایت و یکِ سوکتِ باز به‌ازایِ هر رباتِ فروشگاه).
۳) سقفِ هم‌زمانیِ لازمِ سرویسِ هوشِ مصنوعی برایِ تعدادِ مشتریِ «در حالِ چت» که می‌گویی.

چرا اسکریپت و نه دکمهٔ پنل: این تصمیمِ مالکِ سرویس است (خریدِ سرور)، نه کارِ روزانهٔ ادمین.

اجرا (داخل کانتینر، چون به دیتابیس وصل می‌شود):
    docker compose run --rm bot python3 scripts/scale_readiness.py --shops 1500 --users 1000
    docker compose run --rm bot python3 scripts/scale_readiness.py --check      # پیکربندیِ فعلی

هیچ رازی چاپ نمی‌شود: نه رشتهٔ اتصال، نه توکن، نه رمز.
"""
from __future__ import annotations

import argparse
import asyncio
import sys

sys.path.insert(0, ".")

from sqlalchemy import text as sql_text  # noqa: E402

from app.config import settings  # noqa: E402
from app.database.session import engine  # noqa: E402
from app.services import app_roles  # noqa: E402

# MEASURED (scripts/scale_probe.py، SCALABILITY_AND_LOAD_TEST_REPORT.md §۱۰):
MB_PER_BOT = 0.7  # بدترینِ بازه (۰٫۴ تا ۰٫۷) — محافظه‌کارانه
BASE_RSS_MB = 220.0  # پروسهٔ خالی
DB_CONNECTIONS_RESERVE = 15  # بکاپ، مدیریت، alembic، pgbench‌هایِ دستی
MESSAGES_PER_USER_MINUTE = 2.0  # هر مشتریِ فعال چند پیام در دقیقه می‌فرستد (فرضِ محتاطانه)


def ai_concurrency_needed(users: int, latency_seconds: float, messages_per_minute: float = MESSAGES_PER_USER_MINUTE) -> float:
    """درخواستِ هم‌زمانِ لازم ≈ کاربران × پیام/ثانیه × تأخیر."""
    return users * (messages_per_minute / 60.0) * latency_seconds


def users_supported(ai_max: int, latency_seconds: float, messages_per_minute: float = MESSAGES_PER_USER_MINUTE) -> int:
    """معکوسِ فرمولِ بالا — همان «۴۰ ÷ ۳ ≈ ۱۳ پیام/ثانیه ≈ ۴۰۰ کاربر» که در مستندات هست."""
    if latency_seconds <= 0:
        return 0
    per_second = ai_max / latency_seconds
    return int(per_second * 60 / messages_per_minute)


def poller_processes(shops: int, per_process_cap: int) -> int:
    return max(1, -(-shops // max(1, per_process_cap)))


def ram_for_poller(shops_in_shard: int) -> float:
    return BASE_RSS_MB + shops_in_shard * MB_PER_BOT


async def read_max_connections() -> int:
    async with engine.connect() as connection:
        value = (await connection.execute(sql_text("SHOW max_connections"))).scalar_one()
    return int(value)


def main() -> int:
    parser = argparse.ArgumentParser(description="بررسیِ آمادگیِ ظرفیت (P45)")
    parser.add_argument("--shops", type=int, default=0, help="تعدادِ فروشگاهِ هدف")
    parser.add_argument("--users", type=int, default=0, help="مشتریِ هم‌زمان در حالِ چت")
    parser.add_argument("--latency", type=float, default=4.0, help="تأخیرِ متوسطِ پاسخِ هوشِ مصنوعی (ثانیه)")
    parser.add_argument("--per-process-shops", type=int, default=250, help="سقفِ فروشگاه در هر پروسهٔ poller")
    parser.add_argument("--check", action="store_true", help="فقط پیکربندیِ فعلیِ محیط را بررسی کن")
    args = parser.parse_args()

    processes = 1
    if args.check or args.shops:
        processes = max(1, app_roles.shard_count()) + (1 if app_roles.is_core() else 0)
    pool_each = int(settings.db_pool_size)
    budget = processes * (pool_each + int(settings.db_max_overflow)) + DB_CONNECTIONS_RESERVE

    print(f"نقشِ این پروسه: {app_roles.describe()}  ·  استخرِ هر پروسه: {pool_each}")
    print(f"اتصالِ لازم (تخمینیِ همین پیکربندی): {processes} پروسه × {pool_each} + {DB_CONNECTIONS_RESERVE} = {budget}")

    try:
        max_connections = asyncio.run(read_max_connections())
        verdict = "OK" if budget <= max_connections else "کم است"
        print(f"max_connectionsِ واقعیِ postgres: {max_connections} ⇒ جمعِ اتصال‌ها: {verdict}")
        if budget > max_connections:
            print("  راهِ حل: DB_POOL_SIZE را در هر سرویس کم کن، یا max_connections را بالا ببر،")
            print("  یا پروسه‌ها را بینِ دو ماشین تقسیم کن (لایهٔ ۳).")
    except Exception as exc:  # noqa: BLE001 - ابزارِ تشخیصی نباید با نبودِ دیتابیس بشکند
        print(f"max_connections خوانده نشد ({type(exc).__name__}) — عددِ بالا فقط محاسبهٔ رویِ کاغذ است.")

    if args.shops:
        shards = poller_processes(args.shops, args.per_process_shops)
        per_shard = -(-args.shops // shards)
        print(f"\nحالتِ polling برایِ {args.shops} فروشگاه: {shards} پروسهٔ poller (هر کدام ~{per_shard} فروشگاه)")
        print(f"  رمِ هر poller ≈ {ram_for_poller(per_shard):.0f} مگابایت · سوکت‌هایِ باز ≈ {per_shard} به پروسه")
        print(f"  رمِ کلِ polling ≈ {ram_for_poller(per_shard) * shards / 1024:.1f} گیگ (+ دیتابیس)")
        print("  اگر دامنه و HTTPS داری، لایهٔ ۳-وب این سوکت‌ها را حذف می‌کند:")
        print("    docker compose -f docker-compose.yml -f deploy/docker-compose.t3.yml -f deploy/docker-compose.webhook.yml up -d")

    if args.users:
        needed = ai_concurrency_needed(args.users, args.latency)
        print(f"\nبرایِ {args.users} مشتریِ هم‌زمان با تأخیرِ {args.latency} ثانیه:")
        print(f"  سقفِ هم‌زمانیِ لازمِ سرویسِ هوشِ مصنوعی ≈ {needed:.0f} درخواست (AI_MAX_CONCURRENT)")
        print(f"  با تنظیمِ فعلی ({settings.ai_max_concurrent_calls}) ظرفیت ≈ "
              f"{users_supported(settings.ai_max_concurrent_calls, args.latency)} کاربرِ هم‌زمان")
        print("  ⚠️ این درِ اصلیِ ماست، نه CPUِ سرور. اول از ارائه‌دهندهٔ کلید بپرس چند درخواستِ")
        print("     هم‌زمان مجاز است؛ اگر کمتر از عددِ بالاست، سرورِ قوی‌تر هیچ فرقی نمی‌کند.")

    print("\nلایه‌ها:")
    print("  t1 (همین امروز، ۲–۴ هسته): docker compose up -d bot backup")
    print("  t2 (۸ هسته/۱۶ گیگ، ~۵۰۰–۸۰۰ فروشگاه): docker compose -f docker-compose.yml -f deploy/docker-compose.t2.yml up -d")
    print("  t3 (۱۶ هسته/۳۲ گیگ، ~۱٬۵۰۰ فروشگاه): docker compose -f docker-compose.yml -f deploy/docker-compose.t3.yml up -d")
    print("  t3-وب (۱٬۵۰۰ فروشگاه بدونِ سوکتِ باز، دامنه + HTTPS لازم): + deploy/docker-compose.webhook.yml")
    return 0


if __name__ == "__main__":
    sys.exit(main())
