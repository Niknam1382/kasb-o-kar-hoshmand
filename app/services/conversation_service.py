from __future__ import annotations

import datetime
import logging

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import ConversationMessage

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
    session.add(ConversationMessage(customer_id=customer_id, role="user", content=user_message))
    session.add(ConversationMessage(customer_id=customer_id, role="assistant", content=assistant_reply))
    await session.flush()


async def prune_old_messages(session: AsyncSession, retention_days: int) -> int:
    """
    پیام‌های مکالمه‌ی قدیمی‌تر از retention_days روز رو پاک می‌کنه. تعدادِ
    ردیفِ حذف‌شده رو برمی‌گردونه (برای لاگ‌کردن).

    retention_days <= 0 یعنی پاکسازی غیرفعاله (هیچی حذف نمی‌شه) — یه راهِ
    ایمن برای ادمین که بخواد این ویژگی رو کلاً خاموش کنه، بدونِ نیاز به یه
    فیلدِ boolean جدا.
    """
    if retention_days <= 0:
        return 0

    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=retention_days)
    result = await session.execute(delete(ConversationMessage).where(ConversationMessage.created_at < cutoff))
    deleted_count = result.rowcount or 0
    if deleted_count:
        logger.info("پاکسازیِ خودکارِ مکالمات: %d پیامِ قدیمی‌تر از %d روز حذف شد.", deleted_count, retention_days)
    return deleted_count
