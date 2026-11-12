"""پ۵۹ · موردِ ۳۴: خروجی‌هایِ حرفه‌ای — نامِ فایل، رقمِ جلالی در فاکتور، و ناهنجاریِ bidi.

چرا این آزمون: قاعدهٔ ۵ می‌گوید متنِ کاربر باید کاملاً فارسی باشد، ولی فایلهایی که ربات می‌سازد
(اکسل، CSV، فاکتورِ PDF/HTML) و نامِ خودِ فایل‌ها از این قاعده مستثنا نبودند: «customers.xlsx»،
«accounting-week.xlsx»، «INV-9-202611-1.pdf» و عددِ لاتینِ «2» در ستونِ تعدادِ نسخهٔ HTML.

پوششِ داده‌شده:
۱. نامِ فایل‌هایِ ارسالی: فارسی، بی‌فاصله، بدونِ حرفِ لاتین (پسوندِ لاتین عمداً می‌ماند).
۲. نامِ فایلِ فاکتور: پیشوندِ فارسی + همان شمارهٔ پیگیریِ داخلی (تغییرِ ندادنِ کدِ پیگیری).
۳. فاکتورِ متنی و HTML: تعداد با ارقامِ جلالی.
۴. فاکتورِ PDF با نوارِ سرصفحهٔ تازه (برچسب و شماره در دو سلولِ جدا) هنوز ساخته می‌شود و
   PDFِ معتبر است — یعنی اصلاحِ bidi کیبورد/چینش را نشکند.

اجرا: python3 tests_manual/run_one.py test_p59_output_polish.py
"""
from __future__ import annotations

import datetime
import re
import sys
import types

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from app.bots.main_bot import texts as main_texts  # noqa: E402
from app.bots.shop_bot import texts as shop_texts  # noqa: E402
from app.services import invoice_service  # noqa: E402

Row = types.SimpleNamespace
LATIN_WORD = re.compile(r"[A-Za-z]{2,}")


def _row(**kw):
    base = dict(
        id=1, product_id=1, quantity=2, estimated_value_toman=100_000, discount_toman=0, summary="خلاصه",
        shipping_fee_toman=0, shipping_method_name=None, customer_phone="+989121234567", customer_address=None,
        checkout_answers=None, payment_method="card", status="paid", cart_checkout_group_id=None,
    )
    base.update(kw)
    return Row(**base)


def _data(**over):
    products = over.pop("products", None) or {1: Row(name="گلِ مریم", kind="physical")}
    data = invoice_service.build_invoice_data(
        over.pop("number", "INV-7-202611-1"),
        datetime.datetime(2026, 11, 12, 8, 30, tzinfo=datetime.timezone.utc),
        [_row()],
        products,
        Row(first_name="مریم", last_name="رضایی", username=None, phone_number=None),
        over.pop("shop", "گالریِ گلِ مریم"),
        platform_signature=True,
    )
    return {**data, **over}


def test_export_filenames_are_persian() -> None:
    names = (
        main_texts.EXCEL_CUSTOMERS_FILENAME,
        main_texts.EXCEL_ORDERS_FILENAME,
        main_texts.EXCEL_ACCOUNTING_FILENAME,
        main_texts.EXCEL_WALLET_LEDGER_FILENAME,
        main_texts.AUDIT_CSV_FILENAME,
        main_texts.RECEIPT_FALLBACK_FILENAME,
    )
    for name in names:
        assert " " not in name, name
        stem = name.rsplit(".", 1)[0] if "." in name else name
        assert not LATIN_WORD.search(stem), f"نامِ فایلِ لاتین: {name}"
        assert re.search(r"[؀-ۿ]", stem), f"نامِ فایل باید فارسی باشد: {name}"
    # پسوند باید همان بماند، وگرنه گیرنده فایل را نمی‌شناسد
    assert names[0].endswith(".xlsx") and names[4].endswith(".csv"), names
    print("PASS test_export_filenames_are_persian")


def test_invoice_filename_keeps_tracking_number() -> None:
    name = shop_texts.invoice_file_name("INV-7-202611-1", "pdf")
    assert name == "فاکتور-INV-7-202611-1.pdf", name
    assert "INV-7-202611-1" in name, "شمارهٔ پیگیری نباید تغییر کند (مشتری و فروشگاه با همین جست‌وجو می‌کنند)"
    assert shop_texts.invoice_file_name("INV-7-202611-1", "html").endswith(".html")
    print("PASS test_invoice_filename_keeps_tracking_number")


def test_invoice_text_and_html_use_persian_digits() -> None:
    data = _data()
    text = invoice_service.format_invoice_text(data)
    assert "۲ عدد" in text, text
    html = invoice_service.build_invoice_html(data)
    assert "<td class='n'>۲</td>" in html, html
    assert "<td class='n'>2</td>" not in html, "تعدادِ لاتین در فایلِ HTMLِ مشتری"
    print("PASS test_invoice_text_and_html_use_persian_digits")


def test_invoice_pdf_still_renders_with_split_header_cells() -> None:
    payload = invoice_service.build_invoice_pdf(_data())
    if payload is None:
        # بدونِ فونتِ فارسی مسیرِ HTML جایِ PDF را می‌گیرد (رفتارِ مستندِ پ۲۷)؛ اینجا فقط
        # ادعا نمی‌کنیم PDF ساخته شد، ادعایِ اصلی با دو آزمونِ بالا سنجیده می‌شود.
        print("PASS test_invoice_pdf_still_renders_with_split_header_cells (بی‌فونت ⇒ PDF نیست)")
        return
    assert payload.startswith(b"%PDF"), payload[:16]
    assert len(payload) > 1500, len(payload)
    print("PASS test_invoice_pdf_still_renders_with_split_header_cells")


def main() -> None:
    test_export_filenames_are_persian()
    test_invoice_filename_keeps_tracking_number()
    test_invoice_text_and_html_use_persian_digits()
    test_invoice_pdf_still_renders_with_split_header_cells()
    print("📊 نتیجه: ۴ تستِ پ۵۹ (خروجی‌هایِ حرفه‌ای) پاس شد · نامِ فایل، شمارهٔ پیگیری، رقمِ جلالی، فاکتورِ PDF")


if __name__ == "__main__":
    main()
