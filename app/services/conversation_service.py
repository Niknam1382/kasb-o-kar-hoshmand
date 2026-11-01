from __future__ import annotations

import datetime
import logging

from sqlalchemy import delete, func, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import ConversationMessage, Customer

logger = logging.getLogger(__name__)

DEFAULT_HISTORY_LIMIT = 20
CONVERSATION_PAGE_SIZE = 10


async def get_recent_history(session: AsyncSession, customer_id: int, limit: int = DEFAULT_HISTORY_LIMIT) -> list[dict[str, str]]:
    result = await session.execute(
        select(ConversationMessage)
        .where(ConversationMessage.customer_id == customer_id)
        .order_by(ConversationMessage.id.desc())
        .limit(limit)
    )
    messages = list(reversed(result.scalars().all()))
    return [{"role": m.role, "content": m.content} for m in messages]


async def get_history_page(
    session: AsyncSession, customer_id: int, page: int = 0, page_size: int = CONVERSATION_PAGE_SIZE
) -> tuple[list[ConversationMessage], int, int, int]:
    """(پیام‌هایِ صفحه — کهنه‌ترین اول، صفحه‌یِ معتبر، تعدادِ کلِ صفحه‌ها، تعدادِ کلِ پیام‌ها).

    صفحه‌یِ ۰ = تازه‌ترین‌ها. B4: صفحه‌بندی در SQL انجام می‌شود نه با خواندنِ کلِ تاریخچه در پایتون،
    چون گفتگویِ یک مشتریِ پرحرف می‌تواند هزاران ردیف باشد.
    """
    page_size = max(1, int(page_size))
    total = int(
        (
            await session.execute(
                select(func.count()).select_from(ConversationMessage).where(ConversationMessage.customer_id == customer_id)
            )
        ).scalar_one()
    )
    total_pages = max(1, -(-total // page_size))
    page = max(0, min(int(page), total_pages - 1))
    result = await session.execute(
        select(ConversationMessage)
        .where(ConversationMessage.customer_id == customer_id)
        .order_by(ConversationMessage.id.desc())
        .limit(page_size)
        .offset(page * page_size)
    )
    return list(reversed(result.scalars().all())), page, total_pages, total


async def save_turn(session: AsyncSession, customer_id: int, user_message: str, assistant_reply: str) -> None:
    """یک رفت و برگشت در یک گزاره (P21-C · O1): دو INSERT قبلاً دو round-trip ORM بود."""
    await session.execute(
        insert(ConversationMessage),
        [
            {"customer_id": customer_id, "role": "user", "content": user_message},
            {"customer_id": customer_id, "role": "assistant", "content": assistant_reply},
        ],
    )


async def prune_old_messages(session: AsyncSession, retention_days: int, now: datetime.datetime | None = None) -> int:
    """
    پیام‌های مکالمه‌ی قدیمی‌تر از retention_days روز رو پاک می‌کنه. تعدادِ
    ردیفِ حذف‌شده رو برمی‌گردونه (برای لاگ‌کردن).

    retention_days <= 0 یعنی پاکسازی غیرفعاله (هیچی حذف نمی‌شه) — یه راهِ
    ایمن برای ادمین که بخواد این ویژگی رو کلاً خاموش کنه، بدونِ نیاز به یه
    فیلدِ boolean جدا.
    """
    if retention_days <= 0:
        return 0

    now = now or datetime.datetime.now(datetime.timezone.utc)
    cutoff = now - datetime.timedelta(days=retention_days)
    result = await session.execute(delete(ConversationMessage).where(ConversationMessage.created_at < cutoff))
    deleted_count = result.rowcount or 0
    if deleted_count:
        logger.info("پاکسازیِ خودکارِ مکالمات: %d پیامِ قدیمی‌تر از %d روز حذف شد.", deleted_count, retention_days)
    return deleted_count


async def prune_old_messages_for_shops(
    session: AsyncSession, retention_by_shop: dict[int, int], default_days: int, now: datetime.datetime | None = None
) -> int:
    """A5: نگهداریِ مکالمه per-shop شد.

    `ConversationMessage` ستونِ shop_bot_id ندارد، پس هر DELETE با زیرکوئری رویِ `customers` به
    فروشگاه‌هایِ همان گروه محدود می‌شود. فروشگاه‌ها بر اساسِ مقدارِ روز دسته‌بندی می‌شوند تا به‌ازایِ
    هر مقدارِ *متمایز* فقط یک DELETE اجرا شود. اگر هیچ تفاوتی با پیش‌فرض نباشد، همان مسیرِ سراسریِ
    ساده (بدونِ join) اجرا می‌شود. روزِ ≤ ۰ یعنی پاکسازیِ آن فروشگاه خاموش است.
    """
    now = now or datetime.datetime.now(datetime.timezone.utc)
    if not retention_by_shop or set(retention_by_shop.values()) == {default_days}:
        return await prune_old_messages(session, default_days, now=now)

    groups: dict[int, list[int]] = {}
    for shop_bot_id, days in retention_by_shop.items():
        groups.setdefault(int(days), []).append(int(shop_bot_id))

    deleted_total = 0
    for days, shop_ids in groups.items():
        if days <= 0 or not shop_ids:
            continue
        cutoff = now - datetime.timedelta(days=days)
        result = await session.execute(
            delete(ConversationMessage).where(
                ConversationMessage.created_at < cutoff,
                ConversationMessage.customer_id.in_(select(Customer.id).where(Customer.shop_bot_id.in_(shop_ids))),
            )
        )
        deleted_total += result.rowcount or 0
    if deleted_total:
        logger.info("پاکسازیِ خودکارِ مکالمات (per-shop): %d پیام حذف شد.", deleted_total)
    return deleted_total
