"""توقفِ جاب‌هایِ زمان‌بندی‌شده (W5 · K4). سوییچِ کلی `jobs_paused` + توقفِ گروه‌به‌گروه (`jobs_paused_groups`، CSV).
جاب‌ها فقط *رد می‌شن* (چیزی پاک/جابه‌جا نمی‌شه)؛ بعد از ازسرگیری دورِ بعدی عقب‌افتاده‌ها رو می‌گیره. ثبتِ زمان/عامل برایِ ممیزی."""

from __future__ import annotations

import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.admin_settings_service import get_admin_settings

GROUPS: dict[str, str] = {
    "grace": "مهلتِ اشتراک و انقضایِ اشتراک",
    "reports": "گزارش‌هایِ دوره‌ای و شبانه",
    "wallet": "انقضا و یادآوریِ شارژِ کیف‌پول",
    "orders": "انقضایِ سفارش و پرداخت",
    "prune": "پاکسازیِ مکالمه‌هایِ قدیمی",
    "branding": "بازرسیِ ساعتیِ بیوگرافیِ ربات‌ها",
    "notifications": "تلاشِ دوبارهٔ ارسالِ اعلان‌ها",
    # P44 · موردِ ۵۱: ارسالِ فایلِ بکاپ به ادمین + پاک‌کردنِ قدیمی‌ها (خاموش‌کردنش فقط ردّ شدنِ جاب است).
    "backup": "بکاپِ خودکارِ دیتابیس",
}


def paused_groups(admin_settings) -> set[str]:
    raw = getattr(admin_settings, "jobs_paused_groups", None) or ""
    return {g for g in (part.strip() for part in raw.split(",")) if g in GROUPS}


def is_paused(admin_settings, group: str) -> bool:
    """True اگه سوییچِ کلی روشنه یا همین گروه جدا متوقف شده."""
    return bool(getattr(admin_settings, "jobs_paused", False)) or group in paused_groups(admin_settings)


async def set_global(session: AsyncSession, paused: bool, by: str) -> None:
    row = await get_admin_settings(session)
    row.jobs_paused = paused
    row.jobs_paused_at = datetime.datetime.now(datetime.timezone.utc) if paused else None
    row.jobs_paused_by = by[:64] if paused else None
    await session.flush()


async def toggle_group(session: AsyncSession, group: str, by: str) -> bool | None:
    """گروه رو جابه‌جا می‌کنه؛ برمی‌گردونه وضعیتِ جدید (True=متوقف) یا None برایِ گروهِ نامعتبر."""
    if group not in GROUPS:
        return None
    row = await get_admin_settings(session)
    groups = paused_groups(row)
    now_paused = group not in groups
    groups.symmetric_difference_update({group})
    row.jobs_paused_groups = ",".join(sorted(groups)) or None
    if now_paused:
        row.jobs_paused_at = datetime.datetime.now(datetime.timezone.utc)
        row.jobs_paused_by = by[:64]
    elif not groups and not row.jobs_paused:
        row.jobs_paused_at, row.jobs_paused_by = None, None
    await session.flush()
    return now_paused
