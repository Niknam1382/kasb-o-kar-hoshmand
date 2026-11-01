"""P18 · A2: بیوگرافیِ اجباریِ ربات‌هایِ فروشگاهی (برندینگ).

ادمینِ پلتفرم یک متنِ کوتاه (≤ ۶۰ نویسه) تنظیم می‌کند و آن باید در «About/short description» همه‌یِ
ربات‌هایِ فروشگاهی باشد. فروشگاه‌دار می‌تواند متنِ خودش را *کنارِ* آن بگذارد؛ ترکیب:
«متنِ فروشگاه‌دار — متنِ ادمین» با سقفِ ۱۲۰ نویسه. اگر جا نشد، متنِ فروشگاه‌دار کوتاه می‌شود —
هرگز متنِ ادمین.

بیو در تلگرام *بیرونِ* دیتابیس نگه داشته می‌شود، پس کسی می‌تواند از راهِ دیگرش عوضش کند؛ بنابراین
علاوه بر «موقعِ بالا آمدنِ هر ربات» و «موقعِ تغییرِ متنِ ادمین»، یک پاسِ دوره‌ای (هر ساعت) آن را
می‌خواند و در صورتِ دست‌کاری بازنویسی + به فروشگاه‌دار خبر می‌دهد (با شمارنده در ممیزی).

هیچ‌وقت کرش نمی‌کند: خطایِ شبکه/محدودیتِ نرخ فقط لاگ می‌شود و در پاسِ بعدی تلاش می‌شود.
"""
from __future__ import annotations

import datetime
import logging
import time

from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from app.bots.main_bot import texts
from app.database.models import AuditEventType, ShopBot
from app.services import audit_log_service, shop_owner_service
from app.services.admin_settings_service import get_admin_settings

logger = logging.getLogger(__name__)

BIO_LIMIT = 120  # سقفِ رسمیِ short description در تلگرام
ADMIN_TEXT_LIMIT = 60
SEPARATOR = " — "
OWNER_ALERT_SECONDS = 24 * 60 * 60  # هر فروشگاه حداکثر یک اخطارِ دست‌کاری در شبانه‌روز
# بازرسیِ ساعتی: یک get_short_description به‌ازایِ هر رباتِ فعال در هر دور (بدونِ هزینه وقتی درست باشد).
# شش ساعت برایِ «کسی بیو را عوض کرد و ما برگرداندیم» خیلی کند بود؛ سقفِ نرخِ تلگرام با این حجم خیلی فاصله دارد.
SYNC_INTERVAL_SECONDS = 60 * 60

# تلگرام وقتی بیو تنظیم نشده، این متنِ جاگذاری را برمی‌گرداند. اگر آن را «مقدارِ واقعی» بدانیم،
# اولین پاسِ همگام‌سازی برایِ هر رباتِ تازه «دست‌کاری» ثبت می‌شود و فروشگاه‌دار اخطارِ بی‌دلیل می‌گیرد.
PLACEHOLDER_BIOS = frozenset(
    {
        "a default short description made by @botfather",
        "a bot made by @botfather",
        "a bot description made by @botfather",
    }
)

# پیامدهایِ apply_to_bot (رشته‌هایِ ثابت؛ در شمارشِ sync_all و تست‌ها همین‌ها مقایسه می‌شن)
SKIPPED = "skipped"
UNCHANGED = "unchanged"
APPLIED = "applied"
TAMPERED = "tampered"
ERROR = "error"
NO_TRANSPORT = "no_transport"  # رباتِ این فروشگاه فعلاً به سرویسِ پیام‌رسان وصل نیست

_last_owner_alert_at: dict[int, float] = {}


def reset_alert_cache() -> None:
    """فقط برایِ تست."""
    _last_owner_alert_at.clear()


def compose(owner_text: str | None, admin_text: str | None, limit: int = BIO_LIMIT) -> str:
    """متنِ نهاییِ بیو. بدونِ متنِ ادمین ⇒ رشته‌یِ خالی (یعنی «هیچ کاری نکن»)."""
    admin = (admin_text or "").strip()
    owner = (owner_text or "").strip()
    if not admin:
        return ""
    if not owner:
        return admin[:limit]
    room = limit - len(admin) - len(SEPARATOR)
    if room >= 1:
        return owner[:room].rstrip() + SEPARATOR + admin
    return admin[:limit]


def normalize_admin_text(raw: str | None) -> str | None:
    """متنِ ادمین: حداکثر ۶۰ نویسه؛ خالی/«خالی» ⇒ None (یعنی برندینگ کلاً خاموش)."""
    value = (raw or "").strip()
    if not value or value in {"خالی", "پاک کن", "-"}:
        return None
    return value[:ADMIN_TEXT_LIMIT]


def valid_admin_text(raw: str | None) -> bool:
    value = (raw or "").strip()
    return bool(value) and len(value) <= ADMIN_TEXT_LIMIT


def valid_owner_text(raw: str | None) -> bool:
    value = (raw or "").strip()
    return bool(value) and len(value) <= BIO_LIMIT


def is_due(last_synced: datetime.datetime | None, now: datetime.datetime | None = None) -> bool:
    """پاسِ دوره‌ای هر ۶ ساعت یک‌بار (بر اساسِ برچسبِ زمانِ موفقِ آخر در AdminSettings)."""
    now = now or datetime.datetime.now(datetime.timezone.utc)
    if last_synced is None:
        return True
    if last_synced.tzinfo is None:
        last_synced = last_synced.replace(tzinfo=datetime.timezone.utc)
    return (now - last_synced).total_seconds() >= SYNC_INTERVAL_SECONDS


def _meaningful(value: str | None) -> str:
    """متنِ جاگذاریِ خودِ تلگرام را «بیویِ تنظیم‌نشده» حساب می‌کنیم، نه دست‌کاری."""
    text = (value or "").strip()
    return "" if text.lower() in PLACEHOLDER_BIOS else text


def _outcome_pair(current: str | None, expected: str) -> str:
    previous = _meaningful(current)
    if previous == expected.strip():
        return UNCHANGED
    return TAMPERED if previous else APPLIED


async def apply_to_bot(bot: Bot, shop_bot: ShopBot, admin_text: str | None) -> tuple[str, str]:
    """(وضعیت، بیویِ قبلی). وضعیت‌ها: skipped | unchanged | applied | tampered | error."""
    expected = compose(shop_bot.branding_owner_text, admin_text)
    if not expected:
        return SKIPPED, ""
    try:
        current = _meaningful((await bot.get_my_short_description()).short_description)
    except Exception:  # noqa: BLE001 — شبکه/ریت‌لیمیت: فقط لاگ، تلاشِ دوباره در پاسِ بعد
        logger.warning("خواندنِ بیوگرافیِ رباتِ فروشگاه ناموفق بود (رباتِ %s).", shop_bot.id)
        return ERROR, ""
    outcome = _outcome_pair(current, expected)
    if outcome == UNCHANGED:
        return outcome, current
    try:
        await bot.set_my_short_description(short_description=expected)
    except Exception:  # noqa: BLE001
        logger.warning("ثبتِ بیوگرافیِ رباتِ فروشگاه ناموفق بود (رباتِ %s).", shop_bot.id, exc_info=True)
        return ERROR, current
    return outcome, current


async def apply_for_shop_bot(bot_manager, session: AsyncSession, shop_bot: ShopBot) -> str:
    """اعلامِ متنِ تازه رویِ رباتِ *خودِ همین فروشگاه*.

    خودِ Bot را از caller نمی‌گیرد: در پنلِ فروشگاه‌دار `message.bot` رباتِ *اصلی* است و اگر
    آن را پاس می‌دادیم بیویِ رباتِ اصلی عوض می‌شد (باگِ گزارش‌شده). پیامد برمی‌گرداند تا
    پیامِ درست به کاربر داده شود.
    """
    admin_settings = await get_admin_settings(session)
    bot = bot_manager.get_bot(shop_bot.id)
    if bot is None:
        return NO_TRANSPORT
    outcome, _previous = await apply_to_bot(bot, shop_bot, admin_settings.branding_text)
    return outcome


async def sync_all(session: AsyncSession, bot_manager, main_bot: Bot) -> dict[str, int]:
    """همه‌یِ ربات‌هایِ فروشگاهیِ ثبت‌شده را با متنِ ادمین همگام می‌کند. خلاصه‌یِ شمارش برمی‌گرداند."""
    counts = {"total": 0, "applied": 0, "tampered": 0, "unchanged": 0, "skipped": 0, "error": 0}
    admin_settings = await get_admin_settings(session)
    admin_text = (admin_settings.branding_text or "").strip()
    if not admin_text:
        return counts  # ادمین چیزی ننوشته ⇒ هیچ کاری، هیچ اخطاری

    for shop_bot_id in bot_manager.registered_shop_bot_ids():
        bot = bot_manager.get_bot(shop_bot_id)
        shop_bot = await session.get(ShopBot, shop_bot_id)
        if bot is None or shop_bot is None or not shop_bot.is_active:
            continue
        counts["total"] += 1
        outcome, previous = await apply_to_bot(bot, shop_bot, admin_text)
        counts[outcome] = counts.get(outcome, 0) + 1
        if outcome in (APPLIED, TAMPERED):
            shop_bot.branding_set_at = datetime.datetime.now(datetime.timezone.utc)
        if outcome == TAMPERED:
            shop_bot.branding_tamper_count = int(shop_bot.branding_tamper_count or 0) + 1
            await audit_log_service.log(
                session,
                AuditEventType.BOT_BIO_TAMPERED,
                shop_bot_id=shop_bot.id,
                details="بازنویسی شد؛ متنِ قبلی: " + previous[:140],
            )
            await _alert_owner(main_bot, session, shop_bot)
    if counts["total"] and not counts["error"]:
        admin_settings.branding_synced_at = datetime.datetime.now(datetime.timezone.utc)
    await session.flush()
    if counts["applied"] or counts["tampered"]:
        logger.info(
            "همگام‌سازیِ بیوگرافیِ ربات‌ها: اعمال‌شده=%s بازنویسیِ‌دست‌کاری=%s بدون‌تغییر=%s خطا=%s",
            counts["applied"], counts["tampered"], counts["unchanged"], counts["error"],
        )
    return counts


async def _alert_owner(main_bot: Bot, session: AsyncSession, shop_bot: ShopBot) -> None:
    """اعلانِ نرخ‌محدود (هر فروشگاه حداکثر یک‌بار در ۲۴ ساعت) که بیویش عوض شده و بازگردانده شد."""
    now = time.monotonic()
    previous = _last_owner_alert_at.get(shop_bot.id)
    if previous is not None and now - previous < OWNER_ALERT_SECONDS:
        return
    _last_owner_alert_at[shop_bot.id] = now
    owner = await shop_owner_service.get_by_id(session, shop_bot.shop_owner_id)
    if owner is None:
        return
    try:
        await main_bot.send_message(owner.telegram_id, texts.BOT_BIO_TAMPERED_ALERT)
    except Exception:  # noqa: BLE001 — اعلانِ جانبی هرگز نباید همگام‌سازی را بشکند
        logger.warning("اعلانِ دست‌کاریِ بیوگرافی به فروشگاه‌دار نرسید (رباتِ %s).", shop_bot.id)
