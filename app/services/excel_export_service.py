from __future__ import annotations

import datetime
import io
from typing import Iterable

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Campaign, Customer, OrderConsultation, OrderType, Product, ShopOwner, WalletTransaction
from app.services import accounting_service
from app.utils.jalali import format_jalali_date, format_jalali_datetime
from app.utils.validators import fa_number

# P22 (مشکلِ ۴): همانِ پالتِ فاکتورِ PDF ⇒ فایلِ اکسل و کاغذِ فاکتور یکِ برند باشند.
_BRAND = "0F5E5C"
_BRAND_SOFT = "E4EFEA"
_ZEBRA = "F2F2F2"
_INK = "1F2933"
_MONEY_FORMAT = "#,##0;[Red]-#,##0"

_HEADER_FONT = Font(name="Arial", bold=True, color="FFFFFF")
_HEADER_FILL = PatternFill(fill_type="solid", start_color=_BRAND, end_color=_BRAND)
_BODY_FONT = Font(name="Arial", color=_INK)
_RTL_ALIGNMENT = Alignment(horizontal="right", readingOrder=2, vertical="center", wrap_text=True)
_HEADER_ALIGNMENT = Alignment(horizontal="center", readingOrder=2, vertical="center", wrap_text=True)
_THIN_SIDE = Side(style="thin", color="BFBFBF")
_CELL_BORDER = Border(left=_THIN_SIDE, right=_THIN_SIDE, top=_THIN_SIDE, bottom=_THIN_SIDE)
_ALT_ROW_FILL = PatternFill(fill_type="solid", start_color=_ZEBRA, end_color=_ZEBRA)
_TOTALS_FILL = PatternFill(fill_type="solid", start_color=_BRAND_SOFT, end_color=_BRAND_SOFT)
_TOTALS_FONT = Font(name="Arial", bold=True, color=_BRAND)
_TOTALS_BORDER = Border(
    left=_THIN_SIDE,
    right=_THIN_SIDE,
    bottom=_THIN_SIDE,
    top=Side(style="medium", color=_BRAND),
)
# رنگِ زبانه‌یِ برگه‌ها به‌ترتیبِ ساخته‌شدن (برگه‌هایِ چندگانه چشم‌نواز و قابلِ تشخیص می‌شوند)
_TAB_COLORS = (_BRAND, "2F5496", "B07D00", "6B8E23", "7A3E63", "4F6B7C")


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


def _style_sheet(ws: Worksheet, *, money_cols: Iterable[int] = (), totals: dict[int, object] | None = None, tab_index: int = 0) -> None:
    """آرایشِ مشترکِ همهٔ برگه‌ها: راست‌به‌چپ، سرصفحهٔ برند، ردیف‌هایِ یک‌در‌میان، جداکنندهٔ
    هزارگان، ردیفِ «جمعِ کل»، فیلترِ خودکار، ستون‌هایِ اندازه‌گیری‌شده و زبانهٔ رنگی."""
    ws.sheet_view.rightToLeft = True
    ws.freeze_panes = "A2"
    ws.sheet_properties.tabColor = _TAB_COLORS[tab_index % len(_TAB_COLORS)]

    for cell in ws[1]:
        cell.font = _HEADER_FONT
        cell.fill = _HEADER_FILL
        cell.alignment = _HEADER_ALIGNMENT
        cell.border = _CELL_BORDER
    ws.row_dimensions[1].height = 26

    for row_idx, row in enumerate(ws.iter_rows(min_row=2), start=2):
        for cell in row:
            cell.font = _BODY_FONT
            cell.alignment = _RTL_ALIGNMENT
            cell.border = _CELL_BORDER
            if row_idx % 2 == 0:
                cell.fill = _ALT_ROW_FILL

    money_indexes = {int(index) for index in money_cols}
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            if cell.column in money_indexes and isinstance(cell.value, (int, float)):
                cell.number_format = _MONEY_FORMAT

    last_data_row = ws.max_row
    if totals and last_data_row >= 2:
        totals_row = [None] * max(totals)
        totals_row[0] = "جمعِ کل"
        for column_index, value in totals.items():
            totals_row[column_index - 1] = value
        ws.append(totals_row)
        for cell in ws[last_data_row + 1]:
            cell.fill = _TOTALS_FILL
            cell.font = _TOTALS_FONT
            cell.border = _TOTALS_BORDER
            cell.alignment = _RTL_ALIGNMENT
            if cell.column in money_indexes and isinstance(cell.value, (int, float)):
                cell.number_format = _MONEY_FORMAT

    if ws.max_row > 1:
        ws.auto_filter.ref = f"A1:{get_column_letter(ws.max_column)}{last_data_row}"

    for col in ws.columns:
        max_len = max((len(str(cell.value)) for cell in col if cell.value is not None), default=10)
        ws.column_dimensions[col[0].column_letter].width = min(max(max_len + 4, 12), 45)


def _fmt(dt) -> str:
    """تاریخِ همهٔ فایل‌ها: جلالی و به وقتِ تهران (تا پیشِ این «۱۴۰۴» در اکسل با «2026-11-02 03:04» نوشته می‌شد)."""
    return format_jalali_datetime(dt) if dt else ""


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
        headers.append("تعدادِ سفارش")
    headers += ["تعدادِ مشاوره", "مجموعِ ارزشِ تخمینی (تومان)"]
    value_col = len(headers)
    ws.append(headers)

    total_value = 0
    for c in customers:
        stats = per_customer.get(c.id, {"order": 0, "consultation": 0, "value": 0})
        total_value += stats["value"]
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

    _style_sheet(ws, money_cols=(value_col,), totals={value_col: total_value})
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
            "تاریخِ ثبت",
            "نوع",
            "مشتری",
            "آیدی تلگرامِ مشتری",
            "محصول",
            "تعداد",
            "خلاصه",
            "ارزشِ تخمینی (تومان)",
            "وضعیتِ تایید",
            # ستون‌هایِ کمپین (فازِ ۳) عمداً *آخر* اضافه شدن تا جایگاهِ ستون‌هایِ قبلی عوض نشه.
            # «ارزش تخمینی» همیشه مبلغِ بعد از تخفیفه.
            "تخفیفِ کمپین (تومان)",
            "کمپین",
        ]
    )
    value_col, discount_col = 8, 10

    type_labels = {"order": "—", "consultation": "مشاوره"} if consultation else {"order": "سفارش", "consultation": "مشاوره"}
    total_value = 0
    total_discount = 0
    for order, customer, product, campaign in rows:
        order_type = order.type.value if hasattr(order.type, "value") else order.type
        if order_type == OrderType.ORDER.value or product is not None:
            confirmed_label = "✅ تایید و کسر شده" if order.confirmed else "⏳ در انتظار تایید"
        else:
            confirmed_label = "—"

        total_value += order.estimated_value_toman or 0
        total_discount += order.discount_toman or 0
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

    _style_sheet(ws, money_cols=(value_col, discount_col), totals={value_col: total_value, discount_col: total_discount})
    return _workbook_bytes(wb)


# =============================================================================
# فازِ ۴-ه — خروجیِ اکسلِ حسابداری (فقط‌خواندنی) و دفترِ کیف‌پولِ سوپرادمین
# =============================================================================
MAX_LEDGER_ROWS = 50_000


def _plain_sheet(
    wb: Workbook,
    title: str,
    headers: list[str],
    rows: list[list],
    first: bool = False,
    *,
    money_cols: Iterable[int] = (),
    totals: dict[int, object] | None = None,
    tab_index: int = 0,
) -> Worksheet:
    ws = wb.active if first else wb.create_sheet()
    ws.title = title
    ws.append(headers)
    for row in rows:
        ws.append(row)
    _style_sheet(ws, money_cols=money_cols, totals=totals, tab_index=tab_index)
    return ws


def _jalali_dt(moment) -> str:
    return format_jalali_datetime(moment) if moment else ""


def build_accounting_workbook(report, *, consultation: bool = False) -> bytes:
    """اکسلِ چندبرگه‌یِ حسابداریِ یه بازه. هیچ دیتابیسی نمی‌خونه — فقط از خودِ report (که
    accounting_service.build_report ساخته) استفاده می‌کنه، پس بدونِ session تست‌پذیره.
    هیچ نام/تلفنِ مشتری و هیچ متنِ آزادیِ سفارش توش نیست.

    پ۶۶ · موردِ ۲۴-ب: `consultation=True` همان داده را با واژگانِ «جلسه» بیرون می‌دهد، دو برگهٔ
    «محصولات/کمپین‌ها» را حذف می‌کند و در برگهٔ جزئیات هم ستون‌هایِ نوع/تخفیف/کمپین/پرداختِ آنلاین
    نمی‌آید (در مودِ مشاوره سبدِ تخفیف و درگاهِ مشتری معنا ندارد). برگه‌ها، ترتیبِ ستون‌ها و
    ارقامِ خامِ مسیرِ فروشگاهی عمداً دست‌نخورده ماندند تا خروجیِ تست‌هایِ پ۱۸/پ۵۹ عوض نشود.
    """
    summary = report.summary
    period = summary.period
    noun = "جلسه" if consultation else "سفارش"
    full = accounting_service.summarize_period(
        report.rows, period, report.product_names, report.campaign_names, top_products_limit=None, campaigns_limit=None
    )

    wb = Workbook()
    summary_rows: list[list] = [
        ["بازه", period.label],
        ["از تاریخ", format_jalali_date(period.start)],
        ["تا تاریخ", format_jalali_date(period.end - datetime.timedelta(days=1))],
        [f"{'ارزشِ ناخالص' if consultation else 'فروشِ ناخالص'} (تومان)", summary.gross_toman],
        ["جمعِ تخفیف‌ها (تومان)", summary.discount_toman],
        [f"{'ارزشِ خالص' if consultation else 'فروشِ خالص'} (تومان)", summary.net_toman],
        [f"تعدادِ {noun}ِ تاییدشده", summary.successful_count],
        [f"میانگینِ هر {noun} (تومان)", summary.average_order_toman],
        ["پرداختِ آنلاین — تعداد", summary.online_paid_count],
        ["پرداختِ آنلاین — مبلغ (تومان)", summary.online_paid_toman],
        [f"کلِ {noun}‌هایِ منتظرِ بررسی (فارغ از بازه)", report.pending_total],
    ]
    from app.bots.main_bot import texts

    for status, count in summary.status_counts.items():
        label = texts.consult_status_label(status) if consultation else texts.accounting_status_label(status)
        summary_rows.append([f"تعدادِ {noun}ِ ثبت‌شده در بازه — {label}", count])
    if report.truncated:
        summary_rows.append(["⚠️ هشدار", f"تعدادِ {noun}‌ها از سقفِ گزارش بیشتر بود؛ عددها ناقص‌ان."])
    _plain_sheet(wb, "خلاصه", ["شاخص", "مقدار"], summary_rows, first=True, money_cols=(2,))

    if consultation:
        # پ۶۶: برگهٔ «جلسه‌ها» ستونِ نوع/تخفیف/کمپین/پرداختِ آنلاین ندارد — در مودِ مشاوره نه سبد
        # تخفیف وجود دارد نه درگاهِ مشتری؛ نگه‌داشتنشان یعنی سرستونی که همیشه خالی است.
        detail_rows = [
            [
                row.id,
                texts.consult_status_label(row.status),
                report.product_names.get(row.product_id, "") if row.product_id is not None else "",
                row.quantity,
                row.value_toman,
                _jalali_dt(row.created_at),
                _jalali_dt(row.confirmed_at),
            ]
            for row in report.rows
        ]
        _plain_sheet(
            wb,
            "جلسه‌ها",
            ["شناسه", "وضعیت", "خدمت", "تعداد", "ارزش (تومان)", "تاریخِ ثبت", "تاریخِ تایید"],
            detail_rows,
            money_cols=(5,),
            totals={5: summary.net_toman},
            tab_index=1,
        )
    else:
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
            money_cols=(6, 7),
            totals={6: summary.net_toman, 7: summary.discount_toman},
            tab_index=1,
        )
    next_tab = 2
    if not consultation:
        # پ۶۶: در مودِ مشاوره نه کاتالوگ هست نه تخفیفِ سبد ⇒ این دو برگه حذف می‌شوند (برگهٔ خالیِ
        # بی‌سرِصفحه در Excel/LibreOffice آدرسِ اشتباه به‌نظر می‌رسد).
        _plain_sheet(
            wb,
            "محصولات",
            ["محصول", "تعدادِ فروخته‌شده", "فروشِ خالص (تومان)"],
            [[line.name, line.units, line.net_toman] for line in full.top_products],
            money_cols=(3,),
            totals={3: sum(line.net_toman for line in full.top_products)},
            tab_index=2,
        )
        _plain_sheet(
            wb,
            "کمپین‌ها",
            ["کمپین", "تعدادِ مصرف", "تخفیفِ داده‌شده (تومان)", "فروشِ خالصِ همان سفارش‌ها (تومان)"],
            [[line.name, line.uses, line.discount_toman, line.net_toman] for line in full.campaigns],
            money_cols=(3, 4),
            totals={3: sum(line.discount_toman for line in full.campaigns), 4: sum(line.net_toman for line in full.campaigns)},
            tab_index=3,
        )
        next_tab = 4
    _plain_sheet(
        wb,
        "روزانه",
        ["روز", f"تعدادِ {noun}ِ تاییدشده", "فروشِ خالص (تومان)" if not consultation else "ارزشِ خالص (تومان)"],
        [[line.day_label, line.orders, line.net_toman] for line in full.daily],
        money_cols=(3,),
        totals={3: sum(line.net_toman for line in full.daily)},
        tab_index=next_tab,
    )

    return _workbook_bytes(wb)


MAX_OWNER_WALLET_ROWS = 5_000


async def build_owner_wallet_workbook(
    session: AsyncSession,
    owner_id: int,
    *,
    before_id: int | None = None,
    limit: int = MAX_OWNER_WALLET_ROWS,
) -> tuple[bytes, int, int | None]:
    from app.bots.main_bot import texts

    if type(limit) is not int or limit < 1:
        raise ValueError("سقفِ ردیف‌ها باید مثبت باشد")
    limit = min(limit, MAX_OWNER_WALLET_ROWS)
    if before_id is not None and (type(before_id) is not int or not 1 <= before_id <= 2_147_483_647):
        raise ValueError("نشانگرِ تاریخچه معتبر نیست")
    query = select(
        WalletTransaction.id, WalletTransaction.created_at, WalletTransaction.reason, WalletTransaction.amount_toman,
    ).where(WalletTransaction.shop_owner_id == owner_id)
    if before_id is not None:
        query = query.where(WalletTransaction.id < before_id)
    fetched = (await session.execute(query.order_by(WalletTransaction.id.desc()).limit(limit + 1))).all()
    transactions = fetched[:limit]
    next_cursor = transactions[-1].id if len(fetched) > limit else None
    rows = [
        [fa_number(index), _fmt(transaction.created_at), texts.wallet_reason_label(transaction.reason), transaction.amount_toman]
        for index, transaction in enumerate(transactions, start=1)
    ]
    wb = Workbook()
    ws = _plain_sheet(
        wb, "تاریخچهٔ کیف‌پول", ["ردیف", "تاریخ (تهران)", "دلیل", "مبلغ (تومان؛ مثبت = افزایش، منفی = کاهش)"],
        rows, first=True, money_cols=(4,),
    )
    for row in ws.iter_rows(min_row=2, min_col=4, max_col=4):
        row[0].number_format = "+#,##0;[Red]-#,##0;0"
    notes = [
        ["محدوده", texts.WALLET_HISTORY_EXPORT_SCOPE],
        ["تعدادِ ردیف‌های این فایل", fa_number(len(rows))],
        ["وضعیت", texts.wallet_history_export_note(len(rows), has_more=next_cursor is not None, continuation=before_id is not None)],
    ]
    if before_id is not None:
        notes.append(["ادامه", texts.WALLET_HISTORY_EXPORT_CONTINUATION])
    _plain_sheet(wb, "توضیحات", ["مورد", "مقدار"], notes, tab_index=1)
    return _workbook_bytes(wb), len(rows), next_cursor


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
        ["شناسه", "تاریخ (تهران)", "شناسهٔ فروشگاه‌دار", "آیدی تلگرام", "نام", "دلیل", "مبلغ (تومان؛ منفی = مصرف)", "ارجاع"],
        rows,
        first=True,
        money_cols=(7,),
        tab_index=0,
    )
    note = "همهٔ تراکنش‌ها" if not truncated else f"فقط {fa_number(limit)} تراکنشِ جدیدتر (دفتر بزرگ‌تر است)"
    _plain_sheet(wb, "توضیحات", ["مورد", "مقدار"], [["محدوده", note], ["تعدادِ ردیف‌هایِ این فایل", len(rows)]], money_cols=(2,), tab_index=1)

    return _workbook_bytes(wb)
