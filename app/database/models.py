from __future__ import annotations

import datetime
import enum
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Numeric,
    String,
    Text,
    TypeDecorator,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.utils.encryption import decrypt_token, encrypt_token


class EncryptedToken(TypeDecorator):
    """ستونِ متنیِ رمزنگاری‌شده (Fernet) — شفاف: کد مقدارِ خام می‌نویسه/می‌خونه، دیتابیس فقط رمزِ آن را می‌بینه (W5 · B7).
    خواندنِ مقدارِ قدیمیِ *رمزنگاری‌نشده* (قبل از مایگریشن) خطا نمی‌ده؛ همان مقدار برمی‌گرده و با اولین نوشتن رمز می‌شه."""

    impl = String
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None or value == "":
            return None
        return encrypt_token(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        try:
            return decrypt_token(value)
        except Exception:  # noqa: BLE001 — مقدارِ قدیمیِ خام
            return value


class EncryptedText(EncryptedToken):
    """مثلِ `EncryptedToken` ولی با `impl = Text` ⇒ نوعِ ستون در دیتابیس عوض نمی‌شود.

    برایِ کلیدهایی که ستونشان از قبل Text است (کاوه‌نگار، AI) تا رمزنگاریِ P18 · د(۴) بدونِ
    تغییرِ نوعِ ستون و بدونِ مهاجرتِ داده انجام شود.
    """

    impl = Text

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
    # فازِ ۱ · W2 (C4): ماشینِ وضعیتِ پرداخت — مجموعه‌هایِ مرکزی در services/order_state.py
    AWAITING_PAYMENT = "awaiting_payment"
    RECEIPT_SUBMITTED = "receipt_submitted"
    PAID = "paid"
    REFUND_PENDING = "refund_pending"
    REFUNDED = "refunded"


class CampaignDiscountType(str, enum.Enum):
    """نوعِ تخفیفِ کمپین (فازِ ۳): PERCENT = درصدِ جمعِ سبد (با سقفِ اختیاریِ
    مبلغ)، FIXED = مبلغِ ثابتِ تومانی."""

    PERCENT = "percent"
    FIXED = "fixed"


class KnowledgeGapStatus(str, enum.Enum):
    """وضعیتِ یه «سوالِ بی‌جواب» (فازِ ۴): OPEN = هنوز فروشگاه‌دار جواب نداده،
    ANSWERED = با یه پرسش‌وپاسخِ تاییدشده جواب داده شده، DISMISSED = نادیده گرفته شده."""

    OPEN = "open"
    ANSWERED = "answered"
    DISMISSED = "dismissed"


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
    RECEIPT_ANALYSIS = "receipt_analysis"
    VOICE_TRANSCRIPTION = "voice_transcription"
    ORDER_DETECTION = "order_detection"
    CART_EDIT = "cart_edit"
    CRM_SUMMARY = "crm_summary"
    OWNER_ASSISTANT = "owner_assistant"
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
    ADMIN_BATCH_EXECUTED = "admin_batch_executed"  # W5 · K1/K2
    TIME_FREEZE_CHANGED = "time_freeze_changed"  # W5 · K3
    JOBS_PAUSE_CHANGED = "jobs_pause_changed"  # W5 · K4
    OPERATOR_ADMIN_GRANTED = "operator_admin_granted"
    OPERATOR_ADMIN_REVOKED = "operator_admin_revoked"
    OWNER_WALLET_CORRECTED = "owner_wallet_corrected"
    WALLET_LEDGER_EXPORTED = "wallet_ledger_exported"
    OWNER_PROFILE_UPDATED = "owner_profile_updated"
    OWNER_BUSINESS_MODE_CHANGED = "owner_business_mode_changed"
    CUSTOMER_BLOCK_CHANGED = "customer_block_changed"  # P18 · B4
    BOT_BIO_TAMPERED = "bot_bio_tampered"  # P18 · A2
    BRANDING_TEXT_CHANGED = "branding_text_changed"  # P18 · A2


class AdminRoleType(str, enum.Enum):
    """سطح‌هایِ نقشِ ادمین، فراتر از سوپرادمینِ ثابتِ ADMIN_TELEGRAM_IDS."""

    OPERATOR = "operator"


def _enum_column(enum_cls, **kwargs):
    return mapped_column(String(32), **kwargs)


class AdminSettings(Base):
    __tablename__ = "admin_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)

    # P18 · د(۴): کلیدها رویِ `EncryptedText` (همان Fernet، نوعِ ستون Text می‌ماند ⇒ بدونِ مهاجرت).
    # مقدارِ قدیمیِ رمزنگاری‌نشده هم خوانده می‌شود و با اولین نوشتن رمز می‌شود؛ در پنل فقط ماسک‌شده.
    sms_api_key: Mapped[str | None] = mapped_column(EncryptedText, nullable=True)
    ai_api_key: Mapped[str | None] = mapped_column(EncryptedText, nullable=True)
    ai_model: Mapped[str] = mapped_column(String(100), default="grok-4-1-fast-non-reasoning", nullable=False)
    ai_base_url: Mapped[str] = mapped_column(String(255), default="https://api.x.ai/v1/chat/completions", nullable=False)
    # کلید/مدل/آدرسِ پشتیبان (اختیاری) — اگه پر باشه، وقتی سرویسِ اصلی حتی بعد
    # از تلاشِ مجدد هم شکست بخوره، یه‌بار با این تنظیمات امتحان می‌شه.
    ai_fallback_api_key: Mapped[str | None] = mapped_column(EncryptedText, nullable=True)
    ai_fallback_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ai_fallback_base_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    zarinpal_merchant_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    platform_card_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # طبقِ فایلِ بله_پی که کاربر فرستاد، provider_token از @botfather در بله
    # گرفته می‌شه (نه شماره‌کارت) — ولی این ادعا مستقل از مستنداتِ رسمیِ
    # docs.bale.ai تاییدپذیر نبود (جزئیات در changelog-phase1a-recovery.md).
    # برای همین یه رشته‌ی ساده نگه داشته شده تا هرجور مقداری که بله واقعاً
    # بهتون داد، بدونِ نیاز به تغییرِ مدل قابلِ‌ذخیره باشه.
    bale_provider_token: Mapped[str | None] = mapped_column(EncryptedToken(512), nullable=True)
    # P18 · A1: توکنِ رباتِ بله (سراسری) از پنلِ ادمین؛ اولویت با این مقدار است، بعد `BALE_BOT_TOKEN` در .env.
    bale_bot_token: Mapped[str | None] = mapped_column(EncryptedToken(512), nullable=True)
    # P18 · A1: رازِ وب‌هوکِ بله فقط در حالتِ webhook لازم است و *خودکار* ساخته می‌شود — هرگز از ادمین پرسیده نمی‌شود.
    bale_webhook_secret_auto: Mapped[str | None] = mapped_column(EncryptedToken(512), nullable=True)
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
    # گزارشِ شبانه (فازِ ۳) — جدا از periodic_report_frequency_days بالا (که یه
    # خلاصه‌ی سلامتِ کلی هر N روز می‌فرسته). این یکی هر روز، سرِ یه ساعتِ
    # مشخص، فقط عددهایِ «امروز» رو می‌فرسته (سفارش/مشاوره/مشتریِ جدید،
    # برآوردِ فروشِ تاییدشده). ساعت به‌وقتِ UTC ذخیره می‌شه (پیش‌فرض ۱۸ =
    # ۲۱:۳۰ به‌وقتِ تهران) چون شبکه‌ی سرور UTC ه؛ توی پنلِ ادمین هر دو ساعت
    # (UTC و تقریبیِ تهران) نشون داده می‌شه تا گیج‌کننده نباشه.
    nightly_report_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    nightly_report_hour_utc: Mapped[int] = mapped_column(Integer, default=18, nullable=False)
    # تشخیصِ خلأیِ دانش (فازِ ۴): وقتی روشنه، به پرامپتِ رباتِ فروشگاه یه دستورِ
    # اضافه می‌شه که اگه جوابِ سوالِ مشتری رو نمی‌دونه نشانه‌ی [[GAP]] بذاره و سوال
    # توی «سوال‌هایِ بی‌جواب»ِ فروشگاه‌دار ثبت بشه. هزینه‌ی AIِ اضافه‌ای نداره (همون
    # پاسخِ عادیه). خاموش = پرامپت و رفتار دقیقاً مثلِ قبل.
    knowledge_gap_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    conversation_history_limit: Mapped[int] = mapped_column(Integer, default=20, nullable=False)
    # چند روز پیامِ مکالمه نگه‌داشته بشه قبل از پاکسازیِ خودکار (کارِ دوره‌ای
    # در scheduler.py). صفر یا منفی یعنی پاکسازی غیرفعاله.
    conversation_retention_days: Mapped[int] = mapped_column(Integer, default=90, nullable=False)
    knowledge_items_limit: Mapped[int] = mapped_column(Integer, default=15, nullable=False)
    global_ai_system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    reference_channel_link: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # --- تنظیماتِ سیستمِ کیف‌پول (جایگزینِ اشتراکِ ثابت) ---
    wallet_topup_validity_months: Mapped[int] = mapped_column(Integer, default=12, nullable=False)
    # PHASE 5A: کمترینِ مبلغِ «شارژِ کیف‌پول». تصمیمِ ادمین است، ولی در *سرویسِ* پرداخت
    # هم چک می‌شود (نه فقط در UI) تا فراخوانِ جعلی یا ورودیِ دستکاری‌شده رد شود.
    min_topup_amount_toman: Mapped[int] = mapped_column(Integer, default=50_000, server_default="50000", nullable=False)
    wallet_cost_per_1k_tokens_toman: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    # سه فیلدِ زیر برای محاسبه‌ی خودکارِ wallet_cost_per_1k_tokens_toman از
    # روی فرمول (هزینه‌ی واقعیِ AI × نرخِ ارز × ضریب) هستن — نتیجه توی همون
    # فیلدِ بالا ذخیره می‌شه، این سه‌تا فقط ورودی‌های فرمولن، تا وقتی نرخِ
    # ارز/مدل عوض شد، به‌جای حدس‌زدنِ یه عددِ ثابتِ جدید، دوباره محاسبه بشه.
    ai_cost_usd_per_1m_tokens: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=Decimal("0.014"), nullable=False)
    usd_to_toman_rate: Mapped[int] = mapped_column(Integer, default=100_000, nullable=False)
    wallet_markup_multiplier: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("5.00"), nullable=False)
    wallet_cost_photo_analysis_toman: Mapped[int] = mapped_column(Integer, default=500, nullable=False)
    # W5 · 2.1: هزینه‌یِ تحلیلِ AIِ رسیدِ کارت‌به‌کارت (فقط مشورتی)
    wallet_cost_receipt_analysis_toman: Mapped[int] = mapped_column(Integer, default=500, server_default="500", nullable=False)
    # W5 · 2.2: سقف/کفِ مهلت‌هایِ پرداختی که فروشگاه‌دار می‌تونه تنظیم کنه (guardrail ادمین)
    payment_deadline_min_minutes: Mapped[int] = mapped_column(Integer, default=5, server_default="5", nullable=False)
    payment_deadline_max_minutes: Mapped[int] = mapped_column(Integer, default=1440, server_default="1440", nullable=False)
    review_hold_min_hours: Mapped[int] = mapped_column(Integer, default=1, server_default="1", nullable=False)
    review_hold_max_hours: Mapped[int] = mapped_column(Integer, default=72, server_default="72", nullable=False)
    # W5 · K4: توقفِ جاب‌هایِ زمان‌بندی‌شده (کلی یا گروه‌به‌گروه؛ با ثبتِ زمان/عامل)
    jobs_paused: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    jobs_paused_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    jobs_paused_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    jobs_paused_groups: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # P18 · A3: سرویسِ پیامک (کاوه‌نگار) صریح روشن/خاموش می‌شود؛ خاموش = همان مسیرِ بدونِ پیامکِ امروز
    # (ثبت‌نام هیچ‌وقت گیر نمی‌کند). فرستنده و نامِ قالب هم از پنلِ ادمین (رمزنگاری‌شده).
    sms_enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    sms_sender_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    sms_otp_template: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # P18 · A2: متنِ اجباریِ برندینگِ بیوگرافیِ ربات‌هایِ فروشگاهی (≤۶۰). خالی ⇒ هیچ کاری نمی‌شود.
    branding_text: Mapped[str | None] = mapped_column(String(60), nullable=True)
    branding_synced_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    wallet_cost_voice_transcription_toman: Mapped[int] = mapped_column(Integer, default=300, nullable=False)
    wallet_cost_order_detection_toman: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    wallet_low_balance_warning_toman: Mapped[int] = mapped_column(Integer, default=20_000, nullable=False)
    wallet_trial_credit_toman: Mapped[int] = mapped_column(Integer, default=50_000, nullable=False)

    # فازِ ۱ · P1-S1 (D2): پشتیبانیِ پلتفرم — فقط به فروشگاه‌دارها نشون داده می‌شه (هرگز به مشتری)
    platform_support_username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    platform_support_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    platform_support_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    # فازِ ۱ · P1-S2 (J1): دستورِ سراسریِ AI به‌تفکیکِ مود؛ NULL/خالی = مسیرِ پیش‌فرض (قدیمی ← پیش‌فرضِ حرفه‌ای)
    global_ai_prompt_sales: Mapped[str | None] = mapped_column(Text, nullable=True)
    global_ai_prompt_consultation: Mapped[str | None] = mapped_column(Text, nullable=True)


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
    # فازِ ۱ · P1-S1: مودِ کسب‌وکار روی خودِ فروشگاه‌دار (منبعِ حقیقت؛ ShopBot.tenant_mode هم‌گام می‌شه) و یوزرنیمِ تلگرام
    business_mode: Mapped[str] = mapped_column(String(32), default="sales", server_default="sales", nullable=False)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
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
    # P18 · د: سقفِ ارسالِ ساعتی به‌ازایِ هر شماره، بدونِ ایندکس پیمایشِ کاملِ جدول است.
    __table_args__ = (Index("ix_otp_codes_phone_purpose_sent", "phone_number", "purpose", "sent_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    shop_owner_id: Mapped[int] = mapped_column(ForeignKey("shop_owners.id"), index=True, nullable=False)
    code: Mapped[str] = mapped_column(String(10), nullable=False)
    purpose: Mapped[str] = mapped_column(String(32), nullable=False)
    # P18 · A3: شماره‌ای که پیامک به آن رفته (برایِ سقفِ ساعتی به‌ازایِ هر شماره) و وضعیت/زمانِ ارسال.
    # در لاگ‌ها فقط ماسک‌شده نمایش داده می‌شود، هرگز خودِ شماره.
    phone_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    sent_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    provider_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
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
    # P18 · A7: رسیدِ متنیِ شارژِ اعتبار (مثلِ سمتِ فروشگاه) + پرچمِ تکراری (هرگز ردِ خودکار).
    receipt_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    receipt_tracking_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    receipt_sha256: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    receipt_flags: Mapped[str | None] = mapped_column(String(64), nullable=True)
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
    # کدِ درگاهِ بله‌پیِ خودِ همین فروشگاه (نه پلتفرم) — برایِ اینکه مشتری‌ها
    # بتونن هزینه‌ی سفارش رو مستقیم به حسابِ خودِ فروشگاه‌دار پرداخت کنن (فازِ
    # ۳). درست مثلِ zarinpal_merchant_id بالا رمزنگاری نمی‌شه (هم‌راستا با
    # طرزِ ذخیره‌یِ فعلیِ این‌جور شناسه‌هایِ درگاه در این پروژه — برخلافِ
    # encrypted_token که واقعاً کنترلِ کاملِ رباتُ می‌ده و رمزنگاری می‌شه).
    bale_provider_token: Mapped[str | None] = mapped_column(EncryptedToken(512), nullable=True)
    # سوال‌هایی که فروشگاه‌دار موقعِ چک‌اوتِ سبدِ خرید از مشتری می‌پرسه — هر خط
    # یه سوال. خالی/تنظیم‌نشده = پیش‌فرض (فقط شماره‌تماس + آدرس). دقیقاً مثلِ
    # global_ai_system_prompt یه فیلدِ آزادِ متنیِ فروشگاه‌دار-تعریف‌شده‌ست.
    checkout_questions: Mapped[str | None] = mapped_column(Text, nullable=True)
    # فازِ ۶-الف: مدتِ تجمیعِ پیام‌هایِ پشتِ‌همِ مشتری (ثانیه، ۲ تا ۶۰). null = پیش‌فرضِ سیستم
    # (customer.DEBOUNCE_SECONDS). بیشتر = پیام‌هایِ پشتِ‌هم بیشتر یکی می‌شن و توکنِ کمتری مصرف می‌شه،
    # ولی جوابِ ربات دیرتر میاد. هر فروشگاه‌دار برایِ خودش تنظیم می‌کنه (هزینه با اونه).
    message_batch_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # فازِ ۱ · P1-S1 (D1/D2): پشتیبانیِ فروشگاه برایِ مشتری‌ها (حالتِ relay در فازِ ۲؛ فعلاً فقط direct)
    support_enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    support_mode: Mapped[str] = mapped_column(String(16), default="direct", server_default="direct", nullable=False)
    support_contact_username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    support_contact_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    support_contact_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    tenant_mode: Mapped[TenantMode] = _enum_column(TenantMode, default=TenantMode.SALES, nullable=False)
    knowledge_channel_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    knowledge_channel_bot: Mapped[str | None] = mapped_column(String(16), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    disabled_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_report_sent_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # آخرین تاریخی (نه datetime — فقط روز) که گزارشِ شبانه براش فرستاده شده؛
    # برای جلوگیری از دوبار-فرستادن توی یه روز (چک هر ۳۰ دقیقه اجرا می‌شه).
    last_nightly_report_date: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    # فازِ ۱ · W2 (C2): مسیرِ قدیمیِ «AI از چت سفارش می‌سازه». پیش‌فرض خاموش؛ تا False است
    # `_detect_and_notify_order` اجرا نمی‌شه (هزینه‌یِ ORDER_DETECTION هم صفره).
    legacy_ai_order_detection: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    # P18 · B5: زمانِ گزارشِ دوره‌ای از نگاهِ فروشگاه‌دار و به وقتِ تهران (نه UTC و نه «N روز از آخرین ارسال»).
    # weekday با هفته‌یِ ایرانی: ۰=شنبه … ۶=جمعه.
    weekly_report_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
    weekly_report_weekday: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    weekly_report_hour: Mapped[int] = mapped_column(Integer, default=9, server_default="9", nullable=False)
    # P18 · A5: این پنج مقدار پیش‌تر سراسری بودند و ادمینِ پلتفرم برایِ همه تصمیم می‌گرفت. حالا per-shop اند
    # و NULL یعنی «همان پیش‌فرضِ سراسریِ AdminSettings» ⇒ فروشگاهِ بدونِ تنظیم دقیقاً مثلِ قبل رفتار می‌کند
    # و هیچ مهاجرتِ داده‌ای لازم نیست. ستون‌هایِ سراسری به‌عنوانِ پیش‌فرض سرِ جایشان می‌مانند.
    payment_reservation_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    order_reservation_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    order_confirmation_timeout_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    conversation_retention_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    knowledge_items_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # P18 · B9: روشن/خاموش‌بودن و متنِ پرسشِ پنج گامِ ثابتِ چک‌اوت. JSONِ متنی (نه ستونِ JSONB) تا با
    # بقیه‌یِ ذخیره‌سازیِ این پروژه هم‌خوان باشد؛ NULL ⇒ همه‌یِ گام‌ها روشن با متنِ پیش‌فرض (رفتارِ امروز).
    checkout_config: Mapped[str | None] = mapped_column(Text, nullable=True)
    # P18 · A2: متنِ خودِ فروشگاه‌دار که *کنارِ* متنِ ادمین در بیو می‌آید + ردِ دست‌کاری.
    branding_owner_text: Mapped[str | None] = mapped_column(String(120), nullable=True)
    branding_tamper_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    branding_set_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

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
    # فازِ ۱ · P1-S1 (H2): هویتِ متنیِ مشتری — شماره به‌شکلِ نرمالِ +98…؛ phone_via_contact = از «اشتراکِ مخاطب»ِ خودش آمده
    last_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    phone_via_contact: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    first_seen_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_message_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # CRM (فازِ ۴): یادداشتِ آزادِ فروشگاه‌دار (حداکثر ۱۰۰۰ حرف، سقف توی crm_service) و
    # برچسب‌ها (حداکثر ۵ تا، هر کدوم ≤۲۰ حرفِ نرمال‌شده، جداشده با «,»). فقط خودِ فروشگاه‌دار
    # می‌نویسه و می‌بینه؛ هیچ‌وقت به پرامپتِ رباتِ مشتری یا دستیارِ مدیریتی داده نمی‌شه.
    crm_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    crm_tags: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # P18 · B4: مشتریِ بلاک‌شده ⇒ رباتِ فروشگاه پیامش را بی‌هزینه رد می‌کند (بدونِ AI/سفارش/پرداخت)
    # و فقط یک پیامِ ادبی می‌دهد. در آمار و گزارش‌ها همچنان لحاظ می‌شود.
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)


class Product(Base, CreatedAtMixin):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    shop_bot_id: Mapped[int] = mapped_column(ForeignKey("shop_bots.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    price_toman: Mapped[int] = mapped_column(Integer, nullable=False)
    photo_file_id: Mapped[str | None] = mapped_column(String(255), nullable=True)  # file_idِ رباتِ اصلی (آپلودِ فروشگاه‌دار)
    # W5: file_idِ معتبر برایِ رباتِ فروشگاه (آپلودِ دوباره؛ قالب «<برچسبِ منبع>|<file_id>» تا با تغییرِ عکس خودکار باطل بشه)
    photo_shop_file_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stock_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # جمعِ واحدهایی که الان توسطِ سفارش‌های PENDING رزرو شدن (فقط برای محصولاتی
    # که stock_quantity دارن معنی داره؛ محصولِ نامحدود reserved_quantity=0 می‌مونه
    # و اصلاً چک نمی‌شه). «موجودیِ واقعاً قابل‌فروش» = stock_quantity - reserved_quantity.
    reserved_quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # فازِ ۱ · P1-S3 (B2): نوعِ محصول. physical|digital (String، نه enumِ PostgreSQL).
    # تغییرِ نوعِ محصولِ ساخته‌شده ممنوعه (فقط کپی)؛ مقدارِ پیش‌فرض physical = رفتارِ قبلی.
    kind: Mapped[str] = mapped_column(String(16), default="physical", server_default="physical", nullable=False)
    # فیزیکی (همه اختیاری؛ فقط برایِ پاسخ‌گوییِ AI و نمایش)
    weight_grams: Mapped[int | None] = mapped_column(Integer, nullable=True)
    delivery_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    return_policy: Mapped[str | None] = mapped_column(Text, nullable=True)
    # دستورِ اختصاصیِ AI برایِ همین محصول (در پرامپت به N نویسه کوتاه می‌شه)
    ai_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    # دیجیتال: روشِ تحویل file|link|text|code_pool
    digital_delivery: Mapped[str | None] = mapped_column(String(16), nullable=True)
    digital_file_id: Mapped[str | None] = mapped_column(String(255), nullable=True)  # file_idِ رباتِ اصلی
    digital_file_shop_file_id: Mapped[str | None] = mapped_column(String(255), nullable=True)  # file_idِ معتبر برایِ رباتِ فروشگاه (بعد از اولین ارسال)
    digital_file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    digital_link: Mapped[str | None] = mapped_column(Text, nullable=True)
    digital_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    digital_max_downloads: Mapped[int | None] = mapped_column(Integer, nullable=True)

    shop_bot: Mapped["ShopBot"] = relationship(back_populates="products", lazy="selectin")


class Cart(Base, CreatedAtMixin):
    """سبدِ خریدِ «زنده»یِ هر مشتری در هر فروشگاه — یکی به‌ازایِ هر
    (shop_bot, customer)، همیشه همون ردیف دوباره استفاده می‌شه (بعدِ
    چک‌اوت، فقط آیتم‌هاش پاک می‌شن، خودِ Cart می‌مونه)."""

    __tablename__ = "carts"
    __table_args__ = (UniqueConstraint("shop_bot_id", "customer_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    shop_bot_id: Mapped[int] = mapped_column(ForeignKey("shop_bots.id"), index=True, nullable=False)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True, nullable=False)


class CartItem(Base, CreatedAtMixin):
    __tablename__ = "cart_items"
    __table_args__ = (UniqueConstraint("cart_id", "product_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cart_id: Mapped[int] = mapped_column(ForeignKey("carts.id"), index=True, nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class Campaign(Base, CreatedAtMixin):
    """کمپینِ تخفیفِ مخصوصِ مشتری‌هایِ یه فروشگاه (فازِ ۳) — کاملاً جدا از
    DiscountCode (که فقط تخفیفِ پرداختِ فروشگاه‌دار به *پلتفرمه*).

    code نال = کمپینِ خودکار (بدونِ کد، برایِ همه در پیش‌نمایشِ چک‌اوت اعمال می‌شه)؛
    code پر = مشتری باید کد رو وارد کنه. code همیشه «نرمال‌شده» ذخیره می‌شه
    (campaign_service.normalize_code) و در هر فروشگاه یکتاست (NULLها تداخل ندارن).

    تعدادِ دفعاتِ استفاده *شمارنده* نیست، از روی سفارش‌ها مشتق می‌شه
    (OrderConsultation.campaign_id) — پس ردِ سفارش/انقضایِ رزرو خودبه‌خود سهمیه
    رو آزاد می‌کنه. starts_at/ends_at به UTC.
    """

    __tablename__ = "campaigns"
    __table_args__ = (UniqueConstraint("shop_bot_id", "code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    shop_bot_id: Mapped[int] = mapped_column(ForeignKey("shop_bots.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    discount_type: Mapped[CampaignDiscountType] = _enum_column(CampaignDiscountType, nullable=False)
    # PERCENT: عددِ ۱ تا ۱۰۰ (درصد). FIXED: مبلغِ تومانی.
    discount_value: Mapped[int] = mapped_column(Integer, nullable=False)
    # فقط برایِ PERCENT معنی داره: سقفِ مبلغِ تخفیف (تومان). نال = بدونِ سقف.
    max_discount_toman: Mapped[int | None] = mapped_column(Integer, nullable=True)
    min_cart_total_toman: Mapped[int | None] = mapped_column(Integer, nullable=True)
    starts_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # نال = نامحدود.
    total_usage_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    per_customer_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class DiscountCodeUsage(Base):
    __tablename__ = "discount_code_usages"
    __table_args__ = (UniqueConstraint("discount_code_id", "shop_owner_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    discount_code_id: Mapped[int] = mapped_column(ForeignKey("discount_codes.id"), nullable=False)
    shop_owner_id: Mapped[int] = mapped_column(ForeignKey("shop_owners.id"), nullable=False)
    payment_id: Mapped[int] = mapped_column(ForeignKey("payments.id"), nullable=False)


class KnowledgeGap(Base):
    """سوالی که رباتِ فروشگاه از اطلاعاتِ فروشگاه نتونسته جوابش رو بده (فازِ ۴-الف).

    question_key = هشِ سوالِ نرمال‌شده؛ سوالِ تکراری (حتی با فاصله/رقمِ فارسی/ی-کِ متفاوت)
    یه ردیف می‌مونه و occurrences بالا می‌ره. question_text *غیرِ قابلِ اعتماده* (از مشتری
    میاد): همیشه به‌صورتِ متنِ ساده نشون داده می‌شه و موقعِ رفتن به AI توی بلوکِ نقل‌قول می‌ره.
    """

    __tablename__ = "knowledge_gaps"
    __table_args__ = (UniqueConstraint("shop_bot_id", "question_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    shop_bot_id: Mapped[int] = mapped_column(ForeignKey("shop_bots.id"), index=True, nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    question_key: Mapped[str] = mapped_column(String(64), nullable=False)
    occurrences: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    first_seen_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_seen_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    status: Mapped[KnowledgeGapStatus] = _enum_column(KnowledgeGapStatus, default=KnowledgeGapStatus.OPEN, nullable=False)


class LearnedAnswer(Base, CreatedAtMixin):
    """پرسش‌وپاسخِ تاییدشده توسطِ فروشگاه‌دار (فازِ ۴-ب) — تنها راهِ «یادگیریِ» ربات: هیچ‌چیز
    خودکار از مکالمه‌ها یاد گرفته نمی‌شه. جواب رو خودِ فروشگاه‌دار می‌نویسه (قابلِ اعتماد)؛
    سوال ممکنه از متنِ مشتری اومده باشه (غیرِ قابلِ اعتماد) و توی پرامپت به‌شکلِ نقل‌قول می‌ره."""

    __tablename__ = "learned_answers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    shop_bot_id: Mapped[int] = mapped_column(ForeignKey("shop_bots.id"), index=True, nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    source_gap_id: Mapped[int | None] = mapped_column(ForeignKey("knowledge_gaps.id"), index=True, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


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
    # W5 · 2.2: بعد از «استردادِ انجام‌شد» اگه فروشگاه‌دار موجودی رو برگردوند (یک‌بار)
    restocked_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reservation_expires_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # پرداختِ آنلاینِ سفارش از طریقِ بله‌پی (فازِ ۳) — کاملاً مستقل از status
    # بالا: فروشگاه‌دار همچنان از همون مسیرِ همیشگی (confirm_order/advance_status)
    # سفارش رو پردازش می‌کنه؛ این سه ستون فقط اطلاعِ «آیا/کِی/با چه شناسه‌ای
    # مشتری آنلاین پرداخت کرد» رو نگه می‌دارن تا فروشگاه‌دار موقعِ پردازش، لازم
    # نباشه دوباره وجه رو نقدی/دستی از مشتری بگیره.
    bale_invoice_payload: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    bale_transaction_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    bale_paid_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # سبدِ خرید (فازِ ۳): وقتی یه چک‌اوتِ سبد به چند ردیفِ OrderConsultation
    # (یکی به‌ازایِ هر محصول — همون الگویِ تک‌محصولیِ فعلی برایِ هر ردیف حفظ
    # می‌شه) تبدیل می‌شه، همه‌شون یه cart_checkout_group_idِ مشترک می‌گیرن — فقط
    # برایِ گروه‌بندیِ نمایشی (یه اطلاع‌رسانیِ ترکیبی به فروشگاه‌دار، یه لینکِ
    # پرداختِ مشترک برایِ کلِ سبد)، نه یه رابطه‌ی دیتابیسیِ رسمی. checkout_answers
    # جوابِ سوال‌هایِ چک‌اوت (یا پیش‌فرض: شماره/آدرس) رو به‌شکلِ متنِ فرمت‌شده نگه
    # می‌داره — customer_phone/customer_address بالا دست‌نخورده و مخصوصِ همون
    # فلویِ چتِ AIِ قبلی می‌مونن.
    cart_checkout_group_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    checkout_answers: Mapped[str | None] = mapped_column(Text, nullable=True)

    # کمپینِ تخفیف (فازِ ۳): اگه این ردیف از یه چک‌اوتِ سبد با کمپین ثبت شده باشه،
    # campaign_id همون کمپینه و discount_toman «سهمِ همین ردیف» از تخفیفِ سبده
    # (تخفیفِ سبد متناسب با مبلغِ هر ردیف پخش می‌شه و جمعِ سهم‌ها دقیقاً برابرِ
    # تخفیفِ کلِ سبده). estimated_value_toman از اول *بعد از تخفیف* ذخیره می‌شه،
    # پس آمار/اکسل/بله‌پی بدونِ هیچ تغییری فروشِ خالص رو جمع می‌زنن.
    campaign_id: Mapped[int | None] = mapped_column(ForeignKey("campaigns.id"), index=True, nullable=True)
    discount_toman: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # فازِ ۱ · P1-S3 (B2): تحویلِ محصولِ دیجیتال. digital_delivered_at خالی = هنوز تحویل نشده
    # (ایدمپوتنسی)؛ digital_download_count شمارِ دفعاتِ ارسال (اولین تحویل = ۱) برایِ سقفِ digital_max_downloads.
    digital_delivered_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    digital_download_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)

    # فازِ ۱ · W2 (C4/C3): پرداخت/ارسال. شناسه‌یِ واحدِ وضعیت = cart_checkout_group_id (تک‌محصولی = گروهِ یک‌ردیفی)
    paid_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    tracking_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    carrier_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    shipping_fee_toman: Mapped[int | None] = mapped_column(Integer, nullable=True)
    shipping_method_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    cancel_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    payment_method: Mapped[str | None] = mapped_column(String(32), nullable=True)


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
    """این کلید برای چه نوع فراخوانی‌ای مناسبه — پاسخِ متنی، تحلیلِ عکس، هر دو، یا رونویسیِ صوت.

    `both` همان معنایِ همیشگی را دارد (چت + بینایی)؛ `stt` عمداً با `both` یکی نیست تا
    کلیدهایِ چتِ قدیمی ناگهانی در مسیرِ صوت وارد نشوند.
    """

    CHAT = "chat"
    VISION = "vision"
    BOTH = "both"
    STT = "stt"


class AiApiKeyPoolEntry(Base, CreatedAtMixin):
    """
    یه کلیدِ API در استخرِ کلیدهای هوش مصنوعیِ پلتفرم. وقتی چند کلید ثبت شده
    باشه، هر فراخوانی از یه کلیدِ تصادفی شروع می‌کنه و اگه اون شکست خورد
    (یا مدارِ قطعش به‌خاطرِ شکست‌های پیاپیِ اخیر باز باشه)، به کلیدِ بعدی
    می‌ره — هم بارِ درخواست‌ها بینِ چند کلید پخش می‌شه، هم یه کلیدِ مشکل‌دار
    کلِ پلتفرم رو از کار نمی‌ندازه. اگه هیچ کلیدی توی استخر نباشه،
    admin_settings.ai_api_key/ai_fallback_api_key (روشِ قدیمی) استفاده می‌شه.

    P18 · A4: هر ورودی علاوه بر مدلِ اصلی، فهرستِ ترتیبیِ مدل‌هایِ پشتیبانِ
    *همان کلید* را هم دارد (`fallback_models`؛ با ویرگول/خطِ جدید جدا می‌شن).
    اولِ همان کلید تا آخرِ فهرست امتحان می‌شود و بعد کلیدِ بعدیِ استخر؛
    سلامت و cooldown به‌ازایِ (کلید + مدل) ثبت می‌شود.
    """

    __tablename__ = "ai_api_key_pool"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    api_key: Mapped[str] = mapped_column(EncryptedToken, nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    fallback_models: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
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


class PaymentEventLog(Base):
    """B12: ردِ هر تماس/رویدادِ پرداخت (بله/زرین‌پال) برایِ عیب‌یابی با پولِ واقعی؛ JSONِ خام بدونِ توکن/شماره‌کارت."""

    __tablename__ = "payment_event_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    direction: Mapped[str] = mapped_column(String(8), nullable=False)  # out = درخواست به ارائه‌دهنده، in = رویدادِ ورودی
    method: Mapped[str] = mapped_column(String(64), nullable=False)
    reference: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    # د(ز): شناسه‌یِ همبستگی — کدام فروشگاه و کدام گروه/سفارش، تا لاگِ پرداخت قابلِ ردیابی باشد.
    shop_bot_id: Mapped[int | None] = mapped_column(Integer, index=True, nullable=True)
    group_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class DigitalCode(Base, CreatedAtMixin):
    """استخرِ کد/لایسنسِ محصولِ دیجیتالِ `code_pool` (یک ردیف = یک کد).
    code رمزنگاری‌شده (`encrypt_token`)؛ code_hash (sha256 از متنِ نرمال‌شده) فقط برایِ
    جلوگیری از کدِ تکراری در همون محصول. status: available|delivered. اختصاص فقط با
    SELECT … FOR UPDATE SKIP LOCKED (digital_service)."""

    __tablename__ = "digital_codes"
    __table_args__ = (UniqueConstraint("product_id", "code_hash"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True, nullable=False)
    code: Mapped[str] = mapped_column(Text, nullable=False)
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="available", server_default="available", index=True, nullable=False)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders_consultations.id"), index=True, nullable=True)
    delivered_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ShippingMethod(Base, CreatedAtMixin):
    """روشِ ارسالِ فروشگاه (فیزیکی). در W1 فقط تعریف/نمایش؛ اعمالِ هزینه در چک‌اوت با W2."""

    __tablename__ = "shipping_methods"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    shop_bot_id: Mapped[int] = mapped_column(ForeignKey("shop_bots.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    fee_toman: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    free_over_toman: Mapped[int | None] = mapped_column(Integer, nullable=True)
    eta_text: Mapped[str | None] = mapped_column(String(128), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)


class OrderEvent(Base, CreatedAtMixin):
    """خط‌زمانِ سفارش (C4): هر گذارِ وضعیت/رویدادِ مهم یک ردیف. هرگز ویرایش/حذف نمی‌شه."""

    __tablename__ = "order_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders_consultations.id"), index=True, nullable=True)
    group_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    from_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    to_status: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(16), default="system", server_default="system", nullable=False)
    actor_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class Invoice(Base, CreatedAtMixin):
    """فاکتورِ هر گروهِ سفارش (C8): اسنپ‌شاتِ ثابت؛ برایِ هر group_id فقط یکی (ایدمپوتنت)."""

    __tablename__ = "invoices"
    __table_args__ = (UniqueConstraint("shop_bot_id", "group_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    shop_bot_id: Mapped[int] = mapped_column(ForeignKey("shop_bots.id"), index=True, nullable=False)
    group_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    number: Mapped[str] = mapped_column(String(48), unique=True, nullable=False)
    data_json: Mapped[str] = mapped_column(Text, nullable=False)


class InvoiceCounter(Base):
    """شمارنده‌یِ فاکتور به‌ازایِ (فروشگاه، ماه)؛ فقط با SELECT … FOR UPDATE افزایش می‌یابد."""

    __tablename__ = "invoice_counters"
    __table_args__ = (UniqueConstraint("shop_bot_id", "period"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    shop_bot_id: Mapped[int] = mapped_column(ForeignKey("shop_bots.id"), index=True, nullable=False)
    period: Mapped[str] = mapped_column(String(6), nullable=False)  # YYYYMM
    last_seq: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)


class CustomerAddress(Base, CreatedAtMixin):
    """دفترچه‌آدرسِ مشتری (C3) — هر مشتری در هر فروشگاه؛ حداکثر یک پیش‌فرض."""

    __tablename__ = "customer_addresses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True, nullable=False)
    label: Mapped[str | None] = mapped_column(String(64), nullable=True)
    province: Mapped[str | None] = mapped_column(String(64), nullable=True)
    city: Mapped[str | None] = mapped_column(String(64), nullable=True)
    address: Mapped[str] = mapped_column(Text, nullable=False)
    postal_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)


class CartAiProposal(Base, CreatedAtMixin):
    """پیشنهادِ ویرایشِ سبد توسطِ AI (C2): ذخیره تا تاییدِ یک‌ضربه‌ایِ مشتری؛ انقضا ۱۰ دقیقه."""

    __tablename__ = "cart_ai_proposals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cart_id: Mapped[int] = mapped_column(ForeignKey("carts.id"), index=True, nullable=False)
    ops_json: Mapped[str] = mapped_column(Text, nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(16), nullable=False)
    used: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)


class DirectMessage(Base, CreatedAtMixin):
    """پیامِ مستقیمِ فروشگاه‌دار به مشتری (D5-ساده) — ثبتِ ارسال/خطا."""

    __tablename__ = "direct_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    shop_bot_id: Mapped[int] = mapped_column(ForeignKey("shop_bots.id"), index=True, nullable=False)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True, nullable=False)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders_consultations.id"), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    delivered: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)


class ShopPaymentSettings(Base, CreatedAtMixin):
    """روش‌هایِ پرداختِ مشتریِ هر فروشگاه (C5) — ۱:۱ با ShopBot. شماره‌کارت/مرچنت رمزنگاری‌شده."""

    __tablename__ = "shop_payment_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    shop_bot_id: Mapped[int] = mapped_column(ForeignKey("shop_bots.id"), unique=True, nullable=False)
    card_enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    card_number_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    card_holder_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    bank_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    card_deadline_minutes: Mapped[int] = mapped_column(Integer, default=60, server_default="60", nullable=False)
    receipt_review_hold_minutes: Mapped[int] = mapped_column(Integer, default=1440, server_default="1440", nullable=False)
    bale_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
    bale_deadline_minutes: Mapped[int] = mapped_column(Integer, default=15, server_default="15", nullable=False)
    zarinpal_enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    zarinpal_merchant_id_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    zarinpal_deadline_minutes: Mapped[int] = mapped_column(Integer, default=15, server_default="15", nullable=False)
    manual_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
    auto_accept_online: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
    receipt_ai_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
    max_receipt_attempts: Mapped[int] = mapped_column(Integer, default=5, server_default="5", nullable=False)


class OrderPayment(Base, CreatedAtMixin):
    """یک تلاشِ پرداخت برایِ یک گروهِ سفارش (C6/C7/M). status: initiated|submitted|approved|rejected|expired|failed|paid."""

    __tablename__ = "order_payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    group_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    shop_bot_id: Mapped[int] = mapped_column(ForeignKey("shop_bots.id"), index=True, nullable=False)
    method: Mapped[str] = mapped_column(String(16), nullable=False)  # card | bale | zarinpal
    status: Mapped[str] = mapped_column(String(16), default="initiated", server_default="initiated", nullable=False)
    amount_toman: Mapped[int] = mapped_column(Integer, nullable=False)
    receipt_sha256: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    tracking_ref: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    # W5: رسیدِ متنی (مثلاً متنِ کپی‌شده از اپِ بانک/پیامک)؛ هش‌اش در receipt_sha256 برایِ تشخیصِ تکراری می‌رود
    receipt_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_verdict: Mapped[str | None] = mapped_column(String(16), nullable=True)
    flags: Mapped[str | None] = mapped_column(String(200), nullable=True)
    decided_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    reject_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempt_no: Mapped[int] = mapped_column(Integer, default=1, server_default="1", nullable=False)
    # آنلاین (بله‌پی/زرین‌پال): payload/authority + شناسه‌یِ تراکنشِ تاییدشده (UNIQUE ⇒ ایدمپوتنسیِ B10)
    provider_ref: Mapped[str | None] = mapped_column(String(160), index=True, nullable=True)
    transaction_ref: Mapped[str | None] = mapped_column(String(80), unique=True, nullable=True)
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    # W5 · 2.2: هشدارِ «۲ ساعت تا انقضایِ بررسیِ رسید» فقط یک‌بار
    review_warned_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TimeFreeze(Base, CreatedAtMixin):
    """W5 · K3: «توقفِ زمان» — موقعِ ازسرگیری، همه‌یِ تاریخ‌هایِ انقضایِ مشمول به‌اندازه‌یِ مدتِ توقف جلو می‌رن
    (شارژِ کیف‌پول و اشتراک) و در طولِ توقف جاب‌هایِ انقضا/یادآوری/مهلت برایِ مشمولین رد می‌شن.
    scope: 'all' (همه) | 'owner' (یک فروشگاه‌دار). status: active | resumed. `ends_at` = سقفِ خودکارِ ازسرگیری."""

    __tablename__ = "time_freezes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scope: Mapped[str] = mapped_column(String(8), nullable=False)
    shop_owner_id: Mapped[int | None] = mapped_column(ForeignKey("shop_owners.id"), index=True, nullable=True)
    status: Mapped[str] = mapped_column(String(12), default="active", server_default="active", index=True, nullable=False)
    started_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    max_days: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_by: Mapped[str] = mapped_column(String(64), nullable=False)
    resumed_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resumed_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    shifted_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    affected_count: Mapped[int | None] = mapped_column(Integer, nullable=True)


class AdminCreditBatch(Base, CreatedAtMixin):
    """W5 · K1/K2: یک عملیاتِ گروهیِ ادمین (هدیه‌یِ اعتبار / تمدیدِ روز). جریان: پیش‌نمایش ← تایید ← اجرا.
    `batch_id` یکتا + ردیف‌هایِ AdminCreditBatchItem (UNIQUE به‌ازایِ هر فروشگاه‌دار) ⇒ اجرایِ دوباره/دابل‌تپ اثرِ دوم ندارد."""

    __tablename__ = "admin_credit_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_id: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(8), nullable=False)  # gift | extend
    params_json: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(12), default="previewed", server_default="previewed", nullable=False)
    target_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    applied_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    skipped_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    executed_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AdminCreditBatchItem(Base):
    __tablename__ = "admin_credit_batch_items"
    __table_args__ = (UniqueConstraint("batch_id", "shop_owner_id", name="uq_credit_batch_owner"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    shop_owner_id: Mapped[int] = mapped_column(ForeignKey("shop_owners.id"), index=True, nullable=False)
