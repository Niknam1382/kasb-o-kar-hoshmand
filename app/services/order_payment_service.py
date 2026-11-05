"""پرداختِ سفارش — کارت‌به‌کارت با رسید (C6) و پایه‌یِ مشترکِ پرداختِ آنلاین (C7/M).

اصول: (۱) هیچ پرداختی بدونِ تاییدِ فروشگاه‌دار (کارت) یا تاییدِ سمتِ سرورِ درگاه (آنلاین) `paid` نمی‌شه؛
(۲) همه‌یِ گذارها از `order_transition_service.transition_group` (قفل/ایدمپوتنسی/رزرو/خط‌زمان)؛
(۳) تصمیمِ فروشگاه‌دار و تاییدِ درگاه ایدمپوتنت‌اند؛ (۴) هر خطا/وضعیتِ ناشناخته ⇒ `needs_review`، نه سکوتِ بی‌صدا.
اعلان‌ها کارِ هندلره (بعد از commit)؛ این سرویس پیام نمی‌فرسته.
"""

from __future__ import annotations

import datetime
import hashlib
import re

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import OrderConsultation, OrderPayment, OrderStatus
from app.services import order_state, order_transition_service, product_service
from app.services.payment_settings_service import deadline_minutes, normalize_digits

# --- وضعیتِ پرداخت ---
P_INITIATED = "initiated"
P_SUBMITTED = "submitted"
P_APPROVED = "approved"
P_REJECTED = "rejected"
P_EXPIRED = "expired"
P_FAILED = "failed"
P_PAID = "paid"
ACTIVE_PAYMENT_STATUSES = (P_INITIATED, P_SUBMITTED)

MAX_RECEIPT_BYTES = 5 * 1024 * 1024
TRACKING_MIN_DIGITS = 6

_CLAIM_RE = re.compile(r"(پرداخت\s*(کردم|شد|انجام)|واریز\s*(کردم|شد)|کارت\s*به\s*کارت\s*(کردم|شد)|پول\s*(رو|را)?\s*(ریختم|فرستادم|زدم)|حساب\s*(رو|را)?\s*(پر|واریز))")


def now_utc() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


# ---------------------------------------------------------------------------
# منطقِ خالص
# ---------------------------------------------------------------------------
def looks_like_payment_claim(text: str) -> bool:
    """«پرداخت کردم/واریز کردم/…» — برایِ نگهبانِ سفارشِ awaiting_payment (به‌جایِ صدا زدنِ AI)."""
    normalized = normalize_digits(text or "").replace("\u200c", " ").replace("ي", "ی").replace("ك", "ک")
    return bool(_CLAIM_RE.search(normalized))


def extract_tracking_ref(text: str) -> str | None:
    """شماره‌پیگیری = دنباله‌ای از ≥۶ رقم (ارقامِ فارسی نرمال)؛ وگرنه None. حداکثر ۳۲ رقم."""
    digits = re.sub(r"[\s\-_.]", "", normalize_digits(text or ""))
    if digits.isascii() and digits.isdecimal() and TRACKING_MIN_DIGITS <= len(digits) <= 32:
        return digits
    return None


RECEIPT_TEXT_MIN_LENGTH = 8
RECEIPT_TEXT_MAX_LENGTH = 1000
RECEIPT_TEXT_MIN_DIGITS = 4
_LABELED_TRACKING_RE = re.compile(r"(?:شماره\s*)?(?:پیگیری|رهگیری|مرجع|tracking|ref)[^\d]{0,14}(\d{6,32})", re.IGNORECASE)


def parse_receipt_text(raw: str | None) -> tuple[str, str | None] | None:
    """رسیدِ متنی (W5): متنِ آزادِ کپی‌شده از اپِ بانک/پیامک. معتبر ⇒ (متنِ تمیز, شماره‌پیگیریِ برچسب‌دار یا None)؛
    خیلی کوتاه/بلند یا بدونِ حداقل ۴ رقم (مبلغ/تاریخ/پیگیری) ⇒ None. شماره‌پیگیری فقط وقتی استخراج می‌شه که کنارِ برچسبش
    («پیگیری/رهگیری/مرجع») باشد — مبلغ و شماره‌کارت هرگز به‌عنوانِ پیگیری برداشته نمی‌شن."""
    text = " ".join((raw or "").replace("\u200c", " ").split())
    if not (RECEIPT_TEXT_MIN_LENGTH <= len(text) <= RECEIPT_TEXT_MAX_LENGTH):
        return None
    normalized = normalize_digits(text)
    if sum(ch.isdigit() for ch in normalized) < RECEIPT_TEXT_MIN_DIGITS:
        return None
    match = _LABELED_TRACKING_RE.search(normalized)
    return text, (match.group(1) if match else None)


def receipt_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def payment_flags(*, duplicate_hash: bool, duplicate_tracking: bool) -> str | None:
    flags = []
    if duplicate_hash:
        flags.append("dup_file")
    if duplicate_tracking:
        flags.append("dup_tracking")
    return ",".join(flags) or None


# ---------------------------------------------------------------------------
# DB
# ---------------------------------------------------------------------------
async def group_rows(session: AsyncSession, shop_bot_id: int, group_key: str, *, lock: bool = False) -> list[OrderConsultation]:
    if group_key.startswith("o") and group_key[1:].isdecimal():
        query = select(OrderConsultation).where(OrderConsultation.id == int(group_key[1:]), OrderConsultation.shop_bot_id == shop_bot_id)
    else:
        query = select(OrderConsultation).where(
            OrderConsultation.cart_checkout_group_id == group_key, OrderConsultation.shop_bot_id == shop_bot_id
        )
    query = query.order_by(OrderConsultation.id)
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    return list((await session.execute(query)).scalars().all())


def set_group_deadline(rows: list[OrderConsultation], minutes: int, *, now: datetime.datetime | None = None) -> datetime.datetime:
    expires = (now or now_utc()) + datetime.timedelta(minutes=minutes)
    for row in rows:
        row.reservation_expires_at = expires
    return expires


async def count_attempts(session: AsyncSession, shop_bot_id: int, group_id: str, method: str) -> int:
    result = await session.execute(
        select(func.count())
        .select_from(OrderPayment)
        .where(OrderPayment.shop_bot_id == shop_bot_id, OrderPayment.group_id == group_id, OrderPayment.method == method)
    )
    return int(result.scalar_one())


async def get_active_payment(session: AsyncSession, shop_bot_id: int, group_id: str, method: str | None = None) -> OrderPayment | None:
    query = select(OrderPayment).where(
        OrderPayment.shop_bot_id == shop_bot_id,
        OrderPayment.group_id == group_id,
        OrderPayment.status.in_(ACTIVE_PAYMENT_STATUSES),
    )
    if method:
        query = query.where(OrderPayment.method == method)
    result = await session.execute(query.order_by(OrderPayment.id.desc()))
    return result.scalars().first()


async def get_payment_locked(session: AsyncSession, payment_id: int, shop_bot_id: int) -> OrderPayment | None:
    result = await session.execute(
        select(OrderPayment)
        .where(OrderPayment.id == payment_id, OrderPayment.shop_bot_id == shop_bot_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return result.scalar_one_or_none()


def _group_key_of(rows: list[OrderConsultation]) -> str:
    return order_transition_service.group_key(rows[0])


async def start_payment(
    session: AsyncSession, rows: list[OrderConsultation], method: str, settings_row, *, actor_ref: str | None = None, fresh: bool = False
) -> tuple[OrderPayment, datetime.datetime]:
    """شروعِ پرداخت با `method` برایِ گروهِ awaiting_payment: ساخت/استفادهٔ مجددِ OrderPayment فعال + تنظیمِ مهلتِ رزرو.
    ایدمپوتنت: اگه پرداختِ فعالِ همین روش هست همون برمی‌گرده (مهلت دوباره‌تنظیم نمی‌شه)."""
    first = rows[0]
    key = _group_key_of(rows)
    existing = await get_active_payment(session, first.shop_bot_id, key, method)
    if existing is not None and not fresh:
        expires = first.reservation_expires_at or set_group_deadline(rows, deadline_minutes(settings_row, method))
        return existing, expires
    if fresh and existing is not None:
        existing.status = P_EXPIRED
    expires = set_group_deadline(rows, deadline_minutes(settings_row, method))
    attempt = await count_attempts(session, first.shop_bot_id, key, method) + 1
    payment = OrderPayment(
        group_id=key,
        shop_bot_id=first.shop_bot_id,
        method=method,
        status=P_INITIATED,
        amount_toman=order_transition_service.group_total_toman(rows),
        attempt_no=attempt,
    )
    session.add(payment)
    for row in rows:
        row.payment_method = method
    await session.flush()
    return payment, expires


class ReceiptError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code  # too_many_attempts | not_awaiting | no_payment


async def submit_receipt(
    session: AsyncSession,
    rows: list[OrderConsultation],
    settings_row,
    *,
    file_sha256: str | None,
    tracking_ref: str | None,
    receipt_text: str | None = None,
) -> OrderPayment:
    """ثبتِ رسید ⇒ پرداخت `submitted` + سفارش `receipt_submitted` + تمدیدِ رزرو تا `receipt_review_hold`.
    تکراری‌بودن فقط پرچم است (هرگز خودکار رد/تایید)."""
    first = rows[0]
    key = _group_key_of(rows)
    if not all(order_state.value_of(r.status) == order_state.AWAITING_PAYMENT for r in rows):
        raise ReceiptError("not_awaiting")
    payment = await get_active_payment(session, first.shop_bot_id, key, "card")
    if payment is None:
        raise ReceiptError("no_payment")
    attempts = await count_attempts(session, first.shop_bot_id, key, "card")
    if attempts > settings_row.max_receipt_attempts:
        raise ReceiptError("too_many_attempts")

    dup_hash = dup_track = False
    if file_sha256:
        dup_hash = bool(
            (
                await session.execute(
                    select(OrderPayment.id).where(
                        OrderPayment.shop_bot_id == first.shop_bot_id,
                        OrderPayment.receipt_sha256 == file_sha256,
                        OrderPayment.id != payment.id,
                        OrderPayment.status.in_((P_SUBMITTED, P_APPROVED)),
                    )
                )
            ).first()
        )
    if tracking_ref:
        dup_track = bool(
            (
                await session.execute(
                    select(OrderPayment.id).where(
                        OrderPayment.shop_bot_id == first.shop_bot_id,
                        OrderPayment.tracking_ref == tracking_ref,
                        OrderPayment.id != payment.id,
                        OrderPayment.status.in_((P_SUBMITTED, P_APPROVED)),
                    )
                )
            ).first()
        )
    payment.receipt_sha256 = file_sha256
    payment.tracking_ref = tracking_ref
    payment.receipt_text = receipt_text
    payment.flags = payment_flags(duplicate_hash=dup_hash, duplicate_tracking=dup_track)
    payment.status = P_SUBMITTED

    result = await order_transition_service.transition_group(
        session, rows[0], order_state.RECEIPT_SUBMITTED, actor_type="customer", actor_ref=str(first.customer_id)
    )
    if not result.ok:
        raise ReceiptError("not_awaiting")
    set_group_deadline(rows, settings_row.receipt_review_hold_minutes)
    await session.flush()
    return payment


class DecisionResult:
    late: bool = False  # تاییدِ رسیدِ کارت بعد از انقضا (W5 · 2.2)
    oversold: bool = False  # موقعِ رزروِ دوباره موجودی کم بود

    def __init__(self, ok: bool, changed: bool = False, reason: str | None = None, rows=None, payment=None, final_status: str | None = None) -> None:
        self.ok, self.changed, self.reason, self.rows, self.payment, self.final_status = ok, changed, reason, rows or [], payment, final_status


async def approve_payment(session: AsyncSession, payment_id: int, shop_bot_id: int, *, decided_by: str) -> DecisionResult:
    """تاییدِ رسید توسطِ فروشگاه‌دار ⇒ سفارش `paid`. دابل‌تپ ⇒ ok بدونِ تغییر."""
    payment = await get_payment_locked(session, payment_id, shop_bot_id)
    if payment is None:
        return DecisionResult(False, reason="not_found")
    rows = await group_rows(session, shop_bot_id, payment.group_id, lock=True)
    if not rows:
        return DecisionResult(False, reason="not_found")
    if payment.status == P_APPROVED:
        return DecisionResult(True, False, rows=rows, payment=payment, final_status=order_state.PAID)
    if (
        payment.status == P_EXPIRED
        and payment.method == "card"
        and (payment.receipt_sha256 or payment.tracking_ref)
        and {order_state.value_of(r.status) for r in rows} == {order_state.EXPIRED}
    ):
        # W5 · 2.2: رسیدِ ثبت‌شده‌ای که مهلتِ بررسیش تموم شده بود؛ فروشگاه‌دار هنوز می‌تونه تایید کنه
        # (مثلِ پرداختِ دیرهنگامِ آنلاین): دوباره رزرو ⇒ paid؛ موجودیِ ناکافی ⇒ پرچمِ نیازِ بررسی.
        oversold = await _reactivate_expired(session, rows)
        late_result = await order_transition_service.transition_group(
            session, rows[0], order_state.PAID, actor_type="owner", actor_ref=decided_by, reason="late_receipt_approval"
        )
        if not late_result.ok:
            return DecisionResult(False, reason="illegal", rows=rows, payment=payment)
        payment.status = P_APPROVED
        payment.decided_at = now_utc()
        payment.decided_by = decided_by[:32]
        payment.needs_review = oversold
        await session.flush()
        outcome = DecisionResult(True, True, rows=rows, payment=payment, final_status=order_state.PAID)
        outcome.late, outcome.oversold = True, oversold
        return outcome
    if payment.status != P_SUBMITTED:
        return DecisionResult(False, reason="illegal", rows=rows, payment=payment)
    result = await order_transition_service.transition_group(
        session, rows[0], order_state.PAID, actor_type="owner", actor_ref=decided_by
    )
    if not result.ok:
        return DecisionResult(False, reason="illegal", rows=rows, payment=payment)
    payment.status = P_APPROVED
    payment.decided_at = now_utc()
    payment.decided_by = decided_by[:32]
    await session.flush()
    return DecisionResult(True, True, rows=rows, payment=payment, final_status=order_state.PAID)


async def reject_payment(
    session: AsyncSession, payment_id: int, shop_bot_id: int, settings_row, *, reason: str, decided_by: str
) -> DecisionResult:
    """ردِ رسید: تلاشِ مجدد باقی‌مونده ⇒ سفارش برمی‌گرده `awaiting_payment` با مهلتِ تازه؛ وگرنه `rejected` (رزرو آزاد)."""
    payment = await get_payment_locked(session, payment_id, shop_bot_id)
    if payment is None:
        return DecisionResult(False, reason="not_found")
    rows = await group_rows(session, shop_bot_id, payment.group_id, lock=True)
    if not rows:
        return DecisionResult(False, reason="not_found")
    if payment.status == P_REJECTED:
        return DecisionResult(True, False, rows=rows, payment=payment, final_status=order_state.value_of(rows[0].status))
    if payment.status != P_SUBMITTED:
        return DecisionResult(False, reason="illegal", rows=rows, payment=payment)

    attempts = await count_attempts(session, shop_bot_id, payment.group_id, payment.method)
    can_retry = attempts < settings_row.max_receipt_attempts
    target = order_state.AWAITING_PAYMENT if can_retry else order_state.REJECTED
    result = await order_transition_service.transition_group(
        session, rows[0], target, actor_type="owner", actor_ref=decided_by, reason=reason
    )
    if not result.ok:
        return DecisionResult(False, reason="illegal", rows=rows, payment=payment)
    payment.status = P_REJECTED
    payment.reject_reason = reason[:1000]
    payment.decided_at = now_utc()
    payment.decided_by = decided_by[:32]
    if can_retry:
        set_group_deadline(rows, deadline_minutes(settings_row, payment.method))
    await session.flush()
    return DecisionResult(True, True, rows=rows, payment=payment, final_status=target)


async def mark_link_failed(session: AsyncSession, payment: OrderPayment, *, reason: str) -> None:
    """P25: لینکِ پرداخت ساخته شد ولی به دستِ مشتری نرسید (مثلاً آدرس را تلگرام رد کرد).

    فقط همین تلاشِ پرداخت باطل می‌شود؛ سفارش دست‌نخورده در `awaiting_payment` و با همان مهلت
    می‌ماند تا مشتری بتواند دوباره (با این روش یا روشِ دیگر) پرداخت کند. ایدمپوتنت است.
    """
    if payment.status in (P_PAID, P_APPROVED, P_FAILED):
        return
    payment.status = P_FAILED
    payment.reject_reason = reason[:1000]
    payment.decided_at = now_utc()
    payment.decided_by = "system"
    await session.flush()


async def expire_stale_payment_groups(session: AsyncSession) -> list[list[OrderConsultation]]:
    """جابِ انقضا (F7): گروه‌هایِ awaiting_payment/receipt_submitted با مهلتِ گذشته ⇒ `expired` + آزادسازیِ رزرو
    + پرداختِ فعالشون `expired`. گروه‌هایی که تغییر کردن برمی‌گردن (تا هندلر اطلاع بده). ایدمپوتنت."""
    now = now_utc()
    result = await session.execute(
        select(OrderConsultation)
        .where(
            OrderConsultation.status.in_((OrderStatus.AWAITING_PAYMENT, OrderStatus.RECEIPT_SUBMITTED)),
            OrderConsultation.reservation_expires_at.is_not(None),
            OrderConsultation.reservation_expires_at < now,
        )
        .order_by(OrderConsultation.reservation_expires_at.asc())
        .limit(order_state.EXPIRY_SCAN_BATCH)
    )
    seen: set[tuple[int, str]] = set()
    expired_groups: list[list[OrderConsultation]] = []
    for row in list(result.scalars().all()):
        key = (row.shop_bot_id, _group_key_of([row]))
        if key in seen:
            continue
        seen.add(key)
        transition = await order_transition_service.transition_group(
            session, row, order_state.EXPIRED, actor_type="system", reason="expired"
        )
        if transition.ok and transition.changed:
            expired_groups.append(transition.rows)
            actives = await session.execute(
                select(OrderPayment).where(
                    OrderPayment.shop_bot_id == key[0], OrderPayment.group_id == key[1], OrderPayment.status.in_(ACTIVE_PAYMENT_STATUSES)
                )
            )
            for payment in actives.scalars().all():
                payment.status = P_EXPIRED
    if expired_groups:
        await session.flush()
    return expired_groups


REVIEW_WARNING_LEAD = datetime.timedelta(hours=2)


async def due_review_warnings(session: AsyncSession, *, now: datetime.datetime | None = None) -> list[tuple[OrderPayment, list[OrderConsultation], float]]:
    """W5 · 2.2: رسیدهایِ `submitted` که تا انقضایِ بررسیشون ≤ ۲ ساعت مونده و هنوز هشدار نگرفتن.
    هر پرداخت دقیقاً یک‌بار علامت می‌خوره (`review_warned_at`) ⇒ جابِ ۶۰ثانیه‌ای تکرار نمی‌کنه. (پرداخت, ردیف‌ها, ساعتِ مانده)"""
    now = now or now_utc()
    result = await session.execute(
        select(OrderPayment).where(OrderPayment.status == P_SUBMITTED, OrderPayment.review_warned_at.is_(None)).with_for_update(skip_locked=True)
    )
    due: list[tuple[OrderPayment, list[OrderConsultation], float]] = []
    for payment in result.scalars().all():
        rows = await group_rows(session, payment.shop_bot_id, payment.group_id)
        expires = rows[0].reservation_expires_at if rows else None
        if expires is None or expires <= now or expires - now > REVIEW_WARNING_LEAD:
            continue
        payment.review_warned_at = now
        due.append((payment, rows, (expires - now).total_seconds() / 3600))
    if due:
        await session.flush()
    return due


async def expire_if_overdue(session: AsyncSession, rows: list[OrderConsultation]) -> bool:
    """expire-on-read (F7): مهلتِ این گروه گذشته؟ ⇒ همان لحظه `expired` (رزرو آزاد). فراخوان commit می‌کنه."""
    if not rows:
        return False
    first = rows[0]
    if order_state.value_of(first.status) not in (order_state.AWAITING_PAYMENT, order_state.RECEIPT_SUBMITTED):
        return False
    if first.reservation_expires_at is None or first.reservation_expires_at >= now_utc():
        return False
    transition = await order_transition_service.transition_group(
        session, first, order_state.EXPIRED, actor_type="system", reason="expired"
    )
    if not (transition.ok and transition.changed):
        return False
    key = _group_key_of(rows)
    actives = await session.execute(
        select(OrderPayment).where(
            OrderPayment.shop_bot_id == first.shop_bot_id, OrderPayment.group_id == key, OrderPayment.status.in_(ACTIVE_PAYMENT_STATUSES)
        )
    )
    for payment in actives.scalars().all():
        payment.status = P_EXPIRED
    await session.flush()
    return True


# ---------------------------------------------------------------------------
# پرداختِ آنلاین (بله‌پی / زرین‌پال) — فقط بعد از تاییدِ سمتِ سرورِ درگاه صدا زده می‌شه (B10/B11)
# ---------------------------------------------------------------------------
class OnlineResult:
    def __init__(self, ok: bool, changed: bool = False, rows=None, payment=None, late: bool = False, needs_review: bool = False, final_status: str | None = None, oversold: bool = False) -> None:
        self.ok, self.changed, self.rows, self.payment = ok, changed, rows or [], payment
        self.late, self.needs_review, self.final_status, self.oversold = late, needs_review, final_status, oversold


async def get_latest_payment(session: AsyncSession, shop_bot_id: int, group_id: str, method: str) -> OrderPayment | None:
    result = await session.execute(
        select(OrderPayment)
        .where(OrderPayment.shop_bot_id == shop_bot_id, OrderPayment.group_id == group_id, OrderPayment.method == method)
        .order_by(OrderPayment.id.desc())
    )
    return result.scalars().first()


async def get_by_provider_ref(session: AsyncSession, provider_ref: str, method: str) -> OrderPayment | None:
    result = await session.execute(
        select(OrderPayment).where(OrderPayment.provider_ref == provider_ref, OrderPayment.method == method).order_by(OrderPayment.id.desc())
    )
    return result.scalars().first()


async def _reactivate_expired(session: AsyncSession, rows: list[OrderConsultation]) -> bool:
    """پرداختِ دیرهنگام: گروهِ expired دوباره رزرو می‌شه (اگه موجودی هست). برمی‌گردونه `oversold`."""

    oversold = False
    for row in rows:
        row.status = OrderStatus.AWAITING_PAYMENT
    await order_transition_service.record_event(
        session, rows[0], order_state.EXPIRED, order_state.AWAITING_PAYMENT, actor_type="system", reason="late_payment"
    )
    for row in rows:
        if row.product_id is None:
            continue
        product = await product_service.lock_for_update(session, row.product_id)
        if product is None or product.stock_quantity is None:
            continue
        qty = row.quantity or 1
        if product.stock_quantity - product.reserved_quantity >= qty:
            product.reserved_quantity += qty
            row.stock_reserved = True
        else:
            oversold = True
    if rows:
        # گروه دوباره واردِ جریانِ پرداخت شده ⇒ رزروِ کمیسیون هم باید دوباره گرفته شود
        # (چک‌اوتِ عادی همین کار را می‌کند؛ این مسیرِ «پرداختِ دیرهنگام» از آن رد می‌شد).
        await order_transition_service.apply_commission(session, rows, order_state.AWAITING_PAYMENT)
    return oversold


def _record_payment_method(rows, method: str) -> None:
    """نامِ روشِ پرداخت روی ردیف‌ها (P39 · باگِ ۳): فاکتور و پنلِ فروشگاه‌دار باید دقیقاً
    بگویند پول از کجا آمده؛ مسیرِ قدیمیِ بله‌پی هرگز `payment_method` را پر نمی‌کرد و فاکتور
    «پرداختِ دستی» می‌زد. روشِ ازپیش‌ثبت‌شده (مثلاً کارت‌به‌کارت) بازنویسی نمی‌شود."""
    for row in rows:
        if not row.payment_method or row.payment_method == "manual":
            row.payment_method = method


async def apply_verified_gateway_payment(
    session: AsyncSession, rows, *, actor_ref: str, auto_accept: bool
) -> OnlineResult:
    """ماشینِ وضعیتِ پرداختِ آنلاینِ تاییدشده، رویِ ردیف‌هایی که ردیفِ `OrderPayment` ندارند.

    P39 · باگِ ۳: مسیرِ قدیمیِ بله‌پی («سفارشِ تکی» و سبدِ ساخته‌شده با `create_invoice_link`)
    هیچ ردیفِ پرداختی نمی‌سازد؛ پیش از این فقط `bale_paid_at` مهر می‌خورد، status روی
    «منتظرِ پرداخت» می‌ماند، خطِ زمانی جلو نمی‌آمد، فاکتوری نمی‌رفت و کمیسیونِ رزروشده هرگز
    تسویه نمی‌شد. فراخوان باید قبلش استعلامِ سمتِ سرور + تطبیقِ مبلغ + قفلِ ردیف‌ها را انجام
    داده باشد.
    """
    if not rows:
        return OnlineResult(False)

    statuses = {order_state.value_of(r.status) for r in rows}
    late = needs_review = oversold = False
    if statuses <= {order_state.PENDING, order_state.AWAITING_PAYMENT, order_state.RECEIPT_SUBMITTED}:
        _record_payment_method(rows, actor_ref)
        if order_state.PENDING in statuses:
            # گروه هرگز واردِ جریانِ پرداخت نشده بود (پیشنهادِ پرداخت در پایانِ چک‌اوت) ⇒ رزرو
            # همین‌جا گرفته می‌شود تا تسویهٔ داخلِ گذار (وضعیت paid) نرخِ snapshot‌شده داشته باشد.
            await order_transition_service.apply_commission(session, rows, order_state.AWAITING_PAYMENT)
        result = await order_transition_service.transition_group(
            session, rows[0], order_state.PAID, actor_type="system", actor_ref=actor_ref
        )
        if not result.ok:
            needs_review = True
    elif statuses == {order_state.EXPIRED}:
        late = True
        oversold = await _reactivate_expired(session, rows)
        needs_review = oversold
        _record_payment_method(rows, actor_ref)
        result = await order_transition_service.transition_group(
            session, rows[0], order_state.PAID, actor_type="system", actor_ref=actor_ref, reason="late_payment"
        )
        if not result.ok:
            needs_review = True
    elif statuses <= {order_state.PAID, order_state.PROCESSING, order_state.SHIPPED, order_state.COMPLETED}:
        needs_review = True  # قبلاً پرداخت شده و پول دوباره آمده ⇒ باید بازبینی/استرداد شود
    else:
        needs_review = True  # لغو/ردشده/استردادشده ولی پول گرفته شد

    final_status = order_state.value_of(rows[0].status)
    if auto_accept and final_status == order_state.PAID and not needs_review:
        moved = await order_transition_service.transition_group(
            session, rows[0], order_state.PROCESSING, actor_type="system", actor_ref="auto_accept"
        )
        if moved.ok:
            final_status = order_state.PROCESSING
    return OnlineResult(
        True, True, rows=rows, late=late, needs_review=needs_review, final_status=final_status, oversold=oversold
    )


async def apply_verified_online_payment(
    session: AsyncSession, payment_id: int, shop_bot_id: int, *, transaction_ref: str, auto_accept: bool
) -> OnlineResult:
    """تنها مسیرِ اعتباردهیِ پرداختِ آنلاین با ردیفِ `OrderPayment`: قفل ⇒ ایدمپوتنسی
    (`transaction_ref` یکتا) ⇒ ماشینِ وضعیتِ `apply_verified_gateway_payment` ⇒ ثبتِ ردیفِ پرداخت.
    **فراخوان باید قبلش تاییدِ سمتِ سرور (inquire/verify) و تطبیقِ مبلغ را انجام داده باشد.**"""
    payment = await get_payment_locked(session, payment_id, shop_bot_id)
    if payment is None:
        return OnlineResult(False)
    if payment.status == P_PAID:
        return OnlineResult(True, False, payment=payment)
    duplicate = await session.execute(
        select(OrderPayment.id).where(OrderPayment.transaction_ref == transaction_ref, OrderPayment.id != payment.id)
    )
    if duplicate.first() is not None:
        return OnlineResult(True, False, payment=payment, needs_review=True)
    rows = await group_rows(session, shop_bot_id, payment.group_id, lock=True)
    if not rows:
        return OnlineResult(False)

    result = await apply_verified_gateway_payment(session, rows, actor_ref=payment.method, auto_accept=auto_accept)
    needs_review = result.needs_review

    payment.status = P_PAID
    payment.transaction_ref = transaction_ref[:80]
    payment.decided_at = now_utc()
    payment.decided_by = "gateway"
    payment.needs_review = needs_review
    await session.flush()

    return OnlineResult(
        True,
        True,
        rows=result.rows,
        payment=payment,
        late=result.late,
        needs_review=needs_review,
        final_status=result.final_status,
        oversold=result.oversold,
    )

