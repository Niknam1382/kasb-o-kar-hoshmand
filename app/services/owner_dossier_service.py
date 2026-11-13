"""پروندهٔ کاملِ یکِ فروشگاه‌دار (پ۶۷ · نیمهٔ بازِ موردِ ۲۷/۴۱: «مدیریتِ جامعِ کاربران»).

چرا: اطلاعاتِ یکِ کاربر در چهار صفحهٔ جدا پخش بود — «👥 مدیریت فروشگاه‌دارها» (هویت + وضعیتِ ربات +
موجودی)، «📊 مصرفِ کاربران» (پولِ مصرفی، ولی *به‌ازایِ هر مشتری*)، «🧹 کاربرانِ غیرفعال» (دیدار و
حذفِ حساب) و «⏱ اعتبار و زمان» (تمدیدِ *گروهی*). ادمین برایِ تصمیم‌گیری مجبور بود چهار صفحه را باز
و در ذهنش جمع کند. این سرویس همان‌ها را در یکِ نما می‌آورد و **هیچ فعلِ تازه‌ای اختراع نمی‌کند**:
دکمه‌هایِ صفحه همه به کال‌بک‌هایِ موجود می‌روند که چک‌هایِ RBAC و ممیزیِ خودشان را دارند.

سه قید:
• فقط‌خواندنی جزِ عملِ «تمدیدِ روز» که از `subscription_service.extend_by_days` (همان مسیرِ
  تمدیدِ گروهیِ K2) استفاده می‌کند؛ هیچ‌جای دیگر پولِ واقعی جابه‌جا نمی‌شود.
• شمارش‌ها همه با کوئریِ تجمیعیِ ایندکس‌دار رویِ `shop_owner_id` / `shop_bot_id` می‌آیند (≈۱۳
  جمله، صفحه‌ای که با درخواستِ ادمین باز می‌شود، نه در مسیرِ داغ).
• شمارهٔ تلفن *ماسک‌شده* نشان داده می‌شود و ایمیلِ کامل فقط وقتی نمایش داده می‌شود که ادمین
  خودش آن را در کارتِ پروفایل دیده باشد (از همین‌جا: `mask_phone` و ایمیلِ خودِ حساب).
"""

from __future__ import annotations

import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import (
    AuditLogEntry,
    Campaign,
    OrderConsultation,
    Payment,
    PaymentStatus,
    WalletTransaction,
    WalletTransactionReason,
)
from app.services import (
    ai_debt_service,
    bale_bot_service,
    customer_service,
    instagram_service,
    moderation_service,
    order_service,
    shop_bot_service,
    subscription_service,
    wallet_service,
)
from app.database.models import ShopOwner

# همان مجموعهٔ دلایلِ مصرفِ AI که `stats_service` و پنلِ «📊 مصرفِ کاربران» می‌شمارند؛ عمداً این‌جا
# هم از خودِ enum ساخته می‌شود تا اگر دلیلِ تازه‌ای به `WalletTransactionReason` اضافه شد، درِ
# شمارشِ پرونده باز نماند (برعکسِ importِ یکِ فهرستِ خصوصیِ ماژولِ دیگر).
AI_REASON_VALUES = [
    WalletTransactionReason.CHAT_MESSAGE.value,
    WalletTransactionReason.PHOTO_ANALYSIS.value,
    WalletTransactionReason.RECEIPT_ANALYSIS.value,
    WalletTransactionReason.VOICE_TRANSCRIPTION.value,
    WalletTransactionReason.ORDER_DETECTION.value,
    WalletTransactionReason.CART_EDIT.value,
    WalletTransactionReason.CRM_SUMMARY.value,
    WalletTransactionReason.OWNER_ASSISTANT.value,
]
USAGE_WINDOW_DAYS = 30
AUDIT_PREVIEW_LIMIT = 5


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _days_since(moment: datetime.datetime | None, *, now: datetime.datetime) -> int | None:
    if moment is None:
        return None
    reference = moment if moment.tzinfo else moment.replace(tzinfo=datetime.timezone.utc)
    return max(0, int((now - reference).total_seconds() // 86_400))


async def _scalar(session: AsyncSession, statement) -> int:
    return int((await session.execute(statement)).scalar_one() or 0)


async def build(session: AsyncSession, owner_id: int, *, now: datetime.datetime | None = None) -> dict[str, Any] | None:
    """پروندهٔ یکِ فروشگاه‌دار. `None` ⇒ حساب وجود ندارد (ادمینِ عملیاتی خارج از دامنه *اینجا*
    نمی‌رسد؛ چکِ دامنه در هندلر است، نه در سرویس)."""
    owner = await session.get(ShopOwner, owner_id)
    if owner is None:
        return None
    moment = now or _utcnow()
    since = moment - datetime.timedelta(days=USAGE_WINDOW_DAYS)

    shop_bot = await shop_bot_service.get_by_owner(session, owner)
    subscription = await subscription_service.get_latest_subscription_by_owner_id(session, owner.id)
    usable = await subscription_service.is_shop_usable(session, owner.id)
    data: dict[str, Any] = {
        "owner_id": owner.id,
        "telegram_id": int(owner.telegram_id),
        "name": f"{(owner.first_name or '').strip()} {(owner.last_name or '').strip()}".strip() or None,
        "username": owner.username,
        "phone_masked": None,
        "email": owner.email,
        "business_mode": owner.business_mode,
        "registration_completed": bool(owner.registration_completed),
        "is_deleted": bool(owner.is_deleted),
        "deleted_at": owner.deleted_at,
        "last_seen_at": owner.last_seen_at,
        "last_seen_days": _days_since(owner.last_seen_at, now=moment),
        "deleted_days": _days_since(owner.deleted_at, now=moment),
        "created_at": getattr(owner, "created_at", None),
        "referral_code": owner.referral_code,
        "wallet_toman": int(owner.wallet_balance_toman or 0),
        "usable_toman": wallet_service.usable_credit(owner),
        "reserved_toman": int(owner.commission_reserved_toman or 0),
        "debt_toman": await ai_debt_service.open_total_for_owner(session, owner.id),
    }
    from app.utils.validators import mask_phone

    data["phone_masked"] = mask_phone(owner.phone_number) if owner.phone_number else None

    # اشتراک
    if subscription is None:
        data["subscription"] = None
        data["shop_usable"] = bool(usable)
    else:
        end = subscription.end_date
        reference = end if end.tzinfo else end.replace(tzinfo=datetime.timezone.utc)
        data["subscription"] = {
            "status": subscription.status.value if hasattr(subscription.status, "value") else str(subscription.status),
            "end_date": end,
            "days_left": int((reference - moment).total_seconds() // 86_400),
            "is_trial": bool(subscription.is_trial),
            "duration_months": int(subscription.duration_months),
            "usable": bool(usable),
        }

    # دو جمعِ تجمیعی (نه چهار جمله): پرداخت‌هایِ تاییدشده و مصرفِ AI. هر دو رویِ همین یکِ حساب.
    payments_count, payments_total = (
        await session.execute(
            select(func.count(), func.coalesce(func.sum(Payment.final_amount), 0)).where(
                Payment.shop_owner_id == owner.id, Payment.status == PaymentStatus.APPROVED
            )
        )
    ).one()
    data["payments"] = {"count": int(payments_count or 0), "total_toman": int(payments_total or 0)}

    usage_calls, usage_toman = (
        await session.execute(
            select(func.count(), func.coalesce(func.sum(-WalletTransaction.amount_toman), 0)).where(
                WalletTransaction.shop_owner_id == owner.id,
                WalletTransaction.reason.in_(AI_REASON_VALUES),
                WalletTransaction.amount_toman < 0,
                WalletTransaction.created_at >= since,
            )
        )
    ).one()
    data["usage"] = {"days": USAGE_WINDOW_DAYS, "toman": int(usage_toman or 0), "calls": int(usage_calls or 0)}

    if shop_bot is None:
        data["shop_bot"] = None
        data["connections"] = {"bale": False, "bale_username": None, "bale_enabled": False, "instagram": None}
        data["activity"] = {"customers": 0, "orders": 0, "open_orders": 0, "campaigns": 0, "moderation_open": 0, "audit_rows": 0}
        return data

    bot_id = int(shop_bot.id)
    account = await instagram_service.account_for_shop(session, bot_id)
    data["shop_bot"] = {
        "id": bot_id,
        "bot_username": shop_bot.bot_username,
        "bot_telegram_id": int(shop_bot.bot_telegram_id),
        "is_active": bool(shop_bot.is_active),
        "disabled_reason": shop_bot.disabled_reason,
        "tenant_mode": shop_bot.tenant_mode.value if hasattr(shop_bot.tenant_mode, "value") else str(shop_bot.tenant_mode),
        "has_token": bool(shop_bot.encrypted_token),
        "bale_provider": bool(shop_bot.bale_provider_token),
        "zarinpal": bool(shop_bot.zarinpal_merchant_id),
        "knowledge_channel": bool(shop_bot.knowledge_channel_id),
        "support_enabled": bool(shop_bot.support_enabled),
    }
    data["connections"] = {
        "bale": bale_bot_service.has_token(shop_bot),
        "bale_username": shop_bot.bale_bot_username,
        "bale_enabled": bool(shop_bot.bale_bot_enabled),
        "instagram": None
        if account is None
        else {
            "ig_username": account.ig_username,
            "is_active": bool(account.is_active),
            "muted": instagram_service.is_muted(account, moment),
            "muted_until": instagram_service.mute_until(account, moment),
            "auto_reply_dm": bool(account.auto_reply_dm),
            "auto_reply_comments": bool(account.auto_reply_comments),
        },
    }

    data["activity"] = {
        "customers": await customer_service.count_by_shop_bot(session, bot_id),
        "orders": await _scalar(session, select(func.count()).select_from(OrderConsultation).where(OrderConsultation.shop_bot_id == bot_id)),
        "open_orders": await order_service.count_open_orders(session, bot_id),
        "campaigns": await _scalar(
            session, select(func.count()).select_from(Campaign).where(Campaign.shop_bot_id == bot_id, Campaign.is_active.is_(True))
        ),
        "moderation_open": await moderation_service.count_reports(session, [bot_id], only_open=True),
        "audit_rows": await _scalar(session, select(func.count()).select_from(AuditLogEntry).where(AuditLogEntry.shop_bot_id == bot_id)),
    }
    return data


async def recent_audit(session: AsyncSession, shop_bot_id: int | None, limit: int = AUDIT_PREVIEW_LIMIT) -> list[tuple[str, datetime.datetime]]:
    """چند ردیفِ آخرِ ممیزیِ همین فروشگاه (برایِ همان صفحه؛ متنِ خامِ ممیزی در «📜 گزارشِ ممیزی» است).

    شناسهٔ ربات را *می‌گیرد* و دوباره نمی‌خواند: این تابع درست بعدِ `build()` صدا زده می‌شود و
    آنجا همان ربات باز شده بود — یکِ SELECTِ دوباره رویِ `shop_bots` و `shop_owners` برایِ
    صفحه‌ای که ادمین هر بار فقط یکِ حساب را می‌بیند، بی‌دلیل بود.
    """
    if shop_bot_id is None:
        return []
    rows = (
        await session.execute(
            select(AuditLogEntry.event_type, AuditLogEntry.created_at)
            .where(AuditLogEntry.shop_bot_id == shop_bot_id)
            .order_by(AuditLogEntry.id.desc())
            .limit(limit)
        )
    ).all()
    out: list[tuple[str, datetime.datetime]] = []
    for event_type, created_at in rows:
        out.append((event_type.value if hasattr(event_type, "value") else str(event_type), created_at))
    return out


def extend_allowed(data: dict[str, Any]) -> tuple[bool, str | None]:
    """تمدیدِ روز فقط رویِ حسابی معنا دارد که بسته نشده باشد (`None` ⇒ آزاد)."""
    if data["is_deleted"]:
        return False, "deleted"
    return True, None
