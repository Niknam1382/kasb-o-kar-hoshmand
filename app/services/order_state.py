"""ماشینِ وضعیتِ سفارش — منبعِ حقیقتِ یکتایِ مجموعه‌هایِ وضعیت و گذارهایِ مجاز (C4).

این ماژول عمداً **خالص** است (هیچ import از SQLAlchemy/aiogram/models ندارد) تا هم در
sandbox تست‌پذیر باشد و هم هیچ دورِ import نسازد. مقدارها همان مقدارِ رشته‌ایِ
`OrderStatus` هستند (ستونِ enum از نوعِ `String(32)` است ⇒ مقدارِ تازه مایگریشنِ
ساختاری نمی‌خواهد).

قاعده: هر وضعیتِ تازه فقط از همین‌جا وارد می‌شود و همه‌یِ مصرف‌کننده‌ها
(stats، accounting، crm، campaign، expiry، excel، texts) از همین مجموعه‌ها می‌خوانند.
"""

from __future__ import annotations

# ── مقدارهای وضعیت (برابرِ OrderStatus.value) ──────────────────────────────
AWAITING_CUSTOMER_CONFIRMATION = "awaiting_customer_confirmation"
PENDING = "pending"
CONFIRMED = "confirmed"
PROCESSING = "processing"
SHIPPED = "shipped"
COMPLETED = "completed"
CANCELLED = "cancelled"
REJECTED = "rejected"
EXPIRED = "expired"
# تازه (C4)
AWAITING_PAYMENT = "awaiting_payment"
RECEIPT_SUBMITTED = "receipt_submitted"
PAID = "paid"
REFUND_PENDING = "refund_pending"
REFUNDED = "refunded"

ALL_STATUSES: tuple[str, ...] = (
    AWAITING_CUSTOMER_CONFIRMATION,
    PENDING,
    AWAITING_PAYMENT,
    RECEIPT_SUBMITTED,
    PAID,
    CONFIRMED,
    PROCESSING,
    SHIPPED,
    COMPLETED,
    REFUND_PENDING,
    REFUNDED,
    CANCELLED,
    REJECTED,
    EXPIRED,
)

# ترتیبِ نمایش در گزارش‌ها (accounting.STATUS_ORDER)
DISPLAY_ORDER: tuple[str, ...] = ALL_STATUSES

# «باز» = هنوز به نتیجه‌یِ نهایی نرسیده (تغییرِ مود تا وقتی هستن مسدوده؛ A3).
# SHIPPED عمداً مثلِ رفتارِ قبلی بیرونِ این مجموعه است.
OPEN: frozenset[str] = frozenset(
    {
        AWAITING_CUSTOMER_CONFIRMATION,
        PENDING,
        CONFIRMED,
        PROCESSING,
        AWAITING_PAYMENT,
        RECEIPT_SUBMITTED,
        PAID,
        REFUND_PENDING,
    }
)

# پرداخت انجام شده (یا بعدِ پرداخت)
PAID_OR_LATER: frozenset[str] = frozenset({PAID, PROCESSING, SHIPPED, COMPLETED, REFUND_PENDING})

# فروشِ موفق (درآمد): مثلِ SUCCESS_STATUSES قبلی + paid. استردادشده/درخواستِ استرداد درآمد نیست.
REVENUE: frozenset[str] = frozenset({CONFIRMED, PROCESSING, SHIPPED, COMPLETED, PAID})

# وضعیت‌هایی که رزروِ موجودی باید در آن‌ها آزاد باشد
RELEASES_RESERVATION: frozenset[str] = frozenset({REJECTED, EXPIRED, CANCELLED, REFUNDED})

# وضعیت‌هایی که در آن‌ها رزروِ موجودی نگه داشته می‌شود (منتظرِ پرداخت/تصمیم)
HOLDS_RESERVATION: frozenset[str] = frozenset({PENDING, AWAITING_PAYMENT, RECEIPT_SUBMITTED})

# پایانی (دیگه گذاری ندارن)
TERMINAL: frozenset[str] = frozenset({COMPLETED, CANCELLED, REJECTED, EXPIRED, REFUNDED})

# تحویلِ خودکارِ دیجیتال برایِ این وضعیت‌ها مجازه (ایدمپوتنت؛ digital_service.deliver_order)
DELIVERABLE: frozenset[str] = frozenset({CONFIRMED, PAID, PROCESSING, SHIPPED, COMPLETED})

# ── گذارهایِ مجاز ───────────────────────────────────────────────────────
TRANSITIONS: dict[str, frozenset[str]] = {
    AWAITING_CUSTOMER_CONFIRMATION: frozenset({PENDING, CANCELLED, EXPIRED}),
    PENDING: frozenset({CONFIRMED, REJECTED, CANCELLED, EXPIRED}),
    # awaiting_payment → pending: انتخابِ «پرداختِ دستی» (فروشگاه‌دار مثلِ مسیرِ قدیمی دستی تایید می‌کنه)
    AWAITING_PAYMENT: frozenset({RECEIPT_SUBMITTED, PAID, PENDING, CANCELLED, EXPIRED, REJECTED}),
    RECEIPT_SUBMITTED: frozenset({PAID, AWAITING_PAYMENT, REJECTED, EXPIRED}),
    PAID: frozenset({PROCESSING, COMPLETED, REFUND_PENDING}),
    CONFIRMED: frozenset({PROCESSING, REFUND_PENDING}),
    PROCESSING: frozenset({SHIPPED, COMPLETED, REFUND_PENDING}),
    SHIPPED: frozenset({COMPLETED, REFUND_PENDING}),
    REFUND_PENDING: frozenset({REFUNDED}),
    COMPLETED: frozenset(),
    CANCELLED: frozenset(),
    REJECTED: frozenset(),
    EXPIRED: frozenset(),
    REFUNDED: frozenset(),
}

# ردِ فروشگاه‌دار: از این وضعیت‌ها مجازه (paid به بعد ⇒ refund_pending، نه rejected)
REJECTABLE: frozenset[str] = frozenset({PENDING, AWAITING_PAYMENT, RECEIPT_SUBMITTED})
REFUNDABLE: frozenset[str] = frozenset({PAID, CONFIRMED, PROCESSING, SHIPPED})
# لغوِ مشتری فقط قبل از پرداخت
CUSTOMER_CANCELLABLE: frozenset[str] = frozenset({AWAITING_PAYMENT})

# پیشرویِ دکمه‌ایِ فروشگاه‌دار (قدمِ بعدی) — فقط برایِ گروه
NEXT_STEP: dict[str, str] = {
    CONFIRMED: PROCESSING,
    PAID: PROCESSING,
    PROCESSING: SHIPPED,
    SHIPPED: COMPLETED,
}

ACTOR_TYPES: tuple[str, ...] = ("customer", "owner", "system", "admin")


def value_of(status) -> str:
    """مقدارِ رشته‌ایِ یک وضعیت (enum یا رشته)."""
    return status.value if hasattr(status, "value") else str(status)


def can_transition(from_status, to_status) -> bool:
    f, t = value_of(from_status), value_of(to_status)
    return t in TRANSITIONS.get(f, frozenset())


def is_open(status) -> bool:
    return value_of(status) in OPEN


def is_paid_or_later(status) -> bool:
    return value_of(status) in PAID_OR_LATER


def is_deliverable(status) -> bool:
    return value_of(status) in DELIVERABLE


def next_step(status) -> str | None:
    return NEXT_STEP.get(value_of(status))


def validate_tables() -> list[str]:
    """خطاهایِ ناهم‌خوانیِ داخلیِ جدول‌ها (برایِ تستِ نگهبان)."""
    errors: list[str] = []
    allv = set(ALL_STATUSES)
    for src, dsts in TRANSITIONS.items():
        if src not in allv:
            errors.append(f"unknown source {src}")
        for d in dsts:
            if d not in allv:
                errors.append(f"unknown target {src}->{d}")
    for name, group in (
        ("OPEN", OPEN),
        ("PAID_OR_LATER", PAID_OR_LATER),
        ("REVENUE", REVENUE),
        ("RELEASES_RESERVATION", RELEASES_RESERVATION),
        ("HOLDS_RESERVATION", HOLDS_RESERVATION),
        ("TERMINAL", TERMINAL),
        ("DELIVERABLE", DELIVERABLE),
    ):
        for v in group:
            if v not in allv:
                errors.append(f"{name} has unknown {v}")
    for t in TERMINAL:
        if TRANSITIONS.get(t):
            errors.append(f"terminal {t} has outgoing transitions")
    if set(TRANSITIONS) != allv:
        errors.append("TRANSITIONS keys != ALL_STATUSES")
    return errors
