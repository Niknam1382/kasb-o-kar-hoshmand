"""P44 · موردِ ۵۱ (نیمهٔ دوم): بکاپِ خودکارِ دیتابیس، با نگهداری و ارسالِ فایل به ادمین.

تقسیمِ کار:
· سرویسِ جانبیِ `backup` در docker-compose (ایمیجِ خودِ `postgres:16` ⇒ نسخهٔ `pg_dump` همیشه با
  نسخهٔ سر یکی است؛ `pg_dump` پانزده نمی‌تواند شانزده را بگیرد) هر شب یکِ فایلِ
  `kasbokar-YYYYMMDD-HHMMSS.dump` در پوشهٔ مشترک `/backups` می‌سازد.
· این ماژول سمتِ اپ است: تازه‌ترین فایلی که هنوز فرستاده نشده را **یک‌بار** برایِ همهٔ ادمین‌ها
  می‌فرستد، زمانِ همان فایل را در `admin_settings.backup_last_sent_at` ذخیره می‌کند (پس ری‌استارتِ
  اپ یا چند دورِ جاب در یک روز، فایلِ تکراری نمی‌فرستد) و فایل‌هایِ قدیمی‌تر از
  `backup_retention_days` را پاک می‌کند.

چرا خودِ فایل برایِ ادمین می‌رود: خواستِ صریحِ مالکِ محصول. سقفِ ۴۵ مگابایت گذاشته شده چون
رباتِ تلگرام/بله بزرگ‌تر از آن را قبول نمی‌کند؛ در آن حالت متنِ جای‌نما می‌رود و فایل رویِ دیسک
سالم می‌ماند ⇒ بکاپ هیچ‌وقت به‌خاطرِ محدودیتِ پیام از دست نمی‌رود.

قاعدهٔ ۷ (اول commit، بعدِ شبکه): مارکرِ «ارسال شد» پیش ازِ ارسال ذخیره و commit می‌شود. اگر
تلگرام در همان لحظه قطع باشد، آن فایل دوباره فرستاده نمی‌شود — و این عمدی است: فایل رویِ دیسک
است و دکمهٔ «📦 ارسالِ دستیِ آخرین بکاپ» همان لحظه قابلِ دریافتش است؛ ارسالِ خودکارِ دوباره یعنی
اسپمِ فایلِ تکراری برایِ ادمین.

رازها: این ماژول هیچ‌جا رشتهٔ اتصالِ دیتابیس نمی‌سازد و چیزی چاپ نمی‌کند جز نامِ فایل و تعدادِ
دریافت‌کننده‌ها (pg_dump با متغیرهایِ محیطیِ کانتینرِ خودش کار می‌کند).
"""

from __future__ import annotations

import datetime
import logging
import re
from pathlib import Path

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import FSInputFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.bots.main_bot import texts as main_texts
from app.config import settings
from app.services.admin_settings_service import get_admin_settings
from app.utils.jalali import format_jalali_datetime
from app.utils.validators import fa_number

logger = logging.getLogger(__name__)

DUMP_NAME_RE = re.compile(r"^kasbokar-(\d{8})-(\d{6})\.dump$")
# رباتِ تلگرام فایلِ بزرگ‌تر از ۵۰ مگابایت را قبول نمی‌کند؛ چند مگابایت پایین‌تر می‌نشینیم تا
# سرِ حدِ واقعی گیر نکنیم.
MAX_SEND_BYTES = 45 * 1024 * 1024


def backup_root() -> Path:
    return Path(settings.backup_dir)


def parse_dump_name(name: str) -> datetime.datetime | None:
    """`kasbokar-20261109-030512.dump` ⇒ datetimeِ UTC؛ هر نامِ دیگر ⇒ None (دست نمی‌خورد)."""
    match = DUMP_NAME_RE.match(name)
    if match is None:
        return None
    try:
        return datetime.datetime.strptime(f"{match.group(1)}{match.group(2)}", "%Y%m%d%H%M%S").replace(
            tzinfo=datetime.timezone.utc
        )
    except ValueError:
        return None


def list_dumps(root: Path | None = None) -> list[tuple[datetime.datetime, Path]]:
    """فایل‌هایِ بکاپِ معتبر، قدیمی به تازه. پوشهٔ نبودِ پوشه یا نامِ بی‌ربط = فهرستِ خالی (نه خطا)."""
    base = root if root is not None else backup_root()
    try:
        entries = list(base.iterdir())
    except OSError:
        return []
    found: list[tuple[datetime.datetime, Path]] = []
    for path in entries:
        stamp = parse_dump_name(path.name)
        if stamp is not None and path.is_file():
            found.append((stamp, path))
    found.sort(key=lambda item: item[0])
    return found


def expired_dumps(dumps: list[tuple[datetime.datetime, Path]], retention_days: int, now: datetime.datetime) -> list[Path]:
    """آن‌چه بیش از `retention_days` روز از ساختنش گذشته. `retention_days <= 0` = هیچ‌وقت پاک نکن."""
    days = int(retention_days or 0)
    if days <= 0:
        return []
    cutoff = now - datetime.timedelta(days=days)
    return [path for stamp, path in dumps if stamp < cutoff]


def prune(dumps: list[tuple[datetime.datetime, Path]], retention_days: int, now: datetime.datetime) -> list[str]:
    """پاک‌کردنِ فایل‌هایِ از مهلت‌گذشته؛ فقط فایل‌هایی که خودمان نام‌گذاری‌شان را قبول داریم."""
    deleted: list[str] = []
    for path in expired_dumps(dumps, retention_days, now):
        try:
            path.unlink()
            deleted.append(path.name)
        except OSError:
            logger.exception("پاک‌کردنِ فایلِ بکاپِ قدیمی ناموفق بود: %s", path.name)
    return deleted


async def _deliver(main_bot: Bot, path: Path, admins: list[int], *, manual: bool = False) -> tuple[int, int, int]:
    """(ارسال‌شده، ناموفق، اندازه). هر دریافت‌کننده جدا؛ بلاک‌کردنِ یکِ ادمین بقیه را متوقف نمی‌کند."""
    size = path.stat().st_size
    if size > MAX_SEND_BYTES:
        sent = 0
        for chat_id in admins:
            try:
                await main_bot.send_message(
                    chat_id, main_texts.ADMIN_BACKUP_TOO_LARGE_TEXT.format(size_mb=fa_number(size // (1024 * 1024)))
                )
                sent += 1
            except TelegramAPIError:
                logger.exception("ارسالِ جای‌نمایِ بکاپ به ادمین %s ناموفق بود.", chat_id)
        return sent, len(admins) - sent, size
    caption = main_texts.admin_backup_caption(path.name, size, manual=manual)
    sent = 0
    for chat_id in admins:
        try:
            await main_bot.send_document(chat_id, document=FSInputFile(str(path)), caption=caption)
            sent += 1
        except TelegramAPIError:
            logger.exception("ارسالِ فایلِ بکاپ به ادمین %s ناموفق بود.", chat_id)
    return sent, len(admins) - sent, size


async def run_nightly(session: AsyncSession, main_bot: Bot, *, now: datetime.datetime | None = None) -> dict:
    """جابِ شبانه: ارسالِ فایلِ تازه (اگر روشن باشد) + پاک‌سازیِ قدیمی‌ها."""
    admin_settings = await get_admin_settings(session)
    # بررسیِ سوییچ پیش ازِ هر دسترسیِ دیسکی: خاموش ⇒ نه پوشه خوانده می‌شود نه فایلی پاک می‌شود.
    if not admin_settings.nightly_backup_enabled:
        return {"status": "off", "files": 0}
    # خوانده‌شدن پیش ازِ commit: بعدِ commit سشنِ async نمی‌تواند ستونی را تنبل‌بار کند.
    retention_days = int(admin_settings.backup_retention_days)
    moment = now or datetime.datetime.now(datetime.timezone.utc)
    dumps = list_dumps()
    result = {"status": "no-file", "files": len(dumps), "sent": 0, "failed": 0, "deleted": []}
    fresh = [item for item in dumps if _not_sent_yet(admin_settings, item[0])]
    if fresh:
        stamp, path = fresh[-1]
        admins = sorted(settings.admin_ids)
        if not admins:
            result["status"] = "no-admin"
        else:
            # قاعدهٔ ۷: اول مارکر ذخیره و commit شود، بعدِ شبکه.
            admin_settings.backup_last_sent_at = stamp
            await session.flush()
            await session.commit()
            sent, failed, _size = await _deliver(main_bot, path, admins)
            result.update({"status": "sent" if sent else "failed", "sent": sent, "failed": failed, "file": path.name})
    elif dumps:
        result["status"] = "already-sent"
        result["file"] = dumps[-1][1].name
    result["deleted"] = prune(dumps, retention_days, moment)
    if result["deleted"]:
        logger.info("نگهداریِ بکاپ: %s فایلِ قدیمی پاک شد.", len(result["deleted"]))
    return result


def _not_sent_yet(admin_settings, stamp: datetime.datetime) -> bool:
    last = admin_settings.backup_last_sent_at
    if last is None:
        return True
    if last.tzinfo is None:
        last = last.replace(tzinfo=datetime.timezone.utc)
    return stamp > last


async def send_latest_now(session: AsyncSession, main_bot: Bot) -> dict:
    """دکمهٔ دستیِ ادمین: تازه‌ترین فایلِ موجود را بدونِ توجه به مارکر می‌فرستد (مارکر هم تازه می‌شود)."""
    admin_settings = await get_admin_settings(session)
    dumps = list_dumps()
    result = {"status": "no-file", "files": len(dumps), "sent": 0, "failed": 0}
    if not dumps:
        return result
    stamp, path = dumps[-1]
    admins = sorted(settings.admin_ids)
    if not admins:
        result["status"] = "no-admin"
        return result
    admin_settings.backup_last_sent_at = stamp
    await session.flush()
    await session.commit()
    sent, failed, _size = await _deliver(main_bot, path, admins, manual=True)
    result.update({"status": "sent" if sent else "failed", "sent": sent, "failed": failed, "file": path.name})
    return result


def status_lines(admin_settings, root: Path | None = None, now: datetime.datetime | None = None) -> list[str]:
    """چند خطِ خوانا برایِ صفحهٔ «بکاپ و نگهداری»: پوشه، تعدادِ فایل، آخرین ارسالی، مهلتِ نگه‌داشتن.

    نامِ پوشه و نامِ فایل داده‌اند (نه متنِ انگلیسیِ قاطیِ فارسی)؛ دستورِ docker راه‌اندازی عمداً اینجا
    نوشته نمی‌شود و در `docs/deployment-playbook.md` §بکاپ آمده است."""
    moment = now or datetime.datetime.now(datetime.timezone.utc)
    base = root if root is not None else backup_root()
    dumps = list_dumps(base)
    lines = [f"🗂 پوشهٔ بکاپ: {base}"]
    if not dumps:
        lines.append("• هنوز هیچ فایلی در این پوشه نیست ⇒ سرویسِ بکاپ روشن نیست (راهنمایِ استقرار §بکاپ).")
    else:
        lines.append(f"• {fa_number(len(dumps))} فایلِ بکاپ موجود — تازه‌ترین: {dumps[-1][1].name}")
        would_delete = expired_dumps(dumps, admin_settings.backup_retention_days, moment)
        if would_delete:
            lines.append(f"• در همین دور، {fa_number(len(would_delete))} فایلِ قدیمی پاک می‌شود.")
    last = admin_settings.backup_last_sent_at
    lines.append(f"• آخرین ارسال به ادمین: {format_jalali_datetime(last) if last else 'هنوز ارسال نشده'}")
    lines.append(
        f"• نگه‌داشتن: {fa_number(int(admin_settings.backup_retention_days))} روز · "
        f"ارسالِ خودکار: {'روشن' if admin_settings.nightly_backup_enabled else 'خاموش'}"
    )
    return lines
