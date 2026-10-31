"""
صورت‌حسابِ قابلیت‌هایِ AIِ *سمتِ فروشگاه‌دار* (فازِ ۴: دستیارِ مدیریتی، خلاصه‌یِ هوشمندِ CRM).

عمداً نسخه‌یِ جدا از customer.py::_deduct_and_notify ـه (اون خصوصیه و مالِ رباتِ فروشگاهیه و
تست‌شده؛ بندِ ۵۰) — اینجا اعلانِ «کیف‌پول خالی/کم» با رباتِ *اصلی* فرستاده می‌شه.

قاعده‌هایِ مشترک:
- قبل از فراخوانیِ AI: موجودیِ کیف‌پول با تخمینِ هزینه چک می‌شه (has_funds).
- کسر فقط *بعد از موفقیتِ* AI (charge_owner)؛ شکستِ AI → بدونِ کسر.
- محدودیتِ نرخ با سطلِ جدا برایِ هر قابلیت (allow_request) تا با سطلِ پیام‌هایِ چتِ مشتری قاطی نشه.
"""
from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

from app.bots.main_bot import texts as main_texts
from app.database.models import WalletTransactionReason
from app.services import wallet_service
from app.services.rate_limiter import rate_limiter

logger = logging.getLogger(__name__)

KIND_ASSISTANT = "assistant"
KIND_CRM_SUMMARY = "crm_summary"

# (حداکثر درخواست، بازه‌یِ ثانیه‌ای)
_LIMITS = {KIND_ASSISTANT: (20, 600), KIND_CRM_SUMMARY: (10, 600)}
# شناسه‌یِ سطل = منفیِ (آفست + شناسه‌یِ فروشگاه) تا هیچ‌وقت با شناسه‌یِ مثبتِ چتِ مشتری یا
# شناسه‌یِ منفیِ سادهیِ امتحانِ کدِ تخفیف (campaign_service) برخورد نکنه.
_BUCKET_OFFSETS = {KIND_ASSISTANT: 10_000_000, KIND_CRM_SUMMARY: 20_000_000}


def allow_request(kind: str, shop_bot_id: int, owner_telegram_id: int) -> bool:
    max_requests, window_seconds = _LIMITS[kind]
    return rate_limiter.check_and_record(-(_BUCKET_OFFSETS[kind] + shop_bot_id), owner_telegram_id, max_requests, window_seconds)


def has_funds(owner, estimated_cost_toman: int) -> bool:
    return owner is not None and owner.wallet_balance_toman >= max(1, estimated_cost_toman)


async def charge_owner(
    session, owner, admin_settings, amount_toman: int, reason: WalletTransactionReason, main_bot: Bot
) -> bool:
    """بعدِ فراخوانیِ موفقِ AI صدا زده می‌شه. اگه موجودی در لحظه‌یِ کسر کافی نبود (مثلاً یه پیامِ
    هم‌زمانِ مشتری مصرفش کرده) فقط لاگ می‌شه — جوابِ تولیدشده از دست نمی‌ره. خروجی: آیا کسر انجام شد."""
    success = await wallet_service.deduct(session, owner, amount_toman, reason)
    if not success:
        logger.warning("کسرِ %s تومنِ %s برایِ فروشگاه‌دارِ %s ناموفق بود (موجودیِ ناکافی در لحظه‌یِ کسر).", amount_toman, reason, owner.id)

    if owner.wallet_balance_toman <= 0:
        if await wallet_service.try_claim_empty_notification(session, owner):
            try:
                await main_bot.send_message(owner.telegram_id, main_texts.wallet_empty_notification())
            except TelegramAPIError:
                logger.exception("اطلاع‌رسانیِ اتمامِ کیف‌پول به فروشگاه‌دار %s ناموفق بود.", owner.telegram_id)
    elif owner.wallet_balance_toman < admin_settings.wallet_low_balance_warning_toman:
        if await wallet_service.try_claim_low_balance_notification(session, owner):
            try:
                await main_bot.send_message(owner.telegram_id, main_texts.wallet_low_balance_notification(owner.wallet_balance_toman))
            except TelegramAPIError:
                logger.exception("اطلاع‌رسانیِ کمبودِ کیف‌پول به فروشگاه‌دار %s ناموفق بود.", owner.telegram_id)
    return success
