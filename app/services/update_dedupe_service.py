"""P45 · ظرفیت: «این آپدیت را قبلاً دیده‌ایم؟» — بینِ پروسه‌ها، بدونِ سرویسِ تازه.

در حالتِ webhook تلگرام همان `update_id` را دوباره می‌فرستد اگر پاسخِ HTTP دیر برسد، و آن دوباره
ممکن است به پروسهٔ دیگری برسد. محافظِ درِحافظهٔ `app.main._seen_update_ids` فقط برایِ یکِ پروسه
کار می‌کند؛ اینجا همان سؤال با یکِ `INSERT … ON CONFLICT DO NOTHING` رویِ دیتابیس پاسخ داده
می‌شود — اتمیک، بدونِ Redis، و فقط در حالتِ webhook (مسیرِ polling همان offset و قفلِ شارد را دارد
و هیچ statement اضافه‌ای به آن افزوده نشده: سقفِ ۱۲ جمله به‌ازایِ هر پیامِ مشتری دست‌نخورده است).

سطرِ قدیمی در جابِ `prune` پاک می‌شود؛ پنجره‌یِ ۳۰ دقیقه از طولِ عمرِ «دوباره‌دریافتِ» تلگرام
بیشتر است و جدول را کوچک نگه می‌دارد.
"""

from __future__ import annotations

import datetime
import logging

from sqlalchemy import delete, text

logger = logging.getLogger(__name__)

RETENTION_MINUTES = 30


async def claim(bot_id: int, update_id: int) -> bool:
    """True ⇒ تو اولین پروسه‌ای که این آپدیت را دیدی (مالکِ پردازش). False ⇒ تکراری است."""
    from app.database.session import session_scope

    async with session_scope() as session:
        result = await session.execute(
            text("INSERT INTO update_dedupe (bot_id, update_id, seen_at) VALUES (:b, :u, now()) ON CONFLICT DO NOTHING"),
            {"b": int(bot_id), "u": int(update_id)},
        )
        return int(getattr(result, "rowcount", 0) or 0) > 0


async def prune(session, *, now: datetime.datetime | None = None) -> int:
    from app.database.models import UpdateDedupe

    moment = now or datetime.datetime.now(datetime.timezone.utc)
    cutoff = moment - datetime.timedelta(minutes=RETENTION_MINUTES)
    result = await session.execute(delete(UpdateDedupe).where(UpdateDedupe.seen_at < cutoff))
    return int(result.rowcount or 0)
