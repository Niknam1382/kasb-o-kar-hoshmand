from __future__ import annotations

import datetime
import enum
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class CreatedAtMixin:
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AuthMode(str, enum.Enum):
    TEST = "test"
    SMS = "sms"
    EMAIL = "email"


class ReferralRewardType(str, enum.Enum):
    FREE_DAYS = "free_days"
    DISCOUNT_PERCENT = "discount_percent"


class DiscountType(str, enum.Enum):
    PERCENT = "percent"
    FIXED = "fixed"


class PaymentMethod(str, enum.Enum):
    CARD_TO_CARD = "card_to_card"
    ZARINPAL = "zarinpal"
    BALE_PAY = "bale_pay"


class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class SubscriptionStatus(str, enum.Enum):
    TRIAL = "trial"
    ACTIVE = "active"
    GRACE = "grace"
    EXPIRED = "expired"


class OrderType(str, enum.Enum):
    ORDER = "order"
    CONSULTATION = "consultation"


class OrderStatus(str, enum.Enum):
    # کاندیدی که هوش مصنوعی تشخیص داده ولی هنوز خودِ مشتری صحتش رو تایید نکرده؛
    # در این وضعیت هنوز نه رزروِ موجودی انجام شده نه فروشگاه‌دار خبردار شده —
    # این‌ها فقط بعدِ تاییدِ واقعیِ مشتری (customer_confirm_order) اتفاق می‌افتن.
    AWAITING_CUSTOMER_CONFIRMATION = "awaiting_customer_confirmation"
    PENDING = "pending"
    CONFIRMED = "confirmed"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


class TenantMode(str, enum.Enum):
    """
    نوعِ کسب‌وکارِ فروشگاه: SALES (فروشِ محصول با موجودی/قیمت) یا CONSULTATION
    (کسب‌وکارهای خدماتی/مشاوره‌ای که هدفشون گفتگو و راهنماییه، نه فروشِ کالا).
    این فقط رویِ لحن/چارچوبِ هوش مصنوعی و برچسبِ دکمه‌ها اثر می‌ذاره؛ مدلِ
    داده‌ای (محصولات/سفارش‌ها) برای هر دو حالت مشترک می‌مونه.
    """

    SALES = "sales"
    CONSULTATION = "consultation"


class PaymentPurpose(str, enum.Enum):
    SUBSCRIPTION = "subscription"
    WALLET_TOPUP = "wallet_topup"


class WalletTransactionReason(str, enum.Enum):
    CHAT_MESSAGE = "chat_message"
    PHOTO_ANALYSIS = "photo_analysis"
    VOICE_TRANSCRIPTION = "voice_transcription"
    ORDER_DETECTION = "order_detection"
    TOPUP = "topup"
    TRIAL = "trial"
    REFERRAL_REWARD = "referral_reward"
    ADMIN_GRANT = "admin_grant"
    ADMIN_CORRECTION = "admin_correction"
    EXPIRY = "expiry"


class ModerationAction(str, enum.Enum):
    """
    اکشنِ نگهبانِ محتوا وقتی یه پیامِ مشتری با یه قانونِ ممنوعه مطابقت داره.
    WARN: اجازه بده پاسخِ عادی داده بشه، فقط ثبت و به ادمین اطلاع‌رسانی بشه.
    BLOCK: جلوی پاسخِ هوش‌مصنوعی رو بگیر و یه پیامِ خنثی به مشتری بده.
    REVIEW: مثلِ BLOCK، ولی صراحتاً برای بازبینیِ دستیِ ادمین علامت بزن.
    """

    WARN = "warn"
    BLOCK = "block"
    REVIEW = "review"


class AuditEventType(str, enum.Enum):
    MODERATION_MATCH = "moderation_match"
    ADMIN_SETTING_CHANGED = "admin_setting_changed"
    KILL_SWITCH_TOGGLED = "kill_switch_toggled"
    SHOP_SUSPENDED = "shop_suspended"
    SHOP_UNSUSPENDED = "shop_unsuspended"
    PAYMENT_APPROVED = "payment_approved"
    PAYMENT_REJECTED = "payment_rejected"
    OWNER_GIFT_GRANTED = "owner_gift_granted"
    OPERATOR_ADMIN_GRANTED = "operator_admin_granted"
    OPERATOR_ADMIN_REVOKED = "operator_admin_revoked"
    OWNER_WALLET_CORRECTED = "owner_wallet_corrected"


class AdminRoleType(str, enum.Enum):
    """سطح‌هایِ نقشِ ادمین، فراتر از سوپرادمینِ ثابتِ ADMIN_TELEGRAM_IDS."""

    OPERATOR = "operator"


def _enum_column(enum_cls, **kwargs):
    return mapped_column(String(32), **kwargs)


class AdminSettings(Base):
    __tablename__ = "admin_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)

    sms_api_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_api_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_model: Mapped[str] = mapped_column(String(100), default="grok-4-1-fast-non-reasoning", nullable=False)
    ai_base_url: Mapped[str] = mapped_column(String(255), default="https://api.x.ai/v1/chat/completions", nullable=False)
    # کلید/مدل/آدرسِ پشتیبان (اختیاری) — اگه پر باشه، وقتی سرویسِ اصلی حتی بعد
    # از تلاشِ مجدد هم شکست بخوره، یه‌بار با این تنظیمات امتحان می‌شه.
    ai_fallback_api_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_fallback_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ai_fallback_base_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    zarinpal_merchant_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    platform_card_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # طبقِ فایلِ بله_پی که کاربر فرستاد، provider_token از @botfather در بله
    # گرفته می‌شه (نه شماره‌کارت) — ولی این ادعا مستقل از مستنداتِ رسمیِ
    # docs.bale.ai تاییدپذیر نبود (جزئیات در changelog-phase1a-recovery.md).
    # برای همین یه رشته‌ی ساده نگه داشته شده تا هرجور مقداری که بله واقعاً
    # بهتون داد، بدونِ نیاز به تغییرِ مدل قابلِ‌ذخیره باشه.
    bale_provider_token: Mapped[str | None] = mapped_column(String(128), nullable=True)
    platform_card_holder_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    referral_reward_type: Mapped[ReferralRewardType] = _enum_column(
        ReferralRewardType, default=ReferralRewardType.FREE_DAYS, nullable=False
    )
    referral_reward_value: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=10, nullable=False)
    referral_reward_wallet_toman: Mapped[int] = mapped_column(Integer, default=20_000, nullable=False)

    grace_period_hours: Mapped[int] = mapped_column(Integer, default=48, nullable=False)
    rate_limit_max_messages: Mapped[int] = mapped_column(Integer, default=15, nullable=False)
    zarinpal_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # پیش‌فرض False (برخلافِ zarinpal_enabled) چون این مسیر تسته‌نشده‌ست؛ ادمین
    # باید بعدِ یه تراکنشِ آزمایشیِ موفق، دستی از پنل فعالش کنه.
    bale_pay_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    rate_limit_window_seconds: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    payment_reservation_minutes: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    # مدتِ رزروِ خودکارِ موجودی برای سفارش‌هایی که هوش مصنوعی تشخیص داده ولی
    # فروشگاه‌دار هنوز تاییدشون نکرده؛ بعدِ این مدت، رزرو خودکار آزاد می‌شه.
    order_reservation_minutes: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    # مدتی که یه سفارش/مشاوره‌ی کاندید (تشخیص‌داده‌شده ولی هنوز تاییدنشده‌ توسطِ
    # خودِ مشتری) منتظرِ جوابِ مشتری می‌مونه؛ بعدِ این مدت خودکار لغو می‌شه (تا
    # برای همیشه توی حالتِ نامشخص نمونه). چون هنوز رزروِ موجودی نداره، لغوش
    # نیازی به آزادسازیِ رزرو نداره.
    order_customer_confirmation_timeout_minutes: Mapped[int] = mapped_column(Integer, default=60, nullable=False)

    # سوییچ‌های اضطراری/کنترلی: بدونِ نیاز به دیپلویِ جدید، سریع می‌شه جلوی
    # ثبت‌نامِ تازه، شارژِ کیف‌پول، یا کلِ عملکردِ هوش‌مصنوعیِ پلتفرم رو گرفت.
    allow_new_registrations: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    allow_wallet_topups: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    maintenance_mode: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    periodic_report_frequency_days: Mapped[int] = mapped_column(Integer, default=7, nullable=False)

    conversation_history_limit: Mapped[int] = mapped_column(Integer, default=20, nullable=False)
    # چند روز پیامِ مکالمه نگه‌داشته بشه قبل از پاکسازیِ خودکار (کارِ دوره‌ای
    # در scheduler.py). صفر یا منفی یعنی پاکسازی غیرفعاله.
    conversation_retention_days: Mapped[int] = mapped_column(Integer, default=90, nullable=False)
    knowledge_items_limit: Mapped[int] = mapped_column(Integer, default=15, nullable=False)
    global_ai_system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    reference_channel_link: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # --- تنظیماتِ سیستمِ کیف‌پول (جایگزینِ اشتراکِ ثابت) ---
    wallet_topup_validity_months: Mapped[int] = mapped_column(Integer, default=12, nullable=False)
    wallet_cost_per_1k_tokens_toman: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    # سه فیلدِ زیر برای محاسبه‌ی خودکارِ wallet_cost_per_1k_tokens_toman از
    # روی فرمول (هزینه‌ی واقعیِ AI × نرخِ ارز × ضریب) هستن — نتیجه توی همون
    # فیلدِ بالا ذخیره می‌شه، این سه‌تا فقط ورودی‌های فرمولن، تا وقتی نرخِ
    # ارز/مدل عوض شد، به‌جای حدس‌زدنِ یه عددِ ثابتِ جدید، دوباره محاسبه بشه.
    ai_cost_usd_per_1m_tokens: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=Decimal("0.014"), nullable=False)
    usd_to_toman_rate: Mapped[int] = mapped_column(Integer, default=100_000, nullable=False)
    wallet_markup_multiplier: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("5.00"), nullable=False)
    wallet_cost_photo_analysis_toman: Mapped[int] = mapped_column(Integer, default=500, nullable=False)
    wallet_cost_voice_transcription_toman: Mapped[int] = mapped_column(Integer, default=300, nullable=False)
    wallet_cost_order_detection_toman: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    wallet_low_balance_warning_toman: Mapped[int] = mapped_column(Integer, default=20_000, nullable=False)
    wallet_trial_credit_toman: Mapped[int] = mapped_column(Integer, default=50_000, nullable=False)


class DiscountCode(Base):
    __tablename__ = "discount_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    type: Mapped[DiscountType] = _enum_column(DiscountType, nullable=False)
    value: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    max_uses: Mapped[int | None] = mapped_column(Integer, nullable=True)
    used_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    expires_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class MandatoryChannel(Base):
    __tablename__ = "mandatory_channels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    channel_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    invite_link: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class ShopOwner(Base):
    __tablename__ = "shop_owners"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    first_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    registration_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    referral_code: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)
    referred_by_id: Mapped[int | None] = mapped_column(ForeignKey("shop_owners.id"), nullable=True)
    wallet_balance_toman: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    wallet_low_balance_notified_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    wallet_empty_notified_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SubscriptionPlan(Base):
    __tablename__ = "subscription_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    duration_months: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    price_toman: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class OtpCode(Base):
    __tablename__ = "otp_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    shop_owner_id: Mapped[int] = mapped_column(ForeignKey("shop_owners.id"), index=True, nullable=False)
    code: Mapped[str] = mapped_column(String(10), nullable=False)
    purpose: Mapped[str] = mapped_column(String(32), nullable=False)
    expires_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Payment(Base, CreatedAtMixin):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    shop_owner_id: Mapped[int] = mapped_column(ForeignKey("shop_owners.id"), index=True, nullable=False)
    purpose: Mapped[PaymentPurpose] = _enum_column(PaymentPurpose, default=PaymentPurpose.SUBSCRIPTION, nullable=False)
    duration_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    base_amount: Mapped[int] = mapped_column(Integer, nullable=False)
    final_amount: Mapped[int] = mapped_column(Integer, nullable=False)
    method: Mapped[PaymentMethod] = _enum_column(PaymentMethod, nullable=False)
    status: Mapped[PaymentStatus] = _enum_column(PaymentStatus, default=PaymentStatus.PENDING, nullable=False)
    receipt_file_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    discount_code_id: Mapped[int | None] = mapped_column(ForeignKey("discount_codes.id"), nullable=True)
    zarinpal_authority: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    zarinpal_ref_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # payload یکتایی که موقعِ createInvoiceLink ساخته و به بله پاس می‌شه؛ بعدًا
    # توی وب‌هوکِ successful_payment برمی‌گرده تا این Payment پیدا بشه (نقشِ
    # مشابهِ zarinpal_authority رو داره).
    bale_invoice_payload: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    bale_transaction_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reserved_until: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by_admin_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    reviewed_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class WalletCharge(Base, CreatedAtMixin):
    """
    هر «شارژ»ی که فروشگاه‌دار انجام می‌ده (یا از طریقِ پرداخت، یا هدیه‌ی معرفی)،
    یه ردیفِ مستقل اینجا می‌گیره — با تاریخِ انقضای خودش. مصرف به‌صورتِ FIFO از
    قدیمی‌ترین شارژِ منقضی‌نشده کم می‌شه (به wallet_service.py نگاه کن).
    """

    __tablename__ = "wallet_charges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    shop_owner_id: Mapped[int] = mapped_column(ForeignKey("shop_owners.id"), index=True, nullable=False)
    payment_id: Mapped[int | None] = mapped_column(ForeignKey("payments.id"), nullable=True)
    amount_toman: Mapped[int] = mapped_column(Integer, nullable=False)
    remaining_toman: Mapped[int] = mapped_column(Integer, nullable=False)
    expires_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_expired: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    reminder_30d_sent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    reminder_7d_sent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    reminder_1d_sent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class WalletTransaction(Base, CreatedAtMixin):
    """
    دفترِ کاملِ تراکنش‌های کیف‌پول (هم شارژها، هم مصرف‌ها، هم انقضاها) — برای
    شفافیت با فروشگاه‌دار و برای ممیزی. مبلغِ مثبت یعنی افزایشِ اعتبار (شارژ/هدیه)،
    مبلغِ منفی یعنی کاهش (مصرف/انقضا). مجموعِ amount_toman برای یه فروشگاه‌دار
    باید همیشه برابرِ wallet_balance_toman کش‌شده روی ShopOwner باشه.
    """

    __tablename__ = "wallet_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    shop_owner_id: Mapped[int] = mapped_column(ForeignKey("shop_owners.id"), index=True, nullable=False)
    wallet_charge_id: Mapped[int | None] = mapped_column(ForeignKey("wallet_charges.id"), nullable=True)
    amount_toman: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[WalletTransactionReason] = _enum_column(WalletTransactionReason, nullable=False)
    reference: Mapped[str | None] = mapped_column(String(255), nullable=True)


class Referral(Base, CreatedAtMixin):
    __tablename__ = "referrals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    referrer_id: Mapped[int] = mapped_column(ForeignKey("shop_owners.id"), index=True, nullable=False)
    referred_id: Mapped[int] = mapped_column(ForeignKey("shop_owners.id"), unique=True, nullable=False)
    reward_status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    rewarded_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ShopBot(Base):
    __tablename__ = "shop_bots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    shop_owner_id: Mapped[int] = mapped_column(ForeignKey("shop_owners.id"), unique=True, nullable=False)
    encrypted_token: Mapped[str] = mapped_column(Text, nullable=False)
    bot_telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    bot_username: Mapped[str] = mapped_column(String(255), nullable=False)
    webhook_secret_token: Mapped[str] = mapped_column(String(64), nullable=False)
    ai_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    zarinpal_merchant_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tenant_mode: Mapped[TenantMode] = _enum_column(TenantMode, default=TenantMode.SALES, nullable=False)
    knowledge_channel_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    knowledge_channel_bot: Mapped[str | None] = mapped_column(String(16), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    disabled_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_report_sent_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    products: Mapped[list["Product"]] = relationship(back_populates="shop_bot", lazy="selectin")


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    shop_owner_id: Mapped[int] = mapped_column(ForeignKey("shop_owners.id"), index=True, nullable=False)
    status: Mapped[SubscriptionStatus] = _enum_column(SubscriptionStatus, nullable=False)
    duration_months: Mapped[int] = mapped_column(Integer, nullable=False)
    is_trial: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    start_date: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_date: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    grace_reminder_sent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class BotErrorEvent(Base, CreatedAtMixin):
    __tablename__ = "bot_error_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    shop_bot_id: Mapped[int] = mapped_column(ForeignKey("shop_bots.id"), index=True, nullable=False)


class ChannelKnowledge(Base):
    __tablename__ = "channel_knowledge"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    shop_bot_id: Mapped[int] = mapped_column(ForeignKey("shop_bots.id"), index=True, nullable=False)
    source_channel_id: Mapped[str] = mapped_column(String(64), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    posted_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Customer(Base):
    __tablename__ = "customers"
    __table_args__ = (UniqueConstraint("shop_bot_id", "telegram_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    shop_bot_id: Mapped[int] = mapped_column(ForeignKey("shop_bots.id"), index=True, nullable=False)
    telegram_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    first_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_seen_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_message_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Product(Base, CreatedAtMixin):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    shop_bot_id: Mapped[int] = mapped_column(ForeignKey("shop_bots.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    price_toman: Mapped[int] = mapped_column(Integer, nullable=False)
    photo_file_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stock_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # جمعِ واحدهایی که الان توسطِ سفارش‌های PENDING رزرو شدن (فقط برای محصولاتی
    # که stock_quantity دارن معنی داره؛ محصولِ نامحدود reserved_quantity=0 می‌مونه
    # و اصلاً چک نمی‌شه). «موجودیِ واقعاً قابل‌فروش» = stock_quantity - reserved_quantity.
    reserved_quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    shop_bot: Mapped["ShopBot"] = relationship(back_populates="products", lazy="selectin")


class DiscountCodeUsage(Base):
    __tablename__ = "discount_code_usages"
    __table_args__ = (UniqueConstraint("discount_code_id", "shop_owner_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    discount_code_id: Mapped[int] = mapped_column(ForeignKey("discount_codes.id"), nullable=False)
    shop_owner_id: Mapped[int] = mapped_column(ForeignKey("shop_owners.id"), nullable=False)
    payment_id: Mapped[int] = mapped_column(ForeignKey("payments.id"), nullable=False)


class ConversationMessage(Base, CreatedAtMixin):
    __tablename__ = "conversation_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True, nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)


class OrderConsultation(Base, CreatedAtMixin):
    __tablename__ = "orders_consultations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    shop_bot_id: Mapped[int] = mapped_column(ForeignKey("shop_bots.id"), index=True, nullable=False)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True, nullable=False)
    type: Mapped[OrderType] = _enum_column(OrderType, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    estimated_value_toman: Mapped[int | None] = mapped_column(Integer, nullable=True)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"), nullable=True)
    quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # فیلدهای ساختاریافته (بازطراحیِ سفارش‌گیری): قبلاً این دو تا فقط به‌صورتِ
    # چندخطِ اضافه به summary چسبونده می‌شدن؛ حالا ستونِ جداگانه دارن تا هم
    # قابلِ‌کوئری باشن هم بشه توی پیامِ تاییدِ مشتری/اطلاع‌رسانیِ فروشگاه‌دار
    # جدا از خلاصه‌ی آزاد نمایش داده بشن.
    customer_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    customer_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    confirmed_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # وضعیتِ رسمیِ سفارش: confirmed/confirmed_at بالا برای سازگاری با کدِ قدیمی
    # نگه داشته شدن و همزمان با status سینک می‌مونن (وقتی status روی CONFIRMED
    # یا جلوترش می‌ره، confirmed=True می‌شه). status منبعِ اصلیِ واقعیه؛
    # confirmed فقط یه خلاصه‌ی بولینِ مشتق‌شده‌ست.
    status: Mapped[OrderStatus] = _enum_column(OrderStatus, default=OrderStatus.PENDING, nullable=False)
    # آیا این سفارش الان یه رزروِ فعال روی موجودیِ محصول داره؟ برای اینکه بدونیم
    # موقعِ لغو/ردّ/انقضا باید Product.reserved_quantity رو آزاد کنیم یا نه.
    stock_reserved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    reservation_expires_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ModerationRule(Base, CreatedAtMixin):
    """
    قانونِ نگهبانِ محتوا: یه کلیدواژه یا الگوی regex که اگه توی پیامِ مشتری
    دیده بشه، یه اکشن (WARN/BLOCK/REVIEW) اجرا می‌شه. سبک و بدونِ فراخوانیِ
    اضافیِ هوش‌مصنوعی — فقط تطبیقِ متنیِ محلی.
    """

    __tablename__ = "moderation_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pattern: Mapped[str] = mapped_column(String(200), nullable=False)
    is_regex: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    action: Mapped[ModerationAction] = _enum_column(ModerationAction, default=ModerationAction.REVIEW, nullable=False)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class AiKeyCapability(str, enum.Enum):
    """این کلید برای چه نوع فراخوانی‌ای مناسبه — پاسخِ متنی، تحلیلِ عکس، یا هردو."""

    CHAT = "chat"
    VISION = "vision"
    BOTH = "both"


class AiApiKeyPoolEntry(Base, CreatedAtMixin):
    """
    یه کلیدِ API در استخرِ کلیدهای هوش مصنوعیِ پلتفرم. وقتی چند کلید ثبت شده
    باشه، هر فراخوانی از یه کلیدِ تصادفی شروع می‌کنه و اگه اون شکست خورد
    (یا مدارِ قطعش به‌خاطرِ شکست‌های پیاپیِ اخیر باز باشه)، به کلیدِ بعدی
    می‌ره — هم بارِ درخواست‌ها بینِ چند کلید پخش می‌شه، هم یه کلیدِ مشکل‌دار
    کلِ پلتفرم رو از کار نمی‌ندازه. اگه هیچ کلیدی توی استخر نباشه،
    admin_settings.ai_api_key/ai_fallback_api_key (روشِ قدیمی) استفاده می‌شه.
    """

    __tablename__ = "ai_api_key_pool"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    api_key: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    base_url: Mapped[str] = mapped_column(String(255), nullable=False)
    capability: Mapped[AiKeyCapability] = _enum_column(AiKeyCapability, default=AiKeyCapability.CHAT, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class AuditLogEntry(Base, CreatedAtMixin):
    """
    گزارشِ ممیزیِ متمرکز: رویدادهای حساسِ پلتفرم (تطبیقِ نگهبانِ محتوا، تغییرِ
    سوییچ‌ها، تاییدِ پرداخت، تعلیقِ فروشگاه و…) اینجا با زمان و جزئیات ثبت
    می‌شن. نه برای هر رویدادِ ریز (مثلِ هر پیامِ چت)، فقط رویدادهایی که یه‌روز
    ممکنه لازم بشه بررسی بشن.
    """

    __tablename__ = "audit_log_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_type: Mapped[AuditEventType] = _enum_column(AuditEventType, nullable=False, index=True)
    shop_bot_id: Mapped[int | None] = mapped_column(ForeignKey("shop_bots.id"), nullable=True, index=True)
    actor_telegram_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)


class AdminRole(Base, CreatedAtMixin):
    """
    ادمین‌هایِ عملیاتی — یه سطحِ دسترسیِ محدودتر از سوپرادمین (که همچنان از
    طریقِ ADMIN_TELEGRAM_IDS در .env تعریف می‌شه، نه از این جدول). فقط
    سوپرادمین می‌تونه اینجا ردیف اضافه/حذف کنه. اگه این جدول خالی بمونه،
    رفتار دقیقاً مثلِ قبل از RBAC می‌مونه — فقط سوپرادمین‌ها به پنلِ ادمین
    دسترسی دارن؛ سازگاریِ کاملِ عقب، هم‌الگو با استخرِ کلیدهایِ AI.
    """

    __tablename__ = "admin_roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, nullable=False, unique=True)
    role: Mapped[AdminRoleType] = _enum_column(AdminRoleType, nullable=False, default=AdminRoleType.OPERATOR)
    granted_by_telegram_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
