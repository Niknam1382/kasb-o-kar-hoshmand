"""فعالیتِ فروشگاه‌دار: آخرینِ دیدار، دستهٔ «غیرفعال» و حذفِ حساب (P22 · مشکلِ ۸).

سه چیز را این ماژول نگه می‌دارد تا پنلِ ادمین «حَدس» نزند:

- `touch()` رویِ هر پیام/دکمه صدا زده می‌شود، ولی با **شرطِ زمانی در خودِ SQL** ⇒ حداکثر یکِ
  UPDATE به‌ازایِ هر ۱۰ دقیقه برایِ هر فروشگاه‌دار. بدونِ این شرط، جدولِ `shop_owners`
  (که در مسیرِ داغِ هر آپدیتِ رباتِ اصلی خوانده می‌شود) هر کلیک را قفل می‌کرد.
- `last_seen_at = NULL` یعنی «هیچ سوابقی ثبت نشده»، نه «یک سال است نیامده». دسته‌بندیِ
  غیرفعال آن‌ها را *آخر* فهرست می‌کند و برچسبِ «بدونِ سابقه» می‌گیرد؛ حذفِ حساب بر پایهٔ
  نبودِ داده ساخته نمی‌شود (قاعدهٔ پروژه: عددِ تخمینی را حکم نکن).
- حذف = دو حالته. `soft_delete` پیش‌فرض است و همه‌چیز را نگه می‌دارد؛ `shop_purge_service.purge_owner`
  محتوا را می‌بُرد و پوسته را فقط وقتی می‌اندازد که هیچ ردیفِ ممیزی/ارجاعِ واقعی به آن بند نباشد.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import ShopBot, ShopOwner

TOUCH_THROTTLE = datetime.timedelta(minutes=10)
# پنجره‌هایِ «غیرفعال» — تعدادِ روز؛ ۳۰ ≈ «یک ماه» که کاربر گفته بود.
INACTIVE_WINDOWS = (7, 30, 90)
DEFAULT_WINDOW = 30
LIST_LIMIT = 40

NO_HISTORY_LABEL = "بدونِ سابقه"


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


async def touch(session: AsyncSession, owner: ShopOwner, *, now: datetime.datetime | None = None) -> bool:
    """`last_seen_at` را نو می‌کند، ولی فقط اگر از میانه‌بند گذشته باشد. True ⇒ واقعاً نوشت."""
    moment = now or _utcnow()
    result = await session.execute(
        update(ShopOwner)
        .where(
            ShopOwner.id == owner.id,
            or_(ShopOwner.last_seen_at.is_(None), ShopOwner.last_seen_at < moment - TOUCH_THROTTLE),
        )
        .values(last_seen_at=moment)
    )
    return int(result.rowcount or 0) > 0


def inactive_cutoff(days: int, *, now: datetime.datetime | None = None) -> datetime.datetime:
    return (now or _utcnow()) - datetime.timedelta(days=days)


@dataclass(slots=True)
class InactiveOwner:
    owner: ShopOwner
    bot_username: str | None
    since_days: int | None  # None ⇒ بدونِ سابقه

    @property
    def never_seen(self) -> bool:
        return self.since_days is None


async def list_inactive(
    session: AsyncSession,
    days: int,
    *,
    allowed_owner_ids: list[int] | None = None,
    limit: int = LIST_LIMIT,
    now: datetime.datetime | None = None,
) -> list[InactiveOwner]:
    """فروشگاه‌دارهایی که `days` روز است هیچ تعاملی نداشته‌اند (حذف‌شده‌ها بیرون).

    `allowed_owner_ids` همان قراردادِ `admin_role_service`: None ⇒ همه، [] ⇒ هیچ، فهرست ⇒ دامنه."""
    if allowed_owner_ids is not None and not allowed_owner_ids:
        return []
    cutoff = inactive_cutoff(days, now=now)
    query = (
        select(ShopOwner, ShopBot.bot_username)
        .outerjoin(ShopBot, ShopBot.shop_owner_id == ShopOwner.id)
        .where(ShopOwner.is_deleted.is_(False))
        .where(or_(ShopOwner.last_seen_at.is_(None), ShopOwner.last_seen_at < cutoff))
        .order_by(ShopOwner.last_seen_at.asc().nulls_first(), ShopOwner.id.asc())
        .limit(limit)
    )
    if allowed_owner_ids is not None:
        query = query.where(ShopOwner.id.in_(allowed_owner_ids))
    reference = now or _utcnow()
    rows = (await session.execute(query)).all()
    out: list[InactiveOwner] = []
    for owner, bot_username in rows:
        since = None if owner.last_seen_at is None else max(0, int((reference - owner.last_seen_at).total_seconds() // 86_400))
        out.append(InactiveOwner(owner=owner, bot_username=bot_username, since_days=since))
    return out


async def count_inactive(
    session: AsyncSession, days: int, *, allowed_owner_ids: list[int] | None = None, now: datetime.datetime | None = None
) -> int:
    """شمارشِ کاملِ دسته (بدونِ سقفِ فهرست) تا ادمین بداند صفحه‌یِ ۴۰تایی همه‌چیز نیست."""
    if allowed_owner_ids is not None and not allowed_owner_ids:
        return 0
    cutoff = inactive_cutoff(days, now=now)
    query = (
        select(ShopOwner.id)
        .where(ShopOwner.is_deleted.is_(False))
        .where(or_(ShopOwner.last_seen_at.is_(None), ShopOwner.last_seen_at < cutoff))
    )
    if allowed_owner_ids is not None:
        query = query.where(ShopOwner.id.in_(allowed_owner_ids))
    return len((await session.execute(query)).all())


async def count_active(session: AsyncSession, *, allowed_owner_ids: list[int] | None = None) -> int:
    if allowed_owner_ids is not None and not allowed_owner_ids:
        return 0
    query = select(ShopOwner.id).where(ShopOwner.is_deleted.is_(False))
    if allowed_owner_ids is not None:
        query = query.where(ShopOwner.id.in_(allowed_owner_ids))
    return len((await session.execute(query)).all())


async def get(session: AsyncSession, owner_id: int, *, include_deleted: bool = False) -> ShopOwner | None:
    owner = await session.get(ShopOwner, owner_id)
    if owner is None or (owner.is_deleted and not include_deleted):
        return None
    return owner


async def soft_delete(session: AsyncSession, owner: ShopOwner, *, now: datetime.datetime | None = None) -> None:
    """حذفِ نرم: از پنل، آمار و ورودِ کاربر بیرون ⇒ ولی ردیف، پول و ممیزی می‌مانند."""
    owner.is_deleted = True
    owner.deleted_at = now or _utcnow()
    await session.flush()


async def restore(session: AsyncSession, owner: ShopOwner) -> None:
    owner.is_deleted = False
    owner.deleted_at = None
    # «بدونِ سابقه» نشود: بازگشتِ حساب باید از لحظهٔ برگشت «فعال» شمرده شود.
    owner.last_seen_at = _utcnow()
    await session.flush()


def in_scope(owner_id: int, allowed_owner_ids: list[int] | None) -> bool:
    """دامنهٔ ادمینِ عملیاتی رویِ یکِ حسابِ مشخص (None ⇒ همه)."""
    return allowed_owner_ids is None or owner_id in allowed_owner_ids
