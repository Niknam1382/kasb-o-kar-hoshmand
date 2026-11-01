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
from app.services import discount_service, referral_service, shop_bot_service, shop_prefs_service, subscription_service, wallet_service
from app.services.admin_settings_service import get_admin_settings
from app.utils.validators import format_toman

# PHASE 5A — کمترینِ مبلغِ شارژِ کیف‌پول.
# قاعدهٔ دامنه (مستند، نه حدس): حداقل فقط رویِ `PaymentPurpose.WALLET_TOPUP` اثر می‌کند، چون خواسته
# «حداقلِ شارژِ کیف‌پول» است نه «حداقلِ خریدِ اشتراک». مبلغِ *پرداخت‌شده* می‌تواند با کدِ تخفیف کمتر
# از این عدد شود؛ آنچه مقیده شدنِ شارژ را تعیین می‌کند `base_amount` (مقدارِ اعتبار) است.
DEFAULT_MIN_TOPUP_TOMAN = 50_000
MIN_TOPUP_HARD_FLOOR_TOMAN = 1_000  # اگر تنظیمات خراب/صفر/منفی باشد، این کفِ ایمنی در کد می‌ماند


class MinRechargeAmountError(ValueError):
    """مبلغِ شارژ از حداقلِ مجازِ پلتفرم کمتر است. پیامِ فارسی و بدونِ هیچ رازِ فنی."""

    def __init__(self, minimum_toman: int) -> None:
        self.minimum_toman = minimum_toman
        super().__init__(f"حداقلِ مبلغِ شارژ {format_toman(minimum_toman)} است.")


async def minimum_recharge_toman(session: AsyncSession) -> int:
    """عددِ مؤثرِ حداقل: تنظیماتِ ادمین، ولی هیچ‌وقت زیرِ کفِ ایمنیِ کد نه."""
    admin_settings = await get_admin_settings(session)
    try:
        configured = int(admin_settings.min_topup_amount_toman)
    except (TypeError, ValueError):
        configured = DEFAULT_MIN_TOPUP_TOMAN
    return max(MIN_TOPUP_HARD_FLOOR_TOMAN, configured)


async def ensure_recharge_amount_allowed(session: AsyncSession, base_amount: int, purpose: PaymentPurpose) -> int:
    """قبلِ ساختِ هر ردیفِ پرداخت صدا می‌شود؛ None نمی‌دهد و در صورتِ نامعبری `MinRechargeAmountError`."""
    if purpose != PaymentPurpose.WALLET_TOPUP:
        return 0
    try:
        amount = int(base_amount)
    except (TypeError, ValueError) as exc:
        raise MinRechargeAmountError(await minimum_recharge_toman(session)) from exc
    minimum = await minimum_recharge_toman(session)
    if amount < minimum:
        raise MinRechargeAmountError(minimum)
    return amount


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
    await ensure_recharge_amount_allowed(session, base_amount, purpose)  # PHASE 5A (سمتِ سرور)
    admin_settings = await get_admin_settings(session)
    # نکته‌ی مهم: تخفیف همین‌جا و به‌صورت داخلی روی base_amount اعمال می‌شه، نه
    # اینکه از caller انتظار بره base_amount از قبل تخفیف‌خورده باشه — این باعث
    # می‌شد قبلاً مبلغ نهایی کارت‌به‌کارت، تخفیف رو نادیده بگیره.
    discounted_amount = discount_service.apply_discount(base_amount, discount) if discount else base_amount
    final_amount = await _generate_unique_amount(session, discounted_amount)

    # A5: مهلتِ رزروِ مبلغ per-shop است؛ NULL یعنی همان پیش‌فرضِ سراسری.
    reservation_minutes = shop_prefs_service.resolve(
        shop_prefs_service.PAYMENT_RESERVATION, await shop_bot_service.get_by_owner(session, owner), admin_settings
    )

    payment = Payment(
        shop_owner_id=owner.id,
        purpose=purpose,
        duration_months=duration_months,
        base_amount=base_amount,
        final_amount=final_amount,
        method=PaymentMethod.CARD_TO_CARD,
        status=PaymentStatus.PENDING,
        discount_code_id=discount.id if discount else None,
        reserved_until=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=reservation_minutes),
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
    await ensure_recharge_amount_allowed(session, base_amount, purpose)  # PHASE 5A (سمتِ سرور)
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
    await ensure_recharge_amount_allowed(session, base_amount, purpose)  # PHASE 5A (سمتِ سرور)
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


async def get_open_receipt_payments(session: AsyncSession, shop_owner_id: int, limit: int = 10) -> list[Payment]:
    """A7: پرداخت‌هایِ کارت‌به‌کارتِ در انتظارِ رسیدِ خودِ این فروشگاه‌دار (برایِ «📂 پرداخت‌هایِ باز»)."""
    result = await session.execute(
        select(Payment)
        .where(
            Payment.shop_owner_id == shop_owner_id,
            Payment.status == PaymentStatus.PENDING,
            Payment.method == PaymentMethod.CARD_TO_CARD,
            Payment.receipt_file_id.is_(None),
            Payment.receipt_text.is_(None),
        )
        .order_by(Payment.id.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def _exists_other(session: AsyncSession, column, value: str, payment_id: int) -> bool:
    result = await session.execute(
        select(func.count()).select_from(Payment).where(column == value, Payment.id != payment_id)
    )
    return result.scalar_one() > 0


async def attach_text_receipt(
    session: AsyncSession, payment: Payment, text: str, tracking: str | None
) -> tuple[bool, bool]:
    """A7: رسیدِ متنیِ شارژِ اعتبار (همان قاعده‌یِ سمتِ فروشگاه). تکراری بودن فقط **پرچم** می‌خورد، هرگز ردِ خودکار —
    تصمیم با ادمین است. برمی‌گرداند: (متنِ تکراری, پیگیریِ تکراری)."""
    from app.services import order_payment_service

    digest = order_payment_service.receipt_sha256(text.encode("utf-8"))
    dup_text = await _exists_other(session, Payment.receipt_sha256, digest, payment.id)
    dup_tracking = bool(tracking) and await _exists_other(session, Payment.receipt_tracking_ref, tracking, payment.id)
    payment.receipt_text = text[: order_payment_service.RECEIPT_TEXT_MAX_LENGTH]
    payment.receipt_tracking_ref = (tracking[:64] if tracking else None)
    payment.receipt_sha256 = digest
    payment.receipt_flags = order_payment_service.payment_flags(duplicate_hash=dup_text, duplicate_tracking=dup_tracking)
    await session.flush()
    return dup_text, dup_tracking


async def _claim_for_approval(session: AsyncSession, payment: Payment) -> bool:
    """قفلِ سطریِ ردیفِ پرداخت + مطمئن‌شدن از PENDING بودنش در DB (نه در حافظهٔ پایتون).

    سه مسیر می‌توانند یک پرداخت را «تایید» کنند: وب‌هوک/getUpdates بله، صفحهٔ بازگشتِ
    زرین‌پال (که کاربر می‌تواند رفرشش کند) و تاییدِ دستیِ ادمین. هر سه یک خوانشِ ساده
    می‌کنند و بعد بینِ آن خوانش و نوشتن، یک استعلامِ شبکه (چند صد میلی‌ثانیه) فاصله است ⇒
    بدونِ قفل، هر دو «برنده» می‌شوند و کیف‌پول دوباره شارژ می‌شود. اینجا قفل نگه‌داشته
    می‌ماند تا commit؛ بازنده `False` می‌گیرد و هیچ اثری (اعتبار، تخفیف، پاداشِ معرف) نمی‌سازد."""
    result = await session.execute(
        select(Payment)
        .where(Payment.id == payment.id, Payment.status == PaymentStatus.PENDING)
        .with_for_update()
    )
    return result.scalar_one_or_none() is not None


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


async def approve_zarinpal_payment(session: AsyncSession, payment: Payment, ref_id: str) -> tuple[Subscription | WalletCharge | None, dict | None]:
    if not await _claim_for_approval(session, payment):
        # این پرداخت پیش‌تر تایید/رد شده (وب‌هوکِ تکراری یا دو تاییدِ هم‌زمان) ⇒ هیچ اثری نمی‌سازیم.
        return None, None
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


async def approve_bale_payment(session: AsyncSession, payment: Payment, transaction_id: str) -> tuple[Subscription | WalletCharge | None, dict | None]:
    if not await _claim_for_approval(session, payment):
        # این پرداخت پیش‌تر تایید/رد شده (وب‌هوکِ تکراری یا دو تاییدِ هم‌زمان) ⇒ هیچ اثری نمی‌سازیم.
        return None, None
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


async def approve_payment(session: AsyncSession, payment: Payment, admin_telegram_id: int) -> tuple[Subscription | WalletCharge | None, dict | None]:
    if not await _claim_for_approval(session, payment):
        # این پرداخت پیش‌تر تایید/رد شده (وب‌هوکِ تکراری یا دو تاییدِ هم‌زمان) ⇒ هیچ اثری نمی‌سازیم.
        return None, None
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
