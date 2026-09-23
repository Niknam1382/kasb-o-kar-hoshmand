from __future__ import annotations

import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import DiscountCode, DiscountCodeUsage, DiscountType


async def get_by_code(session: AsyncSession, code: str) -> DiscountCode | None:
    result = await session.execute(select(DiscountCode).where(DiscountCode.code == code.strip().upper()))
    return result.scalar_one_or_none()


async def get_all_codes(session: AsyncSession) -> list[DiscountCode]:
    result = await session.execute(select(DiscountCode).order_by(DiscountCode.id.desc()))
    return list(result.scalars().all())


async def validate_code(session: AsyncSession, raw_code: str, shop_owner_id: int) -> DiscountCode | None:
    discount = await get_by_code(session, raw_code)
    if discount is None or not discount.is_active:
        return None

    now = datetime.datetime.now(datetime.timezone.utc)
    if discount.expires_at is not None and discount.expires_at < now:
        return None
    if discount.max_uses is not None and discount.used_count >= discount.max_uses:
        return None

    # هر فروشگاه‌دار فقط یک‌بار می‌تونه از یک کدِ تخفیفِ مشخص استفاده کنه (مهم
    # برای کدهای تخفیفِ شخصی‌سازی‌شده‌ی معرفی که یکبار‌مصرف هستن).
    usage_result = await session.execute(
        select(DiscountCodeUsage).where(
            DiscountCodeUsage.discount_code_id == discount.id, DiscountCodeUsage.shop_owner_id == shop_owner_id
        )
    )
    if usage_result.scalar_one_or_none() is not None:
        return None

    return discount


def apply_discount(base_amount: int, discount: DiscountCode) -> int:
    if discount.type == DiscountType.PERCENT:
        final_price = base_amount - int(base_amount * float(discount.value) / 100)
    else:
        final_price = base_amount - int(discount.value)
    return max(final_price, 0)


async def create_code(
    session: AsyncSession, code: str, discount_type: DiscountType, value: Decimal, max_uses: int | None, expires_at: datetime.datetime | None
) -> DiscountCode:
    discount = DiscountCode(code=code.strip().upper(), type=discount_type, value=value, max_uses=max_uses, expires_at=expires_at)
    session.add(discount)
    await session.flush()
    return discount


async def toggle_code_active(session: AsyncSession, code_id: int) -> DiscountCode | None:
    discount = await session.get(DiscountCode, code_id)
    if discount is not None:
        discount.is_active = not discount.is_active
        await session.flush()
    return discount


async def record_usage(session: AsyncSession, discount_code_id: int, shop_owner_id: int, payment_id: int) -> None:
    session.add(DiscountCodeUsage(discount_code_id=discount_code_id, shop_owner_id=shop_owner_id, payment_id=payment_id))

    discount = await session.get(DiscountCode, discount_code_id)
    if discount is not None:
        discount.used_count += 1

    await session.flush()
