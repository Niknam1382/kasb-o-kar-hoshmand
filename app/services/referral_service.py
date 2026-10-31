from __future__ import annotations

import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Referral, WalletTransactionReason
from app.services import shop_owner_service, wallet_service
from app.services.admin_settings_service import get_admin_settings

REWARD_STATUS_PENDING = "pending"
REWARD_STATUS_REWARDED = "rewarded"


async def get_referral_stats(session: AsyncSession, owner_id: int) -> dict:
    result = await session.execute(select(Referral).where(Referral.referrer_id == owner_id))
    referrals = list(result.scalars().all())
    return {
        "total": len(referrals),
        "rewarded": sum(1 for r in referrals if r.reward_status == REWARD_STATUS_REWARDED),
    }


async def process_referral_reward(session: AsyncSession, referred_owner_id: int, payment_amount_toman: int) -> dict | None:
    """
    با اولین پرداختِ تاییدشده‌ی فردِ معرفی‌شده، فقط به معرف (نه هر دو طرف —
    طبقِ تصمیمِ محصول، برای جلوگیری از سوءاستفاده با حساب‌های فیک) درصدی از
    همون مبلغِ پرداختی به‌عنوانِ پورسانت اعتبار داده می‌شه. قبلاً یه پاداشِ
    *ثابت* و متقابل بود (به هر دو طرف)، که چون به مبلغِ واقعیِ پرداخت وابسته
    نبود، با ساختِ چند حسابِ فیک و تاپ‌آپِ خیلی کم، قابلِ‌سوءاستفاده بود؛
    پورسانتِ درصدی این مشکل رو نداره چون بدونِ پرداختِ واقعی، ارزشی نداره.
    """
    result = await session.execute(
        select(Referral).where(Referral.referred_id == referred_owner_id, Referral.reward_status == REWARD_STATUS_PENDING)
    )
    referral = result.scalar_one_or_none()
    if referral is None:
        return None

    admin_settings = await get_admin_settings(session)
    percent = admin_settings.referral_reward_value
    amount = int((payment_amount_toman * percent / 100).to_integral_value())
    if amount <= 0:
        # ادمین می‌تونه با صفر گذاشتنِ درصد، پاداشِ معرفی رو موقتاً غیرفعال کنه.
        return None

    referrer = await shop_owner_service.get_by_id(session, referral.referrer_id)

    await wallet_service.add_charge(session, referrer, amount, reason=WalletTransactionReason.REFERRAL_REWARD)

    referral.reward_status = REWARD_STATUS_REWARDED
    referral.rewarded_at = datetime.datetime.now(datetime.timezone.utc)
    await session.flush()

    return {
        "referrer_telegram_id": referrer.telegram_id,
        "amount_toman": amount,
        "percent": str(percent),
    }
