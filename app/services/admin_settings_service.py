from __future__ import annotations

import logging
import time
from typing import Any

from sqlalchemy import event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session as SyncSession

from app.database.models import AdminSettings

logger = logging.getLogger(__name__)

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


async def reencrypt_merchant_id(session: AsyncSession) -> bool:
    """پ۱۲۰ · اگر مرچنت‌آیدی زرین‌پالِ پلتفرم هنوز خام در دیتابیس است، یک‌بار بازنویسی شود.

    چرا در بوت‌آپ و نه در مایگریشن: مثلِ رازهایِ وب‌هوک (پ۲۰ · B2) — `ENCRYPTION_KEY` همین‌جا در
    دسترس است و اجرایِ دوباره بی‌اثر می‌ماند. ستون `EncryptedText` مقدار را رمزگشایی‌شده برمی‌گرداند،
    پس برایِ فهمیدنِ «خام بودن» باید خودِ ستون با SQLِ خام خوانده شود.
    """
    from sqlalchemy import text as sql_text
    from sqlalchemy.orm import attributes

    from app.utils.encryption import looks_encrypted

    raw = (await session.execute(sql_text("SELECT zarinpal_merchant_id FROM admin_settings WHERE id = 1"))).scalar()
    if not raw or looks_encrypted(str(raw)):
        return False
    row = await get_admin_settings(session)
    row.zarinpal_merchant_id = row.zarinpal_merchant_id  # نوشتنِ همان متنِ plaintext ⇒ رمز در DB
    attributes.flag_modified(row, "zarinpal_merchant_id")
    await session.flush()
    return True


async def get_admin_settings(session: AsyncSession) -> AdminSettings:
    settings_row = await session.get(AdminSettings, 1)
    if settings_row is None:
        # P33-1: «اولینِ خواندن» را دو جریانِ هم‌زمان نمی‌توانند با هم بسازند. دو تسکِ مستقل
        # (مثلاً میدل‌ور و تسکِ پاسخِ AI با نگهدارندهٔ FSMِ دیتابیسی، یا هر مسیرِ هم‌زمانِ
        # دیگرِ بعدِ reset) هر دو None می‌دیدند و هر دو INSERT id=1 می‌زدند ⇒ رویِ دومی
        # UniqueViolationErrorِ pk_admin_settings (MEASURED در test_checkout_c3 با
        # FSM_STORAGE=postgres). درج داخلِ savepoint است تا در صورتِ باختنِ رقابت،
        # تراکنشِ اصلیِ خواننده (که شاید نوشتهٔ دیگری هم دارد) زنده بماند.
        try:
            async with session.begin_nested():
                session.add(AdminSettings(id=1))
        except IntegrityError:
            logger.info("ردیفِ تنظیمات هم‌زمان ساخته شد؛ همان ردیف خوانده می‌شود.")
        settings_row = await session.get(AdminSettings, 1, populate_existing=True)
        if settings_row is None:
            # رقیب rollback کرد (نه commit) ⇒ حالا خودِ ما می‌سازیمش.
            settings_row = AdminSettings(id=1)
            session.add(settings_row)
            await session.flush()
    return settings_row


async def cached_admin_settings(session: AsyncSession) -> AdminSettings:
    """فقط برایِ مسیرهایِ **فقط‌خواندنی**.

    سطر از سشن جدا (detached) می‌شود تا هیچ‌کس نتواند رویِ نسخهٔ کش‌شده بنویسد و فکر کند
    ذخیره شده است؛ نوشتن همیشه باید از `get_admin_settings` / `update_setting` انجام شود.
    تازه‌ماندنِ داده دوجا تضمین می‌شود: باطل‌سازیِ رویداد-محورِ پایین، و TTLِ
    `READ_CACHE_TTL_SECONDS` فقط به‌عنوانِ سقفِ کهنه‌ماندن در حالتِ چندپروسه‌ای.
    """
    global _cached_row, _cached_at
    now = time.monotonic()
    if _cached_row is not None and (now - _cached_at) < READ_CACHE_TTL_SECONDS:
        return _cached_row
    settings_row = await get_admin_settings(session)
    _cached_row = _value_snapshot(settings_row)
    _cached_at = now
    return _cached_row


def _value_snapshot(row: AdminSettings) -> AdminSettings:
    """کپیِ **مقادیر** در یکِ شیءِ تازه که هیچ سشن/اتصالی ندارد.

    چرا این‌طور (پ۱۰۱): نسخهٔ قبلی خودِ ردیفِ ORM را با `expunge` از سشن بیرون می‌آورد و در کش
    می‌گذاشت. آن شیء هنوز state‌ای داشت که به اتصالِ سشنِ بسته‌شده برمی‌گشت ⇒ در مسیرهایِ HTTPِ
    چندسشنی `SAWarning: non-checked-in connection` و `greenlet is being finalized` می‌دیدیم
    (exit را خراب نمی‌کرد، ولی نویزِ واقعی بود و محکم‌ترینِ نشانهٔ نگهداشتنِ ORMِ مرده). با کپیِ
    مقدار، کش دیگر هیچ ارجاعی به اتصال ندارد و خواندنِ فیلدها هم هیچ IO نمی‌زند.
    """
    return AdminSettings(**{column.key: getattr(row, column.key) for column in row.__table__.columns})


async def update_setting(session: AsyncSession, field_name: str, value: Any) -> AdminSettings:
    settings_row = await get_admin_settings(session)
    setattr(settings_row, field_name, value)
    await session.flush()
    return settings_row
