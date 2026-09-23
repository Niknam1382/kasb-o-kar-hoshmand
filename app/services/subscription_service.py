from __future__ import annotations

import datetime

from dateutil.relativedelta import relativedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import ShopOwner, Subscription, SubscriptionStatus
from app.services.admin_settings_service import get_admin_settings

TRIAL_DURATION_DAYS = 7


async def get_latest_subscription(session: AsyncSession, owner: ShopOwner) -> Subscription | None:
    return await get_latest_subscription_by_owner_id(session, owner.id)


async def get_latest_subscription_by_owner_id(session: AsyncSession, shop_owner_id: int) -> Subscription | None:
    result = await session.execute(
        select(Subscription).where(Subscription.shop_owner_id == shop_owner_id).order_by(Subscription.id.desc()).limit(1)
    )
    return result.scalar_one_or_none()


async def has_ever_had_subscription(session: AsyncSession, owner: ShopOwner) -> bool:
    return await get_latest_subscription(session, owner) is not None


async def activate_trial(session: AsyncSession, owner: ShopOwner) -> Subscription:
    now = datetime.datetime.now(datetime.timezone.utc)
    subscription = Subscription(
        shop_owner_id=owner.id,
        status=SubscriptionStatus.TRIAL,
        duration_months=0,
        is_trial=True,
        start_date=now,
        end_date=now + datetime.timedelta(days=TRIAL_DURATION_DAYS),
    )
    session.add(subscription)
    await session.flush()
    return subscription


async def purchase_or_renew(session: AsyncSession, shop_owner_id: int, duration_months: int) -> Subscription:
    now = datetime.datetime.now(datetime.timezone.utc)
    latest = await get_latest_subscription_by_owner_id(session, shop_owner_id)

    start = latest.end_date if (latest is not None and latest.end_date > now) else now
    end = start + relativedelta(months=duration_months)

    subscription = Subscription(
        shop_owner_id=shop_owner_id,
        status=SubscriptionStatus.ACTIVE,
        duration_months=duration_months,
        is_trial=False,
        start_date=start,
        end_date=end,
    )
    session.add(subscription)
    await session.flush()
    return subscription


async def extend_by_days(session: AsyncSession, shop_owner_id: int, days: int) -> Subscription:
    now = datetime.datetime.now(datetime.timezone.utc)
    latest = await get_latest_subscription_by_owner_id(session, shop_owner_id)

    start = latest.end_date if (latest is not None and latest.end_date > now) else now
    end = start + datetime.timedelta(days=days)

    subscription = Subscription(
        shop_owner_id=shop_owner_id,
        status=SubscriptionStatus.ACTIVE,
        duration_months=0,
        is_trial=False,
        start_date=start,
        end_date=end,
    )
    session.add(subscription)
    await session.flush()
    return subscription


async def is_shop_usable(session: AsyncSession, shop_owner_id: int) -> bool:
    admin_settings = await get_admin_settings(session)
    latest = await get_latest_subscription_by_owner_id(session, shop_owner_id)
    if latest is None:
        return False

    now = datetime.datetime.now(datetime.timezone.utc)
    grace_deadline = latest.end_date + datetime.timedelta(hours=admin_settings.grace_period_hours)
    return now <= grace_deadline
