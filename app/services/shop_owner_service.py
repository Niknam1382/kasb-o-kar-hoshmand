from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Referral, ShopBot, ShopOwner, TenantMode
from app.utils.referral import generate_referral_code
from app.utils.validators import normalize_iran_phone

VALID_BUSINESS_MODES = (TenantMode.SALES.value, TenantMode.CONSULTATION.value)


async def get_by_telegram_id(session: AsyncSession, telegram_id: int) -> ShopOwner | None:
    result = await session.execute(select(ShopOwner).where(ShopOwner.telegram_id == telegram_id))
    return result.scalar_one_or_none()


async def get_by_id(session: AsyncSession, owner_id: int) -> ShopOwner | None:
    return await session.get(ShopOwner, owner_id)


async def get_by_referral_code(session: AsyncSession, code: str) -> ShopOwner | None:
    result = await session.execute(select(ShopOwner).where(ShopOwner.referral_code == code))
    return result.scalar_one_or_none()


async def ids_by_telegram_ids(session: AsyncSession, telegram_ids: list[int]) -> dict[int, int]:
    """نگاشتِ «شناسهٔ تلگرام ← شناسهٔ دیتابیسی» فقط برایِ کسانی که وجود دارند.

    P21-E (F8): دامنهٔ ادمینِ عملیاتی را سوپرادمین با «آیدیِ تلگرام» وارد می‌کند (چیزی که می‌بیند)
    ولی ذخیره با شناسهٔ داخلی می‌شود؛ ناشناخته‌ها بی‌صدا رد نمی‌شوند — UI آن‌ها را گزارش می‌دهد.
    """
    if not telegram_ids:
        return {}
    result = await session.execute(select(ShopOwner.telegram_id, ShopOwner.id).where(ShopOwner.telegram_id.in_(list(telegram_ids))))
    return {int(telegram_id): int(owner_id) for telegram_id, owner_id in result.all()}


async def get_by_ids(session: AsyncSession, owner_ids: list[int]) -> dict[int, ShopOwner]:
    """نگاشتِ «شناسهٔ داخلی ← ردیفِ صاحبِ حساب» در یکِ کوئری (فهرست‌هایِ پنلِ ادمین).

    ترتیبِ ورودی تضمین نمی‌شود؛ فراخوان باید خودش از همان لیستِ ردیف‌ها استفاده کند. شناسهٔ
    تکراری حذف می‌شود تا `IN` بی‌دوده بلند نشود و شناسهٔ ناموجود بی‌صدا از نگاشت بیرون می‌ماند
    (فهرستِ ادمین نباید به‌خاطرِ یکِ ردیفِ پاک‌شده پایین بیاید).
    """
    ids = [int(owner_id) for owner_id in dict.fromkeys(owner_ids or [])]
    if not ids:
        return {}
    result = await session.execute(select(ShopOwner).where(ShopOwner.id.in_(ids)))
    return {owner.id: owner for owner in result.scalars().all()}


async def get_all_registered(session: AsyncSession) -> list[ShopOwner]:
    result = await session.execute(select(ShopOwner).where(ShopOwner.registration_completed.is_(True)).order_by(ShopOwner.id))
    return list(result.scalars().all())


async def get_or_create_shop_owner(
    session: AsyncSession,
    telegram_id: int,
    referred_by_code: str | None = None,
    newcomer_name: str | None = None,
) -> ShopOwner:
    owner = await get_by_telegram_id(session, telegram_id)
    if owner is not None:
        return owner

    referred_by_id = None
    if referred_by_code:
        referrer = await get_by_referral_code(session, referred_by_code)
        if referrer is not None:
            referred_by_id = referrer.id

    code = generate_referral_code()
    while await get_by_referral_code(session, code) is not None:
        code = generate_referral_code()

    owner = ShopOwner(telegram_id=telegram_id, referral_code=code, referred_by_id=referred_by_id)
    session.add(owner)
    await session.flush()

    if referred_by_id is not None:
        referral = Referral(referrer_id=referred_by_id, referred_id=owner.id)
        session.add(referral)
        await session.flush()
        # P42 · موردِ ۲۶: «فلانی با لینکِ تو وارد ربات شد». از صفِ اعلان‌ها می‌رود (نه ارسالِ
        # مستقیم)، تا هیچ فراخوانیِ شبکه‌ای وسطِ نوشتنِ ثبت‌نام نباشد و اگر تلگرام لحظه‌ای
        # قطع بود، خبر در تلاشِ بعدی برسد (qid: خودِ ردیفِ دعوت ⇒ هر دعوت یکِ خبر).
        await _notify_referrer_of_join(session, referral, newcomer_name)

    return owner


async def _notify_referrer_of_join(session: AsyncSession, referral: Referral, newcomer_name: str | None) -> None:
    referrer = await session.get(ShopOwner, referral.referrer_id)
    if referrer is None:
        return
    from app.bots.main_bot import texts
    from app.services import notification_service

    label = (newcomer_name or "").strip() or "یکِ کاربرِ تازه"
    await notification_service.enqueue(
        session,
        referrer.telegram_id,
        texts.referrer_join_notification(label),
        owner_id=referrer.id,
        label="referral_join",
        dedupe_key=f"referral-join:{referral.id}",
    )


async def complete_registration(
    session: AsyncSession,
    owner: ShopOwner,
    first_name: str,
    last_name: str,
    phone_number: str,
    email: str,
    phone_verified: bool,
    email_verified: bool,
    *,
    business_mode: str | None = None,
    username: str | None = None,
) -> ShopOwner:
    owner.first_name = first_name
    owner.last_name = last_name
    owner.phone_number = phone_number
    owner.email = email
    owner.phone_verified = phone_verified
    owner.email_verified = email_verified
    owner.registration_completed = True
    if username is not None:
        owner.username = username or None
    await session.flush()
    if business_mode is not None:
        await set_business_mode(session, owner, business_mode)
    return owner


def normalize_business_mode(mode) -> str:
    """TenantMode یا رشته → «sales» / «consultation». مقدارِ ناشناخته ValueError می‌ده (callbackِ جعلی نباید مود رو خراب کنه)."""
    value = mode.value if hasattr(mode, "value") else str(mode)
    if value not in VALID_BUSINESS_MODES:
        raise ValueError(f"مودِ نامعتبر: {value!r}")
    return value


async def set_business_mode(session: AsyncSession, owner: ShopOwner, mode) -> ShopBot | None:
    """
    منبعِ حقیقتِ واحدِ مود (A3): ShopOwner.business_mode و (اگه رباتی داره) ShopBot.tenant_mode رو هم‌زمان می‌نویسه.
    هیچ داده‌ای پاک نمی‌شه (قاعده‌یِ ۸). چکِ «سفارشِ باز» وظیفه‌یِ فراخوانه (count_open_orders).
    """
    value = normalize_business_mode(mode)
    owner.business_mode = value
    result = await session.execute(select(ShopBot).where(ShopBot.shop_owner_id == owner.id))
    shop_bot = result.scalar_one_or_none()
    if shop_bot is not None:
        shop_bot.tenant_mode = TenantMode(value)
    await session.flush()
    return shop_bot


async def find_other_by_phone(session: AsyncSession, phone: str, exclude_owner_id: int | None = None) -> ShopOwner | None:
    """فروشگاه‌داری (غیر از exclude_owner_id) که همین موبایل رو داره؛ موبایل با هر فرمتی (09…/+98…/فارسی) مقایسه می‌شه."""
    target = normalize_iran_phone(phone)
    if target is None:
        return None
    result = await session.execute(select(ShopOwner).where(ShopOwner.phone_number.is_not(None)))
    for other in result.scalars().all():
        if other.id != exclude_owner_id and normalize_iran_phone(other.phone_number) == target:
            return other
    return None


async def find_other_by_email(session: AsyncSession, email: str, exclude_owner_id: int | None = None) -> ShopOwner | None:
    result = await session.execute(select(ShopOwner).where(func.lower(ShopOwner.email) == email.strip().lower()))
    for other in result.scalars().all():
        if other.id != exclude_owner_id:
            return other
    return None


async def update_name(session: AsyncSession, owner: ShopOwner, *, first_name: str | None = None, last_name: str | None = None) -> ShopOwner:
    if first_name is not None:
        owner.first_name = first_name
    if last_name is not None:
        owner.last_name = last_name
    await session.flush()
    return owner


async def update_phone(session: AsyncSession, owner: ShopOwner, phone_number: str, verified: bool) -> ShopOwner:
    owner.phone_number = phone_number
    owner.phone_verified = verified
    await session.flush()
    return owner


async def update_email(session: AsyncSession, owner: ShopOwner, email: str, verified: bool) -> ShopOwner:
    owner.email = email
    owner.email_verified = verified
    await session.flush()
    return owner
