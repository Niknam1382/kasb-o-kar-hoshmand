from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Referral, ShopOwner
from app.utils.referral import generate_referral_code


async def get_by_telegram_id(session: AsyncSession, telegram_id: int) -> ShopOwner | None:
    result = await session.execute(select(ShopOwner).where(ShopOwner.telegram_id == telegram_id))
    return result.scalar_one_or_none()


async def get_by_id(session: AsyncSession, owner_id: int) -> ShopOwner | None:
    return await session.get(ShopOwner, owner_id)


async def get_by_referral_code(session: AsyncSession, code: str) -> ShopOwner | None:
    result = await session.execute(select(ShopOwner).where(ShopOwner.referral_code == code))
    return result.scalar_one_or_none()


async def get_all_registered(session: AsyncSession) -> list[ShopOwner]:
    result = await session.execute(select(ShopOwner).where(ShopOwner.registration_completed.is_(True)).order_by(ShopOwner.id))
    return list(result.scalars().all())


async def get_or_create_shop_owner(session: AsyncSession, telegram_id: int, referred_by_code: str | None = None) -> ShopOwner:
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
        session.add(Referral(referrer_id=referred_by_id, referred_id=owner.id))
        await session.flush()

    return owner


async def complete_registration(
    session: AsyncSession,
    owner: ShopOwner,
    first_name: str,
    last_name: str,
    phone_number: str,
    email: str,
    phone_verified: bool,
    email_verified: bool,
) -> ShopOwner:
    owner.first_name = first_name
    owner.last_name = last_name
    owner.phone_number = phone_number
    owner.email = email
    owner.phone_verified = phone_verified
    owner.email_verified = email_verified
    owner.registration_completed = True
    await session.flush()
    return owner
