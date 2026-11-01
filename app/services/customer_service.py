from __future__ import annotations

import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Customer
from app.services import platform_service


async def get_by_id(session: AsyncSession, customer_id: int) -> Customer | None:
    return await session.get(Customer, customer_id)


async def get_by_shop_bot_and_telegram_id(
    session: AsyncSession, shop_bot_id: int, telegram_id: int, *, platform: str = platform_service.TELEGRAM
) -> Customer | None:
    result = await session.execute(
        select(Customer).where(
            Customer.shop_bot_id == shop_bot_id, Customer.telegram_id == telegram_id, Customer.platform == platform
        )
    )
    return result.scalar_one_or_none()


async def get_by_shop_bot(session: AsyncSession, shop_bot_id: int) -> list[Customer]:
    """همه‌ی مشتری‌هایِ یه فروشگاهِ مشخص — برایِ پیامِ همگانیِ فروشگاه‌دار به
    مشتری‌هاش (panel.py). فقط telegram_id لازمه برای ارسال، ولی کلِ ردیف
    برمی‌گردونه چون شمارشِ preview هم از همین لیست محاسبه می‌شه."""
    result = await session.execute(select(Customer).where(Customer.shop_bot_id == shop_bot_id))
    return list(result.scalars().all())


async def recipients_by_shop_bot(session: AsyncSession, shop_bot_id: int) -> list[tuple[int, str]]:
    """زوج‌های (شناسه‌یِ کاربر، پلتفرم) برایِ ارسالِ پیام. پلتفرم همیشه همراه است چون
    عددِ یکسان در تلگرام و بله می‌تواند دو آدمِ کاملاً متفاوت باشد."""
    result = await session.execute(
        select(Customer.telegram_id, Customer.platform).where(Customer.shop_bot_id == shop_bot_id)
    )
    return [(int(chat_id), platform or platform_service.TELEGRAM) for chat_id, platform in result.all()]


async def recipients_by_ids(session: AsyncSession, shop_bot_id: int, customer_ids: list[int]) -> list[tuple[int, str]]:
    """همان لیست، فقط برایِ یه بخشِ انتخاب‌شده (CRM). شناسه‌یِ *ردیف* مشتری، نه شناسه‌یِ پیام‌رسان."""
    if not customer_ids:
        return []
    result = await session.execute(
        select(Customer.telegram_id, Customer.platform).where(
            Customer.shop_bot_id == shop_bot_id, Customer.id.in_(list(customer_ids))
        )
    )
    return [(int(chat_id), platform or platform_service.TELEGRAM) for chat_id, platform in result.all()]


async def count_by_shop_bot(session: AsyncSession, shop_bot_id: int) -> int:
    result = await session.execute(select(func.count()).select_from(Customer).where(Customer.shop_bot_id == shop_bot_id))
    return result.scalar_one()


async def list_recent_paged(
    session: AsyncSession, shop_bot_id: int, page: int = 0, page_size: int = 10
) -> tuple[list[Customer], int, int, int]:
    """C2 (پنلِ مشاوره‌ای): فهرستِ مخاطبان، تازه‌ترین فعالیت اول. صفحه‌بندی در SQL.

    (مخاطب، صفحه، تعدادِ کلِ صفحه‌ها، تعدادِ کلِ مخاطبان). NULLهایِ `last_message_at` آخر می‌نشینند.
    """
    page_size = max(1, int(page_size))
    total = int(
        await session.scalar(select(func.count()).select_from(Customer).where(Customer.shop_bot_id == shop_bot_id)) or 0
    )
    total_pages = max(1, -(-total // page_size))
    page = max(0, min(int(page), total_pages - 1))
    result = await session.execute(
        select(Customer)
        .where(Customer.shop_bot_id == shop_bot_id)
        .order_by(Customer.last_message_at.desc().nullslast(), Customer.id.desc())
        .limit(page_size)
        .offset(page * page_size)
    )
    return list(result.scalars().all()), page, total_pages, total


async def get_or_create_customer(
    session: AsyncSession, shop_bot_id: int, telegram_id: int, first_name: str | None, username: str | None,
    last_name: str | None = None, *, platform: str = platform_service.TELEGRAM,
) -> Customer:
    result = await session.execute(
        select(Customer).where(
            Customer.shop_bot_id == shop_bot_id, Customer.telegram_id == telegram_id, Customer.platform == platform
        )
    )
    customer = result.scalar_one_or_none()
    now = datetime.datetime.now(datetime.timezone.utc)
    if customer is None:
        customer = Customer(
            shop_bot_id=shop_bot_id, telegram_id=telegram_id, platform=platform, first_name=first_name,
            username=username, last_name=last_name, last_message_at=now,
        )
        session.add(customer)
    else:
        # عمداً فقط وقتی مقدارِ جدید واقعاً داریم آپدیت می‌کنیم؛ صدا زدنِ این تابع با
        # first_name/username=None (مثلاً از یه تسکِ پس‌زمینه که فقط telegram_id رو
        # داره) نباید اطلاعاتِ قبلاً ذخیره‌شده رو پاک کنه.
        if first_name is not None:
            customer.first_name = first_name
        if username is not None:
            customer.username = username
        if last_name is not None:
            customer.last_name = last_name
        customer.last_message_at = now
    await session.flush()
    return customer
