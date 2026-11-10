from __future__ import annotations

import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import (
    BotErrorEvent,
    ConversationMessage,
    Customer,
    KnowledgeGap,
    KnowledgeGapStatus,
    OrderConsultation,
    OrderStatus,
    Payment,
    PaymentStatus,
    ShopBot,
    ShopOwner,
    WalletTransaction,
    WalletTransactionReason,
)
from app.services import knowledge_service, order_service, product_service


async def _count_customer_messages_since(session: AsyncSession, shop_bot_id: int, since: datetime.datetime) -> int:
    result = await session.execute(
        select(func.count())
        .select_from(ConversationMessage)
        .join(Customer, ConversationMessage.customer_id == Customer.id)
        .where(Customer.shop_bot_id == shop_bot_id, ConversationMessage.role == "user", ConversationMessage.created_at > since)
    )
    return result.scalar_one()


async def _get_top_products(session: AsyncSession, shop_bot_id: int, since: datetime.datetime, limit: int = 5):
    products = await product_service.get_active_by_shop_bot(session, shop_bot_id)
    if not products:
        return []

    summaries = await order_service.get_recent_summaries(session, shop_bot_id, since)
    counts = {p.name: 0 for p in products}
    for summary in summaries:
        for p in products:
            if p.name in summary:
                counts[p.name] += 1

    ranked = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
    return [(name, count) for name, count in ranked if count > 0][:limit]


async def _get_success_rate(session: AsyncSession, shop_bot_id: int, days: int = 30) -> float | None:
    since = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)
    successful = await _count_customer_messages_since(session, shop_bot_id, since)

    error_result = await session.execute(
        select(func.count()).select_from(BotErrorEvent).where(BotErrorEvent.shop_bot_id == shop_bot_id, BotErrorEvent.created_at > since)
    )
    errors = error_result.scalar_one()

    total = successful + errors
    if total == 0:
        return None
    return successful / total * 100


async def get_shops_daily_stats(
    session: AsyncSession, shop_bot_ids: set[int], day_start: datetime.datetime, now: datetime.datetime
) -> dict[int, dict]:
    """P31-B: همان شش عددِ `get_shop_daily_stats` برایِ *همهٔ* فروشگاه‌ها در پنج کوئریِ گروهی.

    چرا: گزارشِ شبانه به‌ازایِ هر فروشگاه پنج‌کوئری می‌زد (با N فروشگاه ⇒ ۵N و رشدِ خطیِ محض).
    این همان الگویِ `commission_receivable_service.open_totals_by_owner` است که در P29 برایِ
    رفعِ همین بیماری ساخته شد. قاعدهٔ امنیتیِ P29 هم رعایت شده: هر عدد **per-shop** با کلیدِ
    `shop_bot_id` برمی‌گردد، نه جمعِ سراسری، وگرنه فروشگاه‌دار عددِ بقیه را در گزارشِ خودش
    می‌بیند (باگی که در P29 همین‌جا گرفته شد).
    """
    empty = {
        "new_orders_today": 0, "new_consultations_today": 0, "confirmed_revenue_today_toman": 0,
        "new_customers_today": 0, "pending_orders_count": 0, "new_knowledge_gaps": 0,
    }
    if not shop_bot_ids:
        return {}
    out = {int(sid): dict(empty) for sid in shop_bot_ids}

    in_ids = OrderConsultation.shop_bot_id.in_(shop_bot_ids)
    types = await session.execute(
        select(OrderConsultation.shop_bot_id, OrderConsultation.type, func.count())
        .where(
            in_ids,
            OrderConsultation.created_at >= day_start,
            OrderConsultation.created_at < now,
        )
        .group_by(OrderConsultation.shop_bot_id, OrderConsultation.type)
    )
    for shop_id, raw_type, count in types.all():
        key = raw_type.value if hasattr(raw_type, "value") else raw_type
        if key == "order":
            out[int(shop_id)]["new_orders_today"] = int(count)
        elif key == "consultation":
            out[int(shop_id)]["new_consultations_today"] = int(count)

    revenue = await session.execute(
        select(OrderConsultation.shop_bot_id, func.coalesce(func.sum(OrderConsultation.estimated_value_toman), 0))
        .where(in_ids, OrderConsultation.confirmed.is_(True), OrderConsultation.confirmed_at >= day_start, OrderConsultation.confirmed_at < now)
        .group_by(OrderConsultation.shop_bot_id)
    )
    for shop_id, total in revenue.all():
        out[int(shop_id)]["confirmed_revenue_today_toman"] = int(total or 0)

    customers = await session.execute(
        select(Customer.shop_bot_id, func.count())
        .where(Customer.shop_bot_id.in_(shop_bot_ids), Customer.first_seen_at >= day_start, Customer.first_seen_at < now)
        .group_by(Customer.shop_bot_id)
    )
    for shop_id, count in customers.all():
        out[int(shop_id)]["new_customers_today"] = int(count)

    pending = await session.execute(
        select(OrderConsultation.shop_bot_id, func.count())
        .where(in_ids, OrderConsultation.status == OrderStatus.PENDING)
        .group_by(OrderConsultation.shop_bot_id)
    )
    for shop_id, count in pending.all():
        out[int(shop_id)]["pending_orders_count"] = int(count)

    gaps = await session.execute(
        select(KnowledgeGap.shop_bot_id, func.count())
        .where(
            KnowledgeGap.shop_bot_id.in_(shop_bot_ids),
            KnowledgeGap.status == KnowledgeGapStatus.OPEN,
            KnowledgeGap.first_seen_at >= day_start,
            KnowledgeGap.first_seen_at < now,
        )
        .group_by(KnowledgeGap.shop_bot_id)
    )
    for shop_id, count in gaps.all():
        out[int(shop_id)]["new_knowledge_gaps"] = int(count)

    return out


async def get_shop_daily_stats(
    session: AsyncSession, shop_bot_id: int, day_start: datetime.datetime, now: datetime.datetime
) -> dict:
    """
    برایِ گزارشِ شبانه (برخلافِ get_shop_stats که تجمعیِ همیشگی/بازه‌ایه): فقط
    عددهایی که از نیمه‌شبِ UTC (day_start) تا همین الان (now) اتفاق افتادن،
    به‌علاوه‌ی یه عددِ غیرِ‌روزانه (سفارش‌هایِ در انتظارِ تاییدِ فروشگاه‌دار،
    فارغ از اینکه امروز ساخته شده باشن یا نه) که خودِ گزارش رو عملی‌تر می‌کنه.
    """
    order_result = await session.execute(
        select(OrderConsultation.type, func.count())
        .where(OrderConsultation.shop_bot_id == shop_bot_id, OrderConsultation.created_at >= day_start, OrderConsultation.created_at < now)
        .group_by(OrderConsultation.type)
    )
    today_counts = {"order": 0, "consultation": 0}
    for order_type, count in order_result.all():
        key = order_type.value if hasattr(order_type, "value") else order_type
        today_counts[key] = count

    # برآوردِ فروشِ «تاییدشده»یِ امروز: مجموعِ estimated_value_toman سفارش‌هایی
    # که امروز توسطِ فروشگاه‌دار تایید شدن (confirmed_at، نه created_at — یه
    # سفارشِ دیروز که امروز تایید شده هم باید توی فروشِ امروز حساب بشه، نه
    # دیروز). این یه برآوردِ هوش‌مصنوعیه، نه رقمِ دقیقِ حسابداری.
    revenue_result = await session.execute(
        select(func.coalesce(func.sum(OrderConsultation.estimated_value_toman), 0)).where(
            OrderConsultation.shop_bot_id == shop_bot_id,
            OrderConsultation.confirmed.is_(True),
            OrderConsultation.confirmed_at >= day_start,
            OrderConsultation.confirmed_at < now,
        )
    )
    confirmed_revenue_today = revenue_result.scalar_one()

    new_customers_result = await session.execute(
        select(func.count())
        .select_from(Customer)
        .where(Customer.shop_bot_id == shop_bot_id, Customer.first_seen_at >= day_start, Customer.first_seen_at < now)
    )
    new_customers_today = new_customers_result.scalar_one()

    pending_result = await session.execute(
        select(func.count())
        .select_from(OrderConsultation)
        .where(OrderConsultation.shop_bot_id == shop_bot_id, OrderConsultation.status == OrderStatus.PENDING)
    )
    pending_orders_count = pending_result.scalar_one()

    # فازِ ۴: سوال‌هایِ بی‌جوابی که امروز برای اولین بار دیده شدن و هنوز بازن (کلیدِ اختیاری؛
    # گزارش فقط وقتی >۰ باشه خطش رو نشون می‌ده).
    new_knowledge_gaps = await knowledge_service.count_new_open_gaps(session, shop_bot_id, day_start, now)

    return {
        "new_orders_today": today_counts["order"],
        "new_consultations_today": today_counts["consultation"],
        "confirmed_revenue_today_toman": confirmed_revenue_today,
        "new_customers_today": new_customers_today,
        "pending_orders_count": pending_orders_count,
        "new_knowledge_gaps": new_knowledge_gaps,
    }


async def get_shop_stats(session: AsyncSession, shop_bot_id: int) -> dict:
    now = datetime.datetime.now(datetime.timezone.utc)
    day_ago = now - datetime.timedelta(days=1)
    week_ago = now - datetime.timedelta(days=7)
    month_ago = now - datetime.timedelta(days=30)

    order_counts = await order_service.count_by_type(session, shop_bot_id)

    return {
        "messages_today": await _count_customer_messages_since(session, shop_bot_id, day_ago),
        "messages_week": await _count_customer_messages_since(session, shop_bot_id, week_ago),
        "messages_month": await _count_customer_messages_since(session, shop_bot_id, month_ago),
        "orders_count": order_counts["order"],
        "consultations_count": order_counts["consultation"],
        "top_products": await _get_top_products(session, shop_bot_id, month_ago),
        "success_rate": await _get_success_rate(session, shop_bot_id),
    }


async def get_platform_stats(session: AsyncSession) -> dict:
    total_owners = await session.scalar(select(func.count()).select_from(ShopOwner).where(ShopOwner.registration_completed.is_(True)))
    total_active_bots = await session.scalar(select(func.count()).select_from(ShopBot).where(ShopBot.is_active.is_(True)))

    owners_with_wallet_balance = await session.scalar(
        select(func.count()).select_from(ShopOwner).where(ShopOwner.wallet_balance_toman > 0)
    )

    total_revenue = await session.scalar(select(func.coalesce(func.sum(Payment.final_amount), 0)).where(Payment.status == PaymentStatus.APPROVED))

    order_result = await session.execute(select(OrderConsultation.type, func.count()).group_by(OrderConsultation.type))
    order_counts = {"order": 0, "consultation": 0}
    for order_type, count in order_result.all():
        key = order_type.value if hasattr(order_type, "value") else order_type
        order_counts[key] = count

    # خلاصه‌ی سبکِ اقتصادِ کیف‌پول (نه هزینه‌ی واقعیِ ارزیِ ارائه‌دهنده‌ی هوش مصنوعی،
    # چون اونو ردیابی نمی‌کنیم؛ این فقط می‌گه چقدر واقعاً پول گرفتیم در برابرِ
    # چقدر رایگان (تراِیل/معرفی/هدیه) بخشیدیم و چقدر مصرف شده).
    usage_reasons = [
        WalletTransactionReason.CHAT_MESSAGE,
        WalletTransactionReason.PHOTO_ANALYSIS,
        WalletTransactionReason.VOICE_TRANSCRIPTION,
        WalletTransactionReason.ORDER_DETECTION,
        WalletTransactionReason.CART_EDIT,
        WalletTransactionReason.CRM_SUMMARY,
        WalletTransactionReason.OWNER_ASSISTANT,
    ]
    total_consumed = await session.scalar(
        select(func.coalesce(func.sum(WalletTransaction.amount_toman), 0)).where(WalletTransaction.reason.in_(usage_reasons))
    )
    giveaway_reasons = [WalletTransactionReason.TRIAL, WalletTransactionReason.REFERRAL_REWARD, WalletTransactionReason.ADMIN_GRANT]
    total_given_away = await session.scalar(
        select(func.coalesce(func.sum(WalletTransaction.amount_toman), 0)).where(WalletTransaction.reason.in_(giveaway_reasons))
    )

    # P30: کمیسیونِ سفارشِ موفق هم از کیف‌پول کسر می‌شود (reason=commission؛ settle منفی،
    # reverse مثبت) — برایِ همین جمعِ خالصِ آن جدا از مصرفِ هوش‌مصنوعی گزارش می‌شود.
    commission_net = await session.scalar(
        select(func.coalesce(func.sum(WalletTransaction.amount_toman), 0)).where(
            WalletTransaction.reason == WalletTransactionReason.COMMISSION
        )
    )

    return {
        "total_owners": total_owners or 0,
        "total_active_bots": total_active_bots or 0,
        "owners_with_wallet_balance": owners_with_wallet_balance or 0,
        "total_revenue_toman": total_revenue or 0,
        "orders_count": order_counts["order"],
        "consultations_count": order_counts["consultation"],
        "total_wallet_consumed_toman": abs(total_consumed or 0),
        "total_given_away_toman": total_given_away or 0,
        "commission_revenue_toman": abs(commission_net or 0),
        "ai_api_revenue_toman": abs(total_consumed or 0),
    }


# =============================================================================
# P51 · موردِ ۴۴: درآمدِ ماهانه به تفکیکِ «حالتِ فروشگاه» (مشاوره / فروش)
# =============================================================================
#
# چرا «روز» در SQL و «ماه» در پایتون: ماهِ جلالی با مرزِ میلادی یکی نیست، پس اگر در
# دیتابیس بر اساسِ سال/ماهِ میلادی گروه‌بندی کنیم، برچسبِ نمودار دروغ می‌گوید. این‌جا
# SQL فقط جمعِ هرِ روز را می‌دهد (کوئریِ ساده، یکِ بار)، و خودِ تقویمِ جلالی — که در پروژه
# همین حالا هست — روزها را در ماه‌هایِ درست می‌نشاند.

_USAGE_REASONS = (
    WalletTransactionReason.CHAT_MESSAGE,
    WalletTransactionReason.PHOTO_ANALYSIS,
    WalletTransactionReason.VOICE_TRANSCRIPTION,
    WalletTransactionReason.ORDER_DETECTION,
    WalletTransactionReason.CART_EDIT,
    WalletTransactionReason.CRM_SUMMARY,
    WalletTransactionReason.OWNER_ASSISTANT,
    WalletTransactionReason.RECEIPT_ANALYSIS,
)
_GIVEAWAY_REASONS = (WalletTransactionReason.TRIAL, WalletTransactionReason.REFERRAL_REWARD, WalletTransactionReason.ADMIN_GRANT)

from app.database.models import TenantMode  # noqa: E402  (فقط برایِ تفکیکِ حالتِ فروشگاه)
from app.utils.jalali import JALALI_MONTH_NAMES, gregorian_to_jalali  # noqa: E402


async def _daily_sums(session: AsyncSession, value, *conditions, join_shop_mode: bool = False) -> dict:
    """جمعِ `value` به تفکیکِ روز (و در صورتِ نیازِ join به `shop_bots` ⇒ (روز، حالت) یا (روز)."""
    day = func.date_trunc("day", WalletTransaction.created_at).label("day")
    if join_shop_mode:
        stmt = (
            select(day, ShopBot.tenant_mode, func.coalesce(func.sum(value), 0))
            .select_from(WalletTransaction)
            .join(ShopBot, ShopBot.shop_owner_id == WalletTransaction.shop_owner_id)
            .where(*conditions)
            .group_by(day, ShopBot.tenant_mode)
        )
    else:
        stmt = (
            select(day, func.coalesce(func.sum(value), 0))
            .select_from(WalletTransaction)
            .where(*conditions)
            .group_by(day)
        )
    result = await session.execute(stmt)
    buckets: dict = {}
    for row in result.all():
        if join_shop_mode:
            moment, mode, total = row
            key = (moment.date(), mode.value if hasattr(mode, "value") else mode)
            buckets[key] = buckets.get(key, 0) + int(total or 0)
        else:
            moment, total = row
            buckets[moment.date()] = int(total or 0)
    return buckets


async def _daily_counts(session: AsyncSession, column, table, *conditions) -> dict:
    day = func.date_trunc("day", column).label("day")
    stmt = select(day, func.count()).select_from(table).where(*conditions).group_by(day)
    result = await session.execute(stmt)
    return {row[0].date(): int(row[1] or 0) for row in result.all()}


def _jalali_month(moment_date: datetime.date) -> tuple[int, int]:
    j_year, j_month, _day = gregorian_to_jalali(moment_date.year, moment_date.month, moment_date.day)
    return j_year, j_month


def _month_label(key: tuple[int, int]) -> str:
    from app.utils.validators import fa_number

    return f"{JALALI_MONTH_NAMES[key[1] - 1]} {fa_number(key[0])}"


def _merge_into(months: dict, buckets, key_of, field: str, *, sign: int = 1) -> None:
    """جمعِ روزها در ماهِ جلالی. `sign=-1` برایِ ردیف‌هایی که در کیف‌پول *منفی* ثبت می‌شوند
    (مصرفِ اعتبار و کمیسیون) ⇒ برگشت‌هایِ مثبتِ همان ماه هم کم می‌شود و عدد «خالص» می‌ماند؛
    دقیقاً همان چیزی که صفحهٔ «خلاصهٔ کلِ دوره» نشان می‌دهد (تا دو صفحه یک رقم ندهند)."""
    for raw_key, total in buckets.items():
        j_key = key_of(raw_key)
        months.setdefault(j_key, {})
        months[j_key][field] = months[j_key].get(field, 0) + sign * int(total)


async def platform_revenue_report(session: AsyncSession, *, since: datetime.datetime, until: datetime.datetime) -> dict:
    """گزارشِ درآمدِ بازه، به تفکیکِ ماهِ جلالی و حالتِ فروشگاه (مشاوره / فروش).

    شش کوئریِ گروهی — صفحهٔ ادمین است، نه مسیرِ پیامِ مشتری. «مصرفِ اعتبار» = درآمدی که
    فروشگاه‌دار بابتِ هوش مصنوعی پرداخته (کسرهایِ کیف‌پول، بدونِ هدیه‌ها)؛ «کمیسیون» =
    سهمِ پلتفرم از سفارش‌ها؛ «نقد دریافتی» = شارژ/اشتراک (که هنوز مصرف نشده، پس با
    درآمدِ محقق‌شده جمع نمی‌شود — این تفکیک عمدی و مهم است).
    """
    window = (WalletTransaction.created_at >= since, WalletTransaction.created_at < until)
    months: dict = {}

    usage = await _daily_sums(session, WalletTransaction.amount_toman, WalletTransaction.reason.in_(_USAGE_REASONS), *window)
    _merge_into(months, usage, _jalali_month, "ai_total", sign=-1)
    by_mode = await _daily_sums(
        session, WalletTransaction.amount_toman, WalletTransaction.reason.in_(_USAGE_REASONS), *window, join_shop_mode=True
    )
    for (day, mode), total in by_mode.items():
        field = "ai_consult" if mode == TenantMode.CONSULTATION.value else "ai_sales"
        _merge_into(months, {day: total}, _jalali_month, field, sign=-1)

    commission = await _daily_sums(
        session, WalletTransaction.amount_toman, WalletTransaction.reason == WalletTransactionReason.COMMISSION, *window
    )
    _merge_into(months, commission, _jalali_month, "commission", sign=-1)

    # نقدِ دریافتی رویِ جدولِ Payment است (شارژِ کیف‌پول و خریدِ اشتراک) — جدا از درآمدِ محقق‌شده.
    pay_day = func.date_trunc("day", Payment.created_at).label("day")
    cash_rows = await session.execute(
        select(pay_day, Payment.purpose, func.coalesce(func.sum(Payment.final_amount), 0))
        .where(Payment.status == PaymentStatus.APPROVED, Payment.created_at >= since, Payment.created_at < until)
        .group_by(pay_day, Payment.purpose)
    )
    for moment, purpose, total in cash_rows.all():
        entry = months.setdefault(_jalali_month(moment.date()), {})
        field = "subscription_cash" if (purpose.value if hasattr(purpose, "value") else purpose) == "subscription" else "topup_cash"
        entry[field] = entry.get(field, 0) + int(total or 0)

    orders = await _daily_counts(session, OrderConsultation.created_at, OrderConsultation, OrderConsultation.created_at >= since, OrderConsultation.created_at < until)
    _merge_into(months, orders, _jalali_month, "orders")
    messages = await _daily_counts(
        session,
        ConversationMessage.created_at,
        ConversationMessage,
        ConversationMessage.role == "user",
        ConversationMessage.created_at >= since,
        ConversationMessage.created_at < until,
    )
    _merge_into(months, messages, _jalali_month, "messages")

    keys = sorted(months)
    series = []
    for key in keys:
        row = {"key": key, "label": _month_label(key)}
        row.update({field: int(months[key].get(field, 0)) for field in _REVENUE_FIELDS})
        series.append(row)

    totals = {field: sum(row[field] for row in series) for field in _REVENUE_FIELDS}
    totals["months"] = len(series)
    return {"since": since, "until": until, "series": series, "totals": totals}


_REVENUE_FIELDS = ("ai_total", "ai_sales", "ai_consult", "commission", "topup_cash", "subscription_cash", "orders", "messages")
