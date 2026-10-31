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
    waiting_discount_type = State()
    waiting_discount_value = State()
    waiting_discount_max_uses = State()


class AdminSettingsStates(StatesGroup):
    waiting_value = State()
    waiting_referral_amount = State()
    waiting_rate_limit_max = State()
    waiting_rate_limit_window = State()


class AdminGiftStates(StatesGroup):
    waiting_amount = State()


class AdminWalletCorrectionStates(StatesGroup):
    waiting_amount = State()
    waiting_reason = State()


class ModerationStates(StatesGroup):
    waiting_pattern = State()


class AiPoolStates(StatesGroup):
    waiting_entry_details = State()


class AdminRoleStates(StatesGroup):
    waiting_telegram_id = State()


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


class AssistantStates(StatesGroup):
    """دستیارِ مدیریتیِ فقط‌خواندنی (فازِ ۴-د). حافظه‌یِ کوتاهِ گفتگو (assistant_history) توی FSM data؛
    برخلافِ PreviewStates.active استثنایِ MenuButtonEscapeMiddleware نیست: دکمه‌هایِ منو از گفتگو خارج می‌کنن."""

    active = State()


class ShopSettingsStates(StatesGroup):
    """تنظیماتِ رباتِ فروشگاه (فازِ ۶-الف). فعلاً فقط مدتِ تجمیعِ پیام‌ها؛ تنظیم‌هایِ بعدی (پشتیبانی، حافظه‌یِ AI،
    محدودیتِ عکس، زمانِ رزرو، ...) همین‌جا اضافه می‌شن."""

    waiting_batch_seconds = State()
    waiting_support_username = State()
    waiting_support_phone = State()
    waiting_support_text = State()
    waiting_report_hour = State()


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


class AdminTimeStates(StatesGroup):
    """W5 · K1–K4: هدیه/تمدیدِ گروهی، توقفِ زمان."""

    waiting_gift_amount = State()
    waiting_extend_days = State()
    waiting_freeze_owner = State()
    waiting_freeze_days = State()
    waiting_freeze_reason = State()
