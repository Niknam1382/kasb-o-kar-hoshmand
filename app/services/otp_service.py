from __future__ import annotations

import datetime
import secrets

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import OtpCode

OTP_TTL_MINUTES = 5


async def generate_otp(session: AsyncSession, shop_owner_id: int, purpose: str) -> str:
    code = f"{secrets.randbelow(1000000):06d}"
    otp = OtpCode(
        shop_owner_id=shop_owner_id,
        code=code,
        purpose=purpose,
        expires_at=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=OTP_TTL_MINUTES),
    )
    session.add(otp)
    await session.flush()
    return code


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
