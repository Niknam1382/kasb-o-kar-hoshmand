"""فاکتورِ خودکار (C8).

- اسنپ‌شاتِ ثابتِ اقلام/تخفیف/ارسال/جمع در لحظه‌یِ ساخت (`invoices.data_json`)؛ هرگز بعداً بازنویسی نمی‌شود.
- برایِ هر (فروشگاه، گروه) فقط یک فاکتور (ایدمپوتنت؛ دوباره‌ارسال همان شماره).
- شماره: `INV-{shop_bot_id}-{YYYYMM}-{seq}` با شمارنده‌یِ قفل‌شده (`SELECT … FOR UPDATE`).
- خروجی: پیامِ متنیِ خوانا + فایلِ HTMLِ چاپ‌پذیرِ RTL (فونتِ سیستمی، بدونِ منبعِ خارجی).
بخشِ «منطقِ خالص» (بدونِ DB) جدا و تست‌پذیر است.
"""

from __future__ import annotations

import datetime
import html
import json

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Invoice, InvoiceCounter, OrderConsultation, Product
from app.services import order_state
from app.services.identity_service import display_user
from app.utils.jalali import format_jalali_date, to_tehran
from app.utils.validators import format_toman

PAYMENT_METHOD_LABELS = {
    "manual": "پرداختِ دستی/هماهنگی با فروشگاه",
    "card": "کارت‌به‌کارت",
    "bale": "بله‌پی",
    "zarinpal": "زرین‌پال",
}


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
    first = rows[0]
    return {
        "number": number,
        "date": format_jalali_date(to_tehran(now)),
        "shop": shop_title,
        "customer": display_user(customer, "short"),
        "phone": first.customer_phone or getattr(customer, "phone_number", None),
        "address": first.customer_address or first.checkout_answers,
        "items": items,
        "list_total": list_total,
        "discount": discount_total,
        "shipping": shipping,
        "shipping_method": first.shipping_method_name,
        "total": list_total - discount_total + shipping,
        "payment_method": first.payment_method or "manual",
        "paid": order_state.value_of(first.status) in order_state.PAID_OR_LATER,
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
