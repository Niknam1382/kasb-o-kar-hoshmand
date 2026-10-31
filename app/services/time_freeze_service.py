"""«توقفِ زمان» (W5 · K3). شروع: فقط یک ردیفِ active ثبت می‌شه (بدونِ تغییرِ تاریخ). ازسرگیری (دستی یا خودکار پس از
`max_days`): در *یک تراکنش* همه‌یِ انقضاهایِ مشمول به‌اندازه‌یِ Δ = زمانِ سپری‌شده جلو می‌رن؛ ایدمپوتنت (قفلِ ردیف + وضعیت).
جاب‌هایِ انقضا/یادآوری/مهلت برایِ مشمولینِ توقف رد می‌شن (`frozen_filter`)."""

from __future__ import annotations

import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import ShopOwner, Subscription, SubscriptionStatus, TimeFreeze, WalletCharge

MIN_DAYS = 1
MAX_DAYS = 30


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


async def active_freezes(session: AsyncSession) -> list[TimeFreeze]:
    result = await session.execute(select(TimeFreeze).where(TimeFreeze.status == "active").order_by(TimeFreeze.id))
    return list(result.scalars().all())


def covers(freezes: list[TimeFreeze], owner_id: int) -> bool:
    return any(f.scope == "all" or f.shop_owner_id == owner_id for f in freezes)


async def frozen_filter(session: AsyncSession) -> tuple[bool, set[int]]:
    """(همه فریزن؟, شناسه‌یِ فروشگاه‌دارهایِ فریزِ تکی). جاب‌ها قبل از اثر می‌پرسن."""
    freezes = await active_freezes(session)
    if any(f.scope == "all" for f in freezes):
        return True, set()
    return False, {f.shop_owner_id for f in freezes if f.shop_owner_id is not None}


async def start(
    session: AsyncSession, *, scope: str, owner_id: int | None, max_days: int, reason: str | None, by: str
) -> TimeFreeze | None:
    """None وقتی ورودی نامعتبر است یا همین دامنه از قبل فریز است (دابل‌تپِ «شروع» = یک ردیف)."""
    if scope not in ("all", "owner") or not (MIN_DAYS <= max_days <= MAX_DAYS):
        return None
    if scope == "owner":
        if owner_id is None or await session.get(ShopOwner, owner_id) is None:
            return None
    else:
        owner_id = None
    current = await active_freezes(session)
    if any(f.scope == "all" for f in current) or (scope == "all" and current) or (scope == "owner" and covers(current, owner_id)):
        return None
    now = _now()
    freeze = TimeFreeze(
        scope=scope,
        shop_owner_id=owner_id,
        status="active",
        started_at=now,
        ends_at=now + datetime.timedelta(days=max_days),
        max_days=max_days,
        reason=(reason or None) and reason[:500],
        started_by=by[:64],
    )
    session.add(freeze)
    await session.flush()
    return freeze


async def _owner_ids_in_scope(session: AsyncSession, freeze: TimeFreeze) -> list[int]:
    if freeze.scope == "owner":
        return [freeze.shop_owner_id] if freeze.shop_owner_id is not None else []
    return list((await session.execute(select(ShopOwner.id))).scalars().all())


async def resume(session: AsyncSession, freeze_id: int, *, by: str, now: datetime.datetime | None = None) -> tuple[TimeFreeze | None, bool]:
    """(ردیف, تغییر کرد؟). فراخوانِ دوم/هم‌زمان ⇒ changed=False و هیچ جابه‌جاییِ دوباره‌ای نیست."""
    now = now or _now()
    result = await session.execute(
        select(TimeFreeze).where(TimeFreeze.id == freeze_id).with_for_update().execution_options(populate_existing=True)
    )
    freeze = result.scalar_one_or_none()
    if freeze is None:
        return None, False
    if freeze.status != "active":
        return freeze, False

    effective_now = min(now, freeze.ends_at)  # حداکثر تا سقفِ خودش جلو می‌بریم (جابِ دیرکرده، مشتری رو بیش‌ازحد جبران نمی‌کنه)
    delta = max(datetime.timedelta(0), effective_now - freeze.started_at)
    affected = 0
    owner_ids = await _owner_ids_in_scope(session, freeze)
    if owner_ids and delta > datetime.timedelta(0):
        charges = (
            await session.execute(
                select(WalletCharge).where(
                    WalletCharge.shop_owner_id.in_(owner_ids), WalletCharge.is_expired.is_(False), WalletCharge.remaining_toman > 0
                )
            )
        ).scalars().all()
        for charge in charges:
            charge.expires_at = charge.expires_at + delta
            affected += 1
        latest = select(Subscription.shop_owner_id, func.max(Subscription.id).label("max_id")).where(
            Subscription.shop_owner_id.in_(owner_ids)
        ).group_by(Subscription.shop_owner_id).subquery()
        subs = (await session.execute(select(Subscription).join(latest, Subscription.id == latest.c.max_id))).scalars().all()
        for sub in subs:
            if sub.status in (SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIAL, SubscriptionStatus.GRACE):
                sub.end_date = sub.end_date + delta
                affected += 1
    freeze.status = "resumed"
    freeze.resumed_at = now
    freeze.resumed_by = by[:64]
    freeze.shifted_seconds = int(delta.total_seconds())
    freeze.affected_count = affected
    await session.flush()
    return freeze, True


async def auto_resume_due(session: AsyncSession, now: datetime.datetime | None = None) -> list[TimeFreeze]:
    """جابِ ازسرگیریِ خودکار پس از `max_days`. برمی‌گردونه فریزهایی که همین الان ازسرگرفته شدن."""
    now = now or _now()
    due_ids = list(
        (await session.execute(select(TimeFreeze.id).where(TimeFreeze.status == "active", TimeFreeze.ends_at <= now))).scalars().all()
    )
    resumed: list[TimeFreeze] = []
    for freeze_id in due_ids:
        freeze, changed = await resume(session, freeze_id, by="system", now=now)
        if changed and freeze is not None:
            resumed.append(freeze)
    return resumed
