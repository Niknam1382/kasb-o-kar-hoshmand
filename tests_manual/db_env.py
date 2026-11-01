"""محیطِ اجرایِ تست (P22 · حفاظتِ دادهٔ کاربر).

هر فایلِ تست با `reset_database()` همهٔ جدول‌ها را TRUNCATE می‌کند. تا پیشِ این، سوئیت رویِ
همان دیتابیسِ توسعه (`kasbokar`) اجرا می‌شد و هر اجرایِ تست، تنظیماتی را که ادمین در پنل
نوشته بود (برند/بیو، قیمت‌ها، کلیدها، فروشگاه‌هایِ ساخته‌شده) پاک می‌کرد. اینجا همه‌چیز به یکِ
دیتابیسِ جدا (`kasbokar_test`) هدایت می‌شود و `harness` هم رویِ همان اسم قفل می‌کند.

هیچ گاهی رشتهٔ اتصال چاپ نمی‌شود (شاملِ رمزِ دیتابیس است).
"""
from __future__ import annotations

import os
import subprocess
import sys
from urllib.parse import urlsplit, urlunsplit

TEST_DB_NAME = "kasbokar_test"
ADMIN_TELEGRAM_IDS = "12345"


def base_database_url() -> str:
    return (os.environ.get("DATABASE_URL") or "").strip()


def test_database_url() -> str:
    """همان اتصال، فقط نامِ دیتابیس عوض می‌شود. بدونِ DATABASE_URL (تستِ بدونِ دیتابیس) رشتهٔ خالی."""
    raw = base_database_url()
    if not raw:
        return ""
    parts = urlsplit(raw)
    dbname = (parts.path.rsplit("/", 1) or ["", ""])[-1].split("?")[0]
    if dbname == TEST_DB_NAME:
        return raw
    prefix = parts.path.rsplit("/", 1)[0]
    return urlunsplit((parts.scheme, parts.netloc, f"{prefix}/{TEST_DB_NAME}", parts.query, parts.fragment))


def is_test_database(url: str | None = None) -> bool:
    raw = (url if url is not None else base_database_url()) or ""
    if not raw:
        return True  # بدونِ اتصال ⇒ هیچ TRUNCATE‌ای هم رخ نمی‌دهد
    dbname = (urlsplit(raw).path or "").rsplit("/", 1)[-1].split("?")[0]
    return dbname.endswith("_test") or dbname.endswith("_load") or dbname == "test"


def child_env(**extra: str) -> dict[str, str]:
    env = {**os.environ, "ADMIN_TELEGRAM_IDS": ADMIN_TELEGRAM_IDS}
    if base_database_url():
        env["DATABASE_URL"] = test_database_url()
    env.update(extra)
    return env


def _run(args: list[str], note: str) -> int:
    result = subprocess.run(args, env=child_env(), capture_output=True, text=True)
    if result.returncode != 0:
        tail = (result.stdout + result.stderr).strip().splitlines()[-6:]
        print(f"⚠️ {note} موفق نبود: {' / '.join(tail)}")
    return result.returncode


def prepare() -> None:
    """دیتابیسِ تست را می‌سازد (اگر نبود) و مایگریشن‌ها را رویش می‌زند."""
    if not base_database_url():
        return
    boot = urlsplit(base_database_url())
    boot_url = urlunsplit((boot.scheme, boot.netloc, "/postgres", "", ""))
    if _run([sys.executable, "-c", _ENSURE_DB_SNIPPET, boot_url, TEST_DB_NAME], "ساختِ دیتابیسِ تست"):
        return
    _run([sys.executable, "-m", "alembic", "upgrade", "head"], "مایگریشنِ دیتابیسِ تست")


_ENSURE_DB_SNIPPET = """
import asyncio, sys
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

url, name = sys.argv[1], sys.argv[2]

async def main() -> None:
    engine = create_async_engine(url, isolation_level="AUTOCOMMIT")
    async with engine.connect() as conn:
        found = (await conn.execute(text("select 1 from pg_database where datname = :n"), {"n": name})).scalar()
        if not found:
            await conn.execute(text(f'CREATE DATABASE "{name}"'))
            print("created")
        else:
            print("exists")
    await engine.dispose()

asyncio.run(main())
"""
