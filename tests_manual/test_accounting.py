"""
تست: حسابداریِ فقط‌خواندنی (فازِ ۴-ه) + خروجیِ اکسل + دفترِ کیف‌پولِ سوپرادمین.

پوشش:
۱. بازه‌ها بر اساسِ تقویمِ تهران (نیمه‌شب = ۲۰:۳۰ UTC)، مرزِ دقیقِ نیمه‌شب، ماهِ شمسیِ جاری
   (اول/آخرِ ماه، اسفندِ کبیسه) و half-open بودنِ بازه‌ها.
۲. جمع‌بندیِ خالص: فروشِ خالص/ناخالص/تخفیف/میانگین، فقط سفارشِ تاییدشده با confirmed_at توی بازه (ردشده/
   منقضی/لغو شمرده نمی‌شه)، وضعیت‌ها بر اساسِ created_at، پرداختِ آنلاین، پرفروش‌ها، کمپین‌ها (مصرف =
   تعدادِ چک‌اوتِ متمایز)، فروشِ روزانه (جمعِ روزها = جمعِ کل).
۳. اکسل: برگه‌ها و مقدارها درسته؛ فهرستِ محصول/کمپین کامله (نه فقط ۵ تایِ اول)؛ هیچ نام/تلفن/آدرس/آیدیِ مشتری توش نیست.
۴. دیتابیس: هم‌تعریف با stats_service (همون عددِ «فروشِ تاییدشده»)، ایزوله‌یِ هر فروشگاه، بازه‌یِ هفته شاملِ ۳ روزِ قبل.
۵. پنل: گزارش، دکمه‌هایِ بازه، اکسل، بازه‌یِ جعلی → امروز؛ فروشگاهِ بدونِ سفارش کرش نمی‌کنه.
۶. فقط‌خواندنی: دیدنِ گزارش‌ها و گرفتنِ اکسل هیچ سفارش/تراکنشی رو تغییر نمی‌ده.
۷. دفترِ کیف‌پول (اکسل): فقط سوپرادمین (دکمه فقط برایِ اون، هندلر هم محافظت می‌شه)، ثبت در ممیزی، فقط‌خواندنی.

اجرا: python3 tests_manual/test_accounting.py
"""
from __future__ import annotations

import asyncio
import datetime
import io
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from openpyxl import load_workbook  # noqa: E402
from sqlalchemy import func, select  # noqa: E402

from harness import build_test_dispatchers, reset_database  # noqa: E402
from phase4_helpers import Chat, add_customer, add_order, callbacks, reply_keyboard_texts  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from app.bots.main_bot import texts  # noqa: E402
from app.database.models import (  # noqa: E402
    AuditEventType,
    AuditLogEntry,
    OrderConsultation,
    OrderStatus,
    OrderType,
    ShopOwner,
    WalletTransaction,
)
from app.database.session import session_scope  # noqa: E402
from app.services import accounting_service as acc  # noqa: E402
from app.services import admin_role_service, excel_export_service, product_service, stats_service  # noqa: E402
from app.utils.jalali import format_jalali_date  # noqa: E402

ADMIN_TG_ID = 12345  # باید با ADMIN_TELEGRAM_IDS توی .env یکی باشه
OPERATOR_TG_ID = 993031
OWNER_TG_ID = 993001
SHOP_BOT_TG_ID = 993002
CUSTOMER_TG_ID = 993003
OTHER_OWNER_TG_ID = 993011
OTHER_SHOP_BOT_TG_ID = 993012

UTC = datetime.timezone.utc
DAY = datetime.timedelta(days=1)
START = datetime.datetime(2026, 10, 4, 20, 30, tzinfo=UTC)  # نیمه‌شبِ تهران، ۵ اکتبر ۲۰۲۶ (۱۳ مهر ۱۴۰۵)
END = START + DAY
INSIDE = START + datetime.timedelta(hours=5)
BEFORE = START - datetime.timedelta(hours=5)

PRODUCT_NAMES = {1: "چای", 2: "قهوه", 3: "شکلات"}
CAMPAIGN_NAMES = {7: "جشنواره"}


def _row(
    row_id: int,
    status: str,
    *,
    value: int = 100_000,
    discount: int = 0,
    created=INSIDE,
    confirmed_at=None,
    confirmed: bool | None = None,
    product: int | None = None,
    qty: int = 1,
    campaign: int | None = None,
    group: str | None = None,
    paid=None,
) -> acc.OrderRow:
    if confirmed is None:
        confirmed = status in ("confirmed", "processing", "shipped", "completed")
    return acc.OrderRow(
        id=row_id,
        type="order",
        status=status,
        confirmed=confirmed,
        created_at=created,
        confirmed_at=confirmed_at if confirmed else None,
        value_toman=value,
        discount_toman=discount,
        product_id=product,
        quantity=qty,
        campaign_id=campaign,
        group_id=group,
        bale_paid_at=paid,
    )


def _sample_rows() -> list[acc.OrderRow]:
    return [
        _row(1, "confirmed", value=90_000, discount=10_000, confirmed_at=INSIDE, product=1, qty=2, campaign=7, group="g1"),
        _row(2, "confirmed", value=60_000, discount=5_000, confirmed_at=INSIDE, product=2, campaign=7, group="g1"),
        _row(3, "confirmed", value=45_000, discount=5_000, confirmed_at=INSIDE, product=1, campaign=7, group="g2"),
        _row(4, "rejected", value=999_000),
        _row(5, "pending", value=70_000),
        _row(6, "completed", value=500_000, created=BEFORE, confirmed_at=BEFORE, product=3),  # دیروز تایید شده
        _row(7, "confirmed", value=20_000, created=BEFORE, confirmed_at=INSIDE, product=2),  # قدیمی ثبت، امروز تایید
        _row(8, "shipped", value=30_000, confirmed_at=INSIDE, product=3, paid=INSIDE),
        _row(9, "cancelled", value=40_000, confirmed=True, confirmed_at=INSIDE),  # بعد از تایید لغو شده
    ]


# =============================================================================
# ۱. بازه‌ها
# =============================================================================
def test_periods_and_jalali_month_boundaries_pure() -> None:
    now = datetime.datetime(2026, 10, 5, 10, 0, tzinfo=UTC)
    periods = acc.build_periods(now)
    assert periods["today"].start == START and periods["today"].end == END
    assert periods["week"].start == START - 6 * DAY and periods["week"].end == END
    assert periods["month30"].start == START - 29 * DAY and periods["month30"].end == END
    assert periods["jmonth"].start == datetime.datetime(2026, 9, 22, 20, 30, tzinfo=UTC), "۱ مهر ۱۴۰۵ = ۲۳ سپتامبر، نیمه‌شبِ تهران"
    assert periods["jmonth"].end == datetime.datetime(2026, 10, 22, 20, 30, tzinfo=UTC), "مهر ۳۰ روزه؛ ۱ آبان = ۲۳ اکتبر"
    assert periods["jmonth"].label == "ماهِ جاری (مهر 1405)"
    assert set(acc.PERIOD_KEYS) == set(periods)

    # مرزِ نیمه‌شبِ تهران: یک ثانیه فرق، یک روزِ دیگه
    before_midnight = datetime.datetime(2026, 10, 4, 20, 29, 59, tzinfo=UTC)
    at_midnight = datetime.datetime(2026, 10, 4, 20, 30, 0, tzinfo=UTC)
    assert acc.build_periods(before_midnight)["today"].start == START - DAY
    assert acc.build_periods(at_midnight)["today"].start == START
    assert acc.in_window(START, periods["today"]) and not acc.in_window(END, periods["today"]), "بازه half-open ـه"
    assert not acc.in_window(START - datetime.timedelta(seconds=1), periods["today"]) and not acc.in_window(None, periods["today"])

    # آخرین روز و اولین روزِ ماه
    last_day = acc.build_periods(datetime.datetime(2026, 10, 22, 18, 0, tzinfo=UTC))["jmonth"]  # ۳۰ مهر، ۲۱:۳۰ تهران
    assert last_day.start == periods["jmonth"].start and last_day.end == periods["jmonth"].end
    first_day = acc.build_periods(datetime.datetime(2026, 10, 22, 20, 30, tzinfo=UTC))["jmonth"]  # ۱ آبان، ۰۰:۰۰ تهران
    assert first_day.start == periods["jmonth"].end and first_day.label == "ماهِ جاری (آبان 1405)"
    assert (first_day.end - first_day.start) == 30 * DAY, "آبان ۳۰ روزه‌ست"

    # فروردین ۳۱ روزه، اسفندِ کبیسه ۳۰ روزه
    farvardin = acc.build_periods(datetime.datetime(2026, 4, 1, 9, 0, tzinfo=UTC))["jmonth"]
    assert (farvardin.end - farvardin.start) == 31 * DAY and "فروردین" in farvardin.label
    leap_esfand = acc.build_periods(datetime.datetime(2025, 3, 20, 10, 0, tzinfo=UTC))["jmonth"]  # ۳۰ اسفند ۱۴۰۳
    assert (leap_esfand.end - leap_esfand.start) == 30 * DAY and "اسفند" in leap_esfand.label
    assert leap_esfand.end == datetime.datetime(2025, 3, 20, 20, 30, tzinfo=UTC), "۱ فروردین ۱۴۰۴ = ۲۱ مارس، نیمه‌شبِ تهران"
    normal_esfand = acc.build_periods(datetime.datetime(2026, 3, 10, 10, 0, tzinfo=UTC))["jmonth"]  # ۱۹ اسفند ۱۴۰۴
    assert (normal_esfand.end - normal_esfand.start) == 29 * DAY, "اسفندِ غیرکبیسه ۲۹ روزه‌ست"

    print("✅ test_periods_and_jalali_month_boundaries_pure PASSED")


# =============================================================================
# ۲. جمع‌بندی
# =============================================================================
def test_summarize_period_pure() -> None:
    period = acc.Period("today", "امروز", START, END)
    summary = acc.summarize_period(_sample_rows(), period, PRODUCT_NAMES, CAMPAIGN_NAMES)

    assert summary.net_toman == 245_000, "فقط تاییدشده‌هایِ با confirmed_at توی بازه؛ ردشده/معلق/لغو/دیروز نه"
    assert summary.discount_toman == 20_000 and summary.gross_toman == 265_000
    assert summary.successful_count == 5 and summary.average_order_toman == 49_000
    assert list(summary.status_counts.items()) == [("pending", 1), ("confirmed", 3), ("shipped", 1), ("cancelled", 1), ("rejected", 1)], (
        "وضعیت‌ها بر اساسِ created_at و به ترتیبِ ثابت"
    )
    assert summary.online_paid_count == 1 and summary.online_paid_toman == 30_000
    assert [(p.name, p.units, p.net_toman) for p in summary.top_products] == [
        ("چای", 3, 135_000),
        ("قهوه", 2, 80_000),
        ("شکلات", 1, 30_000),
    ]
    assert [(c.name, c.uses, c.discount_toman, c.net_toman) for c in summary.campaigns] == [("جشنواره", 2, 20_000, 195_000)], (
        "مصرفِ کمپین = تعدادِ چک‌اوتِ متمایز (دو ردیفِ یه سبد = یک بار)"
    )
    assert len(summary.daily) == 1 and summary.daily[0].orders == 5 and summary.daily[0].net_toman == 245_000
    assert summary.daily[0].day_label == format_jalali_date(START)

    # محصول/کمپینِ حذف‌شده نامِ جایگزین می‌گیره؛ ردیفِ کمپین بدونِ شناسه‌یِ سبد جدا شمرده می‌شه
    orphan = acc.summarize_period(
        [
            _row(1, "confirmed", confirmed_at=INSIDE, product=99, campaign=55),
            _row(2, "confirmed", confirmed_at=INSIDE, product=99, campaign=55),
        ],
        period,
        {},
        {},
    )
    assert orphan.top_products[0].name == acc.UNKNOWN_PRODUCT_NAME and orphan.top_products[0].units == 2
    assert orphan.campaigns[0].name == acc.UNKNOWN_CAMPAIGN_NAME and orphan.campaigns[0].uses == 2

    # گرد کردنِ میانگین (نیم به بالا) و تقسیم بر صفر
    assert acc._rounded_average(10, 3) == 3 and acc._rounded_average(5, 2) == 3 and acc._rounded_average(0, 0) == 0
    empty = acc.summarize_period([], period, {}, {})
    assert empty.net_toman == 0 and empty.average_order_toman == 0 and empty.top_products == [] and empty.status_counts == {}

    # فروشِ روزانه توی بازه‌یِ هفته: جمعِ روزها = جمعِ کل
    week = acc.build_periods(datetime.datetime(2026, 10, 5, 10, 0, tzinfo=UTC))["week"]
    week_rows = [
        _row(
            index + 1,
            "confirmed",
            value=10_000 * (index + 1),
            created=week.start + index * DAY,
            confirmed_at=week.start + index * DAY + datetime.timedelta(hours=3),
        )
        for index in range(7)
    ]
    week_summary = acc.summarize_period(week_rows, week, {}, {})
    assert len(week_summary.daily) == 7 and all(day.orders == 1 for day in week_summary.daily)
    assert sum(day.net_toman for day in week_summary.daily) == week_summary.net_toman == 280_000
    assert [day.net_toman for day in week_summary.daily] == [10_000 * n for n in range(1, 8)]

    print("✅ test_summarize_period_pure PASSED")


# =============================================================================
# ۳. اکسل (منطقِ خالص — بدونِ دیتابیس)
# =============================================================================
def _sheet_pairs(workbook, title: str) -> dict:
    return {row[0].value: row[1].value for row in workbook[title].iter_rows(min_row=2)}


def test_excel_workbook_content_pure() -> None:
    period = acc.Period("today", "امروز", START, END)
    rows = _sample_rows()
    summary = acc.summarize_period(rows, period, PRODUCT_NAMES, CAMPAIGN_NAMES)
    report = acc.AccountingReport(
        summary=summary, rows=rows, product_names=PRODUCT_NAMES, campaign_names=CAMPAIGN_NAMES, pending_total=4, truncated=False
    )
    workbook = load_workbook(io.BytesIO(excel_export_service.build_accounting_workbook(report)))

    assert workbook.sheetnames == ["خلاصه", "سفارش‌ها", "محصولات", "کمپین‌ها", "روزانه"]
    pairs = _sheet_pairs(workbook, "خلاصه")
    assert pairs["فروشِ ناخالص (تومان)"] == 265_000
    assert pairs["جمعِ تخفیف‌ها (تومان)"] == 20_000
    assert pairs["فروشِ خالص (تومان)"] == 245_000
    assert pairs["تعدادِ سفارشِ تاییدشده"] == 5 and pairs["میانگینِ هر سفارش (تومان)"] == 49_000
    assert pairs["پرداختِ آنلاین — تعداد"] == 1 and pairs["پرداختِ آنلاین — مبلغ (تومان)"] == 30_000
    assert pairs["کلِ سفارش‌هایِ منتظرِ بررسی (فارغ از بازه)"] == 4
    assert not any(str(key).startswith("⚠️") for key in pairs), "بدونِ truncated هشداری نیست"

    orders_sheet = workbook["سفارش‌ها"]
    assert orders_sheet.max_row == len(rows) + 1, "سربرگ + همه‌یِ ردیف‌ها"
    assert [cell.value for cell in orders_sheet[1]][:3] == ["شناسه", "نوع", "وضعیت"]
    first = [cell.value for cell in orders_sheet[2]]
    assert first[0] == 1 and first[3] == "چای" and first[4] == 2 and first[5] == 90_000 and first[6] == 10_000 and first[7] == "جشنواره"

    campaign_rows = [[cell.value for cell in row] for row in workbook["کمپین‌ها"].iter_rows(min_row=2)]
    assert campaign_rows == [["جشنواره", 2, 20_000, 195_000]]

    # هشدارِ ناقص‌بودن
    truncated_report = acc.AccountingReport(
        summary=summary, rows=rows, product_names=PRODUCT_NAMES, campaign_names=CAMPAIGN_NAMES, pending_total=0, truncated=True
    )
    pairs = _sheet_pairs(load_workbook(io.BytesIO(excel_export_service.build_accounting_workbook(truncated_report))), "خلاصه")
    assert any(str(key).startswith("⚠️") for key in pairs)

    print("✅ test_excel_workbook_content_pure PASSED")


def test_excel_lists_are_complete_even_when_summary_is_truncated() -> None:
    period = acc.Period("today", "امروز", START, END)
    names = {index: f"محصول {index}" for index in range(1, 9)}
    rows = [_row(index, "confirmed", value=1_000 * index, confirmed_at=INSIDE, product=index) for index in range(1, 9)]
    summary = acc.summarize_period(rows, period, names, {})
    assert len(summary.top_products) == acc.TOP_PRODUCTS_LIMIT == 5, "خلاصه‌یِ روی صفحه فقط ۵ تایِ اول"

    report = acc.AccountingReport(summary=summary, rows=rows, product_names=names, campaign_names={}, pending_total=0, truncated=False)
    workbook = load_workbook(io.BytesIO(excel_export_service.build_accounting_workbook(report)))
    assert workbook["محصولات"].max_row == 9, "اکسل فهرستِ کاملِ ۸ محصول رو داره (نه فقط ۵ تایِ اول)"
    assert workbook["کمپین‌ها"].max_row == 1, "بدونِ کمپین فقط سربرگ"
    assert workbook["روزانه"].max_row == 2

    print("✅ test_excel_lists_are_complete_even_when_summary_is_truncated PASSED")


# =============================================================================
# ۴. دیتابیس
# =============================================================================
async def _seed() -> int:
    await reset_database()
    return await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)


async def _seed_sales(shop_bot_id: int, other_shop_bot_id: int) -> dict:
    now = datetime.datetime.now(UTC)
    today = acc.build_periods(now)["today"]
    ts = max(today.start + datetime.timedelta(seconds=1), now - datetime.timedelta(seconds=5))
    old = ts - 3 * DAY
    async with session_scope() as session:
        tea = await product_service.create_product(session, shop_bot_id, "چایِ ممتاز", None, 50_000, None)
        rice = await product_service.create_product(session, shop_bot_id, "برنج", None, 200_000, None)
        tea_id, rice_id = tea.id, rice.id
    customer = await add_customer(shop_bot_id, CUSTOMER_TG_ID, "مشتریِ نمونه", "sample_user")
    other_customer = await add_customer(other_shop_bot_id, CUSTOMER_TG_ID + 1, "مشتریِ فروشگاهِ دیگه", None)
    pii = dict(phone="09121112233", address="خیابانِ محرمانه ۱۲")
    await add_order(
        shop_bot_id,
        customer,
        status=OrderStatus.CONFIRMED,
        value=100_000,
        discount=10_000,
        product_id=tea_id,
        quantity=2,
        created_at=ts,
        confirmed_at=ts,
        **pii,
    )
    await add_order(
        shop_bot_id,
        customer,
        status=OrderStatus.COMPLETED,
        value=50_000,
        product_id=rice_id,
        created_at=ts,
        confirmed_at=ts,
        bale_paid_at=ts,
    )
    await add_order(shop_bot_id, customer, status=OrderStatus.PENDING, value=70_000, created_at=ts)
    await add_order(shop_bot_id, customer, status=OrderStatus.REJECTED, value=80_000, created_at=ts)
    await add_order(shop_bot_id, customer, status=OrderStatus.CONFIRMED, value=30_000, product_id=tea_id, created_at=old, confirmed_at=old)
    await add_order(other_shop_bot_id, other_customer, status=OrderStatus.CONFIRMED, value=999_000, created_at=ts, confirmed_at=ts)
    return {"now": now, "ts": ts}


async def test_db_report_matches_daily_stats_and_is_shop_scoped() -> None:
    shop_bot_id = await _seed()
    other_shop_bot_id = await seed_usable_shop(OTHER_OWNER_TG_ID, OTHER_SHOP_BOT_TG_ID)
    seeded = await _seed_sales(shop_bot_id, other_shop_bot_id)
    now = seeded["now"]

    async with session_scope() as session:
        today_report = await acc.build_report(session, shop_bot_id, "today", now=now)
        week_report = await acc.build_report(session, shop_bot_id, "week", now=now)
        bogus_report = await acc.build_report(session, shop_bot_id, "evil", now=now)
        today = today_report.summary.period
        stats = await stats_service.get_shop_daily_stats(session, shop_bot_id, today.start, today.end)
        other_report = await acc.build_report(session, other_shop_bot_id, "today", now=now)

    summary = today_report.summary
    assert summary.net_toman == 150_000 and summary.discount_toman == 10_000 and summary.gross_toman == 160_000
    assert summary.successful_count == 2 and summary.average_order_toman == 75_000
    assert summary.net_toman == stats["confirmed_revenue_today_toman"], "هم‌تعریف با stats_service: همون «فروشِ تاییدشده»"
    assert list(summary.status_counts.items()) == [("pending", 1), ("confirmed", 1), ("completed", 1), ("rejected", 1)]
    assert summary.online_paid_count == 1 and summary.online_paid_toman == 50_000
    assert [(p.name, p.units, p.net_toman) for p in summary.top_products] == [("چایِ ممتاز", 2, 100_000), ("برنج", 1, 50_000)]
    assert today_report.pending_total == 1 and not today_report.truncated

    assert week_report.summary.net_toman == 180_000 and week_report.summary.successful_count == 3, "بازه‌یِ هفته سفارشِ ۳ روز قبل رو هم داره"
    assert week_report.summary.status_counts["confirmed"] == 2
    assert bogus_report.summary.period.key == "today", "کلیدِ بازه‌یِ نامعتبر → امروز"

    assert other_report.summary.net_toman == 999_000 and other_report.summary.successful_count == 1, "هر فروشگاه فقط دیتایِ خودش"
    assert all(row.id not in {r.id for r in other_report.rows} for row in today_report.rows), "ردیف‌هایِ دو فروشگاه هیچ‌وقت قاطی نمی‌شن"

    print("✅ test_db_report_matches_daily_stats_and_is_shop_scoped PASSED")


async def test_panel_screens_excel_download_and_no_customer_pii(main_dp) -> None:
    shop_bot_id = await _seed()
    other_shop_bot_id = await seed_usable_shop(OTHER_OWNER_TG_ID, OTHER_SHOP_BOT_TG_ID)
    await _seed_sales(shop_bot_id, other_shop_bot_id)
    owner = Chat(main_dp, OWNER_TG_ID)

    await owner.say("🧮 حسابداری")
    text = owner.last_text
    assert "🧮 حسابداری — امروز" in text
    for expected in (
        "فروشِ ناخالص: 160,000 تومان",
        "جمعِ تخفیف‌ها: 10,000 تومان",
        "فروشِ خالص: 150,000 تومان",
        "🧾 سفارشِ تاییدشده: 2",
        "75,000 تومان",
        "💳 پرداختِ آنلاین: 1 مورد — 50,000 تومان",
        "کلاً 1 سفارش منتظرِ بررسیِ شماست",
        "چایِ ممتاز — 2 عدد — 100,000 تومان",
        texts.ACCOUNTING_NOTE,
    ):
        assert expected in text, f"گزارش باید «{expected}» رو داشته باشه:\n{text}"
    assert "999,000" not in text, "فروشِ فروشگاهِ دیگه نباید دیده بشه"
    assert callbacks(owner.last_markup) == ["acct:today", "acct:week", "acct:month30", "acct:jmonth", "acct_xlsx:today"]

    for data in ("acct:week", "acct:month30", "acct:jmonth", "acct:evil", "acct:"):
        await owner.tap(data)
        assert owner.last_toast.get("show_alert") in (None, False), data

    # اکسل
    await owner.tap("acct_xlsx:week")
    assert len(owner.documents) == 1
    document = owner.documents[-1]["document"]
    assert document.filename == "accounting-week.xlsx" and owner.documents[-1]["caption"] == texts.ACCOUNTING_EXCEL_READY
    workbook = load_workbook(io.BytesIO(document.data))
    pairs = _sheet_pairs(workbook, "خلاصه")
    assert pairs["فروشِ خالص (تومان)"] == 180_000 and pairs["تعدادِ سفارشِ تاییدشده"] == 3
    assert workbook["سفارش‌ها"].max_row == 6, "۵ سفارشِ همین فروشگاه توی هفته + سربرگ؛ سفارشِ فروشگاهِ دیگه نیست"
    everything = " | ".join(str(cell.value) for sheet in workbook for row in sheet.iter_rows() for cell in row if cell.value is not None)
    for secret in ("مشتریِ نمونه", "sample_user", "09121112233", "خیابانِ محرمانه", str(CUSTOMER_TG_ID), "مشتریِ فروشگاهِ دیگه"):
        assert secret not in everything, f"اکسلِ حسابداری نباید «{secret}» رو داشته باشه"

    await owner.tap("acct_xlsx:evil")
    assert owner.documents[-1]["document"].filename == "accounting-today.xlsx", "کلیدِ جعلی → امروز"

    # فروشگاه‌دارِ دیگه گزارشِ خودش رو می‌بینه
    other = Chat(main_dp, OTHER_OWNER_TG_ID)
    await other.say("🧮 حسابداری")
    assert "فروشِ خالص: 999,000 تومان" in other.last_text and "150,000" not in other.last_text

    print("✅ test_panel_screens_excel_download_and_no_customer_pii PASSED")


async def test_accounting_is_read_only(main_dp) -> None:
    shop_bot_id = await _seed()
    other_shop_bot_id = await seed_usable_shop(OTHER_OWNER_TG_ID, OTHER_SHOP_BOT_TG_ID)
    await _seed_sales(shop_bot_id, other_shop_bot_id)

    async def snapshot() -> tuple:
        async with session_scope() as session:
            orders = [
                (o.id, str(o.status), o.estimated_value_toman, o.confirmed, o.stock_reserved, o.discount_toman)
                for o in (await session.execute(select(OrderConsultation).order_by(OrderConsultation.id))).scalars()
            ]
            balances = [(o.id, o.wallet_balance_toman) for o in (await session.execute(select(ShopOwner).order_by(ShopOwner.id))).scalars()]
            transaction_count = (await session.execute(select(func.count()).select_from(WalletTransaction))).scalar_one()
        return orders, balances, transaction_count

    before = await snapshot()
    owner = Chat(main_dp, OWNER_TG_ID)
    await owner.say("🧮 حسابداری")
    for key in acc.PERIOD_KEYS:
        await owner.tap(f"acct:{key}")
        await owner.tap(f"acct_xlsx:{key}")
    after = await snapshot()

    assert before == after, "حسابداری فقط می‌خونه: هیچ سفارش، موجودی یا تراکنشی نباید عوض بشه"
    assert len(owner.documents) == len(acc.PERIOD_KEYS)

    print("✅ test_accounting_is_read_only PASSED")


async def test_empty_shop_report_renders_without_errors(main_dp) -> None:
    await _seed()
    owner = Chat(main_dp, OWNER_TG_ID)

    await owner.say("🧮 حسابداری")
    assert "فروشِ خالص: 0 تومان" in owner.last_text and "میانگینِ هر سفارش: 0 تومان" in owner.last_text
    assert "پرفروش" not in owner.last_text and "کمپین" not in owner.last_text and "منتظرِ بررسیِ شماست" not in owner.last_text
    await owner.tap("acct_xlsx:jmonth")
    workbook = load_workbook(io.BytesIO(owner.documents[-1]["document"].data))
    assert _sheet_pairs(workbook, "خلاصه")["فروشِ خالص (تومان)"] == 0 and workbook["سفارش‌ها"].max_row == 1

    print("✅ test_empty_shop_report_renders_without_errors PASSED")


# =============================================================================
# ۷. دفترِ کیف‌پول (اکسل) — فقط سوپرادمین
# =============================================================================
async def test_wallet_ledger_export_is_super_admin_only_and_read_only(main_dp) -> None:
    shop_bot_id = await _seed()
    await seed_usable_shop(OTHER_OWNER_TG_ID, OTHER_SHOP_BOT_TG_ID)
    async with session_scope() as session:
        await admin_role_service.grant_operator(session, OPERATOR_TG_ID, granted_by_telegram_id=ADMIN_TG_ID)
        expected_transactions = (await session.execute(select(func.count()).select_from(WalletTransaction))).scalar_one()
    assert expected_transactions >= 2 and shop_bot_id

    admin = Chat(main_dp, ADMIN_TG_ID)
    await admin.say("/admin")
    assert "📤 دفترِ کیف‌پول (اکسل)" in reply_keyboard_texts(admin.last_markup), "سوپرادمین دکمه رو می‌بینه"
    await admin.say("📤 دفترِ کیف‌پول (اکسل)")
    assert len(admin.documents) == 1
    assert admin.documents[0]["caption"] == texts.ADMIN_WALLET_LEDGER_READY
    workbook = load_workbook(io.BytesIO(admin.documents[0]["document"].data))
    assert workbook.sheetnames == ["دفترِ کیف‌پول", "توضیحات"]
    ledger_rows = [[cell.value for cell in row] for row in workbook["دفترِ کیف‌پول"].iter_rows(min_row=2)]
    assert len(ledger_rows) == expected_transactions
    telegram_ids = {row[3] for row in ledger_rows}
    assert telegram_ids == {OWNER_TG_ID, OTHER_OWNER_TG_ID}, "تراکنش‌هایِ همه‌یِ فروشگاه‌دارها با آیدیِ تلگرامشون"
    assert all(row[6] > 0 for row in ledger_rows), "فقط شارژِ اولیه‌یِ تست داریم (مبلغِ مثبت)"

    async with session_scope() as session:
        entries = list(
            (await session.execute(select(AuditLogEntry).where(AuditLogEntry.event_type == AuditEventType.WALLET_LEDGER_EXPORTED)))
            .scalars()
            .all()
        )
        count_after = (await session.execute(select(func.count()).select_from(WalletTransaction))).scalar_one()
    assert len(entries) == 1 and entries[0].actor_telegram_id == ADMIN_TG_ID, "هر خروجی توی ممیزی ثبت می‌شه"
    assert count_after == expected_transactions, "خروجیِ دفتر فقط‌خواندنیه"

    # ادمینِ عملیاتی: دکمه رو نمی‌بینه و هندلر هم بهش جواب نمی‌ده
    operator = Chat(main_dp, OPERATOR_TG_ID)
    await operator.say("/admin")
    assert "📤 دفترِ کیف‌پول (اکسل)" not in reply_keyboard_texts(operator.last_markup)
    await operator.say("📤 دفترِ کیف‌پول (اکسل)")
    assert operator.documents == []

    # فروشگاه‌دارِ عادی هم همین‌طور
    owner = Chat(main_dp, OWNER_TG_ID)
    await owner.say("📤 دفترِ کیف‌پول (اکسل)")
    assert owner.documents == []

    async with session_scope() as session:
        entries_after = (
            await session.execute(
                select(func.count()).select_from(AuditLogEntry).where(AuditLogEntry.event_type == AuditEventType.WALLET_LEDGER_EXPORTED)
            )
        ).scalar_one()
    assert entries_after == 1, "تلاشِ ناموفق نباید خروجی یا ممیزیِ تازه بسازه"

    print("✅ test_wallet_ledger_export_is_super_admin_only_and_read_only PASSED")


async def main() -> None:
    test_periods_and_jalali_month_boundaries_pure()
    test_summarize_period_pure()
    test_excel_workbook_content_pure()
    test_excel_lists_are_complete_even_when_summary_is_truncated()
    main_dp, _shop_dp, _bot_manager, _main_bot = build_test_dispatchers()
    await test_db_report_matches_daily_stats_and_is_shop_scoped()
    await test_panel_screens_excel_download_and_no_customer_pii(main_dp)
    await test_accounting_is_read_only(main_dp)
    await test_empty_shop_report_renders_without_errors(main_dp)
    await test_wallet_ledger_export_is_super_admin_only_and_read_only(main_dp)


if __name__ == "__main__":
    asyncio.run(main())
