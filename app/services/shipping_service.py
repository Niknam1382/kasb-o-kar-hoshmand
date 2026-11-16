"""روش‌هایِ ارسالِ فروشگاه (فازِ ۱ · P1-S3 / B2). در W1 فقط تعریف/فهرست/نمایش؛
اعمالِ هزینه در چک‌اوت (انتخابِ روش + جمعِ کل + فاکتور) با W2/C3 است."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import ShippingMethod

MAX_METHODS_PER_SHOP = 10
MAX_NAME_LEN = 64
MAX_ETA_LEN = 128


async def list_methods(session: AsyncSession, shop_bot_id: int, only_active: bool = False) -> list[ShippingMethod]:
    query = select(ShippingMethod).where(ShippingMethod.shop_bot_id == shop_bot_id)
    if only_active:
        query = query.where(ShippingMethod.is_active.is_(True))
    result = await session.execute(query.order_by(ShippingMethod.id))
    return list(result.scalars().all())


async def get_owned(session: AsyncSession, method_id: int, shop_bot_id: int) -> ShippingMethod | None:
    result = await session.execute(select(ShippingMethod).where(ShippingMethod.id == method_id, ShippingMethod.shop_bot_id == shop_bot_id))
    return result.scalar_one_or_none()


async def create_method(
    session: AsyncSession,
    shop_bot_id: int,
    name: str,
    fee_toman: int,
    free_over_toman: int | None = None,
    eta_text: str | None = None,
) -> ShippingMethod | None:
    """None وقتی سقفِ تعدادِ روش‌ها پر باشه یا نام/هزینه نامعتبر باشه."""
    name = (name or "").strip()
    if not name or len(name) > MAX_NAME_LEN or fee_toman < 0 or (free_over_toman is not None and free_over_toman < 0):
        return None
    existing = await list_methods(session, shop_bot_id)
    if len(existing) >= MAX_METHODS_PER_SHOP:
        return None
    method = ShippingMethod(
        shop_bot_id=shop_bot_id,
        name=name,
        fee_toman=fee_toman,
        free_over_toman=free_over_toman,
        eta_text=(eta_text or "").strip()[:MAX_ETA_LEN] or None,
        is_active=True,
    )
    session.add(method)
    await session.flush()
    return method


async def toggle_active(session: AsyncSession, method: ShippingMethod) -> bool:
    method.is_active = not method.is_active
    await session.flush()
    return method.is_active


async def delete_method(session: AsyncSession, method: ShippingMethod) -> None:
    await session.delete(method)
    await session.flush()


def fee_for_subtotal(method: ShippingMethod, subtotal_toman: int) -> int:
    """هزینه‌یِ ارسال برایِ جمعِ کالایِ *فیزیکی*؛ بالاتر از آستانه‌یِ رایگان = ۰."""
    if method.free_over_toman is not None and subtotal_toman >= method.free_over_toman:
        return 0
    return max(0, method.fee_toman)


