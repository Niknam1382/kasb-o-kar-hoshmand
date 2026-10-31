from __future__ import annotations

import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import (
    BotErrorEvent,
    ConversationMessage,
    Customer,
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

    return {
        "total_owners": total_owners or 0,
        "total_active_bots": total_active_bots or 0,
        "owners_with_wallet_balance": owners_with_wallet_balance or 0,
        "total_revenue_toman": total_revenue or 0,
        "orders_count": order_counts["order"],
        "consultations_count": order_counts["consultation"],
        "total_wallet_consumed_toman": abs(total_consumed or 0),
        "total_given_away_toman": total_given_away or 0,
    }
