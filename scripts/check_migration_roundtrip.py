#!/usr/bin/env python3
"""آزمونِ رفت‌وبرگشتِ مایگریشن‌ها رویِ یکِ دیتابیسِ یک‌بارمصرف (P31-C).

چرا این اسکریپت وجود دارد: تا امروز فقط `alembic upgrade head` اجرا شده بود. قاعدهٔ §۲-۴
«مایگریشن افزودنی باشد» را حفظ می‌کند، ولی هیچ‌کس بررسی نکرده بود که `downgrade`هایِ همین
فایل‌ها اصلاً کار می‌کنند یا نه — یعنی اگر روزی مجبور به برگشتِ نسخه می‌شدیم، مسیرِ برگشت
تست‌نشده بود. این اسکریپت همان مسیر را رویِ دیتابیسِ تازه می‌آزماید و به `kasbokar` یا
`kasbokar_test` دست نمی‌زند.

استفاده (داخلِ کانتینر):
    docker compose run --rm bot python3 scripts/check_migration_roundtrip.py

خروجی: کدِ ۰ یعنی upgrade ← downgrade base ← upgrade head همه سالم بود.
"""
from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402

from app.config import settings  # noqa: E402

ROUNDTRIP_DB = "kasbokar_roundtrip"


def _admin_url(url: str) -> str:
    head, _, _ = url.rpartition("/")
    return f"{head}/postgres"


def _db_url(url: str, dbname: str) -> str:
    head, _, _ = url.rpartition("/")
    return f"{head}/{dbname}"


def _run_alembic(env: dict, *args: str) -> tuple[int, float, str]:
    started = time.perf_counter()
    proc = subprocess.run(
        ["alembic", *args], env=env, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    elapsed = (time.perf_counter() - started) * 1000.0
    return proc.returncode, elapsed, (proc.stderr or proc.stdout or "")[-400:]


async def _drop_database(url: str) -> None:
    engine = create_async_engine(url, isolation_level="AUTOCOMMIT", pool_size=1, max_overflow=0)
    async with engine.connect() as conn:
        await conn.execute(
            text(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = :dbname AND pid <> pg_backend_pid()"
            ),
            {"dbname": ROUNDTRIP_DB},
        )
        await conn.execute(text(f'DROP DATABASE IF EXISTS "{ROUNDTRIP_DB}"'))
    await engine.dispose()


async def _create_database(url: str) -> None:
    engine = create_async_engine(url, isolation_level="AUTOCOMMIT", pool_size=1, max_overflow=0)
    async with engine.connect() as conn:
        await conn.execute(text(f'CREATE DATABASE "{ROUNDTRIP_DB}"'))
    await engine.dispose()


async def _count_tables(url: str) -> int:
    engine = create_async_engine(url, pool_size=1, max_overflow=0)
    async with engine.connect() as conn:
        value = await conn.scalar(
            text("SELECT count(*) FROM information_schema.tables WHERE table_schema='public'")
        )
    await engine.dispose()
    return int(value or 0)


async def main() -> int:
    admin_url = _admin_url(settings.database_url)
    target_url = _db_url(settings.database_url, ROUNDTRIP_DB)
    env = dict(os.environ, DATABASE_URL=target_url, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")

    print(f"دیتابیسِ یک‌بارمصرف: {ROUNDTRIP_DB} (هیچ اثری رویِ kasbokar/kasbokar_test ندارد)")
    await _drop_database(admin_url)  # اگر از اجرایِ قبلی مانده باشد
    await _create_database(admin_url)

    steps = [
        ("upgrade head", ("upgrade", "head")),
        ("downgrade base", ("downgrade", "base")),
        ("upgrade head (دوباره)", ("upgrade", "head")),
    ]
    for label, args in steps:
        code, elapsed, tail = _run_alembic(env, *args)
        print(f"  {label}: exit={code} در {elapsed:.0f}ms")
        if code != 0:
            print(f"❌ {label} شکست خورد:\n{tail}")
            await _drop_database(admin_url)
            return 1

    code, _, tail = _run_alembic(env, "heads")
    heads = [line for line in tail.splitlines() if "(head)" in line]
    tables = await _count_tables(target_url)
    print(f"  heads پس ازِ بازگشت: {len(heads) if code == 0 else '?'} — {heads[:2]}")
    print(f"  جدول‌هایِ ساخته‌شده در آخرین upgrade: {tables}")

    await _drop_database(admin_url)
    print("✅ رفت‌وبرگشتِ کاملِ مایگریشن‌ها سالم بود؛ دیتابیسِ یک‌بارمصرف حذف شد.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
