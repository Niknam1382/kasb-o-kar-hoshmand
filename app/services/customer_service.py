from __future__ import annotations

import datetime

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
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
    """یک گزاره‌ای: INSERT … ON CONFLICT DO UPDATE (P21-C · O1).

    نسخهٔ قبلی «اول SELECT، بعد شاید INSERT» بود — یعنی برایِ هر پیامِ مشتریِ بازگشتی
    (که غالبِ ترافیک است) یک رفت‌وبرگشتِ اضافه. معنایِ دقیقاً همان حفظ شده:
    `COALESCE(مقدارِ تازه، مقدارِ قبلی)` یعنی فقط وقتی واقعاً چیزی داریم عوضش کن، پس
    صدا زدنِ این تابع با `first_name=None` از یک تسکِ پس‌زمینه هیچ اطلاعاتِ قبلی را پاک
    نمی‌کند، و `last_message_at` همیشه تازه می‌شود.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    stmt = insert(Customer).values(
        shop_bot_id=shop_bot_id,
        telegram_id=telegram_id,
        platform=platform,
        first_name=first_name,
        username=username,
        last_name=last_name,
        last_message_at=now,
    )
    upsert = stmt.on_conflict_do_update(
        constraint="uq_customers_shop_bot_id_platform",
        set_={
            "first_name": func.coalesce(stmt.excluded.first_name, Customer.first_name),
            "username": func.coalesce(stmt.excluded.username, Customer.username),
            "last_name": func.coalesce(stmt.excluded.last_name, Customer.last_name),
            "last_message_at": now,
        },
    )
    customer_id = (await session.execute(upsert.returning(Customer.id))).scalar_one()
    # populate_existing: اگر همین session قبلاً ردیف را خوانده، نسخهٔ کهنهٔ حافظه برگردد نه نو
    return await session.get(Customer, customer_id, populate_existing=True)
