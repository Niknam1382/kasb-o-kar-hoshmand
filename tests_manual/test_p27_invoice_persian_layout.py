"""
تست: P27 — فاکتور قشنگ‌تر، و متنِ فارسی و لاتین در هم قاطی نشود

کاوشِ زندهٔ همین پاس (arabic_reshaper + bidi get_display) نشان داد وقتی در یکِ رشته متنِ فارسی،
شمارهٔ لاتین و تاریخِ عددی کنار هم می‌نشینند، ترتیبِ نمایش به‌هم می‌ریزد:
«فاکتور INV-3-… · ۱۴۰۵/۰۸/۱۱» با «INV-3-…» در جایِ دیگری و جداکننده‌هایِ تاریخِ جداافتاده رستر می‌شد.
پس در فاکتور: برچسبِ فارسی و مقدار در سلول/خطِ جدا، شمارهٔ فاکتور یک‌خطِ مستقل، تاریخ بدونِ
شمارهٔ لاتین در همان رشته، ارقامِ همه فارسی، و «دیجیتال» با گیومهٔ فارسی نه پرانتزِ لاتین.

اجرا: python3 tests_manual/run_one.py test_p27_invoice_persian_layout.py
"""
from __future__ import annotations

import datetime
import re
import sys
from types import SimpleNamespace

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

import arabic_reshaper  # noqa: E402

from app.services import invoice_service  # noqa: E402

PERSIAN = re.compile(r"[؀-ۿ]")
ASCII_LETTER = re.compile(r"[A-Za-z]")
ASCII_DIGIT = re.compile(r"[0-9]")
PERSIAN_DIGIT = re.compile(r"[۰-۹]")

ROWS = [
    SimpleNamespace(
        product_id=1, quantity=2, estimated_value_toman=625_000, discount_toman=125_000,
        shipping_fee_toman=45_000, shipping_method_name="پست پیشتاز", customer_phone="09123456789",
        customer_address="تهران، خیابان ولیعصر، کوچه ۱۲، پلاک ۴۵", payment_method="card",
        status="paid", summary="—"
    ),
    SimpleNamespace(
        product_id=2, quantity=1, estimated_value_toman=300_000, discount_toman=0,
        shipping_fee_toman=45_000, shipping_method_name="پست پیشتاز", customer_phone="09123456789",
        customer_address="تهران، خیابان ولیعصر، کوچه ۱۲، پلاک ۴۵", payment_method="card",
        status="paid", summary="—"
    ),
]
PRODUCTS = {
    1: SimpleNamespace(name="کوله‌پشتی Nike Model-X", kind="physical"),
    2: SimpleNamespace(name="دفترچهٔ یادداشت", kind="digital"),
}
CUSTOMER = SimpleNamespace(first_name="علی", last_name="رضایی", username="ali_r", phone_number="+989123456789", telegram_id=7)


def _data(**over):
    payload = invoice_service.build_invoice_data(
        number="INV-3-202611-07",
        now=datetime.datetime(2026, 11, 2, 12, 0, tzinfo=datetime.timezone.utc),
        rows=ROWS,
        products=PRODUCTS,
        customer=CUSTOMER,
        shop_title="کیف و کفش آریا",
        platform_signature=True,
    )
    payload.update(over)
    return payload


def _captured_strings(data: dict) -> list[str]:
    """هر رشته‌ای که واردِ shaping می‌شود = هر خطِ چاپ‌شده در PDF."""
    original = arabic_reshaper.reshape
    seen: list[str] = []

    def spy(text):
        seen.append(str(text))
        return original(text)

    arabic_reshaper.reshape = spy
    try:
        payload = invoice_service.build_invoice_pdf(data)
    finally:
        arabic_reshaper.reshape = original
    assert payload is not None and payload.startswith(b"%PDF"), "فاکتور باید PDF باشد"
    return seen


# ============================================================================= ۱ — هیچ خطی فارسی + لاتین + رقمِ فارسی نیست
def test_no_line_mixes_latin_letters_with_persian_digits() -> None:
    offenders = []
    parens = []
    for line in _captured_strings(_data()):
        if ASCII_LETTER.search(line) and PERSIAN_DIGIT.search(line):
            offenders.append(line)
        if "(" in line or ")" in line:
            parens.append(line)
    assert not offenders, f"متنِ فارسی و لاتین در یکِ خط (bidi ترتیب را به‌هم می‌ریزد): {offenders}"
    assert not parens, f"پرانتزِ لاتین در متنِ فارسیِ فاکتور: {parens}"
    print("✅ test_no_line_mixes_latin_letters_with_persian_digits PASSED")


# ============================================================================= ۲ — شماره و تاریخ در دو خطِ جدا
def test_number_and_date_are_separate_lines() -> None:
    lines = _captured_strings(_data())
    number_lines = [line for line in lines if "INV-" in line]
    date_lines = [line for line in lines if "آبان" in line]
    assert number_lines and date_lines, (number_lines, date_lines)
    assert not any("INV-" in line and PERSIAN_DIGIT.search(line) for line in lines), "شمارهٔ فاکتور باید در خطِ مستقل باشد"
    assert all(line.count("INV-") == 1 for line in number_lines), number_lines
    assert all(ASCII_DIGIT.search(line) is None for line in date_lines), f"تاریخ نباید رقمِ لاتین داشته باشد: {date_lines}"
    print("✅ test_number_and_date_are_separate_lines PASSED")


# ============================================================================= ۳ — ارقامِ فارسی همه‌جا
def test_amounts_and_quantities_use_persian_digits() -> None:
    lines = _captured_strings(_data())
    with_ascii_digits = [line for line in lines if ASCII_DIGIT.search(line) and "INV-" not in line]
    assert not with_ascii_digits, f"رقمِ لاتین در فاکتور: {with_ascii_digits}"
    assert any("«دیجیتال»" in line for line in lines), "نشانهٔ محصولِ دیجیتال باید با گیومهٔ فارسی باشد"
    assert any(line.startswith("مبلغ") and "تومان" in line for line in lines), "ستونِ مبلغ باید واحد را در سرستون بگوید"
    assert not any(line.endswith("تومان") and "مبلغ" not in line and line.count("تومان") > 1 for line in lines)
    print("✅ test_amounts_and_quantities_use_persian_digits PASSED")


# ============================================================================= ۴ — شماره با فرمتِ ملی و ارقامِ فارسی
def test_invoice_phone_display_is_persian_national_format() -> None:
    assert invoice_service.invoice_phone_display("+989123456789") == "۰۹۱۲۳۴۵۶۷۸۹"
    assert invoice_service.invoice_phone_display("09123456789") == "۰۹۱۲۳۴۵۶۷۸۹"
    assert invoice_service.invoice_phone_display("989123456789") == "۰۹۱۲۳۴۵۶۷۸۹"
    assert invoice_service.invoice_phone_display(None) == "—" and invoice_service.invoice_phone_display("") == "—"
    data = _data()
    assert data["username"] == "ali_r" and data["customer"] == "علی رضایی", data
    assert "+98" not in data["customer"] and "@" not in data["customer"], "نامِ مشتری در فاکتور باید فقط نام باشد"
    html_doc = invoice_service.build_invoice_html(data)
    assert "۰۹۱۲۳۴۵۶۷۸۹" in html_doc and "ali_r" in html_doc, "نسخهٔ HTML هم باید همین نمایش را بدهد"
    print("✅ test_invoice_phone_display_is_persian_national_format PASSED")


# ============================================================================= ۵ — کپشنِ چت هم یکدست فارسی
def test_chat_caption_is_persian_digits_and_no_ascii_parens() -> None:
    text = invoice_service.format_invoice_text(_data())
    assert "× ۲ عدد" in text, text
    assert "(" not in text and ")" not in text, text
    for line in text.splitlines()[1:]:
        assert ASCII_DIGIT.search(line) is None, f"رقمِ لاتین در کپشنِ فاکتور: {line!r}"
    assert "پست پیشتاز" in text and "«پست پیشتاز»" in text, text
    assert "پرداخت‌شده" in text and "کارت‌به‌کارت" in text
    print("✅ test_chat_caption_is_persian_digits_and_no_ascii_parens PASSED")


# ============================================================================= ۶ — شکل‌هایِ لبه هنوز رستر می‌شوند
def test_edge_shapes_still_render_without_breaking() -> None:
    assert invoice_service.build_invoice_pdf(_data(items=[])) is not None, "فاکتورِ بی‌قلم"
    evil = "<script>alert(1)</script>\" OR 1=1-- \n۱۲۳"
    weird = _data(
        customer=evil,
        username="a_b-c",
        phone="00989120000000",
        address=evil * 3,
        shipping_method=evil,
        number=evil,
        items=[{"name": "ی" * 300, "qty": 99, "line_total": 10**15, "discount": 0, "kind": "digital"}],
        list_total=10**15,
        discount=0,
        shipping=0,
        total=10**15,
        paid=False,
        payment_method="zarinpal",
    )
    payload = invoice_service.build_invoice_pdf(weird)
    assert payload is not None and payload.startswith(b"%PDF") and b"<script>" not in payload
    assert invoice_service.build_invoice_html(weird).startswith("<!DOCTYPE html>")
    # بدونِ تاریخ/شماره هم نباید بسازد را بترکاند
    assert invoice_service.build_invoice_pdf(_data(number=None, date=None)) is not None
    print("✅ test_edge_shapes_still_render_without_breaking PASSED")


def main() -> None:
    test_no_line_mixes_latin_letters_with_persian_digits()
    test_number_and_date_are_separate_lines()
    test_amounts_and_quantities_use_persian_digits()
    test_invoice_phone_display_is_persian_national_format()
    test_chat_caption_is_persian_digits_and_no_ascii_parens()
    test_edge_shapes_still_render_without_breaking()
    print("\n✅ همهٔ تست‌هایِ P27ِ «فاکتورِ یکدستِ فارسی و مرتب» پاس شدند")


if __name__ == "__main__":
    main()
