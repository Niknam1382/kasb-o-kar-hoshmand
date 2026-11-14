"""P49-الف: تنها نسخه‌یِ «کسرِ هزینه‌یِ AI از کیف‌پول + اعلانِ به فروشگاه‌دار».

چرا این فایل متولد شد: `customer.py::_deduct_and_notify` دقیقاً همین کار را برایِ تلگرام/بله
می‌کرد ولی *خصوصی* بود و کانالِ سوم (اینستاگرام) هم باید همان مبلغ را همان‌جا کم می‌کرد.
قاعدهٔ پروژه: مسیرِ پول را fork نکن — یکِ helper در لایهٔ سرویس که هر دو صدا می‌زنند.
ریاضیِ هزینه (`estimate_chat_cost`) و منطقِ «بدهی با اعتبارِ صفر» دست‌نخورده از همان تابع
انتقال یافته و `customer.py` فقط به این delegate می‌کند (تست‌هایِ قدیمی با همان نامِ خصوصی کار
می‌کنند: `tests_manual/test_p33_ai_usage_debt.py`).

اعلان‌ها به‌عمق از *رباتِ اصلی* به چتِ خودِ فروشگاه‌دار می‌روند؛ هیچ پیامی به مشتری اینجا
نوشته نمی‌شود (تجربهٔ مشتری نباید با مشکلِ مالیِ فروشگاه خراب شود).
"""

from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

from app.bots.main_bot import texts as main_texts
from app.database.models import WalletTransactionReason
from app.services import ai_debt_service, wallet_service

logger = logging.getLogger(__name__)


async def deduct_and_notify(
    session, owner, admin_settings, amount_toman: int, reason: WalletTransactionReason, main_bot: Bot,
    customer_id: int | None = None, ai_total_tokens: int | None = None,
) -> None:
    """بعدِ فراخوانیِ موفقِ هوش مصنوعی، هزینه رو از کیف‌پول کم می‌کنه و در صورتِ لزوم به فروشگاه‌دار خبر می‌ده.
    این تابع هیچ‌وقت به مشتری خطا نشون نمی‌ده؛ فقط خودِ فروشگاه‌دار (از طریقِ ربات اصلی) مطلع می‌شه.

    `customer_id` (پ۵۵ · موردِ ۲۳) همان کسر را به کاربری وصل می‌کند که پیام داده است؛ بدونِ آن
    (کامنتِ اینستاگرام، خلاصهٔ CRM، دستیارِ مدیریتی) ردیف بی‌نام می‌ماند و در رتبه‌بندیِ مصرفِ
    کاربران شمرده نمی‌شود — عددِ ساختگی از گذشته ساخته نمی‌شود."""
    success = await wallet_service.deduct(
        session, owner, amount_toman, reason, customer_id=customer_id, ai_total_tokens=ai_total_tokens
    )
    if not success:
        # موجودی در لحظه‌یِ کسر کافی نبوده (مثلاً دقیقاً همین چندِ تومنِ آخر رو یه پیامِ هم‌زمانِ
        # دیگه مصرف کرده). چون جوابِ هوش مصنوعی از قبل تولید و برای مشتری فرستاده شده، این
        # کمبودِ جزئی رو نادیده می‌گیریم و اجازه نمی‌دیم تجربه‌ی مشتری خراب بشه؛ فقط لاگ می‌کنیم.
        logger.warning("کسرِ کیف‌پول برای فروشگاه‌دار %s ناموفق بود (موجودیِ ناکافی در لحظه‌یِ کسر).", owner.id)
        # P33-C: اگر سوییچِ «ادامهٔ سفارش با اعتبارِ صفر» روشن باشد، همین مبلغ به‌عنوانِ
        # بدهیِ مصرفِ AI ثبت می‌شود تا هم ادمین ببیند و هم سقفِ بدهی کلِ درَک را ببیند.
        if admin_settings.orders_allowed_when_wallet_empty:
            reason_value = getattr(reason, "value", reason)
            await ai_debt_service.record(
                session,
                owner_id=owner.id,
                amount_toman=amount_toman,
                reason=str(reason_value),
                note="مصرفِ AI با اعتبارِ صفر (سوییچِ ادامهٔ سفارش روشن)",
            )

    if owner.wallet_balance_toman <= 0:
        if await wallet_service.try_claim_empty_notification(session, owner):
            try:
                await main_bot.send_message(owner.telegram_id, main_texts.wallet_empty_notification())
            except TelegramAPIError:
                logger.exception("اطلاع‌رسانیِ اتمامِ کیف‌پول به فروشگاه‌دار %s ناموفق بود.", owner.telegram_id)
    elif owner.wallet_balance_toman < admin_settings.wallet_low_balance_warning_toman:
        if await wallet_service.try_claim_low_balance_notification(session, owner):
            try:
                await main_bot.send_message(
                    owner.telegram_id, main_texts.wallet_low_balance_notification(owner.wallet_balance_toman)
                )
            except TelegramAPIError:
                logger.exception("اطلاع‌رسانیِ کمبودِ موجودیِ کیف‌پول به فروشگاه‌دار %s ناموفق بود.", owner.telegram_id)
