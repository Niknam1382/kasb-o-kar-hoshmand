"""فاکتورِ خودکار (C8) + فاکتورِ PDFِ فارسی (P18 · B6).

- اسنپ‌شاتِ ثابتِ اقلام/تخفیف/ارسال/جمع در لحظه‌یِ ساخت (`invoices.data_json`)؛ هرگز بعداً بازنویسی نمی‌شود.
- برایِ هر (فروشگاه، گروه) فقط یک فاکتور (ایدمپوتنت؛ دوباره‌ارسال همان شماره).
- شماره: `INV-{shop_bot_id}-{YYYYMM}-{seq}` با شمارنده‌یِ قفل‌شده (`SELECT … FOR UPDATE`).
- خروجی: پیامِ متنیِ خوانا + فایلِ PDFِ راست‌به‌چپ (فونتِ باندل‌شده یا DejaVu سیستمی).
  اگر هر چیزی در مسیرِ PDF بایستد، `build_invoice_pdf` مقدار None می‌دهد و فراخواننده
  همان HTMLِ چاپ‌پذیرِ قبلی را می‌فرستد ⇒ هیچ‌وقت فاکتور گم نمی‌شود.
بخشِ «منطقِ خالص» (بدونِ DB) جدا و تست‌پذیر است.
"""

from __future__ import annotations

import datetime
import html
import json
import logging
import pathlib

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Invoice, InvoiceCounter, OrderConsultation, Product
from app.services import order_state
from app.services.identity_service import display_user
from app.utils.jalali import format_jalali_date, to_tehran
from app.utils.validators import format_toman

logger = logging.getLogger(__name__)

PAYMENT_METHOD_LABELS = {
    "manual": "پرداختِ دستی/هماهنگی با فروشگاه",
    "card": "کارت‌به‌کارت",
    "bale": "بله‌پی",
    "zarinpal": "زرین‌پال",
}

# ترتیبِ جست‌وجویِ فونت: اولِ باندل‌شده در ایمیج (Vazirmatn — بهترین پوششِ فارسی)،
# بعدِ DejaVu که در Dockerfile با fonts-dejavu-core نصب می‌شود.
_BUNDLED_FONTS_DIR = pathlib.Path(__file__).resolve().parent.parent / "assets" / "fonts"
_SYSTEM_FONTS = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/vazirmatn/Vazirmatn-Regular.ttf",
)
_FONT_CACHE: str | None = None


def font_path() -> str | None:
    """مسیرِ اولین فونتِ فارسیِ موجود؛ None ⇒ هیچ فونتی نیست (PDF ساخته نمی‌شود)."""
    global _FONT_CACHE
    if _FONT_CACHE is not None:
        return _FONT_CACHE or None
    candidates = sorted(_BUNDLED_FONTS_DIR.glob("*.ttf")) if _BUNDLED_FONTS_DIR.is_dir() else []
    candidates += [pathlib.Path(p) for p in _SYSTEM_FONTS]
    for path in candidates:
        if path.is_file():
            _FONT_CACHE = str(path)
            return _FONT_CACHE
    _FONT_CACHE = ""
    return None


def shape_text(value: object) -> str:
    """متنِ فارسی/مختلط ← رشته‌یِ «مرتب‌شده برایِ نمایشِ راست‌به‌چپ» (شکلِ حروف + الگوریتمِ bidi).

    کتابخانه‌ها optionalimport هستند: نبودشان نباید ایمپورتِ ماژول را بشکند — مسیرِ HTML
    همیشه کار می‌کند و فقط PDF غیرفعال می‌شود.
    """
    text = str(value if value is not None else "")
    if not text:
        return ""
    import arabic_reshaper
    from bidi.algorithm import get_display

    return get_display(arabic_reshaper.reshape(text))


# ---------------------------------------------------------------------------
# منطقِ خالص
# ---------------------------------------------------------------------------
def build_invoice_data(
    number: str,
    now: datetime.datetime,
    rows: list,
    products: dict[int, object],
    customer,
    shop_title: str,
    *,
    platform_signature: bool = False,
) -> dict:
    """اسنپ‌شاتِ فاکتور از ردیف‌هایِ گروه. `products`: {product_id: Product} (نامِ فعلیِ محصول)."""
    items = []
    list_total = 0
    for r in rows:
        product = products.get(r.product_id) if r.product_id is not None else None
        qty = r.quantity or 1
        line_after_discount = r.estimated_value_toman or 0
        discount = r.discount_toman or 0
        line_list = line_after_discount + discount
        list_total += line_list
        items.append(
            {
                "name": getattr(product, "name", None) or r.summary,
                "qty": qty,
                "line_total": line_list,
                "discount": discount,
                "kind": getattr(product, "kind", None) or "physical",
            }
        )
    discount_total = sum(i["discount"] for i in items)
    shipping = max((r.shipping_fee_toman or 0) for r in rows) if rows else 0
    first = rows[0] if rows else None
    return {
        "number": number,
        "date": format_jalali_date(to_tehran(now)),
        "shop": shop_title,
        "customer": display_user(customer, "short"),
        "phone": (first.customer_phone if first else None) or getattr(customer, "phone_number", None),
        "address": (first.customer_address or first.checkout_answers) if first else None,
        "items": items,
        "list_total": list_total,
        "discount": discount_total,
        "shipping": shipping,
        "shipping_method": first.shipping_method_name if first else None,
        "total": list_total - discount_total + shipping,
        "payment_method": (first.payment_method if first else None) or "manual",
        "paid": bool(first is not None and order_state.value_of(first.status) in order_state.PAID_OR_LATER),
        "signature": bool(platform_signature),
    }


def format_invoice_text(data: dict) -> str:
    lines = [f"🧾 فاکتورِ {data['number']}", f"📅 {data['date']}", f"🏪 {data['shop']}", ""]
    for item in data["items"]:
        lines.append(f"• {item['name']} × {item['qty']} — {format_toman(item['line_total'])}")
    lines.append("")
    if data.get("discount"):
        lines.append(f"🎁 تخفیف: {format_toman(data['discount'])}")
    if data.get("shipping"):
        method = f" ({data['shipping_method']})" if data.get("shipping_method") else ""
        lines.append(f"🚚 هزینه‌یِ ارسال{method}: {format_toman(data['shipping'])}")
    lines.append(f"💰 جمعِ کل: {format_toman(data['total'])}")
    method_label = PAYMENT_METHOD_LABELS.get(data.get("payment_method") or "manual", "—")
    if data.get("paid"):
        lines.append(f"✅ پرداخت‌شده ({method_label})")
    else:
        lines.append(f"📝 ثبت‌شده — پرداخت در محل/هماهنگی با فروشگاه" if (data.get("payment_method") or "manual") == "manual" else f"⏳ منتظرِ پرداخت ({method_label})")
    if data.get("signature"):
        lines.append("\nصادرشده با «کسب‌وکار هوشمند»")
    return "\n".join(lines)


def build_invoice_html(data: dict) -> str:
    """فایلِ HTMLِ چاپ‌پذیرِ RTL؛ همه‌یِ مقدارها escape می‌شن؛ بدونِ منبعِ خارجی."""
    esc = html.escape
    rows_html = "".join(
        f"<tr><td>{esc(str(i['name']))}</td><td>{i['qty']}</td><td>{esc(format_toman(i['line_total']))}</td></tr>"
        for i in data["items"]
    )
    extra = ""
    if data.get("discount"):
        extra += f"<tr><td colspan='2'>تخفیف</td><td>{esc(format_toman(data['discount']))}</td></tr>"
    if data.get("shipping"):
        extra += f"<tr><td colspan='2'>هزینه‌یِ ارسال</td><td>{esc(format_toman(data['shipping']))}</td></tr>"
    method_label = PAYMENT_METHOD_LABELS.get(data.get("payment_method") or "manual", "—")
    state = "پرداخت‌شده" if data.get("paid") else "ثبت‌شده — پرداخت در محل/هماهنگی"
    customer_block = esc(str(data.get("customer") or ""))
    if data.get("phone"):
        customer_block += f"<br>{esc(str(data['phone']))}"
    if data.get("address"):
        customer_block += f"<br>{esc(str(data['address'])).replace(chr(10), '<br>')}"
    signature = "<p class='sig'>صادرشده با «کسب‌وکار هوشمند»</p>" if data.get("signature") else ""
    return (
        "<!DOCTYPE html><html lang='fa' dir='rtl'><head><meta charset='utf-8'>"
        f"<title>{esc(data['number'])}</title>"
        "<style>body{font-family:Tahoma,Arial,sans-serif;margin:24px;color:#111}"
        "table{width:100%;border-collapse:collapse;margin:16px 0}"
        "th,td{border:1px solid #bbb;padding:8px;text-align:right}th{background:#f2f2f2}"
        ".tot{font-weight:bold;font-size:1.1em}.sig{color:#777;font-size:.85em}"
        "@media print{body{margin:0}}</style></head><body>"
        f"<h2>فاکتور {esc(data['number'])}</h2>"
        f"<p>تاریخ: {esc(data['date'])} — فروشگاه: {esc(str(data['shop']))}</p>"
        f"<p>مشتری: {customer_block}</p>"
        f"<table><tr><th>کالا</th><th>تعداد</th><th>مبلغ</th></tr>{rows_html}{extra}"
        f"<tr class='tot'><td colspan='2'>جمعِ کل</td><td>{esc(format_toman(data['total']))}</td></tr></table>"
        f"<p>وضعیتِ پرداخت: {esc(state)} ({esc(method_label)})</p>{signature}</body></html>"
    )


# ---------------------------------------------------------------------------
# PDF (P18 · B6)
# ---------------------------------------------------------------------------
_PDF_MARGIN = 16.0
_PDF_USABLE = 210.0 - 2 * _PDF_MARGIN  # A4 portrait، بدونِ حاشیه
_COL_NAME = _PDF_USABLE - 22.0 - 56.0
_COL_QTY = 22.0
_COL_PRICE = 56.0
_PDF_MAX_ITEMS = 40  # سقفِ دفاعی: فاکتورِ خیلی بزرگ به HTML/متنِ خلاصه برگردانده می‌شود


def _clip(pdf, text: str, max_width: float) -> str:
    """متن را در عرضِ ستون نگه می‌دارد (با …) — نامِ محصولِ طولانی جدول را نمی‌شکند."""
    if pdf.get_string_width(text) <= max_width:
        return text
    while text and pdf.get_string_width(text + "…") > max_width:
        text = text[:-1]
    return (text + "…") if text else ""


def build_invoice_pdf(data: dict) -> bytes | None:
    """فاکتورِ A4ِ راست‌به‌چپ. هر مانعی (کتابخانه، فونت، خطایِ رندر) ⇒ None + لاگ؛ فراخواننده HTML می‌فرستد."""
    font = font_path()
    if font is None:
        logger.warning("B6: هیچ فونتِ فارسیِ قابلِ استفاده پیدا نشد ⇒ فاکتور به‌صورتِ HTML.")
        return None
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display
        from fpdf import FPDF
    except Exception:
        logger.warning("B6: کتابخانه‌هایِ PDF نصب نیستند ⇒ فاکتور به‌صورتِ HTML.", exc_info=True)
        return None

    def fa(value: object) -> str:
        text = str(value if value is not None else "")
        return get_display(arabic_reshaper.reshape(text)) if text else ""

    try:
        pdf = FPDF(format="A4")
        pdf.set_margins(_PDF_MARGIN, _PDF_MARGIN, _PDF_MARGIN)
        pdf.set_auto_page_break(True, margin=_PDF_MARGIN + 6)
        pdf.add_font("fa", "", font)
        pdf.add_page()
        right = _PDF_MARGIN + _PDF_USABLE

        def line_text(text: str, size: float, height: float = 6.5, color: tuple[int, int, int] = (17, 17, 17)) -> None:
            pdf.set_font("fa", "", size)
            pdf.set_text_color(*color)
            pdf.cell(_PDF_USABLE, height, fa(text), new_x="LMARGIN", new_y="NEXT", align="R")
            pdf.set_text_color(17, 17, 17)

        def rule(weight: float = 0.4, color: tuple[int, int, int] = (150, 150, 150)) -> None:
            pdf.set_draw_color(*color)
            pdf.set_line_width(weight)
            y = pdf.get_y()
            pdf.line(_PDF_MARGIN, y, right, y)
            pdf.ln(2.5)

        # --- سرصفحه: نامِ فروشگاه + شماره + تاریخِ جلالی
        line_text(str(data.get("shop") or "—"), 16, 9.0)
        line_text(f"فاکتور {data.get('number') or '—'}", 12, 7.0, (60, 60, 60))
        line_text(f"تاریخ: {data.get('date') or '—'}", 10, 6.5, (60, 60, 60))
        rule(0.8, (35, 35, 35))

        # --- مشتری / تماس / آدرس
        line_text(f"مشتری: {data.get('customer') or '—'}", 10)
        if data.get("phone"):
            line_text(f"تماس: {data['phone']}", 10)
        address = str(data.get("address") or "").strip()
        if address:
            pdf.set_font("fa", "", 9.5)
            pdf.multi_cell(_PDF_USABLE, 5.2, fa("آدرسِ تحویل: " + address), align="R")
        pdf.ln(1.5)

        # --- جدولِ اقلام (ستون‌ها راست‌به‌چپ: کالا، تعداد، مبلغ)
        def row(cells: list[tuple[float, str]], *, header: bool = False, strong: bool = False) -> None:
            widths = [w for w, _ in cells]
            height = 7.2
            y = pdf.get_y()
            x = right
            pdf.set_font("fa", "", 10 if not strong else 10.5)
            if header:
                pdf.set_fill_color(242, 242, 242)
            for width, text in cells:
                x -= width
                pdf.set_xy(x, y)
                align = "R" if width == _COL_NAME else "C"
                content = fa(text)
                if width == _COL_NAME:
                    content = _clip(pdf, content, width - 2.5)
                pdf.cell(width, height, content, border=1, align=align, fill=header)
            pdf.set_xy(_PDF_MARGIN, y + height)

        row([(_COL_NAME, "کالا"), (_COL_QTY, "تعداد"), (_COL_PRICE, "مبلغ")], header=True)
        for item in (data.get("items") or [])[:_PDF_MAX_ITEMS]:
            kind = " (دیجیتال)" if item.get("kind") == "digital" else ""
            row([
                (_COL_NAME, f"{item.get('name') or '—'}{kind}"),
                (_COL_QTY, str(item.get("qty") or 1)),
                (_COL_PRICE, format_toman(int(item.get("line_total") or 0))),
            ])
        if len(data.get("items") or []) > _PDF_MAX_ITEMS:
            line_text(f"… و {len(data['items']) - _PDF_MAX_ITEMS} قلمِ دیگر", 9, 6.0, (90, 90, 90))

        # --- جمع‌ها
        row([(_COL_NAME + _COL_QTY, "جمعِ اقلام"), (_COL_PRICE, format_toman(int(data.get("list_total") or 0)))])
        if data.get("discount"):
            row([(_COL_NAME + _COL_QTY, "تخفیف"), (_COL_PRICE, "− " + format_toman(int(data["discount"])))])
        if data.get("shipping"):
            method = f" — {data['shipping_method']}" if data.get("shipping_method") else ""
            row([(_COL_NAME + _COL_QTY, f"هزینه‌یِ ارسال{method}"), (_COL_PRICE, format_toman(int(data["shipping"])))])
        pdf.set_fill_color(248, 248, 248)
        row([(_COL_NAME + _COL_QTY, "جمعِ کل"), (_COL_PRICE, format_toman(int(data.get("total") or 0)))], strong=True)
        pdf.ln(2.0)

        # --- وضعیتِ پرداخت
        method_label = PAYMENT_METHOD_LABELS.get(data.get("payment_method") or "manual", "—")
        if data.get("paid"):
            line_text(f"پرداخت‌شده ✓ ({method_label})", 10.5)
        elif (data.get("payment_method") or "manual") == "manual":
            line_text("ثبت‌شده — پرداخت در محل/هماهنگی با فروشگاه", 10.5)
        else:
            line_text(f"منتظرِ پرداخت ({method_label})", 10.5)

        # --- پاورقی
        rule(0.4)
        if data.get("signature"):
            line_text("صادرشده با «کسب‌وکار هوشمند»", 9, 5.5, (110, 110, 110))
        line_text(f"این فاکتور رایانه‌ای تولید شده و بدونِ امضا معتبر است — شماره‌یِ {data.get('number') or '—'}", 8.5, 5.5, (110, 110, 110))

        return bytes(pdf.output())
    except Exception:
        logger.exception("B6: ساختِ PDFِ فاکتور ناموفق بود ⇒ فاکتور HTML فرستاده می‌شود.")
        return None


# ---------------------------------------------------------------------------
# DB
# ---------------------------------------------------------------------------
def _period(now: datetime.datetime) -> str:
    return now.strftime("%Y%m")


async def _next_seq(session: AsyncSession, shop_bot_id: int, period: str) -> int:
    """شمارنده‌یِ امن: ردیف با قفل خوانده می‌شه؛ اگه نبود با savepoint ساخته می‌شه (رقابتِ ساخت ⇒ دوباره‌خوانی)."""
    query = (
        select(InvoiceCounter)
        .where(InvoiceCounter.shop_bot_id == shop_bot_id, InvoiceCounter.period == period)
        .with_for_update()
    )
    counter = (await session.execute(query)).scalar_one_or_none()
    if counter is None:
        try:
            async with session.begin_nested():
                session.add(InvoiceCounter(shop_bot_id=shop_bot_id, period=period, last_seq=0))
        except IntegrityError:
            pass
        counter = (await session.execute(query)).scalar_one()
    counter.last_seq += 1
    await session.flush()
    return counter.last_seq


async def get_invoice(session: AsyncSession, shop_bot_id: int, group_id: str) -> Invoice | None:
    result = await session.execute(select(Invoice).where(Invoice.shop_bot_id == shop_bot_id, Invoice.group_id == group_id))
    return result.scalar_one_or_none()


async def ensure_invoice(
    session: AsyncSession,
    rows: list[OrderConsultation],
    customer,
    shop_title: str,
    *,
    platform_signature: bool = False,
) -> tuple[Invoice, bool]:
    """فاکتورِ این گروه (ایدمپوتنت). برمی‌گرداند (فاکتور، تازه‌ساخته‌شد؟)."""
    first = rows[0]
    group_id = first.cart_checkout_group_id or f"o{first.id}"
    existing = await get_invoice(session, first.shop_bot_id, group_id)
    if existing is not None:
        return existing, False

    now = datetime.datetime.now(datetime.timezone.utc)
    seq = await _next_seq(session, first.shop_bot_id, _period(now))
    number = f"INV-{first.shop_bot_id}-{_period(now)}-{seq}"
    product_ids = {r.product_id for r in rows if r.product_id is not None}
    products: dict[int, Product] = {}
    for pid in product_ids:
        product = await session.get(Product, pid)
        if product is not None:
            products[pid] = product
    data = build_invoice_data(number, now, rows, products, customer, shop_title, platform_signature=platform_signature)
    invoice = Invoice(
        shop_bot_id=first.shop_bot_id,
        group_id=group_id,
        number=number,
        data_json=json.dumps(data, ensure_ascii=False),
    )
    try:
        async with session.begin_nested():
            session.add(invoice)
    except IntegrityError:
        # رقابت: هم‌زمان کسِ دیگه ساخته ⇒ همونو برگردون
        existing = await get_invoice(session, first.shop_bot_id, group_id)
        if existing is not None:
            return existing, False
        raise
    return invoice, True


def load_data(invoice: Invoice) -> dict:
    return json.loads(invoice.data_json)
