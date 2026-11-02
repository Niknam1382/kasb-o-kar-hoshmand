"""پاک‌سازیِ محتوایِ حسابِ فروشگاه‌دار (P22 · مشکلِ ۸: «دیلیت اکانت»).

سه تصمیمِ که اینجا مهم‌اند و اگر بعداً کسی آن‌ها را «تمیزکاری» بخواند، خراب می‌شوند:

۱) حذفِ قطعیِ *پوسته* (ردیفِ `shop_owners` و `shop_bots`) مجاز نیست اگر حتی یکِ ردیفِ
   ممیزی به آن ربات ارجاع داشته باشد. `audit_log_entries` زنجیرهٔ هش دارد
   (`scripts/verify_audit_chain.py`): پاک‌کردنِ یکِ ردیفِ میانی، پیوندِ ردیف‌هایِ بعد را
   می‌شکند و دفتری که باید شاهدِ بیرونیِ تصمیم‌هایِ مالی باشد، بی‌ارزش می‌شود. پس
   `purge_owner()` محتوا را می‌بُرد و پوسته را فقط وقتی می‌اندازد که هیچ ارجاعِ ماندگاری نباشد؛
   اگر باشد، پوسته می‌ماند و گزارشِ دقیقی می‌دهد.

۲) ترتیبِ حذف *دستی* است، نه با `ON DELETE CASCADE`. اسکیمای این پروژه cascade ندارد
   (عمدی: حذفِ زنجیره‌ایِ ناخواسته بزرگ‌ترین ریسکش است). فهرست‌هایِ پایین از گرافِ واقعیِ
   کلیدهایِ خارجیِ دیتابیسِ اجرا شده بیرون آمده‌اند؛ هر ستونِ جدیدِ ارجاع‌دهنده باید به همان
   فهرست اضافه شود، وگرنه حذف با `ForeignKeyViolation` بی‌عمل می‌ماند (که امن است، ولی
   کاربر را گیج می‌کند).

۳) تراکنشِ تک‌پارچه: یا همه‌چیز پاک می‌شود یا هیچ‌چیز. فراخواننده باید `commit()` را خودش
   بعدِ نوشتنِ ردیفِ ممیزی انجام دهد.
"""

from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import (
    AdminCreditBatchItem,
    AuditLogEntry,
    BotErrorEvent,
    Campaign,
    Cart,
    CartAiProposal,
    CartItem,
    ChannelKnowledge,
    CommissionReceivable,
    ConversationMessage,
    Customer,
    CustomerAddress,
    DigitalCode,
    DirectMessage,
    DiscountCodeUsage,
    Invoice,
    InvoiceCounter,
    KnowledgeGap,
    LearnedAnswer,
    Notification,
    OrderConsultation,
    OrderEvent,
    OrderPayment,
    OtpCode,
    Payment,
    PaymentEventLog,
    Product,
    Referral,
    ScheduledBroadcast,
    ShippingMethod,
    ShopBot,
    ShopOwner,
    ShopPaymentSettings,
    Subscription,
    TimeFreeze,
    WalletCharge,
    WalletTransaction,
)

# ردیف‌هایِ وابسته‌یِ یکِ رباتِ فروشگاه، به ترتیبِ کلیدِ خارجی (اولِ وابسته‌ها، بعدِ خودِ جدول‌ها).
_BOT_CHILD_COLUMNS = (
    ("order_events", OrderEvent.order_id, "orders"),
    ("digital_codes", DigitalCode.order_id, "orders"),
    ("direct_messages", DirectMessage.order_id, "orders"),
    ("wallet_transactions", WalletTransaction.order_id, "orders"),
    ("cart_items", CartItem.cart_id, "carts"),
    ("cart_ai_proposals", CartAiProposal.cart_id, "carts"),
    ("conversation_messages", ConversationMessage.customer_id, "customers"),
    ("customer_addresses", CustomerAddress.customer_id, "customers"),
    ("direct_messages", DirectMessage.customer_id, "customers"),
    ("carts", Cart.customer_id, "customers"),
    ("orders_consultations", OrderConsultation.customer_id, "customers"),
)

# جدول‌هایی که مستقیم به `shop_bots.id` ارجاع می‌دهند. `audit_log_entries` عمداً در این فهرست نیست.
_BOT_TABLES = (
    "payment_event_logs",
    "invoices",
    "invoice_counters",
    "order_payments",
    "shop_payment_settings",
    "channel_knowledge",
    "knowledge_gaps",
    "learned_answers",
    "campaigns",
    "bot_error_events",
    "scheduled_broadcasts",
    "notifications",
    "shipping_methods",
    "products",
    "customers",
    "orders_consultations",
    "carts",
)

_OWNERSHIP_COLUMNS = (
    ("wallet_transactions", WalletTransaction.shop_owner_id),
    ("wallet_charges", WalletCharge.shop_owner_id),
    ("commission_receivables", CommissionReceivable.shop_owner_id),
    ("discount_code_usages", DiscountCodeUsage.shop_owner_id),
    ("admin_credit_batch_items", AdminCreditBatchItem.shop_owner_id),
    ("otp_codes", OtpCode.shop_owner_id),
    ("payments", Payment.shop_owner_id),
    ("subscriptions", Subscription.shop_owner_id),
    ("time_freezes", TimeFreeze.shop_owner_id),
    ("notifications", Notification.owner_id),
    ("scheduled_broadcasts", ScheduledBroadcast.owner_id),
)

_MODEL_BY_TABLE = {
    "payment_event_logs": PaymentEventLog,
    "invoices": Invoice,
    "invoice_counters": InvoiceCounter,
    "order_payments": OrderPayment,
    "shop_payment_settings": ShopPaymentSettings,
    "channel_knowledge": ChannelKnowledge,
    "knowledge_gaps": KnowledgeGap,
    "learned_answers": LearnedAnswer,
    "campaigns": Campaign,
    "bot_error_events": BotErrorEvent,
    "scheduled_broadcasts": ScheduledBroadcast,
    "notifications": Notification,
    "shipping_methods": ShippingMethod,
    "products": Product,
    "customers": Customer,
    "orders_consultations": OrderConsultation,
    "carts": Cart,
    "order_events": OrderEvent,
    "digital_codes": DigitalCode,
    "direct_messages": DirectMessage,
    "wallet_transactions": WalletTransaction,
    "cart_items": CartItem,
    "cart_ai_proposals": CartAiProposal,
    "conversation_messages": ConversationMessage,
    "customer_addresses": CustomerAddress,
    "wallet_charges": WalletCharge,
    "commission_receivables": CommissionReceivable,
    "discount_code_usages": DiscountCodeUsage,
    "admin_credit_batch_items": AdminCreditBatchItem,
    "otp_codes": OtpCode,
    "payments": Payment,
    "subscriptions": Subscription,
    "time_freezes": TimeFreeze,
}


async def _bots_of(session: AsyncSession, owner_id: int) -> list[ShopBot]:
    return list((await session.execute(select(ShopBot).where(ShopBot.shop_owner_id == owner_id).order_by(ShopBot.id))).scalars().all())


async def _count(session: AsyncSession, model, column, ids: list[int]) -> int:
    if not ids:
        return 0
    return int((await session.execute(select(func.count()).select_from(model).where(column.in_(ids)))).scalar_one())


async def delete_content(session: AsyncSession, owner: ShopOwner) -> dict[str, int]:
    """همهٔ ردیف‌هایِ *محتواییِ* این فروشگاه‌دار و ربات(های)ش را پاک می‌کند.

    `shop_bots`، `shop_owners` و `audit_log_entries` دست‌نخورده می‌مانند؛ این‌ها پوسته و
    شاهدِ ممیزی‌اند و مسئولیتِ `purge_owner()` است.
    """
    removed: dict[str, int] = {}
    bots = await _bots_of(session, owner.id)
    bot_ids = [bot.id for bot in bots]
    if bot_ids:
        order_source = select(OrderConsultation.id).where(OrderConsultation.shop_bot_id.in_(bot_ids))
        customer_source = select(Customer.id).where(Customer.shop_bot_id.in_(bot_ids))
        cart_source = select(Cart.id).where(Cart.shop_bot_id.in_(bot_ids))
        sources = {"orders": order_source, "customers": customer_source, "carts": cart_source}
        for table, column, source_key in _BOT_CHILD_COLUMNS:
            result = await session.execute(delete(_MODEL_BY_TABLE[table]).where(column.in_(sources[source_key])))
            removed[table] = removed.get(table, 0) + int(result.rowcount or 0)
        for table in _BOT_TABLES:
            model = _MODEL_BY_TABLE[table]
            result = await session.execute(delete(model).where(model.shop_bot_id.in_(bot_ids)))
            removed[table] = removed.get(table, 0) + int(result.rowcount or 0)

    owner_ids = [owner.id]
    for table, column in _OWNERSHIP_COLUMNS:
        result = await session.execute(delete(_MODEL_BY_TABLE[table]).where(column.in_(owner_ids)))
        removed[table] = removed.get(table, 0) + int(result.rowcount or 0)
    # دعوت‌هایِ دوطرفه فقط وقتی پاک می‌شوند که هر دو سرِ آن همین حساب باشد؛ اگر آدمِ دیگری با
    # کدِ دعوتِ این حساب ثبت‌نام کرده باشد، آن ردیف تاریخچهٔ حسابِ دیگری است.
    result = await session.execute(delete(Referral).where(Referral.referrer_id.in_(owner_ids), Referral.referred_id.in_(owner_ids)))
    removed["referrals"] = int(result.rowcount or 0)

    owner.wallet_balance_toman = 0
    owner.commission_reserved_toman = 0
    removed["total"] = sum(value for key, value in removed.items() if key != "total")
    return removed


async def blocking_references(session: AsyncSession, owner: ShopOwner) -> dict[str, int]:
    """چه چیزهایی ماندنِ پوسته را مجبور می‌کند (دستیاریِ گزارشِ ادمین)."""
    bots = await _bots_of(session, owner.id)
    bot_ids = [bot.id for bot in bots]
    blockers: dict[str, int] = {}
    if bot_ids:
        audit = await _count(session, AuditLogEntry, AuditLogEntry.shop_bot_id, bot_ids)
        if audit:
            blockers["audit_log_entries"] = audit
    referred = int(
        (
            await session.execute(
                select(func.count()).select_from(ShopOwner).where(ShopOwner.referred_by_id == owner.id, ShopOwner.id != owner.id)
            )
        ).scalar_one()
    )
    if referred:
        blockers["shop_owners.referred_by"] = referred
    return blockers


async def purge_owner(session: AsyncSession, owner: ShopOwner) -> dict:
    """حذفِ قطعی: محتوا می‌رود؛ پوسته فقط وقتی می‌رود که چیزی به آن بند نباشد.

    خروجی: `{"removed": {...}, "shell_removed": bool, "blockers": {جدول: تعداد}}` — هندلرِ پنل
    همین را در ردیفِ ممیزی و در پیامِ ادمین گزارش می‌دهد.
    """
    removed = await delete_content(session, owner)
    blockers = await blocking_references(session, owner)
    shell_removed = False
    if not blockers:
        for bot in await _bots_of(session, owner.id):
            await session.execute(delete(ShopBot).where(ShopBot.id == bot.id))
        await session.execute(delete(ShopOwner).where(ShopOwner.id == owner.id))
        shell_removed = True
    return {"removed": removed, "shell_removed": shell_removed, "blockers": blockers}
