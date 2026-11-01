#!/usr/bin/env python3
"""اجرایِ یکِ فایلِ تست رویِ دیتابیسِ جدا (P22).

تا پیشِ این برایِ دیدنِ خطایِ یکِ فایل، آن را دستی اجرا می‌کردیم؛ آن مسیر رویِ
دیتابیسِ توسعه اجرا می‌شد و `reset_database()` تنظیماتِ پنل را پاک می‌کرد. این پوسته
همان کاری را می‌کند که run_all_tests.py می‌کند، برایِ یکِ فایل:

    python3 tests_manual/run_one.py test_crm.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import db_env

TEST_DIR = Path(__file__).parent


def main() -> int:
    if len(sys.argv) != 2:
        print("استفاده: python3 tests_manual/run_one.py <نامِ فایلِ تست>")
        return 2
    filename = sys.argv[1]
    path = TEST_DIR / filename
    if not path.is_file():
        print(f"❌ پیدا نشد: {path}")
        return 2
    db_env.prepare()
    proc = subprocess.run([sys.executable, str(path)], cwd=str(TEST_DIR.parent), env=db_env.child_env())
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
