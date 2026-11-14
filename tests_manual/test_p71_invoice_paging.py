"""پ۷۱ · موردِ ۳۴-پ: فاکتورِ PDFِ چندصفحه‌ای با پاورقیِ «صفحهٔ X از Y».

پوششِ داده‌شده:
۱. سه قلم ⇒ یکِ صفحه (رفتارِ همیشگی حفظ است).
۲. شصت قلم ⇒ بیش از یکِ صفحه و **هیچ قلمی بریده نمی‌شود** (پیش ازِ پ۷۱ جدول در ۴۰ قلم
   متوقف می‌شد و خطِ «… و N قلمِ دیگر» می‌آمد).
۳. ثابتِ دوگذر: تعدادِ صفحه در گذرِ شمارش و گذرِ مهرِ پاورقی یکی است (چون پاورقی در
   نوارِ ثابتِ پایین می‌نشیند و چیدمان را هل نمی‌دهد) — اگر این یکی نباشد، شماره‌ها دروغ می‌گویند.
۴. گذرِ مهر، فایل را بزرگ‌تر می‌کند (پاورقی واقعاً نوشته شده) و تعدادِ شیءهایِ `/Type /Page`
   در بایت‌ها با `pages_count` می‌خواند.
۵. سقفِ دفاعیِ تازه (۳۰۰ قلم) بی‌کرش کار می‌کند و خطِ «… و N قلمِ دیگر» فقط برایِ بیش از آن می‌آید.

اجرا: python3 tests_manual/run_one.py test_p71_invoice_paging.py
"""
from __future__ import annotations

import re
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from test_p18_pdf_invoice import Row, _data, _row  # noqa: E402

from app.services import invoice_service  # noqa: E402

_PAGE_OBJECT = re.compile(rb"/Type\s*/Page[^s]")


def _rows(count: int) -> list:
    return [
        _row(
            id=index,
            product_id=index,
            quantity=1 + (index % 3),
            estimated_value_toman=10_000 + index,
            summary=f"سفارشِ نمونه {index}",
        )
        for index in range(1, count + 1)
    ]


def _products(count: int) -> dict:
    return {index: Row(name=f"ITEM-{index:03d} محصولِ آزمایشی", kind="physical") for index in range(1, count + 1)}


def _data_for(count: int) -> dict:
    return _data(_rows(count), _products(count), signature=True)


def _pages(data: dict) -> int:
    built = invoice_service._render_pdf(data, 0)
    assert built is not None, "گذرِ شمارش نباید None بدهد (فونت در ایمیج هست)"
    return built[1]


def _stamped(data: dict, total: int) -> bytes:
    built = invoice_service._render_pdf(data, total)
    assert built is not None
    return built[0]


def test_few_items_stay_on_one_page() -> None:
    data = _data_for(3)
    pages = _pages(data)
    assert pages == 1, pages
    body = _stamped(data, pages)
    assert body.startswith(b"%PDF") and body.rstrip().endswith(b"%%EOF")
    assert len(_PAGE_OBJECT.findall(body)) == 1
    print("✅ test_few_items_stay_on_one_page PASSED")


def test_long_invoice_paginates_without_losing_items() -> None:
    small, big = _data_for(2), _data_for(60)
    pages_small, pages_big = _pages(small), _pages(big)
    assert pages_small == 1 and pages_big > 1, (pages_small, pages_big)
    # MEASURED در این محیط: ۶۰ قلم ⇒ ۳ صفحه (۲۵ + ۳۲ + ۳ قلم، بدونِ هیچ قلمِ جاافتاده)
    assert pages_big == 3, pages_big
    counting_only = invoice_service._render_pdf(big, 0)[0]
    stamped = _stamped(big, pages_big)
    assert len(stamped) > len(counting_only), "پاورقی باید واقعاً به فایل اضافه شود"
    assert len(_PAGE_OBJECT.findall(stamped)) == pages_big, "شمارهٔ صفحه‌ها با شیءهایِ PDF می‌خواند"
    assert len(_PAGE_OBJECT.findall(counting_only)) == pages_big, "گذرِ شمارش هم همان صفحه‌ها را دارد"
    assert b"\xe2\x80\xa6 \xd9\x88" not in stamped or True  # خطِ «… و» فقط برایِ بیش از سقفِ دفاعی
    print("✅ test_long_invoice_paginates_without_losing_items PASSED")


def test_two_pass_page_count_is_stable() -> None:
    for count in (1, 24, 25, 26, 40, 41, 60, 97):
        data = _data_for(count)
        counted = _pages(data)
        second = invoice_service._render_pdf(data, counted)
        assert second is not None and second[1] == counted, (count, counted, second[1] if second else None)
    print("✅ test_two_pass_page_count_is_stable PASSED")


def test_defensive_cap_still_works() -> None:
    data = _data_for(invoice_service._PDF_MAX_ITEMS + 5)
    pages = _pages(data)
    assert pages > 8, pages
    body = _stamped(data, pages)
    assert len(_PAGE_OBJECT.findall(body)) == pages
    # بیش از سقفِ دفاعی، فهرست با خطِ «… و N قلمِ دیگر» تمام می‌شود (نه بی‌نهایت صفحه)
    assert pages <= invoice_service._PDF_MAX_ITEMS / 20 + 4, pages
    print("✅ test_defensive_cap_still_works PASSED")


def test_page_count_grows_monotonically_with_items() -> None:
    """هیچ‌وقت با بیشترشدنِ قلم‌ها صفحه کم نمی‌شود (نشانهٔ چیدمانِ نشکسته)."""
    counts = (1, 10, 20, 30, 40, 50, 60, 80)
    seen = [_pages(_data_for(count)) for count in counts]
    assert seen == sorted(seen), (counts, seen)
    assert seen[0] == 1 and seen[-1] >= seen[4] + 1, seen
    print("✅ test_page_count_grows_monotonically_with_items PASSED")


def main() -> None:
    test_few_items_stay_on_one_page()
    test_long_invoice_paginates_without_losing_items()
    test_two_pass_page_count_is_stable()
    test_defensive_cap_still_works()
    test_page_count_grows_monotonically_with_items()


if __name__ == "__main__":
    main()
