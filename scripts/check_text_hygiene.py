#!/usr/bin/env python3
"""گیتِ پاکیزگیِ متن: نویسه‌هایِ الفباهایِ دیگر نباید داخلِ متنِ فارسی بنشینند.

سه بار در این پروژه رخ داد (دو نویسهٔ CJK در متنِ ربات و یکِ واژهٔ روسی در کامنتِ کد؛ همه
تصادفِ تایپِ فارسی با کیبوردِ اشتباه‌اند). Latin عمداً بررسی نمی‌شود چون نامِ تابع، URL و
`noqa` بخشی از کدند؛ واژگانی که «حرفِ فارسیِ هوشِ همان» را می‌سازند (ژ، چ، پ) هم آزادند.
"""

from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SUFFIXES = {".py", ".md", ".yml", ".yaml", ".html"}

# سیریلیک،CJK (هان/هیراگان/کاتاکانا/هانجی)، هیراگان گسترده، فرم‌هایِpresentationِ عربی
FOREIGN = re.compile(r"[Ѐ-ӿ㐀-䶿一-鿿぀-ヿ가-힯ᄀ-ᇿﹰ-﻾]")
PERSIAN = re.compile(r"[؀-ۿ]")


def scan() -> list[str]:
    problems: list[str] = []
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or path.suffix not in SUFFIXES:
            continue
        rel = path.relative_to(ROOT)
        if any(part in {".git", "venv", "__pycache__", "node_modules", "backups"} for part in rel.parts):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            if FOREIGN.search(line) is None:
                continue
            if PERSIAN.search(line) is None:
                continue
            chars = " ".join(f"{c}(U+{ord(c):04X})" for c in set(FOREIGN.findall(line)))
            problems.append(f"{rel}:{lineno}: {chars} — {line.strip()[:80]}")
    return problems


def main() -> int:
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    problems = scan()
    if problems:
        print("خطایِ پاکیزگیِ متن (نویسهٔ بیگانه در خطِ فارسی):")
        for item in problems[:30]:
            print("  " + item)
        if len(problems) > 30:
            print(f"  … و {len(problems) - 30} موردِ دیگر")
        print("❌ گیتِ check_text_hygiene رد شد.")
        return 1
    print("OK — هیچ نویسهٔ سیریلیک/CJK/هانجی در متنِ فارسی نیست")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
