from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class RegistrationStates(StatesGroup):
    """ویزاردِ ثبت‌نام (A1): مود ← نامِ کوچک ← نامِ خانوادگی ← موبایل ← ایمیل ← مرورِ نهایی.
    choosing_mode / confirming_first_name / reviewing با دکمه‌یِ اینلاین جواب داده می‌شن، بقیه با متن."""

    choosing_mode = State()
    waiting_first_name = State()
    confirming_first_name = State()
    waiting_last_name = State()
    waiting_phone = State()
    waiting_phone_otp = State()
    waiting_email = State()
    waiting_email_otp = State()
    reviewing = State()


class ProfileStates(StatesGroup):
    """ویرایشِ اطلاعاتِ فروشگاه‌دار از «👤 پروفایل من» (A2)."""

    waiting_first_name = State()
    waiting_last_name = State()
    waiting_phone = State()
    waiting_phone_otp = State()
    waiting_email = State()
    waiting_email_otp = State()


class ShopBotTokenStates(StatesGroup):
    waiting_token = State()


class BaleShopBotStates(StatesGroup):
    """P19: توکنِ رباتِ بله‌یِ خودِ فروشگاه (کنارِ توکنِ تلگرام).

    P39: توکنِ درگاه از این گروه بیرون رفت — هر دو توکن در همان صفحهٔ
    «💳 پرداختِ آنلاینِ سفارش‌ها» گرفته می‌شوند (`BaleProviderTokenStates`).
    """

    waiting_token = State()


class InstagramStates(StatesGroup):
    """P49-الف: متنِ خوشآمدِ دایرکتِ اینستاگرام (تنظیم/پاک‌کردن با «خالی»)."""

    waiting_greeting = State()
    waiting_instructions = State()  # پ۶۰: متنِ هوشمندسازیِ اینستاگرامِ خودِ فروشگاه


class ProductStates(StatesGroup):
    waiting_name = State()
    waiting_description = State()
    waiting_price = State()
    waiting_photo = State()
    waiting_stock = State()
    waiting_edit_field_value = State()


class DigitalProductStates(StatesGroup):
    """افزودنِ محصولِ دیجیتال (P1-S3 / B2). choosing_mode با دکمه‌یِ اینلاین؛ بقیه با متن/فایل."""

    waiting_name = State()
    waiting_description = State()
    waiting_price = State()
    waiting_photo = State()
    choosing_mode = State()
    waiting_file = State()
    waiting_link = State()
    waiting_text = State()
    waiting_instructions = State()
    waiting_max_downloads = State()
    waiting_codes = State()


class ShippingStates(StatesGroup):
    waiting_name = State()
    waiting_fee = State()
    waiting_free_over = State()
    waiting_eta = State()


class ProductImportStates(StatesGroup):
    waiting_file = State()
    waiting_confirmation = State()


class AiInstructionsStates(StatesGroup):
    waiting_instructions = State()


class PreviewStates(StatesGroup):
    active = State()


class ChannelKnowledgeStates(StatesGroup):
    waiting_channel_proof = State()


class PaymentStates(StatesGroup):
    waiting_discount_code = State()
    waiting_receipt = State()
    waiting_topup_amount = State()


class BroadcastStates(StatesGroup):
    waiting_message = State()
    waiting_confirmation = State()


class CustomerBroadcastStates(StatesGroup):
    """پیامِ همگانیِ فروشگاه‌دار به مشتری‌هایِ خودش (فازِ ۳) — عمداً جدا از
    BroadcastStates بالا، که پیامِ همگانیِ ادمین به فروشگاه‌دارهاست؛ این دو
    قابلیتِ کاملاً متفاوتن (گیرنده/فرستنده/رباتِ ارسال‌کننده هرکدوم فرق داره)
    که فقط اسمِ فارسیِ مشابه دارن."""

    waiting_message = State()
    waiting_confirmation = State()
    # P21-D (F2): «برایِ بعد از» ⇒ بعد از تاییدِ متن، زمانِ ارسال پرسیده می‌شود
    waiting_when = State()


class BaleProviderTokenStates(StatesGroup):
    """کدِ درگاهِ بله‌پیِ خودِ فروشگاه (فازِ ۳، برایِ پرداختِ آنلاینِ سفارشِ
    محصول — نه شارژِ کیف‌پول/تمدیدِ اشتراک که تنظیماتِ سراسریِ ادمینه)."""

    waiting_token = State()


class CheckoutQuestionsStates(StatesGroup):
    """سوال‌هایی که فروشگاه‌دار می‌خواد موقعِ چک‌اوتِ سبدِ خرید از مشتری پرسیده
    بشه (فازِ ۳). هر خط یه سوال."""

    waiting_questions = State()


class AdminChannelStates(StatesGroup):
    waiting_name = State()
    waiting_channel_proof = State()
    waiting_is_primary = State()


class AdminPricingStates(StatesGroup):
    waiting_discount_code = State()
    waiting_discount_value = State()
    waiting_discount_max_uses = State()


class AdminSettingsStates(StatesGroup):
    waiting_value = State()
    waiting_referral_amount = State()


class AdminGiftStates(StatesGroup):
    waiting_amount = State()
    waiting_confirmation = State()


class AdminWalletCorrectionStates(StatesGroup):
    waiting_amount = State()
    waiting_reason = State()


class ModerationStates(StatesGroup):
    waiting_pattern = State()


class PerfRangeStates(StatesGroup):
    """P52 · موردِ ۲۰: ویزاردِ بازهٔ دلخواهِ گزارشِ همزمانی."""

    waiting_from = State()
    waiting_until = State()


class AiUsageStates(StatesGroup):
    """P55 · موردِ ۲۳: فقط نوشتنِ عددِ «سقفِ مصرف در ۲۴ ساعت» برایِ یکِ کاربر."""

    waiting_limit = State()


class StatsRangeStates(StatesGroup):
    """P51 · موردِ ۴۴: ویزاردِ «بازهٔ دلخواه» برایِ نمودارِ درآمد (همان شکلِ بازهٔ ممیزی)."""

    waiting_from = State()
    waiting_until = State()


class AiPoolStates(StatesGroup):
    waiting_entry_details = State()
    waiting_fallback_models = State()
    waiting_max_concurrent = State()  # P47 · سقفِ همزمانیِ همینِ کلید (در پنل، نه در .env)


class AuditRangeStates(StatesGroup):
    """P48 (موردِ ۳۹): پرسشِ دو سرِ بازهٔ دلخواه در صفحهٔ گزارشِ ممیزی."""

    waiting_from = State()
    waiting_until = State()


class AdminRoleStates(StatesGroup):
    waiting_telegram_id = State()
    waiting_scope = State()  # P21-E (F8)


class CampaignWizardStates(StatesGroup):
    """سازنده‌ی کمپین (فازِ ۳) — ویزاردِ چندمرحله‌ایِ فروشگاه‌دار برایِ ساختِ یه تخفیفِ
    مخصوصِ مشتری‌هاش. داده‌ها تویِ FSM data جمع می‌شن و فقط با «تاییدِ نهایی» ساخته می‌شن."""

    waiting_name = State()
    waiting_type = State()
    waiting_value = State()
    waiting_max_discount = State()
    waiting_code_choice = State()
    waiting_code = State()
    waiting_min_cart = State()
    waiting_duration = State()
    waiting_total_limit = State()
    waiting_per_customer_limit = State()
    waiting_confirmation = State()


class KnowledgeStates(StatesGroup):
    """سوال‌هایِ بی‌جواب و پرسش‌وپاسخ‌هایِ تاییدشده (فازِ ۴-الف/ب). داده‌ها (gap_id، سوال، جواب)
    تویِ FSM data جمع می‌شن و فقط با «تاییدِ نهایی» ذخیره می‌شن."""

    waiting_gap_answer = State()
    waiting_gap_confirm = State()
    waiting_edit_answer = State()
    waiting_manual_question = State()
    waiting_manual_answer = State()
    waiting_manual_confirm = State()


class CrmStates(StatesGroup):
    """یادداشت و برچسبِ مشتری (فازِ ۴-ج). customer_id توی FSM data."""

    waiting_note = State()
    waiting_tags = State()
    waiting_search = State()  # P56 · موردِ ۴۱: عبارتِ جست‌وجویِ مشتری (عبارت در FSM data می‌ماند)


class AdminOwnerSearchStates(StatesGroup):
    """P56 · موردِ ۲۷: عبارتِ جست‌وجو در فهرستِ فروشگاه‌دارها؛ صفحه‌گردانی دوباره فیلتر می‌کند."""

    waiting_term = State()


class AssistantStates(StatesGroup):
    """دستیارِ مدیریتیِ فقط‌خواندنی (فازِ ۴-د). حافظه‌یِ کوتاهِ گفتگو (assistant_history) توی FSM data؛
    برخلافِ PreviewStates.active استثنایِ MenuButtonEscapeMiddleware نیست: دکمه‌هایِ منو از گفتگو خارج می‌کنن."""

    active = State()


class ShopSettingsStates(StatesGroup):
    """تنظیماتِ رباتِ فروشگاه (فازِ ۶-الف + P18 · A5/B5/B9): تجمیعِ پیام‌ها، پشتیبانی، زمانِ گزارشِ دوره‌ای،
    مهلت‌ها/حافظه‌یِ per-shop و گام‌هایِ چک‌اوت."""

    waiting_batch_seconds = State()
    waiting_support_username = State()
    waiting_support_phone = State()
    waiting_support_text = State()
    waiting_report_hour = State()
    waiting_pref_value = State()
    waiting_checkout_step_question = State()
    waiting_branding_text = State()
    waiting_stock_threshold = State()  # P21-D (F7)


class OrderOpsStates(StatesGroup):
    """عملیاتِ گروهیِ سفارش توسطِ فروشگاه‌دار (W2 · C4/C9/D5): کدِ رهگیری، دلیلِ ردّ، پیامِ مستقیم."""

    waiting_tracking_code = State()
    waiting_reject_text = State()
    waiting_direct_message = State()


class PaymentSettingsStates(StatesGroup):
    """تنظیمِ روش‌هایِ پرداختِ مشتری (W3 · C5)."""

    waiting_card_number = State()
    waiting_card_holder = State()
    waiting_card_bank = State()
    waiting_deadline = State()
    waiting_hold = State()
    waiting_zarinpal_merchant = State()


class PaymentOpsStates(StatesGroup):
    """تصمیمِ فروشگاه‌دار رویِ رسید (W3 · C6): دلیلِ ردِ متنی."""

    waiting_reject_text = State()


class InactiveOwnerStates(StatesGroup):
    """تاییدِ نوشتاریِ «حذفِ قطعی» (P22 · مشکلِ ۸) — فقط سوپرادمین، فقط برایِ حسابِ ازپیش غیرفعال."""

    waiting_word = State()


class AccountDeletionStates(StatesGroup):
    """پ۶۵ · موردِ ۲۷/۴۱: تاییدِ نوشتاریِ «حذفِ حسابِ من» در پنلِ خودِ فروشگاه‌دار.

    عمداً گروهی جدا از `InactiveOwnerStates` (آن مسیرِ ادمین است و `IsAdmin` فیلتر دارد) و
    عمدتاً واژه‌ای که اینجا پرسیده می‌شود در `_KNOWN_MENU_BUTTONS` ثبت *نمی‌شود*: میدل‌ورِ فرارِ
    منو هر متنی را که با برچسبِ یکِ دکمهٔ منو برابر باشد first `state.clear()` می‌کند، پس اگر
    «حذفِ حساب» دکمهٔ منو هم می‌شد، تایپِ خودِ واژهٔ تایید حالت را می‌ساخت و هیچ‌چیز حذف نمی‌شد.
    """

    waiting_word = State()


class AdminTimeStates(StatesGroup):
    """W5 · K1–K4: هدیه/تمدیدِ گروهی، توقفِ زمان."""

    waiting_gift_amount = State()
    waiting_extend_days = State()
    waiting_freeze_owner = State()
    waiting_freeze_days = State()
    waiting_freeze_reason = State()
