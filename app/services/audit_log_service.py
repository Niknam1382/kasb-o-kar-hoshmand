"""گزارشِ ممیزی با زنجیرهٔ هش (P20).

هر ردیفِ تازه، هشِ ردیفِ قبل از خود (`prev_hash`) و هشِ خود (`row_hash`) را نگه می‌دارد:

    row_hash = sha256(prev_hash + شناسه + زمان + نوع + فروشگاه + عامل + جزئیات)

پس حذف یا تغییرِ داده‌یِ یک رویدادِ قدیمی (که someone می‌تواند فقط با دسترسی به دیتابیس انجام دهد)
زنجیره را می‌شکند و با `python scripts/verify_audit_chain.py` قابلِ کشف است. ردیف‌هایِ قدیمیِ
پیش ازِ P20 هش ندارند و زنجیره از اولین ردیفِ هش‌دار شروع می‌شود (بی‌خطر، بدونِ بازنویسیِ تاریخچه).

هم‌زمانی: دو درجِ هم‌زمان می‌توانند «پیشین» یکسانی ببینند ⇒ حلقه از همسایهٔ مستقیم رد می‌شود.
بازبینی این حالت را *پیوندِ ناهمسایه* می‌شمارد نه تحریف، چون هشِ ذخیره‌شده به ردیفِ واقعیِ دیگری
می‌رسد. تحریف فقط وقتی گزارش می‌شود که هیچ ردیفِ قدیمی‌تری با آن هش وجود نداشته باشد.
"""

from __future__ import annotations

import datetime
import hashlib
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import AuditEventType, AuditLogEntry, ShopBot

GENESIS = "0" * 64


def canonical_payload(entry: AuditLogEntry) -> str:
    """رشته‌یِ پایهیِ هر بازبین: هرچه در ستون‌ها هست، به ترتیبِ ثابت."""
    created = entry.created_at.isoformat() if entry.created_at is not None else ""
    event = getattr(entry.event_type, "value", entry.event_type) or ""
    return "|".join(
        [
            str(entry.id),
            created,
            str(event),
            str(entry.shop_bot_id if entry.shop_bot_id is not None else ""),
            str(entry.actor_telegram_id if entry.actor_telegram_id is not None else ""),
            entry.details or "",
        ]
    )


def compute_hash(prev_hash: str, entry: AuditLogEntry) -> str:
    return hashlib.sha256(f"{prev_hash}{canonical_payload(entry)}".encode("utf-8")).hexdigest()


async def _last_hash_before(session: AsyncSession, entry_id: int) -> str:
    result = await session.execute(
        select(AuditLogEntry.row_hash)
        .where(AuditLogEntry.id < entry_id, AuditLogEntry.row_hash.is_not(None))
        .order_by(AuditLogEntry.id.desc())
        .limit(1)
    )
    return result.scalar_one_or_none() or GENESIS


async def log(
    session: AsyncSession,
    event_type: AuditEventType,
    shop_bot_id: int | None = None,
    actor_telegram_id: int | None = None,
    details: str | None = None,
) -> AuditLogEntry:
    entry = AuditLogEntry(event_type=event_type, shop_bot_id=shop_bot_id, actor_telegram_id=actor_telegram_id, details=details)
    session.add(entry)
    await session.flush()  # id و created_at (server_default) این‌جا پر می‌شوند
    entry.prev_hash = await _last_hash_before(session, entry.id)
    entry.row_hash = compute_hash(entry.prev_hash, entry)
    await session.flush()
    return entry


async def get_recent(session: AsyncSession, limit: int = 20, shop_bot_id: int | None = None) -> list[AuditLogEntry]:
    query = select(AuditLogEntry).order_by(AuditLogEntry.id.desc()).limit(limit)
    if shop_bot_id is not None:
        query = query.where(AuditLogEntry.shop_bot_id == shop_bot_id)
    result = await session.execute(query)
    return list(result.scalars().all())


# P21-E (F9): فیلترهایِ پنل. «همه» کلیدِ پیش‌فرض است؛ بقیه دسته‌بندیِ رویدادها به زبانِ ادمین.
FILTER_GROUPS: dict[str, tuple[str, ...]] = {
    "money": (
        AuditEventType.PAYMENT_APPROVED.value,
        AuditEventType.PAYMENT_REJECTED.value,
        AuditEventType.OWNER_GIFT_GRANTED.value,
        AuditEventType.ADMIN_BATCH_EXECUTED.value,
        AuditEventType.OWNER_WALLET_CORRECTED.value,
        AuditEventType.WALLET_LEDGER_EXPORTED.value,
        AuditEventType.WALLET_RECONCILED.value,
    ),
    "shops": (
        AuditEventType.SHOP_SUSPENDED.value,
        AuditEventType.SHOP_UNSUSPENDED.value,
        AuditEventType.OWNER_PROFILE_UPDATED.value,
        AuditEventType.OWNER_BUSINESS_MODE_CHANGED.value,
        AuditEventType.CUSTOMER_BLOCK_CHANGED.value,
        AuditEventType.OWNER_DEACTIVATED.value,
        AuditEventType.OWNER_RESTORED.value,
        AuditEventType.OWNER_PURGED.value,
        AuditEventType.OWNER_SELF_DELETED.value,  # پ۶۵ · حذفِ حساب از پنلِ خودِ فروشگاه‌دار
    ),
    "settings": (
        AuditEventType.ADMIN_SETTING_CHANGED.value,
        AuditEventType.KILL_SWITCH_TOGGLED.value,
        AuditEventType.TIME_FREEZE_CHANGED.value,
        AuditEventType.JOBS_PAUSE_CHANGED.value,
        AuditEventType.BRANDING_TEXT_CHANGED.value,
    ),
    "roles": (AuditEventType.OPERATOR_ADMIN_GRANTED.value, AuditEventType.OPERATOR_ADMIN_REVOKED.value),
    "brand": (AuditEventType.BOT_BIO_TAMPERED.value, AuditEventType.MODERATION_MATCH.value),
}
WINDOW_HOURS: dict[str, int] = {"24": 24, "7d": 24 * 7, "30d": 24 * 30}


def _filtered_statement(
    *,
    group: str | None = None,
    window: str | None = None,
    since: datetime.datetime | None = None,
    until: datetime.datetime | None = None,
    actor_telegram_id: int | None = None,
    allowed_owner_ids: set[int] | None = None,
    now: datetime.datetime | None = None,
):
    """مجموعهٔ فیلترهایِ دفترِ ممیزی، یک‌بار و به‌صورتِ مشترک (موردِ ۱۳ و ۴۸).

    `since`/`until` بازهٔ دلخواه‌اند و بر `window` اولویت دارند؛ اگر هیچ‌کدام داده نشود،
    همان رفتارِ قبلی (بدونِ فیلترِ زمان) باقی می‌ماند.
    """
    statement = select(AuditLogEntry)
    events = FILTER_GROUPS.get(group or "")
    if events:
        statement = statement.where(AuditLogEntry.event_type.in_(events))
    if since is not None or until is not None:
        if since is not None:
            statement = statement.where(AuditLogEntry.created_at >= since)
        if until is not None:
            statement = statement.where(AuditLogEntry.created_at < until)
    else:
        hours = WINDOW_HOURS.get(window or "")
        if hours:
            start = (now or datetime.datetime.now(datetime.timezone.utc)) - datetime.timedelta(hours=hours)
            statement = statement.where(AuditLogEntry.created_at >= start)
    if actor_telegram_id is not None:
        statement = statement.where(AuditLogEntry.actor_telegram_id == actor_telegram_id)
    if allowed_owner_ids is not None:
        if allowed_owner_ids:
            in_scope = select(ShopBot.id).where(ShopBot.shop_owner_id.in_(sorted(allowed_owner_ids)))
            statement = statement.where(AuditLogEntry.shop_bot_id.is_(None) | AuditLogEntry.shop_bot_id.in_(in_scope))
        else:
            statement = statement.where(AuditLogEntry.shop_bot_id.is_(None))
    return statement


async def query(
    session: AsyncSession,
    *,
    group: str | None = None,
    window: str | None = None,
    since: datetime.datetime | None = None,
    until: datetime.datetime | None = None,
    actor_telegram_id: int | None = None,
    limit: int = 25,
    now: datetime.datetime | None = None,
    allowed_owner_ids: set[int] | None = None,
) -> list[AuditLogEntry]:
    """دفترِ ممیزی با فیلترِ دسته/بازهٔ زمانی/عامل. هیچ فیلدی ⇒ همان `get_recent`.

    `allowed_owner_ids` (P21-F): دامنهٔ ادمینِ عملیاتی. ردیف‌هایِ مربوط بهِ فروشگاه‌دارِ دیگر
    دیده نمی‌شوند، چون `details` همان ردیف‌ها مبلغ و شناسهٔ فروشگاه‌دارِ آن مشتری را دارد.
    ردیف‌هایِ بی‌فروشگاه (سوییچ‌ها، تنظیمات، نقش‌ها) پلتفرمی‌اند و برایِ همهٔ ادمین‌ها می‌مانند.
    None ⇒ بدونِ محدودیت (سوپرادمین). مجموعهٔ تهی ⇒ فقطِ ردیف‌هایِ پلتفرمی.
    """
    statement = _filtered_statement(
        group=group,
        window=window,
        since=since,
        until=until,
        actor_telegram_id=actor_telegram_id,
        allowed_owner_ids=allowed_owner_ids,
        now=now,
    ).order_by(AuditLogEntry.id.desc()).limit(limit)
    result = await session.execute(statement)
    return list(result.scalars().all())


async def count_rows(
    session: AsyncSession,
    *,
    group: str | None = None,
    window: str | None = None,
    since: datetime.datetime | None = None,
    until: datetime.datetime | None = None,
    actor_telegram_id: int | None = None,
    allowed_owner_ids: set[int] | None = None,
    now: datetime.datetime | None = None,
) -> dict[str, int]:
    """«چند ردیف است و از چه نوع» برایِ سرِصفحهٔ ممیزی (موردِ ۴۸: آمارِ حرفه‌ایِ همان بازه).

    یکِ کوئریِ گروهی به‌جایِ فهرست‌کردنِ ردیف‌ها — با صدها‌هزار ردیفِ دفتر هم ارزان می‌ماند.
    """
    statement = (
        _filtered_statement(
            group=group,
            window=window,
            since=since,
            until=until,
            actor_telegram_id=actor_telegram_id,
            allowed_owner_ids=allowed_owner_ids,
            now=now,
        )
        .with_only_columns(AuditLogEntry.event_type, func.count())
        .group_by(AuditLogEntry.event_type)
    )
    result = await session.execute(statement)
    counts = {(row[0].value if hasattr(row[0], "value") else row[0]): int(row[1]) for row in result.all()}
    return {"total": sum(counts.values()), **counts}
