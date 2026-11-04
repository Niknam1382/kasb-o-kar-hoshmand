from __future__ import annotations

import datetime
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bots.main_bot import texts
from app.database.models import ShopBot, ShopOwner, TenantMode
from app.services import commission_receivable_service, stats_service, time_freeze_service, wallet_service
from app.services.admin_settings_service import cached_admin_settings
from app.utils.jalali import to_tehran

logger = logging.getLogger(__name__)

# B5: هفته‌یِ ایرانی از نگاهِ فروشگاه‌دار — ۰=شنبه … ۶=جمعه (نامِ روزها در texts.REPORT_WEEKDAY_NAMES).
DEFAULT_REPORT_WEEKDAY = 0
DEFAULT_REPORT_HOUR = 9
_SATURDAY_PY_WEEKDAY = 5  # شنبه در weekdayِ پایتون (دوشنبه=۰)


def persian_weekday_to_python(index: int) -> int:
    """۰=شنبه … ۶=جمعه ← weekdayِ پایتون (۰=دوشنبه)."""
    return (_SATURDAY_PY_WEEKDAY + int(index)) % 7


async def _owners_by_id(session: AsyncSession, shop_bots) -> dict[int, ShopOwner]:  # noqa: ANN001
    """مالکِ همهٔ این فروشگاه‌ها در یکِ کوئری.

    پیش‌ازاین هر حلقهٔ گزارش به‌ازایِ هر فروشگاه `session.get(ShopOwner, …)` می‌زد ⇒ با ۵۰۰ فروشگاه،
    ۵۰۰ کوئری در هر پاسِ ۳۰دقیقه‌ای (و دو پاسِ گزارش). نتیجه همان ردیف‌هایِ ORM است، فقط یک‌بار خوانده می‌شوند.
    """
    owner_ids = {bot.shop_owner_id for bot in shop_bots}
    if not owner_ids:
        return {}
    rows = (await session.execute(select(ShopOwner).where(ShopOwner.id.in_(owner_ids)))).scalars().all()
    return {owner.id: owner for owner in rows}


def latest_window_start(now_tehran: datetime.datetime, weekday_index: int, hour: int) -> datetime.datetime:
    """آغازِ تازه‌ترین بازه‌یِ مجازِ ارسال (aware، به وقتِ تهران).

    «تازه‌ترین» نه «امروز»: اگر ربات وسطِ هفته خاموش بوده، با بالا آمدن همان گزارشِ عقب‌افتاده یک‌بار
    می‌رود و بعد تا هفته‌یِ بعد تکرار نمی‌شود.
    """
    target = persian_weekday_to_python(weekday_index)
    days_back = (now_tehran.weekday() - target) % 7
    candidate = (now_tehran - datetime.timedelta(days=days_back)).replace(
        hour=max(0, min(23, int(hour))), minute=0, second=0, microsecond=0
    )
    if candidate > now_tehran:
        candidate -= datetime.timedelta(days=7)
    return candidate


async def send_due_reports(session: AsyncSession, main_bot: Bot, now: datetime.datetime | None = None) -> None:
    """گزارشِ دوره‌ای: روزِ هفته + ساعتِ *هر فروشگاه*، به وقتِ تهران، دقیقاً یک‌بار در هر بازه‌یِ هفتگی.

    B5: پیش از این مبنا «N روز از آخرین ارسال» بود و چون جاب هر ۳۰ دقیقه چک می‌کرد، لحظه‌یِ ارسال هر
    هفته کمی جابه‌جا می‌شد و هرگز به ساعتِ موردِ انتظارِ فروشگاه‌دار نمی‌رسید (و مبنایش UTC بود).
    `admin_settings.periodic_report_frequency_days` فقط بازه‌یِ پوششِ متنِ گزارش است، نه زمان‌بندی.
    `now` اختیاری است و فقط برایِ تست پاس داده می‌شود (مثلِ `send_due_nightly_reports`).
    """
    admin_settings = await cached_admin_settings(session)
    now = now or datetime.datetime.now(datetime.timezone.utc)
    now_tehran = to_tehran(now)

    all_frozen, frozen_owner_ids = await time_freeze_service.frozen_filter(session)
    if all_frozen:
        return  # K3/K4: در توقفِ زمان هیچ گزارشی نمی‌رود

    result = await session.execute(select(ShopBot).where(ShopBot.is_active.is_(True)))
    active_bots = result.scalars().all()
    owners = await _owners_by_id(session, active_bots)

    for shop_bot in active_bots:
        if not shop_bot.weekly_report_enabled or shop_bot.shop_owner_id in frozen_owner_ids:
            continue
        window_start = latest_window_start(now_tehran, shop_bot.weekly_report_weekday, shop_bot.weekly_report_hour)
        if shop_bot.last_report_sent_at is not None and to_tehran(shop_bot.last_report_sent_at) >= window_start:
            continue  # همین بازه قبلاً فرستاده شده ⇒ دوباره نمی‌رود

        stats = await stats_service.get_shop_stats(session, shop_bot.id)
        owner = owners[shop_bot.shop_owner_id]
        try:
            await main_bot.send_message(owner.telegram_id, texts.periodic_report_text(stats, admin_settings.periodic_report_frequency_days))
            shop_bot.last_report_sent_at = now
            await session.flush()
        except TelegramAPIError:
            logger.exception("ارسال گزارشِ دوره‌ای برای فروشگاه‌دار %s ناموفق بود.", owner.telegram_id)


async def send_due_nightly_reports(session: AsyncSession, main_bot: Bot, now: datetime.datetime | None = None) -> None:
    """
    گزارشِ شبانه (فازِ ۳): جدا از send_due_reports بالا (که یه خلاصه‌ی سلامتِ
    کلی هر N روزه). این یکی هر روز، وقتی ساعتِ UTC از admin_settings.
    nightly_report_hour_utc گذشت، فقط عددهایِ «امروز» رو می‌فرسته — و چون این
    تابع هر ۳۰ دقیقه صدا زده می‌شه، last_nightly_report_date جلویِ دوبار-
    فرستادن توی یه روز رو می‌گیره.

    پارامترِ now اختیاریه (فقط برای تست — تا بشه بدونِ وابستگی به ساعتِ واقعیِ
    اجرا، رفتارِ «هنوز نرسیده»/«همین الان دوباره چک شد ولی امروز قبلاً رفته»
    رو دقیق تست کرد). توی اجرایِ واقعی (scheduler.py) همیشه None پاس داده
    می‌شه و ساعتِ واقعی استفاده می‌شه.
    """
    admin_settings = await cached_admin_settings(session)
    if not admin_settings.nightly_report_enabled:
        return

    now = now or datetime.datetime.now(datetime.timezone.utc)
    if now.hour < admin_settings.nightly_report_hour_utc:
        return
    today = now.date()

    result = await session.execute(select(ShopBot).where(ShopBot.is_active.is_(True)))
    active_bots = result.scalars().all()
    owners = await _owners_by_id(session, active_bots)
    # P29: طلبِ کمیسیونِ *هر فروشگاه* در یکِ کوئریِ گروهی. پیش‌ازاین داخلِ همین حلقه
    # `commission_receivable_service.summary(session)` صدا زده می‌شد که جمعِ سراسریِ پنلِ ادمین است
    # ⇒ هم با ۵۰۰ فروشگاه در هر پاسِ گزارش یکِ aggregate رویِ کلِ جدول ۵۰۰ بار می‌خورد، هم فروشگاه‌دار
    # عددِ بدهیِ بقیه را در گزارشِ خصوصیِ خودش می‌دید.
    debts = await commission_receivable_service.open_totals_by_owner(session, set(owners))

    # P31-B: آمارِ روزانهٔ همهٔ فروشگاه‌هایِ نوبت‌دار در پنج کوئریِ گروهی. پیش‌ازاین داخلِ همین
    # حلقه پنج‌کوئری به‌ازایِ هر فروشگاه زده می‌شد (۵۰۰ فروشگاه ⇒ ~۲٬۵۰۰ کوئری در یکِ پاس).
    # `day_start` برایِ همه یکی است (نیمه‌شبِ UTCِ همان روز)، پس بیرون از حلقه حساب می‌شود.
    day_start = datetime.datetime.combine(today, datetime.time.min, tzinfo=datetime.timezone.utc)
    due_bots = [bot for bot in active_bots if bot.last_nightly_report_date != today]
    daily_stats = await stats_service.get_shops_daily_stats(session, {bot.id for bot in due_bots}, day_start, now)

    for shop_bot in due_bots:
        stats = daily_stats.get(shop_bot.id)
        owner = owners.get(shop_bot.shop_owner_id)
        if owner is None or stats is None:
            continue
        # P21-D (F1): موجودی، قابل‌صرف، اعتبارِ در آستانهٔ انقضا و طلبِ کمیسیونِ وصول‌نشده به همان پیام اضافه می‌شوند.
        usable, expiring, expiring_days = await wallet_service.credit_summary(session, owner)
        debt = debts.get(shop_bot.shop_owner_id, 0)
        message = texts.nightly_report_text(stats, consultation=shop_bot.tenant_mode == TenantMode.CONSULTATION)
        message += "\n" + texts.digest_wallet_line(
            int(owner.wallet_balance_toman or 0), usable, expiring if expiring_days is not None else 0, expiring_days, debt
        )
        try:
            await main_bot.send_message(owner.telegram_id, message)
            shop_bot.last_nightly_report_date = today
            await session.flush()
        except TelegramAPIError:
            logger.exception("ارسال گزارشِ شبانه برای فروشگاه‌دار %s ناموفق بود.", owner.telegram_id)
