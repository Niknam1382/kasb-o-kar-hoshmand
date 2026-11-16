"""پ۱۰۶ · نشانه‌هایِ مارکداون نباید در PDFِ راهنما چاپ شوند (یافتهٔ بازرسیِ چشمی).

در `docs/user-guide.md` یکِ `**bold**` از وسطِ خط باز می‌شود و در خطِ بعد بسته می‌شود؛ regexِ تک‌خطی
`_BOLD` آن را نمی‌گیرد و ستاره‌ها عیناً در PDF دیده شدند. سه ادعا:
۱. `plain()` جفت‌هایِ کامل را برمی‌دارد و **هر `**` بی‌جفتی** را هم پاک می‌کند.
۲. هیچ خطی از هیچِ راهنمایِ `.md` که به PDF می‌رود، بعد ازِ `plain()` ستارهٔ مارکداون ندارد.
۳. کدبلوک (`…`) و ایتالیک هم پاک می‌شوند و متنِ فارسیِ خودِ جمله نمی‌سوزد.

اجرا: python3 tests_manual/run_one.py test_p106_pdf_markers.py
"""
from __future__ import annotations

import glob
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from scripts.build_docs_pdf import plain  # noqa: E402


def test_plain_removes_paired_and_unpaired_markers() -> None:
    assert plain("این **مهم** است") == "این مهم است"
    assert plain("هیچ مبلغی هم از کیف‌پولِ") == "هیچ مبلغی هم از کیف‌پولِ"
    assert plain("ادامهٔ **هیچ مبلغی هم از کیف‌پولِ") == "ادامهٔ هیچ مبلغی هم از کیف‌پولِ"
    assert plain("پایانِ **کم نمی‌شود، چون پاسخ ساخته نمی‌شود") == "پایانِ کم نمی‌شود، چون پاسخ ساخته نمی‌شود"
    assert plain("با `docker compose up` شروع کن") == "با docker compose up شروع کن"
    assert plain("کلمهٔ *کج*") == "کلمهٔ کج"
    assert "کیف‌پول" in plain("**کیف‌پولِ** تو"), "متنِ فارسی نباید بسوزد"
    print("PASS test_plain_removes_paired_and_unpaired_markers")


def test_no_guide_line_keeps_markdown_stars_after_plain() -> None:
    """اسکنِ همهٔ مستندات — **در صورتِ دیدنِ `docs/`**.

    `docs/` در `.dockerignore` است ⇒ داخلِ ایمیجِ ربات وجود ندارد و سوئیتِ استاندارد آن را نمی‌بیند.
    اگر نبود، ادعایِ «صفر ستاره در X خط» را **ساخته نمی‌کنیم**: صریح اعلام می‌شود که این قسمت در آن
    محیط اجرا نشده (NOT RUN) و فقط نمونهٔ ساختگیِ داخلِ تست سنجیده می‌شود. رویِ میزبان (یا با
    `-v "$PWD/docs:/app/docs:ro"`) همان اسکنِ کامل اجرا می‌شود.
    """
    paths = sorted(glob.glob("docs/*.md"))
    if not paths:
        lines = [
            "3. اولین‌بار که توکن رو ثبت می‌کنی، ازت می‌پرسه این ربات قراره چیکار کنه: **🛍",
            "   فروشِ محصول** (اگه کالای واقعی با قیمت/موجودی می‌فروشی) یا **💬 مشاوره و",
            "   خدمات** (اگه فقط قراره گفتگو کنه و راهنمایی بده — مثلِ مشاوره یا خدماتِ",
        ]
        for line in lines:
            assert "**" not in plain(line), line[:60]
        print("PASS test_no_guide_line_keeps_markdown_stars_after_plain (docs/ در این ایمیج نیست ⇒ اسکنِ کامل NOT RUN، نمونهٔ سه‌خطی سنجیده شد)")
        return
    checked = 0
    for path in paths:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                stripped = plain(line)
                checked += 1
                assert "**" not in stripped, f"{path}: {line[:80]}"
    assert checked > 5_000, checked
    print(f"PASS test_no_guide_line_keeps_markdown_stars_after_plain ({checked} خط از {len(paths)} فایل)")


def main() -> None:
    test_plain_removes_paired_and_unpaired_markers()
    test_no_guide_line_keeps_markdown_stars_after_plain()


if __name__ == "__main__":
    main()
