from __future__ import annotations

import dataclasses
import datetime
import logging
import secrets

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import OtpCode
from app.services import sms_service

logger = logging.getLogger(__name__)

OTP_TTL_MINUTES = 5
# P18 · A3: سقفِ ارسالِ پیامک به‌ازایِ هر شماره (در هر ساعت) — از هزینه‌یِ باز و سوءاستفاده از
# «دکمه‌یِ ارسالِ دوباره» جلوگیری می‌کند. شمارش از خودِ ردیف‌هایِ `otp_codes` انجام می‌شود.
MAX_SENDS_PER_PHONE_PER_HOUR = 3
SEND_WINDOW_MINUTES = 60
# تعدادِ پیامک‌هایِ ارسالی طیِ این پنجره، مبنایِ برآوردِ حجم/هزینه در پنلِ ادمین است
# (کاوه‌نگار به‌ازایِ پیام صورتحساب می‌کند؛ نرخِ واحد را ما نمی‌دانیم و عددِ ساختگی نمی‌سازیم).
COST_WINDOW_DAYS = 30


async def _count(session: AsyncSession, *conditions) -> int:
    """شمارش در SQL (ردیف‌ها به پایتون نمی‌آیند) — هر دو شمارنده‌یِ سقف/حجم از این استفاده می‌کنند."""
    result = await session.execute(select(func.count()).select_from(OtpCode).where(*conditions))
    return int(result.scalar_one())


async def generate_otp(session: AsyncSession, shop_owner_id: int, purpose: str, phone_number: str | None = None) -> str:
    code = f"{secrets.randbelow(1000000):06d}"
    otp = OtpCode(
        shop_owner_id=shop_owner_id,
        code=code,
        purpose=purpose,
        phone_number=phone_number,
        expires_at=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=OTP_TTL_MINUTES),
    )
    session.add(otp)
    await session.flush()
    return code


async def pending_otp(session: AsyncSession, shop_owner_id: int, purpose: str) -> OtpCode | None:
    """تازه‌ترین کدِ مصرف‌نشده و منقضی‌نشده (برایِ همان هدف). None ⇒ کدِ معتبری نیست."""
    now = datetime.datetime.now(datetime.timezone.utc)
    result = await session.execute(
        select(OtpCode)
        .where(
            OtpCode.shop_owner_id == shop_owner_id,
            OtpCode.purpose == purpose,
            OtpCode.consumed.is_(False),
            OtpCode.expires_at > now,
        )
        .order_by(OtpCode.id.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def sent_recently(session: AsyncSession, phone_number: str | None, purpose: str) -> int:
    """چند پیامکِ این هدف به این شماره در پنجره‌یِ جاری رفته است (سقفِ ساعتی)."""
    if not phone_number:
        return 0
    since = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=SEND_WINDOW_MINUTES)
    return await _count(session, OtpCode.phone_number == phone_number, OtpCode.purpose == purpose, OtpCode.sent_at >= since)


async def mark_sent(session: AsyncSession, otp: OtpCode, provider_status: str | None) -> None:
    """B4/A3: ردپایِ ارسال (برایِ سقف و برایِ برآوردِ حجم) — بدونِ لاگ‌کردنِ شماره‌یِ کامل."""
    otp.sent_at = datetime.datetime.now(datetime.timezone.utc)
    otp.provider_status = (provider_status or "ok")[:32]
    await session.flush()


async def sent_count_within(session: AsyncSession, days: int = COST_WINDOW_DAYS) -> int:
    """تعدادِ پیامک‌هایِ موفقی که در پنجره‌یِ N روزه رفته (مبنایِ نمایشِ حجم/هزینه در پنل)."""
    since = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)
    return await _count(session, OtpCode.sent_at >= since)


@dataclasses.dataclass(frozen=True)
class OtpDelivery:
    """نتیجه‌یِ تلاشِ ارسالِ کد. `reason` هیچ رازِ فنی ندارد و فقط برایِ انتخابِ پیامِ درست است."""

    delivered: bool
    code: str
    reason: str | None = None  # None | disabled | no_key | rate_limited | send_failed


async def send_phone_code(
    session: AsyncSession, *, shop_owner_id: int, purpose: str, phone: str, admin_settings
) -> OtpDelivery:
    """تولیدِ کد و تلاشِ ارسالِ پیامک، با درِ روشن/خاموشِ صریحِ A3.

    هر حالتِ «نرفتن» به یک پیامِ متفاوت می‌رسد ولی ثبت‌نام را نمی‌شکند:
    * `disabled`/`no_key`/`send_failed` ⇒ کد در همان چت نشان داده می‌شود (جایگزینِ امروز).
    * `rate_limited` ⇒ کد نشان داده **نمی‌شود**، وگرنه سقفِ ساعتی بی‌معنا می‌شود.
    """
    code = await generate_otp(session, shop_owner_id, purpose, phone)
    if not admin_settings.sms_enabled:
        return OtpDelivery(False, code, "disabled")
    if not (admin_settings.sms_api_key or "").strip():
        logger.warning("پیامک روشن است ولی کلیدِ API تنظیم نشده؛ کد در چت نشان داده می‌شود.")
        return OtpDelivery(False, code, "no_key")
    if await sent_recently(session, phone, purpose) >= MAX_SENDS_PER_PHONE_PER_HOUR:
        return OtpDelivery(False, code, "rate_limited")
    otp = await pending_otp(session, shop_owner_id, purpose)
    try:
        # سرشماره می‌تواند در دیتابیسِ قدیمی با ارقامِ فارسی مانده باشد؛ provider فقط لاتین می‌پذیرد.
        # قالبِ تنظیم‌نشده هم همین‌جا به پیش‌فرض تبدیل می‌شود تا هر provider یکسان صدا زده شود.
        status = await sms_service.get_sms_service(
            admin_settings.sms_api_key,
            sms_service.normalize_sender_digits(admin_settings.sms_sender_number),
            admin_settings.sms_otp_template or sms_service.DEFAULT_OTP_TEMPLATE,
        ).send_otp(phone, code)
    except sms_service.SmsServiceError as exc:
        logger.warning("ارسال پیامکِ OTP ناموفق بود: %s", exc)
        return OtpDelivery(False, code, "send_failed")
    if otp is not None:
        await mark_sent(session, otp, status)
    return OtpDelivery(True, code)


async def verify_otp(session: AsyncSession, shop_owner_id: int, purpose: str, code: str) -> bool:
    now = datetime.datetime.now(datetime.timezone.utc)
    result = await session.execute(
        select(OtpCode)
        .where(
            OtpCode.shop_owner_id == shop_owner_id,
            OtpCode.purpose == purpose,
            OtpCode.code == code,
            OtpCode.consumed.is_(False),
            OtpCode.expires_at > now,
        )
        .order_by(OtpCode.id.desc())
    )
    otp = result.scalar_one_or_none()
    if otp is None:
        return False
    otp.consumed = True
    await session.flush()
    return True
