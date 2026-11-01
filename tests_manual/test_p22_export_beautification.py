"""
تست: P22 — آراستنِ فایل‌هایِ خروجی (مشکلِ ۴ کاربر: «فاکتور و فایل‌های خروجی را زیباتر کن»)

پوشش:
۱. اکسلِ سفارش‌ها/مشتریان: تاریخِ جلالی به وقتِ تهران (نه «2026-11-02 03:04»)، جداکنندهٔ
   هزارگان رویِ ستون‌هایِ پولی، ردیفِ «جمعِ کل»، فیلترِ خودکار، زبانهٔ رنگی و سرصفحهٔ برند.
۲. فاکتورِ HTML (زاپاسِ فاکتورِ PDF): نوارِ برند، برچسبِ وضعیتِ رنگی برایِ هر سه حالت،
   ردیفِ جمعِ کل و escape شدنِ متنِ کاربر (نامِ محصول با `<script>` نباید اجرا شود).
۳. CSVِ دفترِ ممیزی: سرستونِ فارسی، برچسبِ فارسی برایِ *همهٔ* انواعِ رویداد و تاریخِ جلالی در پنل.

اجرا: python3 tests_manual/run_one.py test_p22_export_beautification.py
"""
from __future__ import annotations

import asyncio
import datetime
import io
import re
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests_manual"))

from openpyxl import load_workbook  # noqa: E402

from harness import reset_database  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from app.bots.main_bot import texts  # noqa: E402
from app.database.models import AuditEventType, Customer, OrderConsultation, OrderType  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import excel_export_service, invoice_service  # noqa: E402
from app.utils import csv_export  # noqa: E402
from app.utils.jalali import JALALI_MONTH_NAMES  # noqa: E402

OWNER_TG_ID = 999_601
SHOP_BOT_TG_ID = 999_602
JALALI_RE = re.compile(r"\d{1,2} (?:" + "|".join(JALALI_MONTH_NAMES) + r") \d{4}")

STAMP = datetime.datetime(2026, 11, 2, 3, 4, tzinfo=datetime.timezone.utc)  # ۱۳:۳۴ به وقتِ تهران


async def _seed_shop() -> int:
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    async with session_scope() as session:
        first = Customer(shop_bot_id=shop_bot_id, telegram_id=2001, first_name="نیلوفر", username="niloofar_shop", first_seen_at=STAMP)
        second = Customer(shop_bot_id=shop_bot_id, telegram_id=2002, first_name="کیوان", first_seen_at=STAMP)
        session.add_all([first, second])
        await session.flush()
        session.add_all(
            [
                OrderConsultation(
                    shop_bot_id=shop_bot_id,
                    customer_id=first.id,
                    type=OrderType.ORDER,
                    summary="خریدِ ۲ عدد کیف",
                    estimated_value_toman=900_000,
                    discount_toman=50_000,
                    created_at=STAMP,
                ),
                OrderConsultation(
                    shop_bot_id=shop_bot_id, customer_id=first.id, type=OrderType.CONSULTATION, summary="سوالِ رنگ‌بندی", created_at=STAMP
                ),
                OrderConsultation(
                    shop_bot_id=shop_bot_id,
                    customer_id=second.id,
                    type=OrderType.ORDER,
                    summary="خریدِ کفش",
                    estimated_value_toman=1_200_000,
                    discount_toman=None,
                    created_at=STAMP,
                ),
            ]
        )
    return shop_bot_id


def _header(ws) -> list:
    return [cell.value for cell in ws[1]]


# ============================================================================= ۱ — اکسل
async def test_orders_workbook_is_beautified() -> None:
    shop_bot_id = await _seed_shop()
    async with session_scope() as session:
        raw = await excel_export_service.build_orders_workbook(session, shop_bot_id)
    ws = load_workbook(io.BytesIO(raw)).active

    assert _header(ws)[0] == "تاریخِ ثبت", _header(ws)
    assert _header(ws)[7] == "ارزشِ تخمینی (تومان)", _header(ws)
    date_cell = ws.cell(row=2, column=1).value
    assert JALALI_RE.search(date_cell or ""), f"تاریخ باید جلالی باشد: {date_cell!r}"
    assert "ساعت" in date_cell and "T" not in (date_cell or ""), date_cell
    assert str(ws["A1"].fill.start_color.rgb).endswith("0F5E5C"), "سرصفحه باید رنگِ برند باشد"
    assert ws.sheet_properties.tabColor is not None, "برگه باید زبانهٔ رنگی داشته باشد"
    assert ws.freeze_panes == "A2" and ws.sheet_view.rightToLeft is True

    money = [c for c in ws["H"] if isinstance(c.value, (int, float))]
    assert money and all(c.number_format == "#,##0;[Red]-#,##0" for c in money), [c.number_format for c in money]

    last = ws.max_row
    assert ws.cell(row=last, column=1).value == "جمعِ کل", ws.cell(row=last, column=1).value
    assert ws.cell(row=last, column=8).value == 2_100_000, ws.cell(row=last, column=8).value
    assert ws.cell(row=last, column=10).value == 50_000, ws.cell(row=last, column=10).value
    # فیلترِ خودکار ردیفِ «جمعِ کل» را در بر نمی‌گیرد (وگرنه جمع به‌عنوانِ داده فیلتر می‌شد)
    assert ws.auto_filter.ref is not None and ws.auto_filter.ref.endswith(str(last - 1)), ws.auto_filter.ref
    print("✅ test_orders_workbook_is_beautified PASSED")


async def test_customers_workbook_has_totals_and_jalali_dates() -> None:
    shop_bot_id = await _seed_shop()
    async with session_scope() as session:
        raw = await excel_export_service.build_customers_workbook(session, shop_bot_id)
    ws = load_workbook(io.BytesIO(raw)).active

    assert "مجموعِ ارزشِ تخمینی (تومان)" in _header(ws), _header(ws)
    seen = ws.cell(row=2, column=4).value  # ستونِ «اولین پیام»
    assert JALALI_RE.search(seen or ""), f"تاریخِ عضویت باید جلالی باشد: {seen!r}"
    last = ws.max_row
    assert ws.cell(row=last, column=1).value == "جمعِ کل"
    assert ws.cell(row=last, column=8).value == 2_100_000, ws.cell(row=last, column=8).value
    print("✅ test_customers_workbook_has_totals_and_jalali_dates PASSED")


# ============================================================================= ۲ — HTMLِ فاکتور
def _invoice_data(**overrides) -> dict:
    data = {
        "number": "INV-1404-0007",
        "date": "11 آبان 1404",
        "shop": "فروشگاهِ آزمون",
        "customer": "مریم رضایی",
        "phone": "09120000000",
        "address": "تهران، آزادی\nپلاکِ ۱۰",
        "items": [{"name": "کیفِ <script>alert(1)</script>", "qty": 2, "line_total": 300_000, "discount": 50_000, "kind": "physical"}],
        "list_total": 300_000,
        "discount": 50_000,
        "shipping": 40_000,
        "shipping_method": "پستِ <b>پیشتاز</b>",
        "total": 290_000,
        "payment_method": "bale",
        "paid": True,
        "signature": True,
    }
    data.update(overrides)
    return data


def test_invoice_html_is_beautified_and_escaped() -> None:
    out = invoice_service.build_invoice_html(_invoice_data())
    assert "dir='rtl'" in out and "#0f5e5c" in out, "باید راست‌به‌چپ و با پالتِ برند باشد"
    assert "class='pill paid'" in out and "✅ پرداخت‌شده" in out, out[:400]
    assert "جمعِ کل" in out and "290,000" in out
    assert "🚚 هزینه‌یِ ارسال" in out and "40,000" in out and "🎁 تخفیف" in out
    # تزریق: نامِ محصول/روشِ ارسال از کاربر می‌آید ⇒ باید escape شود
    assert "<script>" not in out and "&lt;script&gt;" in out, out[:400]
    assert "<b>پیشتاز</b>" not in out and "&lt;b&gt;پیشتاز" in out
    assert "<br>" in out, "آدرسِ چندقطری باید به خط‌شکسته تبدیل شود"

    pending = invoice_service.build_invoice_html(_invoice_data(paid=False))
    assert "class='pill pending'" in pending and "⏳ منتظرِ پرداخت" in pending
    manual = invoice_service.build_invoice_html(_invoice_data(paid=False, payment_method="manual"))
    assert "class='pill manual'" in manual and "پرداخت در محل" in manual
    print("✅ test_invoice_html_is_beautified_and_escaped PASSED")


# ============================================================================= ۳ — CSVِ ممیزی و برچسبِ رویدادها
def test_audit_csv_is_persian_and_every_event_is_labelled() -> None:
    headers = texts.audit_csv_headers()
    assert len(headers) == 8, headers
    for header in headers:
        assert re.search(r"[؀-ۿ]", str(header)), f"سرستونِ فایل باید فارسی باشد: {header}"
    assert "هشِ ردیفِ زنجیره" in headers

    # هیچ نوعِ رویدادی نباید با نامِ خامِ انگلیسی در فایل بماند
    for event in AuditEventType:
        label = texts.audit_event_label(event)
        assert label != event.value, f"بدونِ برچسبِ فارسی: {event.value}"
        assert re.search(r"[؀-ۿ]", label), label

    row = [1, "11 آبان 1404، ساعت 13:34", texts.audit_event_label(AuditEventType.PAYMENT_APPROVED), 7, "@demo", 3, "=SUM(1,2)", "abc"]
    content = csv_export.build_csv(headers, [row])
    assert content.startswith(b"\xef\xbb\xbf"), "BOMِ فارسی لازم است"
    text = content.decode("utf-8-sig")
    assert "'=SUM(1,2)" in text, "خنثی‌سازیِ فرمول باید دست‌نخورده بماند"
    assert "✅ تاییدِ پرداخت" in text

    entry = types.SimpleNamespace(
        event_type=AuditEventType.AUDIT_EXPORTED,
        created_at=STAMP,
        actor_telegram_id=7,
        details="۳۰ ردیف",
    )
    line = texts.audit_log_entry_line(entry)
    assert JALALI_RE.search(line), line
    assert "📥 خروجیِ CSVِ دفترِ ممیزی" in line, line
    print("✅ test_audit_csv_is_persian_and_every_event_is_labelled PASSED")


async def main() -> None:
    await test_orders_workbook_is_beautified()
    await test_customers_workbook_has_totals_and_jalali_dates()
    test_invoice_html_is_beautified_and_escaped()
    test_audit_csv_is_persian_and_every_event_is_labelled()


if __name__ == "__main__":
    asyncio.run(main())
