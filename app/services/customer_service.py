from __future__ import annotations

import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Customer


async def get_by_id(session: AsyncSession, customer_id: int) -> Customer | None:
    return await session.get(Customer, customer_id)


async def get_by_shop_bot_and_telegram_id(session: AsyncSession, shop_bot_id: int, telegram_id: int) -> Customer | None:
    result = await session.execute(select(Customer).where(Customer.shop_bot_id == shop_bot_id, Customer.telegram_id == telegram_id))
    return result.scalar_one_or_none()


async def get_or_create_customer(
    session: AsyncSession, shop_bot_id: int, telegram_id: int, first_name: str | None, username: str | None
) -> Customer:
    result = await session.execute(
        select(Customer).where(Customer.shop_bot_id == shop_bot_id, Customer.telegram_id == telegram_id)
    )
    customer = result.scalar_one_or_none()
    now = datetime.datetime.now(datetime.timezone.utc)
    if customer is None:
        customer = Customer(shop_bot_id=shop_bot_id, telegram_id=telegram_id, first_name=first_name, username=username, last_message_at=now)
        session.add(customer)
    else:
        # عمداً فقط وقتی مقدارِ جدید واقعاً داریم آپدیت می‌کنیم؛ صدا زدنِ این تابع با
        # first_name/username=None (مثلاً از یه تسکِ پس‌زمینه که فقط telegram_id رو
        # داره) نباید اطلاعاتِ قبلاً ذخیره‌شده رو پاک کنه.
        if first_name is not None:
            customer.first_name = first_name
        if username is not None:
            customer.username = username
        customer.last_message_at = now
    await session.flush()
    return customer
