from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import SubscriptionPlan


async def get_all_plans(session: AsyncSession, active_only: bool = False) -> list[SubscriptionPlan]:
    stmt = select(SubscriptionPlan).order_by(SubscriptionPlan.duration_months)
    if active_only:
        stmt = stmt.where(SubscriptionPlan.is_active.is_(True))
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_by_id(session: AsyncSession, plan_id: int) -> SubscriptionPlan | None:
    return await session.get(SubscriptionPlan, plan_id)


async def get_by_duration(session: AsyncSession, duration_months: int) -> SubscriptionPlan | None:
    result = await session.execute(select(SubscriptionPlan).where(SubscriptionPlan.duration_months == duration_months))
    return result.scalar_one_or_none()


async def create_plan(session: AsyncSession, duration_months: int, price_toman: int) -> SubscriptionPlan:
    plan = SubscriptionPlan(duration_months=duration_months, price_toman=price_toman)
    session.add(plan)
    await session.flush()
    return plan


async def update_price(session: AsyncSession, plan: SubscriptionPlan, new_price_toman: int) -> None:
    plan.price_toman = new_price_toman
    await session.flush()


async def toggle_plan_active(session: AsyncSession, plan_id: int) -> SubscriptionPlan | None:
    plan = await session.get(SubscriptionPlan, plan_id)
    if plan is not None:
        plan.is_active = not plan.is_active
        await session.flush()
    return plan
