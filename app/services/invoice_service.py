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
from app.services.identity_service import display_name
from app.utils.jalali import format_jalali_date, to_tehran
from app.utils.validators import fa_grouped, fa_number, format_toman, normalize_iran_phone

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
def invoice_phone_display(value: object) -> str:
    """شماره در فاکتور: فرمتِ ملی و ارقامِ فارسی («۰۹۱۲…» نه «+۹۸…») تا هیچ کاراکترِ لاتین
    داخلِ متنِ فارسی ننشیند؛ کاوشِ همین پاس نشان داد رشته‌هایِ مخلوط در PDF جابه‌جا می‌شوند."""
    raw = str(value or "").strip()
    if not raw:
        return "—"
    return fa_number(normalize_iran_phone(raw) or raw)


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
        "customer": display_name(customer),
        "username": (getattr(customer, "username", None) or "").strip() or None,
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
    """کپشنِ متنیِ فاکتور در چتِ مشتری — P27: ارقامِ فارسی و بدونِ پرانتزِ لاتین، تا متنِ فارسی
    و رشتهٔ لاتین (شمارهٔ فاکتور استثناست) در یکِ خطِ نامرتبِ دوجیهتی درنیاید."""
    lines = [f"🧾 فاکتورِ {data['number']}", f"📅 {data['date']}", f"🏪 {data['shop']}", ""]
    for item in data["items"]:
        lines.append(f"• {item['name']} × {fa_number(item['qty'])} عدد — {format_toman(item['line_total'])}")
    lines.append("")
    if data.get("discount"):
        lines.append(f"🎁 تخفیف: {format_toman(data['discount'])}")
    if data.get("shipping"):
        method = f" «{data['shipping_method']}»" if data.get("shipping_method") else ""
        lines.append(f"🚚 هزینه‌یِ ارسال{method}: {format_toman(data['shipping'])}")
    lines.append(f"💰 جمعِ کل: {format_toman(data['total'])}")
    method_label = PAYMENT_METHOD_LABELS.get(data.get("payment_method") or "manual", "—")
    if data.get("paid"):
        lines.append(f"✅ پرداخت‌شده «{method_label}»")
    else:
        lines.append("📝 ثبت‌شده — پرداخت در محل/هماهنگی با فروشگاه" if (data.get("payment_method") or "manual") == "manual" else f"⏳ منتظرِ پرداخت ({method_label})")
    if data.get("signature"):
        lines.append("\nصادرشده با «کسب‌وکار هوشمند»")
    return "\n".join(lines)


def build_invoice_html(data: dict) -> str:
    """فایلِ HTMLِ چاپ‌پذیرِ RTL (زاپاسِ فاکتورِ PDF) — P22 (مشکلِ ۴): همانِ پالتِ برند،
    نوارِ سرصفحه، برچسبِ وضعیتِ رنگی، ردیف‌هایِ یک‌در‌میان و جمعِ کلِ برجسته.
    همه‌یِ مقدارها escape می‌شوند و هیچِ منبعِ خارجی (فونت/CSS/تصویر) ندارند."""
    esc = html.escape
    method_label = PAYMENT_METHOD_LABELS.get(data.get("payment_method") or "manual", "—")
    if data.get("paid"):
        status_class, status_text = "paid", f"✅ پرداخت‌شده · {method_label}"
    elif (data.get("payment_method") or "manual") == "manual":
        status_class, status_text = "manual", "📝 ثبت‌شده — پرداخت در محل/هماهنگی"
    else:
        status_class, status_text = "pending", f"⏳ منتظرِ پرداخت · {method_label}"

    item_rows = "".join(
        f"<tr><td>{esc(str(i['name']))}</td><td class='n'>{esc(str(i['qty']))}</td>"
        f"<td class='m'>{esc(format_toman(i['line_total']))}</td></tr>"
        for i in data["items"]
    )
    extra = ""
    if data.get("discount"):
        extra += f"<tr><td>🎁 تخفیف</td><td></td><td class='m'>− {esc(format_toman(data['discount']))}</td></tr>"
    if data.get("shipping"):
        ship_label = "🚚 هزینه‌یِ ارسال" + (f" ({esc(str(data['shipping_method']))})" if data.get("shipping_method") else "")
        extra += f"<tr><td>{ship_label}</td><td></td><td class='m'>{esc(format_toman(data['shipping']))}</td></tr>"

    customer_block = esc(str(data.get("customer") or ""))
    if data.get("username"):
        customer_block += f"<br>{esc(str(data['username']))}"
    if data.get("phone"):
        customer_block += f"<br>{esc(invoice_phone_display(data['phone']))}"
    if data.get("address"):
        customer_block += f"<br>{esc(str(data['address'])).replace(chr(10), '<br>')}"
    signature = "<p class='foot'>صادرشده با «کسب‌وکار هوشمند»</p>" if data.get("signature") else ""
    return (
        "<!DOCTYPE html><html lang='fa' dir='rtl'><head><meta charset='utf-8'>"
        f"<title>{esc(str(data['number']))}</title>"
        "<style>"
        "body{font-family:Tahoma,Arial,sans-serif;margin:24px;color:#1f2933;background:#fff;line-height:1.7}"
        ".card{max-width:760px;margin:0 auto}"
        ".band{background:#0f5e5c;color:#fff;padding:14px 18px;border-radius:10px;display:flex;"
        "justify-content:space-between;align-items:center;gap:12px}"
        ".band h2{margin:0;font-size:1.15em}"
        ".pill{padding:4px 12px;border-radius:999px;font-size:.85em;white-space:nowrap}"
        ".pill.paid{background:#167444;color:#fff}.pill.pending{background:#b06a0a;color:#fff}"
        ".pill.manual{background:#e5e7eb;color:#374151}"
        ".meta{display:flex;flex-wrap:wrap;gap:4px 24px;margin:16px 2px 4px;color:#4b5563;font-size:.92em}"
        ".meta b{color:#1f2933;font-weight:600}"
        "table{width:100%;border-collapse:collapse;margin-top:8px}"
        "thead th{background:#e4efea;color:#0f5e5c;border-bottom:2px solid #0f5e5c;padding:9px;text-align:right}"
        "td{border-bottom:1px solid #e5e7eb;padding:9px}"
        "tbody tr:nth-child(even) td{background:#f7faf9}"
        ".m,.n{text-align:left;white-space:nowrap}"
        "tr.tot td{background:#0f5e5c;color:#fff;font-weight:700;font-size:1.05em;border:none}"
        ".foot{margin-top:16px;color:#7b8794;font-size:.85em;text-align:center}"
        "@media print{body{margin:0}.card{max-width:none}}"
        "</style></head><body><div class='card'>"
        f"<div class='band'><h2>🧾 فاکتورِ {esc(str(data['number']))}</h2>"
        f"<span class='pill {status_class}'>{esc(status_text)}</span></div>"
        f"<div class='meta'><span>🏪 <b>{esc(str(data['shop']))}</b></span>"
        f"<span>📅 {esc(str(data['date']))}</span>"
        f"<span>👤 {customer_block}</span></div>"
        "<table><thead><tr><th>کالا</th><th>تعداد</th><th>مبلغ</th></tr></thead>"
        f"<tbody>{item_rows}{extra}"
        f"<tr class='tot'><td>جمعِ کل</td><td></td><td class='m'>{esc(format_toman(data['total']))}</td></tr>"
        "</tbody></table>"
        f"{signature}</div></body></html>"
    )


# ---------------------------------------------------------------------------
# PDF (P18 · B6)
# ---------------------------------------------------------------------------
_PDF_MARGIN = 16.0
_PDF_USABLE = 210.0 - 2 * _PDF_MARGIN  # A4 portrait، بدونِ حاشیه
_COL_NAME = _PDF_USABLE - 18.0 - 56.0  # کالا | تعداد | مبلغ
_COL_QTY = 18.0
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

        def rule(weight: float = 0.4, color: tuple[int, int, int] = (150, 150, 150)) -> None:
            pdf.set_draw_color(*color)
            pdf.set_line_width(weight)
            y = pdf.get_y()
            pdf.line(_PDF_MARGIN, y, right, y)
            pdf.ln(2.5)

        # --- پالتِ برند (P27 · زیباییِ فاکتور): نوارِ سرصفحهٔ بلند، پنلِ نرمِ مشخصات،
        # جدولِ یک‌در‌میان، کادرِ جمعِ کل و پاورقیِ چسبانِ پایینِ صفحه. رنگ‌ها کم‌تعداد و
        # چاپی‌دوست‌اند (در چاپِ سیاه‌وسفید هم خوانا می‌مانند).
        brand = (15, 94, 92)
        brand_soft = (238, 246, 245)
        zebra = (248, 250, 250)
        ink = (17, 17, 17)
        ink_soft = (95, 95, 95)
        discount_ink = (151, 58, 46)
        rule_grey = (150, 150, 150)
        a4_height = 297.0

        def line_text(
            text: str,
            size: float,
            height: float = 6.5,
            color: tuple[int, int, int] = ink,
            *,
            width: float = _PDF_USABLE,
            align: str = "R",
        ) -> None:
            pdf.set_font("fa", "", size)
            pdf.set_text_color(*color)
            pdf.cell(width, height, fa(text), new_x="LMARGIN", new_y="NEXT", align=align)
            pdf.set_text_color(*ink)

        def two_cell(label: str, value: str, *, size: float = 10.0, height: float = 6.8, label_width: float = 46.0) -> None:
            """برچسبِ فارسی سمتِ راست، مقدار سمتِ چپ — در دو سلولِ جدا.

            چرا جدا؟ کاوشِ زندهٔ همین پاس (arabic_reshaper + get_display) نشان داد وقتی در یکِ رشته
            متنِ فارسی، شمارهٔ لاتین و تاریخِ عددی کنار هم می‌نشینند، الگوریتمِ bidi ترتیب را
            به‌هم می‌ریزد: «فاکتور INV-3-… · ۱۴۰۵/۰۸/۱۱» به‌شکلِ «INV-3-… · ۱۴۰۵/۰۸/۱۱ فاکتور»
            رستر می‌شد. یکِ رشته یا کاملاً فارسی است یا یکِ برچسب + یکِ مقدار.
            """
            y = pdf.get_y()
            pdf.set_font("fa", "", size)
            pdf.set_text_color(*ink)
            pdf.set_xy(right - label_width - 2.0, y)
            pdf.cell(label_width, height, fa(label), align="R")
            pdf.set_text_color(*ink_soft)
            pdf.set_xy(_PDF_MARGIN + 2.0, y)
            pdf.cell(_PDF_USABLE - label_width - 4.0, height, fa(value), align="R")
            pdf.set_text_color(*ink)
            pdf.set_xy(_PDF_MARGIN, y + height)

        def band(shop_title: str, number: str, date: str) -> None:
            """نوارِ سرصفحه: نامِ فروشگاه بزرگ و سفید؛ شماره و تاریخ در خط‌هایِ جدا."""
            height = 26.0
            top = pdf.get_y()
            pdf.set_fill_color(*brand)
            pdf.rect(_PDF_MARGIN, top, _PDF_USABLE, height, style="F")
            pdf.set_text_color(255, 255, 255)
            pdf.set_font("fa", "", 15)
            pdf.set_xy(_PDF_MARGIN + 2.0, top + 2.0)
            pdf.cell(_PDF_USABLE - 4.0, 9.0, fa(_clip(pdf, shop_title, _PDF_USABLE - 4.0)), align="R")
            pdf.set_font("fa", "", 9)
            pdf.set_xy(_PDF_MARGIN + 2.0, top + 12.2)
            pdf.cell(_PDF_USABLE - 4.0, 5.4, fa(f"شمارهٔ فاکتور: {number}"), align="R")
            pdf.set_xy(_PDF_MARGIN + 2.0, top + 18.0)
            pdf.cell(_PDF_USABLE - 4.0, 5.4, fa(f"تاریخ: {date}"), align="R")
            pdf.set_text_color(*ink)
            pdf.set_xy(_PDF_MARGIN, top + height + 3.5)

        def chip(label: str, color: tuple[int, int, int]) -> None:
            width = min(_PDF_USABLE, pdf.get_string_width(fa(label)) + 10.0)
            pdf.set_fill_color(*color)
            pdf.set_text_color(255, 255, 255)
            pdf.set_font("fa", "", 10)
            pdf.set_xy(right - width, pdf.get_y())
            pdf.cell(width, 8.0, fa(label), align="C", fill=True)
            pdf.set_text_color(*ink)
            pdf.set_xy(_PDF_MARGIN, pdf.get_y() + 8.0)

        # --- سرصفحه
        band(
            str(data.get("shop") or "—"),
            str(data.get("number") or "—"),
            str(data.get("date") or "—"),
        )

        # --- پنلِ مشخصات (بک‌گراندِ نرم، برچسب/مقدار در دو ستونِ جدا)
        address = str(data.get("address") or "").strip()
        meta_rows = [
            ("مشتری:", str(data.get("customer") or "—")),
            ("تماس:", invoice_phone_display(data.get("phone"))),
        ]
        username = str(data.get("username") or "").strip()
        if username:
            meta_rows.insert(1, ("یوزرنیم:", username if username.startswith("@") else f"@{username}"))
        # ارتفاعِ پنل از رویِ قدراِسنجیِ واقعیِ متنِ آدرس حساب می‌شود (چندخطی شدنِ آدرس
        # جدول را زیرِ کادرِ نرم هل نمی‌دهد)؛ fpdf2 با dry_run قدِ سلول را می‌دهد.
        pdf.set_font("fa", "", 9.6)
        address_height = (
            float(pdf.multi_cell(_PDF_USABLE - 4.0, 5.0, fa(address), align="R", dry_run=True, output="HEIGHT"))
            if address else 0.0
        )
        panel_height = 6.8 * len(meta_rows) + (address_height + 1.6 if address else 0.0) + 4.0
        panel_top = pdf.get_y()
        pdf.set_fill_color(*brand_soft)
        pdf.rect(_PDF_MARGIN, panel_top, _PDF_USABLE, panel_height, style="F")
        pdf.set_xy(_PDF_MARGIN + 2.0, panel_top + 2.0)
        for label, value in meta_rows:
            two_cell(label, value)
        if address:
            pdf.set_font("fa", "", 9.6)
            pdf.set_text_color(*ink_soft)
            pdf.multi_cell(_PDF_USABLE - 4.0, 5.0, fa("آدرسِ تحویل: " + address), align="R")
            pdf.set_text_color(*ink)
        pdf.set_xy(_PDF_MARGIN, panel_top + panel_height + 3.0)

        # --- جدولِ اقلام (ستون‌ها راست‌به‌چپ: کالا، تعداد، مبلغ)
        def row(cells: list[tuple[float, str]], *, header: bool = False, strong: bool = False, shade: bool = False, money_ink=None) -> None:
            height = 8.0 if header else 7.4
            y = pdf.get_y()
            x = right
            pdf.set_font("fa", "", 10 if not header and not strong else 10.5)
            if header:
                pdf.set_fill_color(*brand)
            elif strong:
                pdf.set_fill_color(*brand)
            elif shade:
                pdf.set_fill_color(*zebra)
            if not header and not strong:
                pdf.set_draw_color(*rule_grey)
            for width, text in cells:
                x -= width
                pdf.set_xy(x, y)
                align = "C" if width in (_COL_QTY, _COL_PRICE) else "R"
                content = fa(text)
                if width == _COL_NAME:
                    content = _clip(pdf, content, width - 2.5)
                if header or strong:
                    pdf.set_text_color(255, 255, 255)
                elif money_ink is not None and width == _COL_PRICE:
                    pdf.set_text_color(*money_ink)
                edge = 0 if (header or strong) else "B"
                pdf.cell(width, height, content, border=edge, align=align, fill=header or strong or shade)
                if header or strong:
                    pdf.set_text_color(*ink)
            pdf.set_xy(_PDF_MARGIN, y + height)

        row([(_COL_NAME, "کالا"), (_COL_QTY, "تعداد"), (_COL_PRICE, "مبلغ — تومان")], header=True)
        items = data.get("items") or []
        for index, item in enumerate(items[:_PDF_MAX_ITEMS]):
            kind = " «دیجیتال»" if item.get("kind") == "digital" else ""
            row(
                [
                    (_COL_NAME, f"{item.get('name') or '—'}{kind}"),
                    (_COL_QTY, fa_number(item.get("qty") or 1)),
                    (_COL_PRICE, fa_grouped(int(item.get("line_total") or 0))),
                ],
                shade=index % 2 == 1,
            )
        if len(items) > _PDF_MAX_ITEMS:
            line_text(f"… و {fa_number(len(items) - _PDF_MAX_ITEMS)} قلمِ دیگر", 9, 6.0, ink_soft)

        pdf.ln(1.5)
        # --- جمع‌ها (هم‌ترازِ ستون‌هایِ جدول؛ تخفیف بی‌علامتِ لاتین، فقط با رنگِ متمایز)
        row([(_COL_NAME + _COL_QTY, "جمعِ اقلام"), (_COL_PRICE, fa_grouped(int(data.get("list_total") or 0)))])
        if data.get("discount"):
            row(
                [(_COL_NAME + _COL_QTY, "تخفیف"), (_COL_PRICE, fa_grouped(int(data["discount"])))],
                shade=True,
                money_ink=discount_ink,
            )
        if data.get("shipping"):
            row([(_COL_NAME + _COL_QTY, "هزینهٔ ارسال"), (_COL_PRICE, fa_grouped(int(data["shipping"])))])
            if data.get("shipping_method"):
                line_text(f"روشِ ارسال: {data['shipping_method']}", 9, 5.6, ink_soft)
        row(
            [(_COL_NAME + _COL_QTY, "جمعِ کل — تومان"), (_COL_PRICE, fa_grouped(int(data.get("total") or 0)))],
            strong=True,
        )
        pdf.ln(4.0)

        # --- وضعیتِ پرداخت (برچسبِ رنگی)
        method_label = PAYMENT_METHOD_LABELS.get(data.get("payment_method") or "manual", "—")
        if data.get("paid"):
            # نکته: فونتِ Vazirmatn نشانهٔ «✓» را ندارد و در PDF جعبه می‌شود (تستِ گلیف همان را
            # می‌گیرد)؛ پس وضعیت فقط با رنگ و متن گفته می‌شود.
            chip(f"پرداخت‌شده — {method_label}", (22, 116, 68))
        elif (data.get("payment_method") or "manual") == "manual":
            chip("ثبت‌شده — پرداخت در محل/هماهنگی با فروشگاه", (96, 96, 96))
        else:
            chip(f"منتظرِ پرداخت — {method_label}", (176, 106, 10))

        # --- پاورقیِ چسبان: خطِ نازک، توضیح، و شماره در سلولِ جدا از متنِ فارسی
        footer_y = max(pdf.get_y() + 8.0, a4_height - _PDF_MARGIN - 16.0)
        pdf.set_xy(_PDF_MARGIN, footer_y)
        pdf.set_draw_color(*rule_grey)
        pdf.set_line_width(0.4)
        pdf.line(_PDF_MARGIN, footer_y, right, footer_y)
        pdf.ln(2.2)
        if data.get("signature"):
            line_text("صادرشده با «کسب‌وکار هوشمند»", 9, 5.4, ink_soft)
        line_text("این فاکتور رایانه‌ای تولید شده و بدونِ امضا معتبر است.", 8.5, 5.4, ink_soft)

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
