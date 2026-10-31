from __future__ import annotations

import datetime
import secrets

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import (
    DiscountCode,
    Payment,
    PaymentMethod,
    PaymentPurpose,
    PaymentStatus,
    ShopOwner,
    Subscription,
    WalletCharge,
    WalletTransactionReason,
)
from app.services import discount_service, referral_service, subscription_service, wallet_service
from app.services.admin_settings_service import get_admin_settings


async def get_by_id(session: AsyncSession, payment_id: int) -> Payment | None:
    return await session.get(Payment, payment_id)


async def get_history_by_owner(session: AsyncSession, shop_owner_id: int, limit: int = 20) -> list[Payment]:
    result = await session.execute(
        select(Payment).where(Payment.shop_owner_id == shop_owner_id).order_by(Payment.id.desc()).limit(limit)
    )
    return list(result.scalars().all())


async def get_pending_payments(session: AsyncSession, limit: int = 20) -> list[Payment]:
    result = await session.execute(
        select(Payment).where(Payment.status == PaymentStatus.PENDING).order_by(Payment.id.asc()).limit(limit)
    )
    return list(result.scalars().all())


async def get_by_zarinpal_authority(session: AsyncSession, authority: str) -> Payment | None:
    result = await session.execute(select(Payment).where(Payment.zarinpal_authority == authority))
    return result.scalar_one_or_none()


async def get_by_bale_payload(session: AsyncSession, payload: str) -> Payment | None:
    result = await session.execute(select(Payment).where(Payment.bale_invoice_payload == payload))
    return result.scalar_one_or_none()


async def _is_first_approved_payment(session: AsyncSession, shop_owner_id: int, excluding_payment_id: int) -> bool:
    result = await session.execute(
        select(func.count())
        .select_from(Payment)
        .where(
            Payment.shop_owner_id == shop_owner_id,
            Payment.status == PaymentStatus.APPROVED,
            Payment.id != excluding_payment_id,
        )
    )
    return result.scalar_one() == 0


async def _amount_currently_reserved(session: AsyncSession, amount: int) -> bool:
    now = datetime.datetime.now(datetime.timezone.utc)
    result = await session.execute(
        select(Payment).where(
            Payment.final_amount == amount, Payment.status == PaymentStatus.PENDING, Payment.reserved_until > now
        )
    )
    return result.scalar_one_or_none() is not None


async def _generate_unique_amount(session: AsyncSession, base_amount: int) -> int:
    for _ in range(30):
        suffix = secrets.randbelow(90) + 10
        candidate = base_amount + suffix
        if not await _amount_currently_reserved(session, candidate):
            return candidate
    raise RuntimeError("ساخت مبلغ منحصربه‌فرد بعد از چند تلاش ناموفق بود.")


async def create_card_to_card_payment(
    session: AsyncSession,
    owner: ShopOwner,
    base_amount: int,
    discount: DiscountCode | None,
    duration_months: int | None = None,
    purpose: PaymentPurpose = PaymentPurpose.SUBSCRIPTION,
) -> Payment:
    admin_settings = await get_admin_settings(session)
    # نکته‌ی مهم: تخفیف همین‌جا و به‌صورت داخلی روی base_amount اعمال می‌شه، نه
    # اینکه از caller انتظار بره base_amount از قبل تخفیف‌خورده باشه — این باعث
    # می‌شد قبلاً مبلغ نهایی کارت‌به‌کارت، تخفیف رو نادیده بگیره.
    discounted_amount = discount_service.apply_discount(base_amount, discount) if discount else base_amount
    final_amount = await _generate_unique_amount(session, discounted_amount)

    payment = Payment(
        shop_owner_id=owner.id,
        purpose=purpose,
        duration_months=duration_months,
        base_amount=base_amount,
        final_amount=final_amount,
        method=PaymentMethod.CARD_TO_CARD,
        status=PaymentStatus.PENDING,
        discount_code_id=discount.id if discount else None,
        reserved_until=datetime.datetime.now(datetime.timezone.utc)
        + datetime.timedelta(minutes=admin_settings.payment_reservation_minutes),
    )
    session.add(payment)
    await session.flush()
    return payment


async def create_zarinpal_payment(
    session: AsyncSession,
    owner: ShopOwner,
    base_amount: int,
    discount: DiscountCode | None,
    authority: str,
    duration_months: int | None = None,
    purpose: PaymentPurpose = PaymentPurpose.SUBSCRIPTION,
) -> Payment:
    discounted_amount = discount_service.apply_discount(base_amount, discount) if discount else base_amount

    payment = Payment(
        shop_owner_id=owner.id,
        purpose=purpose,
        duration_months=duration_months,
        base_amount=base_amount,
        final_amount=discounted_amount,
        method=PaymentMethod.ZARINPAL,
        status=PaymentStatus.PENDING,
        discount_code_id=discount.id if discount else None,
        zarinpal_authority=authority,
    )
    session.add(payment)
    await session.flush()
    return payment


async def create_bale_payment(
    session: AsyncSession,
    owner: ShopOwner,
    base_amount: int,
    discount: DiscountCode | None,
    invoice_payload: str,
    duration_months: int | None = None,
    purpose: PaymentPurpose = PaymentPurpose.SUBSCRIPTION,
) -> Payment:
    discounted_amount = discount_service.apply_discount(base_amount, discount) if discount else base_amount

    payment = Payment(
        shop_owner_id=owner.id,
        purpose=purpose,
        duration_months=duration_months,
        base_amount=base_amount,
        final_amount=discounted_amount,
        method=PaymentMethod.BALE_PAY,
        status=PaymentStatus.PENDING,
        discount_code_id=discount.id if discount else None,
        bale_invoice_payload=invoice_payload,
    )
    session.add(payment)
    await session.flush()
    return payment


async def attach_receipt(session: AsyncSession, payment: Payment, file_id: str) -> None:
    payment.receipt_file_id = file_id
    await session.flush()


async def _apply_payment_effect(session: AsyncSession, payment: Payment) -> Subscription | WalletCharge:
    """بسته به هدفِ پرداخت، اثرِ واقعیِ اون رو اعمال می‌کنه: برای شارژِ کیف‌پول،
    مبلغ به کیف‌پولِ فروشگاه‌دار اضافه می‌شه؛ برای اشتراک (میراثی)، همون منطقِ
    قبلیِ تمدید/فعال‌سازیِ اشتراک اجرا می‌شه."""
    if payment.purpose == PaymentPurpose.WALLET_TOPUP:
        owner = await session.get(ShopOwner, payment.shop_owner_id)
        return await wallet_service.add_charge(
            session, owner, payment.final_amount, reason=WalletTransactionReason.TOPUP, payment_id=payment.id
        )
    return await subscription_service.purchase_or_renew(session, payment.shop_owner_id, payment.duration_months)


async def approve_zarinpal_payment(session: AsyncSession, payment: Payment, ref_id: str) -> tuple[Subscription | WalletCharge, dict | None]:
    is_first = await _is_first_approved_payment(session, payment.shop_owner_id, payment.id)

    payment.status = PaymentStatus.APPROVED
    payment.zarinpal_ref_id = ref_id
    payment.reviewed_at = datetime.datetime.now(datetime.timezone.utc)
    await session.flush()

    if payment.discount_code_id is not None:
        await discount_service.record_usage(session, payment.discount_code_id, payment.shop_owner_id, payment.id)

    effect = await _apply_payment_effect(session, payment)

    reward_info = None
    if is_first:
        reward_info = await referral_service.process_referral_reward(session, payment.shop_owner_id, payment.final_amount)

    return effect, reward_info


async def approve_bale_payment(session: AsyncSession, payment: Payment, transaction_id: str) -> tuple[Subscription | WalletCharge, dict | None]:
    is_first = await _is_first_approved_payment(session, payment.shop_owner_id, payment.id)

    payment.status = PaymentStatus.APPROVED
    payment.bale_transaction_id = transaction_id
    payment.reviewed_at = datetime.datetime.now(datetime.timezone.utc)
    await session.flush()

    if payment.discount_code_id is not None:
        await discount_service.record_usage(session, payment.discount_code_id, payment.shop_owner_id, payment.id)

    effect = await _apply_payment_effect(session, payment)

    reward_info = None
    if is_first:
        reward_info = await referral_service.process_referral_reward(session, payment.shop_owner_id, payment.final_amount)

    return effect, reward_info


async def approve_payment(session: AsyncSession, payment: Payment, admin_telegram_id: int) -> tuple[Subscription | WalletCharge, dict | None]:
    is_first = await _is_first_approved_payment(session, payment.shop_owner_id, payment.id)

    payment.status = PaymentStatus.APPROVED
    payment.reviewed_at = datetime.datetime.now(datetime.timezone.utc)
    payment.reviewed_by_admin_id = admin_telegram_id
    await session.flush()

    if payment.discount_code_id is not None:
        await discount_service.record_usage(session, payment.discount_code_id, payment.shop_owner_id, payment.id)

    effect = await _apply_payment_effect(session, payment)

    reward_info = None
    if is_first:
        reward_info = await referral_service.process_referral_reward(session, payment.shop_owner_id, payment.final_amount)

    return effect, reward_info


async def reject_payment(
    session: AsyncSession, payment: Payment, admin_telegram_id: int | None, reason: str | None = None
) -> None:
    payment.status = PaymentStatus.REJECTED
    payment.reviewed_at = datetime.datetime.now(datetime.timezone.utc)
    payment.reviewed_by_admin_id = admin_telegram_id
    payment.rejection_reason = reason
    await session.flush()
