from __future__ import annotations

import time
from typing import Any

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session as SyncSession

from app.database.models import AdminSettings

# P31: کشِ فقط‌خواندنیِ تنظیماتِ سراسری.
# چرا لازم بود: یکِ پیامِ متنیِ مشتری این سطر را در سه سشنِ جدا (میدل‌ور ← تسکِ پاسخِ AI ←
# تسکِ تشخیصِ سفارش) می‌خواند و هر پاسِ جاب شش‌بار.
#
# TTL عمداً از فاصلۀ debounce (۳ ثانیه در پیش‌فرضِ کد) بزرگ‌تر است: با TTLِ دو ثانیه، تسکِ
# پاسخِ AI که ۳ ثانیه بعد ازِ میدل‌ور اجرا می‌شود کشِ سوخته می‌دید و همان SELECT را دوباره
# می‌زد. چون باطل‌سازی رویداد-محورِ پایین را داریم، تازگیِ داده در تک‌پروسه به نوشتن گره
# خورده است نه به TTL؛ TTL فقط سقفِ کهنه‌ماندن در حالتِ چندپروسه‌ای است.
READ_CACHE_TTL_SECONDS = 30.0

_cached_row: AdminSettings | None = None
_cached_at = 0.0


def reset_read_cache() -> None:
    """پاک‌کردنِ کشِ خواندن (برایِ تست و برایِ هر flushِ دست‌کاری‌کردهٔ AdminSettings)."""
    global _cached_row, _cached_at
    _cached_row = None
    _cached_at = 0.0


@event.listens_for(SyncSession, "after_flush", propagate=True)
def _invalidate_read_cache_on_flush(session: SyncSession, flush_context: Any) -> None:
    """هر سشنی که در آن سطرِ تنظیمات نو یا کثیف باشد، کشِ خواندن را باطل می‌کند.

    این راهِ مطمئن‌تر از «یادآوریِ invalidate در ۱۴ نقطهٔ نوشتن» است: اگر روزی هندلرِ تازه‌ای
    مستقیم فیلدی را عوض کند، باز هم کشِ کهنه سرویسِ پول را گمراه نمی‌کند.
    """
    try:
        changed = session.dirty or session.new
        if any(isinstance(obj, AdminSettings) for obj in changed):
            reset_read_cache()
    except Exception:  # noqa: BLE001 — باطل‌سازیِ کش هرگز نباید flush را بشکند
        reset_read_cache()


async def get_admin_settings(session: AsyncSession) -> AdminSettings:
    settings_row = await session.get(AdminSettings, 1)
    if settings_row is None:
        settings_row = AdminSettings(id=1)
        session.add(settings_row)
        await session.flush()
    return settings_row


async def cached_admin_settings(session: AsyncSession) -> AdminSettings:
    """فقط برایِ مسیرهایِ **فقط‌خواندنی**.

    سطر از سشن جدا (detached) می‌شود تا هیچ‌کس نتواند رویِ نسخهٔ کش‌شده بنویسد و فکر کند
    ذخیره شده است؛ نوشتن همیشه باید از `get_admin_settings` / `update_setting` انجام شود.
    تازه‌ماندنِ داده دوجا تضمین می‌شود: باطل‌سازیِ رویداد-محورِ بالا، و TTLِ دو ثانیه برایِ
    حالتِ چندپروسه‌ای (روشن‌شدنِ «حالتِ تعمیر» در بدترین حالت دو ثانیه طول می‌کشد).
    """
    global _cached_row, _cached_at
    now = time.monotonic()
    if _cached_row is not None and (now - _cached_at) < READ_CACHE_TTL_SECONDS:
        return _cached_row
    settings_row = await get_admin_settings(session)
    session.sync_session.expunge(settings_row)
    _cached_row = settings_row
    _cached_at = now
    return settings_row


async def update_setting(session: AsyncSession, field_name: str, value: Any) -> AdminSettings:
    settings_row = await get_admin_settings(session)
    setattr(settings_row, field_name, value)
    await session.flush()
    return settings_row
