from __future__ import annotations

import datetime
import logging

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import ConversationMessage

logger = logging.getLogger(__name__)

DEFAULT_HISTORY_LIMIT = 20


async def get_recent_history(session: AsyncSession, customer_id: int, limit: int = DEFAULT_HISTORY_LIMIT) -> list[dict[str, str]]:
    result = await session.execute(
        select(ConversationMessage)
        .where(ConversationMessage.customer_id == customer_id)
        .order_by(ConversationMessage.id.desc())
        .limit(limit)
    )
    messages = list(reversed(result.scalars().all()))
    return [{"role": m.role, "content": m.content} for m in messages]


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
