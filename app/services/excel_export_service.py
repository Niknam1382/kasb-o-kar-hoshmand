from __future__ import annotations

import datetime
import io

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.worksheet.worksheet import Worksheet
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Campaign, Customer, OrderConsultation, OrderType, Product, ShopOwner, WalletTransaction
from app.services import accounting_service
from app.utils.jalali import format_jalali_date, format_jalali_datetime

_HEADER_FONT = Font(name="Arial", bold=True, color="FFFFFF")
_HEADER_FILL = PatternFill(fill_type="solid", start_color="2F5496", end_color="2F5496")
_BODY_FONT = Font(name="Arial")
_RTL_ALIGNMENT = Alignment(horizontal="right", readingOrder=2, vertical="center", wrap_text=True)
_HEADER_ALIGNMENT = Alignment(horizontal="center", readingOrder=2, vertical="center", wrap_text=True)
_THIN_SIDE = Side(style="thin", color="BFBFBF")
_CELL_BORDER = Border(left=_THIN_SIDE, right=_THIN_SIDE, top=_THIN_SIDE, bottom=_THIN_SIDE)
_ALT_ROW_FILL = PatternFill(fill_type="solid", start_color="F2F2F2", end_color="F2F2F2")


def _workbook_bytes(wb: Workbook) -> bytes:
    """ذخیره‌یِ کتابِ اکسل با خنثی‌سازیِ تزریقِ فرمول (CSV/Formula injection): متنِ کاربر (نام، آدرس، توضیح…) که با «=» شروع بشه
    openpyxl اون رو *فرمول* ذخیره می‌کنه و باز کردنِ فایل توسطِ فروشگاه‌دار می‌تونه اجراش کنه. همه‌یِ سلول‌هایِ فرمولی به متنِ ساده تبدیل می‌شن."""
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for cell in row:
                if cell.data_type == "f":
                    cell.data_type = "s"
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def _style_sheet(ws: Worksheet) -> None:
    ws.sheet_view.rightToLeft = True
    ws.freeze_panes = "A2"

    for cell in ws[1]:
        cell.font = _HEADER_FONT
        cell.fill = _HEADER_FILL
        cell.alignment = _HEADER_ALIGNMENT
        cell.border = _CELL_BORDER
    ws.row_dimensions[1].height = 24

    for row_idx, row in enumerate(ws.iter_rows(min_row=2), start=2):
        for cell in row:
            cell.font = _BODY_FONT
            cell.alignment = _RTL_ALIGNMENT
            cell.border = _CELL_BORDER
            if row_idx % 2 == 0:
                cell.fill = _ALT_ROW_FILL

    for col in ws.columns:
        max_len = max((len(str(cell.value)) for cell in col if cell.value is not None), default=10)
        ws.column_dimensions[col[0].column_letter].width = min(max(max_len + 4, 12), 45)


def _fmt(dt) -> str:
    return dt.strftime("%Y-%m-%d %H:%M") if dt else ""


async def build_customers_workbook(session: AsyncSession, shop_bot_id: int, consultation: bool = False) -> bytes:
    result = await session.execute(select(Customer).where(Customer.shop_bot_id == shop_bot_id).order_by(Customer.id))
    customers = result.scalars().all()

    # تعداد سفارش/مشاوره و مجموع ارزش تخمینی به‌ازای هر مشتری، با یک کوئری گروه‌بندی‌شده
    stats_result = await session.execute(
        select(
            OrderConsultation.customer_id,
            OrderConsultation.type,
            func.count(),
            func.coalesce(func.sum(OrderConsultation.estimated_value_toman), 0),
        )
        .where(OrderConsultation.shop_bot_id == shop_bot_id)
        .group_by(OrderConsultation.customer_id, OrderConsultation.type)
    )
    per_customer: dict[int, dict[str, int]] = {}
    for customer_id, order_type, count, total_value in stats_result.all():
        key = order_type.value if hasattr(order_type, "value") else order_type
        entry = per_customer.setdefault(customer_id, {"order": 0, "consultation": 0, "value": 0})
        entry[key] = count
        entry["value"] += int(total_value or 0)

    wb = Workbook()
    ws = wb.active
    # C1: در مودِ مشاوره‌ای نه ستون «تعداد سفارش» و نه واژه‌یِ «سفارش» جایی دارد.
    ws.title = "مخاطبان" if consultation else "مشتریان"
    headers = ["نام", "یوزرنیم", "آیدی تلگرام", "اولین پیام", "آخرین پیام"]
    if not consultation:
        headers.append("تعداد سفارش")
    headers += ["تعداد مشاوره", "مجموع ارزش تخمینی (تومان)"]
    ws.append(headers)

    for c in customers:
        stats = per_customer.get(c.id, {"order": 0, "consultation": 0, "value": 0})
        row = [
            c.first_name or "",
            f"@{c.username}" if c.username else "",
            c.telegram_id,
            _fmt(c.first_seen_at),
            _fmt(c.last_message_at),
        ]
        if not consultation:
            row.append(stats["order"])
        row += [stats["consultation"], stats["value"]]
        ws.append(row)

    _style_sheet(ws)
    return _workbook_bytes(wb)


async def build_orders_workbook(session: AsyncSession, shop_bot_id: int, consultation: bool = False) -> bytes:
    result = await session.execute(
        select(OrderConsultation, Customer, Product, Campaign)
        .join(Customer, OrderConsultation.customer_id == Customer.id)
        .outerjoin(Product, OrderConsultation.product_id == Product.id)
        .outerjoin(Campaign, OrderConsultation.campaign_id == Campaign.id)
        .where(OrderConsultation.shop_bot_id == shop_bot_id)
        .order_by(OrderConsultation.id.desc())
    )
    rows = result.all()

    wb = Workbook()
    ws = wb.active
    ws.title = "مشاوره‌ها" if consultation else "سفارش‌ها و مشاوره‌ها"
    ws.append(
        [
            "تاریخ",
            "نوع",
            "مشتری",
            "آیدی تلگرام مشتری",
            "محصول",
            "تعداد",
            "خلاصه",
            "ارزش تخمینی (تومان)",
            "وضعیت تایید",
            # ستون‌هایِ کمپین (فازِ ۳) عمداً *آخر* اضافه شدن تا جایگاهِ ستون‌هایِ قبلی عوض نشه.
            # «ارزش تخمینی» همیشه مبلغِ بعد از تخفیفه.
            "تخفیف کمپین (تومان)",
            "کمپین",
        ]
    )

    type_labels = {"order": "—", "consultation": "مشاوره"} if consultation else {"order": "سفارش", "consultation": "مشاوره"}
    for order, customer, product, campaign in rows:
        order_type = order.type.value if hasattr(order.type, "value") else order.type
        if order_type == OrderType.ORDER.value or product is not None:
            confirmed_label = "✅ تایید و کسر شده" if order.confirmed else "⏳ در انتظار تایید"
        else:
            confirmed_label = "—"

        ws.append(
            [
                _fmt(order.created_at),
                type_labels.get(order_type, order_type),
                customer.first_name or "",
                customer.telegram_id,
                product.name if product is not None else "",
                order.quantity or "",
                order.summary,
                order.estimated_value_toman or "",
                confirmed_label,
                order.discount_toman or "",
                campaign.name if campaign is not None else "",
            ]
        )

    _style_sheet(ws)
    return _workbook_bytes(wb)


# =============================================================================
# فازِ ۴-ه — خروجیِ اکسلِ حسابداری (فقط‌خواندنی) و دفترِ کیف‌پولِ سوپرادمین
# =============================================================================
MAX_LEDGER_ROWS = 50_000


def _plain_sheet(wb: Workbook, title: str, headers: list[str], rows: list[list], first: bool = False) -> Worksheet:
    ws = wb.active if first else wb.create_sheet()
    ws.title = title
    ws.append(headers)
    for row in rows:
        ws.append(row)
    _style_sheet(ws)
    return ws


def _jalali_dt(moment) -> str:
    return format_jalali_datetime(moment) if moment else ""


def build_accounting_workbook(report) -> bytes:
    """اکسلِ چندبرگه‌یِ حسابداریِ یه بازه. هیچ دیتابیسی نمی‌خونه — فقط از خودِ report (که
    accounting_service.build_report ساخته) استفاده می‌کنه، پس بدونِ session تست‌پذیره.
    هیچ نام/تلفنِ مشتری و هیچ متنِ آزادیِ سفارش توش نیست."""
    summary = report.summary
    period = summary.period
    full = accounting_service.summarize_period(
        report.rows, period, report.product_names, report.campaign_names, top_products_limit=None, campaigns_limit=None
    )

    wb = Workbook()
    summary_rows: list[list] = [
        ["بازه", period.label],
        ["از تاریخ", format_jalali_date(period.start)],
        ["تا تاریخ", format_jalali_date(period.end - datetime.timedelta(days=1))],
        ["فروشِ ناخالص (تومان)", summary.gross_toman],
        ["جمعِ تخفیف‌ها (تومان)", summary.discount_toman],
        ["فروشِ خالص (تومان)", summary.net_toman],
        ["تعدادِ سفارشِ تاییدشده", summary.successful_count],
        ["میانگینِ هر سفارش (تومان)", summary.average_order_toman],
        ["پرداختِ آنلاین — تعداد", summary.online_paid_count],
        ["پرداختِ آنلاین — مبلغ (تومان)", summary.online_paid_toman],
        ["کلِ سفارش‌هایِ منتظرِ بررسی (فارغ از بازه)", report.pending_total],
    ]
    from app.bots.main_bot import texts

    for status, count in summary.status_counts.items():
        summary_rows.append([f"تعدادِ سفارشِ ثبت‌شده در بازه — {texts.accounting_status_label(status)}", count])
    if report.truncated:
        summary_rows.append(["⚠️ هشدار", "تعدادِ سفارش‌ها از سقفِ گزارش بیشتر بود؛ عددها ناقص‌ان."])
    _plain_sheet(wb, "خلاصه", ["شاخص", "مقدار"], summary_rows, first=True)

    order_rows = []
    for row in report.rows:
        order_rows.append(
            [
                row.id,
                "سفارش" if row.type == "order" else "مشاوره",
                texts.accounting_status_label(row.status),
                report.product_names.get(row.product_id, "") if row.product_id is not None else "",
                row.quantity,
                row.value_toman,
                row.discount_toman,
                report.campaign_names.get(row.campaign_id, "") if row.campaign_id is not None else "",
                _jalali_dt(row.created_at),
                _jalali_dt(row.confirmed_at),
                _jalali_dt(row.bale_paid_at),
            ]
        )
    _plain_sheet(
        wb,
        "سفارش‌ها",
        [
            "شناسه",
            "نوع",
            "وضعیت",
            "محصول",
            "تعداد",
            "مبلغِ خالص (بعد از تخفیف)",
            "تخفیف",
            "کمپین",
            "تاریخِ ثبت",
            "تاریخِ تایید",
            "پرداختِ آنلاین",
        ],
        order_rows,
    )
    _plain_sheet(
        wb,
        "محصولات",
        ["محصول", "تعدادِ فروخته‌شده", "فروشِ خالص (تومان)"],
        [[line.name, line.units, line.net_toman] for line in full.top_products],
    )
    _plain_sheet(
        wb,
        "کمپین‌ها",
        ["کمپین", "تعدادِ مصرف", "تخفیفِ داده‌شده (تومان)", "فروشِ خالصِ همون سفارش‌ها (تومان)"],
        [[line.name, line.uses, line.discount_toman, line.net_toman] for line in full.campaigns],
    )
    _plain_sheet(
        wb,
        "روزانه",
        ["روز", "تعدادِ سفارشِ تاییدشده", "فروشِ خالص (تومان)"],
        [[line.day_label, line.orders, line.net_toman] for line in full.daily],
    )

    return _workbook_bytes(wb)


async def build_wallet_ledger_workbook(session: AsyncSession, limit: int = MAX_LEDGER_ROWS) -> bytes:
    """دفترِ کلِ تراکنش‌هایِ کیف‌پولِ *همه‌یِ* فروشگاه‌دارها (فقط سوپرادمین؛ هندلر چک می‌کنه).
    فقط‌خواندنی: نه تراکنشی ساخته می‌شه نه عوض. جدیدترین‌ها اول؛ حداکثر limit ردیف."""
    from app.bots.main_bot import texts

    result = await session.execute(
        select(WalletTransaction, ShopOwner)
        .join(ShopOwner, WalletTransaction.shop_owner_id == ShopOwner.id)
        .order_by(WalletTransaction.id.desc())
        .limit(limit + 1)
    )
    fetched = result.all()
    truncated = len(fetched) > limit

    rows = []
    for transaction, owner in fetched[:limit]:
        owner_name = " ".join(part for part in (owner.first_name, owner.last_name) if part)
        rows.append(
            [
                transaction.id,
                _fmt(transaction.created_at),
                owner.id,
                owner.telegram_id,
                owner_name,
                texts.wallet_reason_label(transaction.reason),
                transaction.amount_toman,
                transaction.reference or "",
            ]
        )

    wb = Workbook()
    _plain_sheet(
        wb,
        "دفترِ کیف‌پول",
        ["شناسه", "تاریخ (UTC)", "شناسه‌یِ فروشگاه‌دار", "آیدی تلگرام", "نام", "دلیل", "مبلغ (تومان؛ منفی = مصرف)", "ارجاع"],
        rows,
        first=True,
    )
    note = "همه‌یِ تراکنش‌ها" if not truncated else f"فقط {limit} تراکنشِ جدیدتر (دفتر بزرگ‌تره)"
    _plain_sheet(wb, "توضیحات", ["مورد", "مقدار"], [["محدوده", note], ["تعدادِ ردیف‌هایِ این فایل", len(rows)]])

    return _workbook_bytes(wb)
