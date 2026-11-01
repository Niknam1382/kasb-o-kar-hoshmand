"""P18 · A2 (+ P21-A): بیوگرافیِ اجباریِ ربات‌هایِ فروشگاهی (برندینگ).

ادمینِ پلتفرم یک متنِ کوتاه (≤ ۶۰ نویسه) تنظیم می‌کند و آن باید در «About/short description» همه‌یِ
ربات‌هایِ فروشگاهی باشد. فروشگاه‌دار می‌تواند متنِ خودش را *کنارِ* آن بگذارد؛ ترکیب:
«متنِ فروشگاه‌دار — متنِ ادمین» با سقفِ ۱۲۰ نویسه. اگر جا نشد، متنِ فروشگاه‌دار کوتاه می‌شود —
هرگز متنِ ادمین. اگر ادمین متنِ خودش را ننویسد، باز هم «متنِ خودِ فروشگاه» پایش و بازگردانی می‌شود.

قاعدهٔ سختِ محصول: نوشتنِ بیو **فقط** رویِ ربات‌هایی که این سامانه برایِ فروشگاه‌دارها ساخته
(تلگرام و بله، هر دو). رباتِ اصلیِ پلتفرم در این سرویس فقط پیامِ اخطار می‌فرستد و `_apply_to_bot`
اگر همان ربات به او داده شود، `ValueError` می‌دهد.

بیو در تلگرام/بله *بیرونِ دیتابیس* نگه داشته می‌شود، پس کسی می‌تواند از راهِ دیگرش عوضش کند؛
بنابراین علاوه بر «موقعِ اتصالِ هر ربات» و «موقعِ تغییرِ متنِ ادمین»، یک پاسِ دوره‌ای (فاصله‌اش را
ادمین تعیین می‌کند، پیش‌فرض ۶۰ دقیقه، با نوبتِ per-ربات) آن را می‌خواند و در صورتِ دست‌کاری یا
حذف، بازنویسی می‌کند و **فقط به همان فروشگاه** خبر می‌دهد (حداکثر یک اخطار در ۲۴ ساعت، ثبت‌شده
در دیتابیس، و یک ردیفِ ممیزی با شمارنده).

هیچ‌وقت کرش نمی‌کند: خطایِ شبکه/محدودیتِ نرخ فقط لاگ می‌شود و در پاسِ بعدی تلاش می‌شود.
"""
from __future__ import annotations

import datetime
import logging

from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bots.main_bot import texts
from app.config import settings
from app.database.models import AuditEventType, ShopBot, ShopOwner
from app.services import audit_log_service, platform_service, shop_owner_service
from app.services.admin_settings_service import get_admin_settings

logger = logging.getLogger(__name__)

BIO_LIMIT = 120  # سقفِ رسمیِ short description در تلگرام
ADMIN_TEXT_LIMIT = 60
SEPARATOR = " — "
OWNER_ALERT_SECONDS = 24 * 60 * 60  # هر فروشگاه حداکثر یک اخطارِ دست‌کاری در شبانه‌روز
# فاصلهِ پیش‌فرضِ بازرسی؛ از P21-A مقدارِ واقعی را ادمین در «فاصلهٔ بازرسیِ بیو» تعیین می‌کند
# (AdminSettings.branding_check_minutes). این فقط fallback است.
SYNC_INTERVAL_SECONDS = 60 * 60
CHECK_MINUTES_FLOOR = 5
CHECK_MINUTES_CEILING = 1440
# قفلِ همگامِ جاب برایِ هر پلتفرم (تلگرام و بله دو رباتِ جدا با یکِ بیویند).
_TRANSPORTS = ("telegram", "bale")

# تلگرام وقتی بیو تنظیم نشده، این متنِ جاگذاری را برمی‌گرداند. اگر آن را «مقدارِ واقعی» بدانیم،
# اولین پاسِ همگام‌سازی برایِ هر رباتِ تازه «دست‌کاری» ثبت می‌شود و فروشگاه‌دار اخطارِ بی‌دلیل می‌گیرد.
PLACEHOLDER_BIOS = frozenset(
    {
        "a default short description made by @botfather",
        "a bot made by @botfather",
        "a bot description made by @botfather",
    }
)

# پیامدهایِ _apply_to_bot (رشته‌هایِ ثابت؛ در شمارشِ sync_all و تست‌ها همین‌ها مقایسه می‌شن)
SKIPPED = "skipped"
UNCHANGED = "unchanged"
APPLIED = "applied"  # اولین بار، یا متنِ دلخواه عوض شده (ادمین/فروشگاه‌دار ویرایش کرده) ⇒ تخلف نیست
TAMPERED = "tampered"  # متنِ غریبه رویِ ربات است ⇒ تخلف
REMOVED = "removed"  # بیویی که خودمان نوشته بودیم حذف شده ⇒ تخلف
ERROR = "error"
NO_TRANSPORT = "no_transport"  # رباتِ این فروشگاه فعلاً به سرویسِ پیام‌رسان وصل نیست
BREACHES = (TAMPERED, REMOVED)

def compose(owner_text: str | None, admin_text: str | None, limit: int = BIO_LIMIT) -> str:
    """متنِ نهاییِ بیو.

    متنِ ادمین چسبِ برندِ پلتفرم است، ولی از P21-A نبودنش دیگر محافظتِ «متنِ خودِ فروشگاه» را
    خاموش نمی‌کند: اگر ادمین چیزی ننویسد، همان متنِ فروشگاه هدفِ بازرسی است. خواستهٔ صریحِ محصول:
    تک‌تکِ ربات‌ها باید متنشان دست‌نخورده بماند، حتی وقتی برندِ سراسری تنظیم نشده است.
    """
    admin = (admin_text or "").strip()
    owner = (owner_text or "").strip()
    if not admin:
        return owner[:limit]
    if not owner:
        return admin[:limit]
    room = limit - len(admin) - len(SEPARATOR)
    if room >= 1:
        return owner[:room].rstrip() + SEPARATOR + admin
    return admin[:limit]


def expected_bio(shop_bot: ShopBot, admin_settings) -> str:
    return compose(shop_bot.branding_owner_text, getattr(admin_settings, "branding_text", None))


def interval_of(admin_settings) -> int:
    """فاصلهٔ بازرسیِ دقیقه‌ایِ ادمین، با کفِ و سقفِ ایمن (بدونِ اعتمادِ کور به دادهٔ جدول)."""
    minutes = getattr(admin_settings, "branding_check_minutes", None) or CHECK_MINUTES_FLOOR
    minutes = int(minutes)
    if minutes < CHECK_MINUTES_FLOOR:
        minutes = CHECK_MINUTES_FLOOR
    if minutes > CHECK_MINUTES_CEILING:
        minutes = CHECK_MINUTES_CEILING
    return minutes


def valid_check_minutes(raw: str | None) -> bool:
    value = (raw or "").strip()
    if not value.isdigit():
        return False
    return CHECK_MINUTES_FLOOR <= int(value) <= CHECK_MINUTES_CEILING


def normalize_check_minutes(raw: str | None) -> int:
    return int(CHECK_MINUTES_FLOOR if not valid_check_minutes(raw) else (raw or "").strip())


def _aware(value: datetime.datetime | None) -> datetime.datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=datetime.timezone.utc)


def is_due(
    last_synced: datetime.datetime | None,
    now: datetime.datetime | None = None,
    interval_seconds: int = SYNC_INTERVAL_SECONDS,
) -> bool:
    """یک ردیفِ «آخرین بازرسیِ موفقِ سراسری» را می‌سنجد (برایِ سازگاریِ تست‌هایِ پیشین)."""
    now = now or datetime.datetime.now(datetime.timezone.utc)
    last_synced = _aware(last_synced)
    if last_synced is None:
        return True
    return (now - last_synced).total_seconds() >= interval_seconds


def is_due_for(shop_bot: ShopBot, now: datetime.datetime | None = None) -> bool:
    """نوبتِ بازرسیِ *همین* ربات رسید؟ ردیف‌هایِ تازه (بدونِ برچسب) همیشه واج‌اند."""
    due_at = _aware(shop_bot.branding_next_check_at)
    if due_at is None:
        return True
    return (now or datetime.datetime.now(datetime.timezone.utc)) >= due_at


def mark_checked(shop_bot: ShopBot, interval_seconds: int, now: datetime.datetime | None = None) -> None:
    """ثبتِ «بازرسی شد» و تعیینِ نوبتِ بعدیِ همین ربات (خطایِ یک ربات، بقیه را پشتِ سرِ خودش نمی‌کشد)."""
    now = now or datetime.datetime.now(datetime.timezone.utc)
    shop_bot.branding_checked_at = now
    shop_bot.branding_next_check_at = now + datetime.timedelta(seconds=interval_seconds)


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


def _meaningful(value: str | None) -> str:
    """متنِ جاگذاریِ خودِ تلگرام را «بیویِ تنظیم‌نشده» حساب می‌کنیم، نه دست‌کاری."""
    text = (value or "").strip()
    return "" if text.lower() in PLACEHOLDER_BIOS else text


def _outcome_pair(current: str, expected: str, applied: str | None) -> str:
    """طبقه‌بندیِ بیویِ فعلی نسبت به چیزی که باید باشد.

    تفاوتِ اصلی با P18: «نامطابق بودن» به‌خودی‌خود تخلف نیست. اگر متنِ دلخواه عوض شده باشد
    (ادمین برندِ پلتفرم را عوض کرده یا خودِ فروشگاه‌دار متنش را ویرایش کرده)، بیویِ کهنه هم
    نامطابق است — ولی آن نامطابقت کارِ خودمان بوده، نه دست‌کاری. مقایسه با
    `branding_applied_bio` (همان رشته‌ای که خودمان نوشتیم) همین دو را از هم جدا می‌کند و
    اخطارِ بی‌دلیلِ «بیوت دستکاری شد» را که در P18 وجود داشت می‌بندد.
    """
    if current == expected.strip():
        return UNCHANGED
    if not current:
        return REMOVED if applied else APPLIED
    if applied and current == applied.strip():
        return APPLIED
    return TAMPERED


async def _apply_to_bot(bot: Bot, shop_bot: ShopBot, admin_text: str | None) -> tuple[str, str]:
    """(وضعیت، بیویِ قبلی) رویِ *یک* ترنسپورت. private است: caller فقط رباتِ فروشگاه می‌گیرد."""
    _assert_not_main_bot(bot)
    expected = compose(shop_bot.branding_owner_text, admin_text)
    if not expected:
        return SKIPPED, ""
    try:
        current = _meaningful((await bot.get_my_short_description()).short_description)
    except Exception:  # noqa: BLE001 — شبکه/ریت‌لیمیت: فقط لاگ، تلاشِ دوباره در پاسِ بعد
        logger.warning("خواندنِ بیوگرافیِ رباتِ فروشگاه ناموفق بود (رباتِ %s).", shop_bot.id)
        return ERROR, ""
    outcome = _outcome_pair(current, expected, shop_bot.branding_applied_bio)
    if outcome == UNCHANGED:
        return outcome, current
    try:
        await bot.set_my_short_description(short_description=expected)
    except Exception:  # noqa: BLE001
        logger.warning("ثبتِ بیوگرافیِ رباتِ فروشگاه ناموفق بود (رباتِ %s).", shop_bot.id, exc_info=True)
        return ERROR, current
    # از این لحظه می‌دانیم چه چیزی را خودمان نوشته‌ایم ⇒ در بازرسیِ بعدی «حذف/دستکاری» از
    # «ویرایشِ عادیِ متن» قابلِ تفکیک است.
    shop_bot.branding_applied_bio = expected[:200]
    return outcome, current


def _assert_not_main_bot(bot: Bot) -> None:
    """B6 (قاعدهٔ محصول): بیوگرافی هرگز نباید رویِ رباتِ اصلیِ «کسب و کار هوشمند» نوشته شود.

    رباتِ اصلی فقط برایِ فرستادنِ پیامِ اخطار به فروشگاه‌دار در این سرویس مصرف می‌شود. مقایسه
    در حافظه است و هیچ توکنی لاگ/چاپ نمی‌شود.
    """
    main_token = (settings.main_bot_token or "").strip()
    if main_token and bot.token == main_token:
        raise ValueError("بیوگرافی فقط رویِ ربات‌هایِ فروشگاهیِ ساخته‌شده اعمال می‌شود، نه رباتِ اصلی")


_OUTCOME_SEVERITY = (ERROR, NO_TRANSPORT, TAMPERED, REMOVED, APPLIED, SKIPPED, UNCHANGED)


def _worst(outcomes: list[str]) -> str:
    """بدترینِ پیامدِ بینِ ترنسپورت‌هایِ یکِ فروشگاه (خطا > بدونِ اتصال > دست‌کاری > اعمال > …)."""
    for severity in _OUTCOME_SEVERITY:
        if severity in outcomes:
            return severity
    return SKIPPED


def transports_for(bot_manager, shop_bot: ShopBot) -> list[tuple[str, Bot]]:
    """ربات‌هایِ فعالِ *همین* فروشگاه، به‌ازایِ هر پلتفرم (تلگرام و بله دو رباتِ جدا‌اند)."""
    found: list[tuple[str, Bot]] = []
    telegram_bot = bot_manager.get_bot(shop_bot.id)
    if telegram_bot is not None:
        found.append((platform_service.TELEGRAM, telegram_bot))
    bale_bot = bot_manager.get_bale_bot(shop_bot.id)
    if bale_bot is not None:
        found.append((platform_service.BALE, bale_bot))
    return found


async def apply_for_shop_bot(bot_manager, session: AsyncSession, shop_bot: ShopBot) -> str:
    """اعلام/بازبینیِ متنِ بیو رویِ ربات(های)ِ *خودِ همین فروشگاه*.

    خودِ Bot را از caller نمی‌گیرد: در پنلِ فروشگاه‌دار `message.bot` رباتِ *اصلی* است و اگر
    آن را پاس می‌دادیم بیویِ رباتِ اصلی عوض می‌شد (باگِ گزارش‌شدهٔ P18). از P21-A هر دو
    ترنسپورتِ فروشگاه (تلگرام و بله) پوشش داده می‌شوند، چون بیویِ رباتِ بله هم «متنِ ماست».
    تخلفِ پیدا‌شده همان مسیرِ پاسِ دوره‌ای شمارش و ممیزی می‌شود (فقط اخطار نمی‌فرستد، چون
    کسی که پرسید خودِ فروشگاه‌دار است و پیامِ نتیجه را همان لحظه می‌بیند).
    """
    admin_settings = await get_admin_settings(session)
    results = await _apply_transports(bot_manager, shop_bot, admin_settings.branding_text)
    if not results:
        return NO_TRANSPORT
    now = datetime.datetime.now(datetime.timezone.utc)
    await _record_breach(session, shop_bot, results, now)
    shop_bot.branding_set_at = now
    return _worst([outcome for _platform, outcome, _previous in results])


async def _apply_transports(bot_manager, shop_bot: ShopBot, admin_text: str | None) -> list[tuple[str, str, str]]:
    """[(پلتفرم، پیامد، بیویِ قبلی)] — هستهِٔ مشترکِ «پنلِ فروشگاه‌دار» و «پاسِ دوره‌ای»."""
    results: list[tuple[str, str, str]] = []
    for platform, bot in transports_for(bot_manager, shop_bot):
        outcome, previous = await _apply_to_bot(bot, shop_bot, admin_text)
        results.append((platform, outcome, previous))
    return results


async def _record_breach(session: AsyncSession, shop_bot: ShopBot, results: list[tuple[str, str, str]], now: datetime.datetime) -> str | None:
    """اگر بیو دستکاری یا حذف شده بود: شمارنده + ردیفِ ممیزی. نامِ تخلف برمی‌گرداند (یا None).

    «ویرایشِ عادیِ متن» (ادمین یا خودِ فروشگاه‌دار) اینجا نمی‌آید، چون پیامدش APPLIED است نه
    TAMPERED/REMOVED — همان تفکیکی که در P18 نبود و باعث می‌شد هر تغییرِ برندِ سراسری، برایِ
    تک‌تکِ ربات‌ها «دستکاری» ثبت شود و به صاحبانشان اخطار برود.
    """
    breach = next((outcome for _platform, outcome, _previous in results if outcome in BREACHES), None)
    if breach is None:
        return None
    shop_bot.branding_tamper_count = int(shop_bot.branding_tamper_count or 0) + 1
    previous_text = next(previous for _platform, outcome, previous in results if outcome == breach)
    reason = "حذف" if breach == REMOVED else "جایگزینی"
    await audit_log_service.log(
        session,
        AuditEventType.BOT_BIO_TAMPERED,
        shop_bot_id=shop_bot.id,
        details=f"متنِ بیو {reason} شد و بازگردانی شد؛ متنِ دیده‌شده: " + previous_text[:140],
    )
    return breach


async def sync_all(session: AsyncSession, bot_manager, main_bot: Bot, *, force: bool = False) -> dict[str, int]:
    """پاسِ دوره‌ایِ بازرسیِ بیو رویِ ربات‌هایِ فروشگاهی (تلگرام و بله)، هرکدام در نوبتِ خودش.

    سه تغییرِ P21-A:
    ۱) نوبت «per-ربات» است (`branding_next_check_at`)، نه یکِ برچسبِ سراسری که یکِ رباتِ
       توکن‌باطل باعث می‌شد برایِ *همه* در هر لوپ دوباره درخواستِ API زده شود؛
    ۲) متنِ خودِ فروشگاه هم وقتی ادمین برندِ سراسری ننوشته محافظت می‌شود؛
    ۳) «حذفِ بیو» هم مثلِ «جایگزینیِ بیو» اخطار دارد — ولی فقط برایِ همان فروشگاه، و سقفِ
       ۲۴ساعته‌اش حالا در دیتابیس است نه در حافظهٔ پروسه.

    `shops` = تعدادِ فروشگاه‌هایی که در این دور بازبینی شدند؛ `total` = تعدادِ ترنسپورت‌ها.
    """
    counts = {"shops": 0, "total": 0, "applied": 0, "tampered": 0, "removed": 0, "unchanged": 0, "skipped": 0, "error": 0}
    admin_settings = await get_admin_settings(session)
    interval_seconds = interval_of(admin_settings) * 60
    now = datetime.datetime.now(datetime.timezone.utc)
    shop_bot_ids = sorted(set(bot_manager.registered_shop_bot_ids()) | set(bot_manager.registered_bale_bot_ids()))

    for shop_bot_id in shop_bot_ids:
        shop_bot = await session.get(ShopBot, shop_bot_id)
        if shop_bot is None or not shop_bot.is_active:
            continue
        if not force and not is_due_for(shop_bot, now):
            continue
        results = await _apply_transports(bot_manager, shop_bot, admin_settings.branding_text)
        if not results:
            continue
        counts["shops"] += 1
        counts["total"] += len(results)
        for _platform, outcome, _previous in results:
            counts[outcome] = counts.get(outcome, 0) + 1
        shop_bot.branding_checked_at = now
        shop_bot.branding_next_check_at = now + datetime.timedelta(seconds=interval_seconds)

        if any(outcome in (APPLIED, TAMPERED, REMOVED) for _platform, outcome, _previous in results):
            shop_bot.branding_set_at = now
        breach = await _record_breach(session, shop_bot, results, now)
        if breach is not None:
            await _alert_owner(main_bot, session, shop_bot, now, removed=breach == REMOVED)
    if counts["shops"]:
        admin_settings.branding_synced_at = now
    await session.flush()
    if counts["applied"] or counts["tampered"]:
        logger.info(
            "همگام‌سازیِ بیوگرافیِ ربات‌ها: فروشگاه=%s ترنسپورت=%s اعمال‌شده=%s بازگردانیِ‌دست‌کاری=%s بدون‌تغییر=%s خطا=%s",
            counts["shops"], counts["total"], counts["applied"], counts["tampered"], counts["unchanged"], counts["error"],
        )
    return counts


async def _alert_owner(main_bot: Bot, session: AsyncSession, shop_bot: ShopBot, now: datetime.datetime, *, removed: bool = False) -> bool:
    """اعلانِ فقط به *همان* فروشگاهِ دست‌کاری‌شده، حداکثر یک‌بار در ۲۴ ساعت (ماندگار در دیتابیس)."""
    last_alert = _aware(shop_bot.branding_last_alert_at)
    if last_alert is not None and (now - last_alert).total_seconds() < OWNER_ALERT_SECONDS:
        return False
    owner = await shop_owner_service.get_by_id(session, shop_bot.shop_owner_id)
    if owner is None:
        return False
    try:
        await main_bot.send_message(owner.telegram_id, texts.BOT_BIO_REMOVED_ALERT if removed else texts.BOT_BIO_TAMPERED_ALERT)
    except Exception:  # noqa: BLE001 — اعلانِ جانبی هرگز نباید همگام‌سازی را بشکند
        logger.warning("اعلانِ دست‌کاریِ بیوگرافی به فروشگاه‌دار نرسید (رباتِ %s).", shop_bot.id)
        return False
    shop_bot.branding_last_alert_at = now
    return True


async def tamper_report(session: AsyncSession, limit: int = 10) -> list[dict]:
    """فروشگاه‌دارهایی که بیویِ برندشان بیش از همه دست‌کاری/حذف شده (برایِ گزارشِ ادمین)."""
    result = await session.execute(
        select(ShopBot, ShopOwner.telegram_id, ShopOwner.first_name, ShopOwner.last_name)
        .join(ShopOwner, ShopOwner.id == ShopBot.shop_owner_id)
        .where(ShopBot.branding_tamper_count > 0)
        .order_by(ShopBot.branding_tamper_count.desc(), ShopBot.id)
        .limit(limit)
    )
    rows: list[dict] = []
    for shop_bot, telegram_id, first_name, last_name in result.all():
        rows.append(
            {
                "shop_bot_id": shop_bot.id,
                "bot_username": shop_bot.bot_username,
                "owner_label": " ".join(part for part in (first_name, last_name) if part) or str(telegram_id),
                "tamper_count": int(shop_bot.branding_tamper_count or 0),
                "checked_at": _aware(shop_bot.branding_checked_at),
                "next_check_at": _aware(shop_bot.branding_next_check_at),
            }
        )
    return rows
