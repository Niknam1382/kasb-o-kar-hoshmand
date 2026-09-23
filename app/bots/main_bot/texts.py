from __future__ import annotations

import datetime

from app.utils.validators import format_toman

# =============================================================================
# عمومی
# =============================================================================
GENERIC_ERROR = "متاسفانه یه خطای غیرمنتظره پیش اومد. لطفاً دوباره امتحان کن."
INVALID_INPUT_RETRY = "این ورودی معتبر نیست. لطفاً دوباره امتحان کن."
OPERATION_CANCELLED = "عملیات لغو شد."
ASK_TO_USE_PANEL_BUTTONS = "لطفاً از دکمه‌های پایین صفحه استفاده کن."
ADMIN_INVALID_NUMBER = "این یک عدد معتبر نیست. لطفاً دوباره امتحان کن."
ADMIN_INVALID_PERCENT = "درصد باید عددی بین ۱ تا ۱۰۰ باشد."


# =============================================================================
# استارت / گیت کانال اجباری (مرحله ۲)
# =============================================================================
def channels_gate_intro(channels) -> str:
    lines = ["👋 برای استفاده از ربات، اول باید عضو کانال‌(های) زیر بشی:"]
    for ch in channels:
        lines.append(f"• {ch.name}")
    lines.append("\nبعد از عضویت، روی دکمه‌ی «✅ عضو شدم» بزن.")
    return "\n".join(lines)


CHANNELS_GATE_STILL_NOT_MEMBER = "❗️ هنوز عضو همه‌ی کانال‌های بالا نشدی. لطفاً عضو شو و دوباره امتحان کن."
CHANNELS_GATE_PASSED = "✅ عضویتت تایید شد!"


# =============================================================================
# ثبت‌نام (مرحله ۲ و ۳)
# =============================================================================
ASK_FIRST_NAME = "برای شروع، لطفاً نامت رو بنویس:"
REGISTRATION_CLOSED = "ثبت‌نامِ کاربرانِ جدید فعلاً موقتاً بسته‌ست. لطفاً بعداً دوباره امتحان کن یا با پشتیبانی در تماس باش."
ASK_LAST_NAME = "نام خانوادگیت چیه؟"
ASK_PHONE = "شماره موبایلت رو بفرست (می‌تونی از دکمه‌ی زیر هم استفاده کنی):"
INVALID_PHONE = "شماره موبایل معتبر نیست. لطفاً یه شماره ایرانی معتبر بفرست (مثلاً 09123456789)."
ASK_EMAIL = "ایمیلت رو بفرست:"
INVALID_EMAIL = "این ایمیل معتبر به‌نظر نمی‌رسه. لطفاً دوباره امتحان کن."
OTP_INVALID_OR_EXPIRED = "کد وارد شده اشتباهه یا منقضی شده. لطفاً دوباره امتحان کن."


def otp_sent_sms(phone: str) -> str:
    return f"📲 یه کد تایید ۶ رقمی به شماره {phone} پیامک شد. لطفاً همون کد رو اینجا بفرست:"


def otp_sent_email(email: str) -> str:
    return f"📧 یه کد تایید ۶ رقمی به ایمیل {email} ارسال شد. لطفاً همون کد رو اینجا بفرست:"


def test_mode_otp_notice(code: str) -> str:
    return f"🧪 حالت تست فعاله — کد تایید: {code}\n(در حالت واقعی این کد پیامک/ایمیل می‌شه.)"


def registration_complete_welcome(first_name: str) -> str:
    return (
        f"🎉 خوش اومدی {first_name}!\n\n"
        "ثبت‌نامت با موفقیت کامل شد. حالا می‌تونی از پنل فروشگاه‌دارت استفاده کنی."
    )


def trial_offer_text(reference_channel_link: str | None = None, trial_credit_toman: int = 0) -> str:
    lines = [
        "🎁 می‌خوای رایگان پلتفرم رو امتحان کنی؟",
        f"با فعال‌سازی اعتبار آزمایشی، {format_toman(trial_credit_toman)} اعتبار هدیه می‌گیری و بلافاصله می‌تونی ربات فروشگاهی خودت رو راه بندازی.",
        "این اعتبار صرفِ پاسخ‌گویی هوش مصنوعی به مشتری‌هات می‌شه؛ هر چقدر مصرفت کمتر باشه، بیشتر دووم می‌آره.",
    ]
    if reference_channel_link:
        lines.append(f"\nبرای آشنایی بیشتر با امکانات، سری به کانال مرجع بزن:\n{reference_channel_link}")
    return "\n".join(lines)


def trial_activated(credit_toman: int) -> str:
    return (
        f"✅ اعتبار آزمایشی‌ت فعال شد! {format_toman(credit_toman)} به کیف‌پولت اضافه شد "
        "و می‌تونی از همه‌ی امکانات استفاده کنی."
    )


# =============================================================================
# پنل فروشگاه‌دار
# =============================================================================
PANEL_WELCOME_BACK = "به پنل فروشگاه‌داری خوش اومدی. یکی از گزینه‌های زیر رو انتخاب کن:"


# =============================================================================
# توکن ربات فروشگاهی (مرحله ۴)
# =============================================================================
ASK_SHOP_BOT_TOKEN = (
    "لطفاً توکن ربات تلگرامی‌ای که از @BotFather گرفتی رو اینجا بفرست.\n"
    "(چیزی شبیه به 123456789:AAxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx)\n\n"
    "برای انصراف، /cancel رو بفرست."
)
INVALID_BOT_TOKEN = "این توکن معتبر نیست یا نتونستم باهاش به تلگرام وصل بشم. لطفاً دوباره بررسی و امتحان کن."
BOT_TOKEN_ALREADY_USED = "این توکن قبلاً برای یه ربات دیگه توی همین پلتفرم ثبت شده."


def shop_bot_token_saved(username: str) -> str:
    return f"✅ ربات @{username} با موفقیت وصل شد و آماده‌ی کاره!"


SHOP_BOT_NOT_SET_UP = "هنوز ربات فروشگاهیت رو وصل نکردی. اول از «🔑 ثبت/ویرایش توکن ربات» شروع کن."
WALLET_TOPUPS_DISABLED = "شارژِ کیف‌پول فعلاً موقتاً غیرفعاله. لطفاً بعداً دوباره امتحان کن یا با پشتیبانی در تماس باش."

ASK_TENANT_MODE = (
    "یه سوالِ مهم: این ربات قراره چیکار کنه؟\n\n"
    "🛍 اگه قراره محصول بفروشه (با قیمت و موجودی)، «فروشِ محصول» رو انتخاب کن.\n"
    "💬 اگه فقط قراره گفتگو کنه و مشاوره/خدمات بده (بدونِ فروشِ کالا — مثلِ مشاوره، وقتِ ملاقات، خدماتِ تخصصی)، «مشاوره و خدمات» رو انتخاب کن.\n\n"
    "هروقت خواستی می‌تونی از «🔀 نوعِ کسب‌وکار» توی پنل عوضش کنی."
)

_TENANT_MODE_LABELS = {"sales": "🛍 فروشِ محصول (فروشگاه)", "consultation": "💬 مشاوره و خدمات"}


def tenant_mode_saved_confirmation(tenant_mode) -> str:
    key = tenant_mode.value if hasattr(tenant_mode, "value") else tenant_mode
    label = _TENANT_MODE_LABELS.get(key, key)
    extra = (
        "از این به بعد، دستیارِ هوش‌مصنوعی روی گفتگو و راهنمایی تمرکز می‌کنه، نه فروشِ کالا."
        if key == "consultation"
        else "از این به بعد، دستیارِ هوش‌مصنوعی می‌تونه محصولاتت رو معرفی و بفروشه."
    )
    return f"✅ نوعِ کسب‌وکار روی «{label}» تنظیم شد.\n{extra}"


def tenant_mode_current(tenant_mode) -> str:
    key = tenant_mode.value if hasattr(tenant_mode, "value") else tenant_mode
    label = _TENANT_MODE_LABELS.get(key, key)
    return f"نوعِ کسب‌وکارِ فعلیت: {label}\n\nاگه می‌خوای عوضش کنی، از دکمه‌های زیر انتخاب کن:"

EDIT_INFO_COMING_SOON = "✏️ ویرایش اطلاعات به‌زودی اضافه می‌شه. فعلاً برای تغییر اطلاعاتت با پشتیبانی در تماس باش."


# =============================================================================
# محصولات (مرحله ۵)
# =============================================================================
PRODUCTS_EMPTY = "هنوز هیچ محصولی ثبت نکردی. با «➕ افزودن محصول جدید» شروع کن."
PRODUCTS_LIST_INTRO = "📦 فهرست محصولات فروشگاهت:"
ASK_PRODUCT_NAME = "نام محصول رو بنویس:"
ASK_PRODUCT_DESCRIPTION = "توضیحات محصول رو بنویس (اگه نمی‌خوای توضیحی بدی، بنویس «رد شدن»):"
ASK_PRODUCT_PRICE = "قیمت محصول به تومان رو بنویس (فقط عدد):"
INVALID_PRICE = "قیمت معتبر نیست. لطفاً فقط عدد بفرست (مثلاً 150000)."
ASK_PRODUCT_PHOTO = "اگه می‌خوای یه عکس برای محصول بفرستی الان بفرست، وگرنه بنویس «رد شدن»."
ASK_PRODUCT_STOCK = (
    "موجودی این محصول رو (به تعداد) بنویس. اگه نمی‌خوای موجودی رو پیگیری کنی و "
    "همیشه در دسترس باشه، بنویس «رد شدن»."
)
INVALID_STOCK = "موجودی باید یک عدد صحیح صفر یا بزرگ‌تر باشه. لطفاً دوباره امتحان کن."


def product_added_confirmation(name: str) -> str:
    return f"✅ محصول «{name}» با موفقیت اضافه شد."


def product_detail_text(product) -> str:
    lines = [f"🏷 {product.name}", f"💰 {format_toman(product.price_toman)}"]
    if product.stock_quantity is not None:
        stock_line = "ناموجود" if product.stock_quantity <= 0 else f"{product.stock_quantity} عدد"
        lines.append(f"📦 موجودی: {stock_line}")
    if product.description:
        lines.append(f"\n{product.description}")
    return "\n".join(lines)


def product_deleted_confirmation(name: str) -> str:
    return f"🗑 محصول «{name}» حذف شد."


CONFIRM_DELETE_PRODUCT = "مطمئنی می‌خوای این محصول رو حذف کنی؟"
ASK_EDIT_PRODUCT_FIELD = "کدوم بخش رو می‌خوای ویرایش کنی؟"
ASK_NEW_PRODUCT_NAME = "نام جدید محصول رو بنویس:"
ASK_NEW_PRODUCT_DESCRIPTION = "توضیحات جدید محصول رو بنویس:"
ASK_NEW_PRODUCT_PRICE = "قیمت جدید محصول رو به تومان بنویس:"
ASK_NEW_PRODUCT_PHOTO = "عکس جدید محصول رو بفرست:"
ASK_NEW_PRODUCT_STOCK = "موجودی جدید محصول رو بنویس (برای نامحدود/بدون پیگیری، بنویس «رد شدن»):"

_FIELD_LABELS = {"name": "نام", "description": "توضیحات", "price": "قیمت", "photo": "عکس", "stock": "موجودی"}


def product_field_updated(field: str) -> str:
    return f"✅ {_FIELD_LABELS.get(field, field)}‌ محصول به‌روزرسانی شد."


# =============================================================================
# افزودنِ گروهیِ محصول از اکسل (فازِ ۲-ب، زیربخشِ ۲)
# =============================================================================
PRODUCT_IMPORT_TEMPLATE_CAPTION = "📄 قالبِ افزودنِ گروهیِ محصول"
PRODUCT_IMPORT_INSTRUCTIONS = (
    "فایلِ بالا رو باز کن و برایِ هر محصول یه ردیف (زیرِ هدر) پر کن:\n"
    "• نام محصول — الزامی\n"
    "• توضیحات — اختیاری، برایِ رد کردن خالی بذار\n"
    "• قیمت (تومان) — الزامی، فقط عدد\n"
    "• موجودی — اختیاری، برایِ نامحدود/بدونِ پیگیری خالی بذار\n\n"
    "عکسِ محصول از این راه اضافه نمی‌شه؛ بعد از افزودنِ گروهی، هر محصول رو جداگانه "
    "ویرایش کن و عکسش رو بفرست.\n\n"
    "وقتی فایل آماده شد، همینجا به‌صورتِ فایل (نه عکس) بفرستش."
)
PRODUCT_IMPORT_WRONG_FILE_TYPE = "لطفاً فقط فایلِ اکسلِ همون قالب (.xlsx) رو به‌صورتِ فایل بفرست، نه متن یا عکس."
PRODUCT_IMPORT_INVALID_FILE = "این فایل خراب یا نامعتبره. از همون قالبی که فرستادم استفاده کن و دوباره امتحان کن."
PRODUCT_IMPORT_FILE_TOO_LARGE = "این فایل خیلی بزرگه. لطفاً فایلِ کوچیک‌تری (در حدِ چند صد ردیف) بفرست."
PRODUCT_IMPORT_EMPTY_FILE = "این فایل هیچ داده‌ای نداره. زیرِ ردیفِ هدر، اطلاعاتِ محصولات رو وارد کن و دوباره بفرست."
PRODUCT_IMPORT_CANCELLED = "❌ افزودنِ گروهی لغو شد."
PRODUCT_IMPORT_DOWNLOAD_FAILED = "دانلودِ فایل ناموفق بود. لطفاً دوباره امتحان کن."

_PRODUCT_IMPORT_ERROR_DISPLAY_CAP = 15


def product_import_too_many_rows(max_rows: int) -> str:
    return f"این فایل بیش از {max_rows} ردیف داره. لطفاً فایل رو به چند بخشِ کوچیک‌تر تقسیم کن و هر بخش رو جدا بفرست."


def _format_error_block(errors: list[str]) -> list[str]:
    shown = errors[:_PRODUCT_IMPORT_ERROR_DISPLAY_CAP]
    lines = [f"• {e}" for e in shown]
    remaining = len(errors) - len(shown)
    if remaining > 0:
        lines.append(f"...و {remaining} موردِ دیگه.")
    return lines


def product_import_no_valid_rows(errors: list[str]) -> str:
    lines = ["❌ هیچ ردیفِ معتبری توی فایل پیدا نشد."]
    if errors:
        lines.append("مشکلات:")
        lines.extend(_format_error_block(errors))
    lines.append("\nفایل رو اصلاح کن و دوباره بفرست.")
    return "\n".join(lines)


def product_import_preview(valid_count: int, errors: list[str]) -> str:
    lines = ["📊 بررسیِ فایل تموم شد.", f"✅ {valid_count} ردیفِ معتبر آماده‌ی افزودنه."]
    if errors:
        lines.append(f"\n⚠️ {len(errors)} ردیف مشکل داشت و اضافه نمی‌شه:")
        lines.extend(_format_error_block(errors))
    lines.append(f"\nمی‌خوای همین {valid_count} محصولِ معتبر اضافه بشه؟")
    return "\n".join(lines)


def product_import_result_toast(count: int) -> str:
    return f"✅ {count} محصول با موفقیت اضافه شد."


# =============================================================================
# دستور هوشمندسازی و پیش‌نمایش (مرحله ۶)
# =============================================================================
AI_INSTRUCTIONS_INTRO = "دستور هوشمندسازی چیزیه که به دستیار هوش‌مصنوعیت می‌گه چطور با مشتری‌ها رفتار کنه."


def ai_instructions_current(current: str | None) -> str:
    if not current:
        return "الان دستور خاصی ثبت نکردی؛ دستیار از یه رفتار پیش‌فرض استفاده می‌کنه."
    return f"دستور فعلی:\n\n{current}"


ASK_AI_INSTRUCTIONS = "دستور جدید رو بنویس (مثلاً: «مودب و صمیمی صحبت کن، همیشه محصولات پرفروش رو پیشنهاد بده»):"
AI_INSTRUCTIONS_SAVED = "✅ دستور هوشمندسازی ذخیره شد."

PREVIEW_START_INTRO = "👀 حالت پیش‌نمایش فعال شد. هر پیامی بفرستی، دقیقاً همون‌طوری که مشتری‌هات جواب می‌گیرن جواب می‌گیری.\nبرای پایان، روی «🔚 پایان پیش‌نمایش» بزن."
PREVIEW_END_TEXT = "پیش‌نمایش تموم شد."
AI_ERROR_REPLY_TO_CUSTOMER = "متاسفانه الان امکان پاسخ‌گویی نیست. لطفاً چند لحظه‌ی دیگه دوباره امتحان کن."


# =============================================================================
# کانال دانش‌افزایی (مرحله ۷)
# =============================================================================
ASK_CHANNEL_FORWARD_OR_USERNAME = (
    "یه پیام از کانالت رو اینجا فوروارد کن، یا یوزرنیم کانال (مثل @mychannel) رو بفرست.\n"
    "⚠️ ربات فروشگاهیت باید توی این کانال ادمین باشه."
)
CHANNEL_KNOWLEDGE_NOT_FOUND = "نتونستم این کانال رو پیدا کنم یا ربات فروشگاهیت توش ادمین نیست. لطفاً بررسی و دوباره امتحان کن."


def channel_knowledge_linked(channel_title: str) -> str:
    return f"✅ کانال «{channel_title}» به‌عنوان منبع دانش وصل شد. از این به بعد پست‌های جدیدش به دستیار فروشت اضافه می‌شه."


def channel_knowledge_current(channel_id: str | None) -> str:
    if not channel_id:
        return "هنوز هیچ کانالی به‌عنوان منبع دانش وصل نکردی."
    return f"کانال دانش‌افزایی‌ فعلی: {channel_id}"


# =============================================================================
# کیف‌پول و پرداخت (مرحله ۸، بازآرایی‌شده برای سیستمِ کیف‌پول)
# =============================================================================
def wallet_topup_action_label() -> str:
    return "💰 شارژ کیف‌پول"


def wallet_status_text(balance_toman: int) -> str:
    return f"موجودیِ فعلیِ کیف‌پولت: {format_toman(balance_toman)}"


_WALLET_REASON_LABELS = {
    "chat_message": "💬 پاسخِ چت",
    "photo_analysis": "🖼 تحلیلِ عکس",
    "voice_transcription": "🎙 تبدیلِ صدا به متن",
    "order_detection": "🔍 تشخیصِ سفارش",
    "topup": "💳 شارژ",
    "trial": "🎁 اعتبارِ رایگانِ شروع",
    "referral_reward": "🤝 پاداشِ معرفی",
    "admin_grant": "🎁 هدیه‌ی ادمین",
    "admin_correction": "🧾 اصلاحِ ادمین",
    "expiry": "⌛️ انقضا",
}

WALLET_HISTORY_EMPTY = "هنوز هیچ تراکنشی در کیف‌پولت ثبت نشده."
WALLET_HISTORY_INTRO = "📜 تاریخچه‌ی تراکنش‌های کیف‌پول (۱۵ موردِ اخیر):"


def wallet_transaction_line(transaction) -> str:
    reason_value = transaction.reason.value if hasattr(transaction.reason, "value") else transaction.reason
    label = _WALLET_REASON_LABELS.get(reason_value, reason_value)
    sign = "+" if transaction.amount_toman >= 0 else ""
    when = transaction.created_at.strftime("%Y-%m-%d %H:%M")
    return f"{label}: {sign}{format_toman(transaction.amount_toman)} — {when}"


TOPUP_AMOUNT_PRESETS_TOMAN = [50_000, 100_000, 300_000, 500_000]


def topup_amount_button_label(amount_toman: int) -> str:
    return format_toman(amount_toman)


ASK_TOPUP_AMOUNT = "می‌خوای چقدر شارژ کنی؟"
ASK_CUSTOM_TOPUP_AMOUNT = "مبلغِ موردنظرت رو به تومان بنویس (حداقل ۱۰٬۰۰۰ تومان):"
INVALID_TOPUP_AMOUNT = "لطفاً فقط عدد بنویس (مثلاً 150000) و حداقل ۱۰٬۰۰۰ تومان باشه."
ASK_DISCOUNT_CODE = "اگه کد تخفیف داری بفرست، وگرنه روی «⏭ رد شدن از کد تخفیف» بزن."
INVALID_DISCOUNT_CODE = "این کد تخفیف معتبر نیست، منقضی شده، یا قبلاً استفادش کردی."


def discount_applied_text(discount, final_price: int) -> str:
    return f"✅ کد تخفیف اعمال شد! مبلغ نهایی: {format_toman(final_price)}"


ASK_PAYMENT_METHOD = "روش پرداخت رو انتخاب کن:"

ASK_COST_CALC_VOLUME = "روزانه حدوداً چند پیام از مشتری‌ها انتظار داری؟ (یه تخمینِ کلی کافیه)"

_COST_CALC_DAILY_ESTIMATES = {"low": 15, "medium": 60, "high": 300, "very_high": 700}


def cost_calc_result_text(volume_key: str, cost_per_message_toman: int) -> str:
    daily = _COST_CALC_DAILY_ESTIMATES[volume_key]
    monthly_estimate = daily * 30 * cost_per_message_toman
    return (
        f"📊 با حدودِ {daily} پیامِ مشتری در روز، هزینه‌ی تقریبیِ ماهانه‌ت "
        f"حدودِ {format_toman(monthly_estimate)} خواهد بود.\n\n"
        "این فقط یه تخمینه (بر اساسِ پیام‌های متنی)؛ اگه از تحلیلِ عکس یا رونویسیِ صدا هم "
        "زیاد استفاده کنی، هزینه‌ی واقعی می‌تونه کمی بیشتر بشه. برای خیالِ راحت، پیشنهاد می‌کنیم "
        f"حداقل {format_toman(monthly_estimate * 2)} شارژ کنی."
    )


def card_to_card_payment_instructions(card_number: str, holder_name: str, amount: int) -> str:
    import html

    safe_card = html.escape(card_number)
    safe_name = html.escape(holder_name)
    return (
        "💳 لطفاً مبلغ دقیق زیر رو به شماره کارت زیر واریز کن:\n\n"
        f"شماره کارت: <code>{safe_card}</code>\n"
        f"به‌نام: {safe_name}\n"
        f"مبلغ دقیق: <code>{amount:,}</code> تومان\n\n"
        "👆 روی شماره کارت یا مبلغ بزن تا کپی بشه.\n\n"
        "⚠️ توجه: مبلغ باید دقیقاً همین عدد باشه (چون چند تومن اختلاف برای تشخیص خودکار پرداختته).\n"
        "بعد از واریز، عکس رسید رو همینجا بفرست."
    )


ASK_RECEIPT_PHOTO_NOT_TEXT = "لطفاً عکسِ رسیدِ واریز رو بفرست (نه متن) تا برای بررسی ثبت بشه 🙏"


ASK_PAYMENT_RECEIPT = "لطفاً عکس رسید پرداخت رو بفرست."
RECEIPT_RECEIVED_PENDING_APPROVAL = "✅ رسیدت دریافت شد و برای بررسی به ادمین ارسال شد. بعد از تایید، بهت اطلاع می‌دیم."


def admin_new_payment_notification(payment, owner) -> str:
    owner_name = f"{owner.first_name or ''} {owner.last_name or ''}".strip() or str(owner.telegram_id)
    return (
        "🧾 درخواست پرداخت جدید:\n\n"
        f"فروشگاه‌دار: {owner_name}\n"
        f"مدت: {payment.duration_months} ماه\n"
        f"مبلغ: {format_toman(payment.final_amount)}"
    )


def payment_approved_notification(is_wallet_topup: bool, wallet_amount_toman: int | None = None) -> str:
    if is_wallet_topup and wallet_amount_toman is not None:
        return f"✅ پرداختت تایید شد و {format_toman(wallet_amount_toman)} به کیف‌پولت اضافه شد. ممنون از اعتمادت! 🙏"
    return "✅ پرداختت تایید شد و اشتراکت فعال/تمدید شد. ممنون از اعتمادت! 🙏"


def payment_rejected_notification(reason: str | None) -> str:
    text = "❌ پرداختت تایید نشد."
    if reason:
        text += f"\nدلیل: {reason}"
    text += "\nاگه فکر می‌کنی اشتباهی رخ داده، لطفاً با پشتیبانی تماس بگیر."
    return text


ZARINPAL_REDIRECT_TEXT = "برای پرداخت آنی، روی دکمه‌ی زیر بزن و در درگاه زرین‌پال پرداختت رو کامل کن:"
ZARINPAL_ERROR = "متاسفانه در حال حاضر امکان اتصال به درگاه پرداخت نیست. لطفاً بعداً امتحان کن یا از پرداخت کارت‌به‌کارت استفاده کن."
BALE_PAY_REDIRECT_TEXT = "برای پرداخت با بله‌پی، روی دکمه‌ی زیر بزن، وارد بله بشو و پرداخت رو تایید کن:"
BALE_PAY_ERROR = "متاسفانه در حال حاضر امکان اتصال به بله‌پی نیست. لطفاً بعداً امتحان کن یا از یکی از روش‌های دیگه استفاده کن."
ZARINPAL_PAYMENT_SUCCESSFUL_PAGE = "پرداخت شما با موفقیت انجام شد ✅ می‌تونی به ربات تلگرام برگردی."
ZARINPAL_PAYMENT_FAILED_PAGE = "پرداخت ناموفق بود یا لغو شد ❌ می‌تونی به ربات تلگرام برگردی و دوباره امتحان کنی."


def payment_history_item(payment) -> str:
    status = payment.status.value if hasattr(payment.status, "value") else payment.status
    status_labels = {"pending": "⏳ در انتظار بررسی", "approved": "✅ تایید شده", "rejected": "❌ رد شده"}
    return (
        f"{payment.created_at.strftime('%Y-%m-%d')} — {payment.duration_months} ماه — "
        f"{format_toman(payment.final_amount)} — {status_labels.get(status, status)}"
    )


PAYMENT_HISTORY_EMPTY = "هنوز هیچ پرداختی ثبت نکردی."


# =============================================================================
# آمار (مرحله ۹)
# =============================================================================
def shop_stats_text(stats: dict) -> str:
    lines = [
        "📊 آمار فروشگاهت:\n",
        f"پیام‌های امروز: {stats['messages_today']}",
        f"پیام‌های هفته‌ی اخیر: {stats['messages_week']}",
        f"پیام‌های ماه اخیر: {stats['messages_month']}",
        f"\n🛒 سفارش‌ها: {stats['orders_count']}",
        f"💬 مشاوره‌ها: {stats['consultations_count']}",
    ]
    if stats.get("success_rate") is not None:
        lines.append(f"\n✅ نرخ پاسخ‌گویی موفق: {stats['success_rate']:.1f}٪")
    if stats.get("top_products"):
        lines.append("\n🏆 پرطرفدارترین محصولات:")
        for name, count in stats["top_products"]:
            lines.append(f"  • {name} ({count} بار)")
    return "\n".join(lines)


def platform_stats_text(stats: dict) -> str:
    return (
        "📊 آمار سراسری پلتفرم:\n\n"
        f"👥 فروشگاه‌دارهای ثبت‌نام‌شده: {stats['total_owners']}\n"
        f"🤖 ربات‌های فعال: {stats['total_active_bots']}\n"
        f"💰 فروشگاه‌دارهای دارای موجودیِ کیف‌پول: {stats['owners_with_wallet_balance']}\n"
        f"💵 مجموع درآمد تاییدشده: {format_toman(stats['total_revenue_toman'])}\n"
        f"🛒 مجموع سفارش‌ها: {stats['orders_count']}\n"
        f"💬 مجموع مشاوره‌ها: {stats['consultations_count']}\n\n"
        "— اقتصادِ کیف‌پول —\n"
        f"📥 مجموع درآمدِ واقعی (شارژهای تاییدشده): {format_toman(stats['total_revenue_toman'])}\n"
        f"🎁 مجموعِ اعتبارِ رایگان (تراِیل/معرفی/هدیه): {format_toman(stats['total_given_away_toman'])}\n"
        f"🔥 مجموعِ اعتبارِ مصرف‌شده (هوش‌مصنوعی): {format_toman(stats['total_wallet_consumed_toman'])}\n"
        "(نکته: این هزینه‌ی واقعیِ ارزیِ ارائه‌دهنده‌ی هوش‌مصنوعی رو نشون نمی‌ده، فقط بر اساسِ قیمت‌گذاریِ خودِ پلتفرمه.)"
    )


# =============================================================================
# تشخیص خودکار سفارش/مشاوره (مرحله ۹ + این‌جلسه: کالا/موجودی)
# =============================================================================
def order_detected_notification(order, customer) -> str:
    type_label = "🛒 سفارش جدید" if (order.type.value if hasattr(order.type, "value") else order.type) == "order" else "💬 مشاوره‌ی جدید"
    customer_name = customer.first_name or (f"@{customer.username}" if customer.username else str(customer.telegram_id))
    text = (
        f"{type_label}\n\n"
        f"مشتری: {customer_name}\n"
        f"آیدی تلگرام: {customer.telegram_id}\n"
        f"خلاصه: {order.summary}"
    )
    if order.estimated_value_toman:
        text += f"\nارزش تخمینی: {format_toman(order.estimated_value_toman)}"
    return text


def order_confirmed_stock_notification(product_name: str, remaining_stock: int) -> str:
    return f"✅ سفارش تایید شد و موجودی «{product_name}» کسر شد. موجودی باقی‌مانده: {remaining_stock} عدد."


ORDER_ALREADY_CONFIRMED = "این سفارش قبلاً تایید شده."
ORDER_CANNOT_REJECT = "این سفارش دیگه قابلِ ردکردن نیست (یا قبلاً تایید شده، یا رد/منقضی شده)."
ORDER_REJECTED_CONFIRMATION = "❌ سفارش رد شد و رزروِ موجودی (اگه داشت) آزاد شد."
ORDER_CANNOT_ADVANCE = "وضعیتِ این سفارش قابلِ پیشروی نیست."

_ORDER_STATUS_LABELS = {
    "pending": "⏳ در انتظارِ بررسی",
    "confirmed": "✅ تاییدشده",
    "processing": "📦 در حالِ آماده‌سازی",
    "shipped": "🚚 ارسال‌شده",
    "completed": "🏁 تکمیل‌شده",
    "cancelled": "🚫 لغوشده",
    "rejected": "❌ ردشده",
    "expired": "⌛️ منقضی‌شده (رزرو آزاد شد)",
}

_ORDER_NEXT_STATUS_LABEL = {
    "confirmed": "📦 علامت‌گذاری به‌عنوانِ «در حالِ آماده‌سازی»",
    "processing": "🚚 علامت‌گذاری به‌عنوانِ «ارسال‌شده»",
    "shipped": "🏁 علامت‌گذاری به‌عنوانِ «تکمیل‌شده»",
}


def order_status_label(status) -> str:
    key = status.value if hasattr(status, "value") else status
    return _ORDER_STATUS_LABELS.get(key, key)


def order_next_status_button_label(status) -> str | None:
    key = status.value if hasattr(status, "value") else status
    return _ORDER_NEXT_STATUS_LABEL.get(key)


def order_status_advanced_notification(new_status) -> str:
    return f"وضعیتِ سفارش به‌روزرسانی شد: {order_status_label(new_status)}"


def order_reservation_expired_notification(product_name: str | None, summary: str) -> str:
    if product_name:
        return (
            f"⌛️ رزروِ موجودیِ یه سفارشِ تاییدنشده برای «{product_name}» منقضی شد و موجودیش آزاد شد "
            f"(خلاصه: {summary}).\nاگه هنوز مشتری رو داری، می‌تونی دستی باهاش هماهنگ کنی."
        )
    return f"⌛️ یه سفارشِ تاییدنشده منقضی شد (خلاصه: {summary})."


# =============================================================================
# کد معرف / رفرال (مرحله ۱۰)
# =============================================================================
def referral_code_text(code: str, stats: dict, bot_username: str, reward_wallet_toman: int = 0) -> str:
    lines = [f"🎁 کد معرف تو: {code}\n"]
    if reward_wallet_toman > 0:
        lines.append(
            f"این کد رو با دیگران به اشتراک بذار! وقتی دعوت‌شده‌ت اولین خریدش رو انجام بده، "
            f"هر دوتون {format_toman(reward_wallet_toman)} به کیف‌پولتون اضافه می‌شه.\n"
        )
    else:
        lines.append("این کد رو با دیگران به اشتراک بذار! از هر لینک دعوت که به خرید منجر بشه پاداش می‌گیری.\n")
    lines.append(f"مجموع معرفی‌ها: {stats['total']}")
    lines.append(f"پاداش‌های دریافتی: {stats['rewarded']}\n")
    lines.append(f"لینک دعوتت:\nhttps://t.me/{bot_username}?start={code}")
    return "\n".join(lines)


def referrer_reward_notification(amount_toman: int) -> str:
    return f"🎉 تبریک! یکی از دعوت‌شده‌های تو اولین خریدش رو انجام داد و {format_toman(amount_toman)} به کیف‌پولت اضافه شد."


def referred_reward_notification(amount_toman: int) -> str:
    return f"🎁 چون با کدِ معرف ثبت‌نام کرده بودی، به‌خاطرِ اولین خریدت {format_toman(amount_toman)} پاداش هم به کیف‌پولت اضافه شد!"


# =============================================================================
# دوره‌ی مهلت / گریس‌پیریود (مرحله ۱۰)
# =============================================================================
def grace_period_reminder(hours: int) -> str:
    return (
        f"⏰ اشتراکت به پایان رسیده. تا {hours} ساعت دیگه فرصت داری تمدید کنی تا ربات فروشگاهیت "
        "بدون وقفه کار کنه. بعد از این مهلت، ربات غیرفعال می‌شه."
    )


# =============================================================================
# کیف‌پول
# =============================================================================
def wallet_empty_notification() -> str:
    return (
        "🔴 موجودیِ کیف‌پولت تموم شده و ربات فروشگاهیت فعلاً به مشتری‌ها جواب نمی‌ده.\n"
        "برای ازسرگیریِ فعالیت، از پنل فروشگاه‌داری شارژ کن."
    )


def moderation_review_notification(category: str | None) -> str:
    category_part = f" (دسته: {category})" if category else ""
    return (
        f"⚠️ یه پیامِ مشتری توسطِ نگهبانِ محتوا علامت خورد و بدونِ پاسخ موند{category_part}.\n"
        "پیشنهاد می‌شه مکالمه رو دستی بررسی کنی."
    )


def wallet_low_balance_notification(remaining_toman: int) -> str:
    return (
        f"🟡 موجودیِ کیف‌پولت داره کم می‌شه (فعلاً {format_toman(remaining_toman)}).\n"
        "برای اینکه ربات فروشگاهیت بی‌وقفه به مشتری‌ها جواب بده، از الان شارژش کن."
    )


def wallet_expiry_reminder(days_left: int, amount_toman: int) -> str:
    if days_left <= 1:
        urgency = "فردا"
    else:
        urgency = f"{days_left} روزِ دیگه"
    return (
        f"⏳ بخشی از اعتبارِ کیف‌پولت ({format_toman(amount_toman)}) {urgency} منقضی می‌شه.\n"
        "اگه استفاده نکنیش، از دست می‌ره — پس اگه لازم داری، الان مصرفش کن یا شارژِ تازه بزن."
    )


# =============================================================================
# گزارش دوره‌ای (مرحله ۱۰)
# =============================================================================
def periodic_report_text(stats: dict, freq_days: int) -> str:
    return f"📈 گزارش دوره‌ای ({freq_days} روز اخیر):\n\n" + shop_stats_text(stats)


# =============================================================================
# پیام همگانی / Broadcast (مرحله ۱۰)
# =============================================================================
ASK_BROADCAST_MESSAGE = "متن پیام همگانی رو بنویس:"


def broadcast_preview(text: str) -> str:
    return f"پیش‌نمایش پیام همگانی:\n\n{text}\n\nارسال بشه؟"


def broadcast_sent_confirmation(count: int) -> str:
    return f"✅ پیام همگانی برای {count} فروشگاه‌دار ارسال شد."


BROADCAST_CANCELLED = "ارسال پیام همگانی لغو شد."


# =============================================================================
# خروجی اکسل (مرحله ۱۰)
# =============================================================================
CHOOSE_EXCEL_EXPORT = "کدوم خروجی اکسل رو می‌خوای؟"
EXCEL_EXPORT_EMPTY = "هنوز داده‌ای برای خروجی گرفتن وجود نداره."
EXCEL_EXPORT_READY = "فایل اکسل آماده شد ✅"


# =============================================================================
# پروفایل فروشگاه‌دار (این‌جلسه)
# =============================================================================
def owner_profile_text(owner, shop_bot, wallet_balance_toman: int) -> str:
    owner_name = f"{owner.first_name or ''} {owner.last_name or ''}".strip() or str(owner.telegram_id)
    lines = [
        "👤 پروفایل من\n",
        f"نام: {owner_name}",
        f"شماره موبایل: {owner.phone_number or '—'}",
        f"ایمیل: {owner.email or '—'}",
        f"آیدی تلگرام: {owner.telegram_id}",
        f"کد معرف: {owner.referral_code}",
    ]
    if shop_bot is not None:
        status = "فعال ✅" if shop_bot.is_active else "غیرفعال ❌"
        lines.append(f"ربات فروشگاهی: @{shop_bot.bot_username} — {status}")
    else:
        lines.append("ربات فروشگاهی: هنوز وصل نشده")
    lines.append(wallet_status_text(wallet_balance_toman))
    return "\n".join(lines)


# =============================================================================
# پنل مدیریت / ادمین (مرحله ۱۱)
# =============================================================================
ADMIN_PANEL_INTRO = "🛠 به پنل مدیریت خوش اومدی. یکی از گزینه‌های زیر رو انتخاب کن:"

NO_MANDATORY_CHANNELS = "هیچ کانال اجباری‌ای هنوز تعریف نشده."
MANDATORY_CHANNELS_INTRO = "📢 کانال‌های عضویت اجباری:"
ASK_CHANNEL_NAME = "یه اسم نمایشی برای این کانال بنویس (همینی که کاربرها می‌بینن):"
ASK_CHANNEL_PROOF_ADMIN = (
    "حالا یه پیام از همون کانال رو اینجا فوروارد کن، یا یوزرنیمش رو بفرست (مثل @channel).\n"
    "⚠️ ربات اصلی پلتفرم باید توی این کانال ادمین باشه، وگرنه نمی‌تونه عضویت کاربرها رو چک کنه."
)
CHANNEL_PROOF_INVALID = "نتونستم این کانال رو پیدا کنم یا ربات توش ادمین نیست. لطفاً بررسی و دوباره امتحان کن."
ASK_CHANNEL_IS_PRIMARY = "این کانال به‌عنوان کانال اصلی (نمایش لینکش در اولویت) در نظر گرفته بشه؟"


def channel_added_confirmation(name: str) -> str:
    return f"✅ کانال «{name}» به فهرست کانال‌های اجباری اضافه شد."


def channel_list_item_label(channel) -> str:
    prefix = "⭐️ " if channel.is_primary else ""
    return f"{prefix}{channel.name}"


def channel_deleted_confirmation(name: str) -> str:
    return f"🗑 کانال «{name}» از فهرست کانال‌های اجباری حذف شد."


ADMIN_CHANNEL_DELETE_CONFIRM = "مطمئنی می‌خوای این کانال رو از فهرست کانال‌های اجباری حذف کنی؟"

ADMIN_ONLY_COMMAND = "این دستور فقط برای ادمین‌های پلتفرم در دسترسه."

# --- صف تایید پرداخت‌ها ---
ADMIN_NO_PENDING_PAYMENTS = "هیچ پرداختی در انتظار بررسی‌ای وجود نداره. ✅"
ADMIN_PENDING_PAYMENTS_INTRO = "🧾 پرداخت‌های در انتظار بررسی:"


def admin_payment_rejected_confirmation(owner_name: str) -> str:
    return f"❌ پرداخت {owner_name} رد شد."


def admin_payment_approved_confirmation(owner_name: str) -> str:
    return f"✅ پرداخت {owner_name} تایید شد."


# --- تنظیمات قیمت و تخفیف ---
ADMIN_PRICING_MENU_INTRO = "💰 تنظیمات قیمت و تخفیف:"
ADMIN_ASK_PLAN_DURATION = "مدت طرح (به ماه) رو بنویس:"
ADMIN_ASK_PLAN_PRICE = "قیمت این طرح رو به تومان بنویس:"


def admin_plan_saved(months: int, price: int) -> str:
    return f"✅ طرح {months} ماهه با قیمت {format_toman(price)} ذخیره شد."


def admin_wallet_cost_recalculated(new_cost_toman: int) -> str:
    return (
        f"✅ هزینه‌ی هر ۱۰۰۰ توکن بر اساسِ فرمول محاسبه و روی {format_toman(new_cost_toman)} تنظیم شد.\n"
        "اگه بعداً نرخِ دلار یا هزینه‌ی مدل عوض شد، فقط کافیه دوباره همین دکمه رو بزنی."
    )


ADMIN_ASK_DISCOUNT_CODE_NAME = "کد تخفیف رو بنویس (فقط حروف انگلیسی و عدد):"
ADMIN_DISCOUNT_CODE_INVALID = "کد تخفیف فقط می‌تونه شامل حروف انگلیسی و عدد باشه."
ADMIN_DISCOUNT_CODE_DUPLICATE = "این کد تخفیف قبلاً ثبت شده."
ADMIN_ASK_DISCOUNT_TYPE = "نوع تخفیف چیه؟"
ADMIN_ASK_DISCOUNT_VALUE = "مقدار تخفیف رو بنویس (برای درصدی: عدد بین ۱ تا ۱۰۰؛ برای مبلغ ثابت: تومان):"
ADMIN_ASK_DISCOUNT_MAX_USES = "حداکثر تعداد استفاده چقدر باشه؟ (برای نامحدود بنویس «نامحدود»):"


def admin_discount_code_saved(code: str) -> str:
    return f"✅ کد تخفیف «{code}» ساخته شد."


# --- تنظیمات کلیدها ---
ADMIN_SETTINGS_MENU_INTRO = "🔑 تنظیمات کلیدها و پیکربندی پلتفرم:"
ADMIN_ASK_SMS_API_KEY = "کلید API سرویس پیامک (کاوه‌نگار) رو بفرست:"
ADMIN_ASK_AI_API_KEY = "کلید API هوش مصنوعی رو بفرست:"
ADMIN_ASK_AI_MODEL = "نام مدل هوش مصنوعی رو بفرست:"
ADMIN_ASK_AI_BASE_URL = "آدرس Base URL سرویس هوش مصنوعی رو بفرست (سازگار با فرمت OpenAI؛ برای مثال آدرس GapGPT یا Grok):"
ADMIN_ASK_AI_FALLBACK_API_KEY = (
    "کلید API سرویسِ پشتیبانِ هوش مصنوعی رو بفرست (اختیاری — اگه سرویسِ اصلی قطع بود، خودکار به این سوییچ می‌کنه). "
    "برای پاک‌کردن، «خالی» بفرست:"
)
ADMIN_ASK_AI_FALLBACK_MODEL = "نامِ مدلِ سرویسِ پشتیبان رو بفرست. برای پاک‌کردن، «خالی» بفرست:"
ADMIN_ASK_AI_FALLBACK_BASE_URL = "آدرسِ Base URLِ سرویسِ پشتیبان رو بفرست. برای پاک‌کردن، «خالی» بفرست:"
ADMIN_ASK_ZARINPAL_MERCHANT_ID = "مرچنت آیدی زرین‌پال رو بفرست:"
ADMIN_ASK_BALE_PROVIDER_TOKEN = (
    "provider_tokenِ بله‌پی رو بفرست (از پنلِ بله‌پی یا @botfather در بله می‌گیری — "
    "دقیقِ این مقدار هنوز از سمتِ ما تاییدنشده، جزئیات در changelog پروژه‌ست):"
)
ADMIN_ASK_PLATFORM_CARD_NUMBER = "شماره کارت پلتفرم برای دریافت پرداخت‌های کارت‌به‌کارت رو بفرست:"
ADMIN_ASK_PLATFORM_CARD_HOLDER = "نام صاحب کارت رو بفرست:"
ADMIN_ASK_GRACE_PERIOD_HOURS = "چند ساعت مهلت (گریس‌پیریود) بعد از پایان اشتراک داده بشه؟"
ADMIN_ASK_RATE_LIMIT_MAX_MESSAGES = "حداکثر چند پیام از هر مشتری در بازه‌ی زمانی مجاز باشه؟"
ADMIN_ASK_RATE_LIMIT_WINDOW_SECONDS = "این محدودیت روی چند ثانیه اعمال بشه؟"
ADMIN_ASK_PAYMENT_RESERVATION_MINUTES = "مبلغ‌ منحصربه‌فردِ پرداخت کارت‌به‌کارت چند دقیقه برای همون فروشگاه‌دار رزرو بمونه؟"
ADMIN_ASK_ORDER_RESERVATION_MINUTES = "رزروِ خودکارِ موجودیِ یه سفارشِ تاییدنشده چند دقیقه فعال بمونه تا اگه فروشگاه‌دار اقدام نکرد، خودکار آزاد بشه؟"
ADMIN_ASK_REPORT_FREQUENCY_DAYS = "گزارش دوره‌ای هر چند روز یک‌بار برای فروشگاه‌دارها ارسال بشه؟"
ADMIN_ASK_REFERRAL_PERCENT = (
    "پورسانتِ معرف چند درصد از اولین شارژِ زیرمجموعه‌ش باشه؟ (فقط معرف می‌گیره؛ عدد ۰ یعنی غیرفعال، مثلاً 10):"
)
ADMIN_ASK_CONVERSATION_HISTORY_LIMIT = "حداکثر چند پیام از تاریخچه‌ی مکالمه به‌عنوان حافظه به هوش مصنوعی داده بشه؟"
ADMIN_ASK_CONVERSATION_RETENTION_DAYS = (
    "پیام‌های مکالمه بعد از چند روز به‌طور خودکار پاک بشن؟ (عدد ۰ یعنی پاکسازیِ خودکار غیرفعال بشه)"
)
ADMIN_ASK_KNOWLEDGE_ITEMS_LIMIT = "حداکثر چند پست از کانال دانش‌افزایی به‌عنوان حافظه به هوش مصنوعی داده بشه؟"

ADMIN_ASK_WALLET_COST_PER_1K_TOKENS = "هزینه‌ی هر ۱۰۰۰ توکن (برای پاسخِ چت و تشخیصِ سفارش)، به تومان چقدر باشه؟ (یا از فرمولِ زیر با دکمه‌ی «محاسبه‌ی خودکار» بسازش)"
ADMIN_ASK_AI_COST_USD = "هزینه‌ی واقعیِ مدلِ AI به ازای هر ۱ میلیون توکن، به دلار چقدره؟ (مثلاً برای glm-4-flash: 0.014):"
ADMIN_ASK_USD_TO_TOMAN_RATE = "نرخِ تبدیلِ دلار به تومان (که باید خودتون به‌روز نگهش دارید) چنده؟ (فقط عددِ صحیح، مثلاً 100000):"
ADMIN_ASK_MARKUP_MULTIPLIER = "ضریبِ سودِ شما روی هزینه‌ی خامِ AI (که هزینه‌ی سرور هم توش لحاظ می‌شه) چند برابر باشه؟ (مثلاً 5 یعنی ۵ برابر):"
ADMIN_ASK_WALLET_COST_PHOTO_ANALYSIS = "هزینه‌ی هر بار تحلیلِ هوشمندِ عکس، به تومان چقدر باشه؟"
ADMIN_ASK_WALLET_COST_VOICE_TRANSCRIPTION = "هزینه‌ی هر بار رونویسیِ پیامِ صوتی، به تومان چقدر باشه؟"
ADMIN_ASK_WALLET_COST_ORDER_DETECTION = "هزینه‌ی پیش‌فرضِ تشخیصِ سفارش (وقتی تعدادِ توکنِ واقعی در دسترس نباشه)، به تومان چقدر باشه؟"
ADMIN_ASK_WALLET_TOPUP_VALIDITY_MONTHS = "هر بار شارژِ کیف‌پول، چند ماه اعتبار داشته باشه؟"
ADMIN_ASK_WALLET_TRIAL_CREDIT = "اعتبارِ آزمایشیِ رایگانِ فروشگاه‌دارهای جدید، به تومان چقدر باشه؟"
ADMIN_ASK_WALLET_LOW_BALANCE_WARNING = "از چه موجودی‌ای (به تومان) به پایین‌تر، به فروشگاه‌دار هشدارِ «موجودی کم داره» بدیم؟"
ADMIN_ASK_GLOBAL_SYSTEM_PROMPT = (
    "دستور سراسری هوش مصنوعی رو بنویس (این روی دستور هر فروشگاه هم اضافه می‌شه). "
    "برای پاک کردنش، بنویس «خالی»."
)
ADMIN_ASK_REFERENCE_CHANNEL_LINK = "لینک کانال مرجع (که قبل از فعال‌سازی آزمایشی نمایش داده می‌شه) رو بفرست. برای پاک کردنش، بنویس «خالی»."
ADMIN_SETTING_SAVED = "✅ ذخیره شد."


def _mask_secret(value: str | None) -> str:
    if not value:
        return "تنظیم‌نشده"
    if len(value) <= 4:
        return "●●●●"
    return f"●●●●{value[-4:]}"


def admin_settings_button_labels(admin_settings) -> list[tuple[str, str]]:
    global_prompt_label = "تنظیم‌شده ✅" if admin_settings.global_ai_system_prompt else "خالی"
    reference_channel_label = admin_settings.reference_channel_link or "تنظیم‌نشده"

    return [
        ("sms_api_key", f"📲 کلید پیامک (کاوه‌نگار): {_mask_secret(admin_settings.sms_api_key)}"),
        ("ai_api_key", f"🤖 کلید هوش مصنوعی: {_mask_secret(admin_settings.ai_api_key)}"),
        ("ai_model", f"🧠 مدل هوش مصنوعی: {admin_settings.ai_model}"),
        ("ai_base_url", f"🌐 آدرس سرویس هوش مصنوعی: {admin_settings.ai_base_url}"),
        ("ai_fallback_api_key", f"🛟 کلید هوش‌مصنوعیِ پشتیبان: {_mask_secret(admin_settings.ai_fallback_api_key)}"),
        ("ai_fallback_model", f"🛟 مدلِ پشتیبان: {admin_settings.ai_fallback_model or 'تنظیم‌نشده'}"),
        ("ai_fallback_base_url", f"🛟 آدرسِ سرویسِ پشتیبان: {admin_settings.ai_fallback_base_url or 'تنظیم‌نشده'}"),
        ("zarinpal_merchant_id", f"🏦 مرچنت آیدی زرین‌پال: {_mask_secret(admin_settings.zarinpal_merchant_id)}"),
        ("bale_provider_token", f"🔵 provider_tokenِ بله‌پی: {_mask_secret(admin_settings.bale_provider_token)}"),
        ("platform_card_number", f"💳 شماره کارت پلتفرم: {_mask_secret(admin_settings.platform_card_number)}"),
        ("platform_card_holder_name", f"👤 صاحب کارت: {admin_settings.platform_card_holder_name or 'تنظیم‌نشده'}"),
        ("referral_reward_value", f"🎁 پورسانتِ معرف: {admin_settings.referral_reward_value}٪ از اولین شارژ"),
        ("grace_period_hours", f"⏳ مهلت گریس‌پیریود: {admin_settings.grace_period_hours} ساعت"),
        (
            "rate_limit",
            f"🚦 محدودیت پیام: {admin_settings.rate_limit_max_messages} پیام / {admin_settings.rate_limit_window_seconds} ثانیه",
        ),
        ("payment_reservation_minutes", f"⏱ رزرو مبلغ‌ پرداخت: {admin_settings.payment_reservation_minutes} دقیقه"),
        ("order_reservation_minutes", f"📦 رزروِ موجودیِ سفارش: {admin_settings.order_reservation_minutes} دقیقه"),
        ("periodic_report_frequency_days", f"📈 بازه‌ی گزارش دوره‌ای: هر {admin_settings.periodic_report_frequency_days} روز"),
        ("conversation_history_limit", f"💭 حافظه‌ی مکالمه: {admin_settings.conversation_history_limit} پیام"),
        (
            "conversation_retention_days",
            "🧹 پاکسازیِ خودکارِ مکالمات: "
            + (
                f"هر {admin_settings.conversation_retention_days} روز"
                if admin_settings.conversation_retention_days > 0
                else "غیرفعال"
            ),
        ),
        ("knowledge_items_limit", f"📚 حافظه‌ی کانال دانش: {admin_settings.knowledge_items_limit} پست"),
        ("wallet_cost_per_1k_tokens_toman", f"🪙 هزینه‌ی هر ۱۰۰۰ توکن: {format_toman(admin_settings.wallet_cost_per_1k_tokens_toman)}"),
        ("ai_cost_usd_per_1m_tokens", f"💵 هزینه‌ی خامِ AI: ${admin_settings.ai_cost_usd_per_1m_tokens}/۱M توکن"),
        ("usd_to_toman_rate", f"💱 نرخِ دلار: {format_toman(admin_settings.usd_to_toman_rate)}"),
        ("wallet_markup_multiplier", f"📈 ضریبِ سود: {admin_settings.wallet_markup_multiplier}×"),
        ("wallet_cost_photo_analysis_toman", f"🖼 هزینه‌ی تحلیلِ عکس: {format_toman(admin_settings.wallet_cost_photo_analysis_toman)}"),
        ("wallet_cost_voice_transcription_toman", f"🎙 هزینه‌ی رونویسیِ صوت: {format_toman(admin_settings.wallet_cost_voice_transcription_toman)}"),
        ("wallet_cost_order_detection_toman", f"🔎 هزینه‌ی پیش‌فرضِ تشخیصِ سفارش: {format_toman(admin_settings.wallet_cost_order_detection_toman)}"),
        ("wallet_topup_validity_months", f"📅 اعتبارِ هر شارژ: {admin_settings.wallet_topup_validity_months} ماه"),
        ("wallet_trial_credit_toman", f"🎁 اعتبارِ آزمایشیِ فروشگاه‌دارِ جدید: {format_toman(admin_settings.wallet_trial_credit_toman)}"),
        ("wallet_low_balance_warning_toman", f"🟡 آستانه‌ی هشدارِ کمبودِ موجودی: {format_toman(admin_settings.wallet_low_balance_warning_toman)}"),
        ("global_ai_system_prompt", f"🌍 دستور سراسری هوش مصنوعی: {global_prompt_label}"),
        ("reference_channel_link", f"🔗 کانال مرجع: {reference_channel_label}"),
    ]


SUGGESTED_GLOBAL_SYSTEM_PROMPT = (
    "این چند قانون رو همیشه رعایت کن:\n"
    "۱. هرگز از قالب‌بندی Markdown (مثل **پررنگ** یا لیست‌های شماره‌دار پیچیده) استفاده نکن؛ تلگرام این‌ها رو درست نمایش نمی‌ده.\n"
    "۲. با لحنی محاوره‌ای، مودبانه و صمیمی فارسی صحبت کن؛ رسمی و خشک ننویس.\n"
    "۳. پاسخ‌هات کوتاه و مفید باشن، معمولاً بین ۲ تا ۴ جمله؛ پیام‌های طولانی و خسته‌کننده ننویس.\n"
    "۴. هیچ‌وقت درباره‌ی محصولات یا قیمت‌ها اطلاعات نساز؛ فقط از چیزی که در اختیارت گذاشته شده استفاده کن.\n"
    "۵. بدون اجازه‌ی صریح فروشگاه‌دار، هیچ تعهد یا تخفیفی به مشتری قول نده.\n"
    "۶. اگه سوال از موضوع فروشگاه خارج بود، مودبانه مکالمه رو به سمت محصولات و خدمات فروشگاه برگردون.\n"
    "۷. اگه مشتری ناراحت یا شاکی بود، اول با همدلی جوابش رو بده و بعد سعی کن مشکلش رو حل کنی.\n"
    "۸. وقتی مشتری قصدِ خریدِ مشخصی داره، قبل از جمع‌بندی، دقیقِ محصول(ها) و تعدادشون رو یه‌بار با خودش تایید کن.\n"
    "۹. وقتی مشتری رسیدِ واریز می‌فرسته (عکس یا متن یا هردو)، فقط تاییدِ دریافت بده و بگو در حالِ بررسیه؛ "
    "هیچ‌وقت به‌جای فروشگاه‌دار نگو «سفارشت ثبت شد» یا «تاییدشد» — تاییدِ نهایی فقط با خودِ فروشگاه‌داره."
)

# --- مدیریت فروشگاه‌دارها ---
ADMIN_SHOP_OWNERS_EMPTY = "هیچ فروشگاه‌داری ثبت‌نام نکرده."
ADMIN_SHOP_OWNERS_INTRO = "👥 فهرست فروشگاه‌دارها:"


def admin_owner_list_item_label(owner) -> str:
    return f"{owner.first_name or ''} {owner.last_name or ''}".strip() or str(owner.telegram_id)


ADMIN_OWNER_NO_SHOP_BOT = "این فروشگاه‌دار هنوز ربات فروشگاهی‌ای وصل نکرده."


def admin_owner_suspended_confirmation(owner_name: str) -> str:
    return f"⛔️ ربات فروشگاهی‌ِ {owner_name} معلق شد."


def admin_owner_unsuspended_confirmation(owner_name: str) -> str:
    return f"✅ ربات فروشگاهی‌ِ {owner_name} دوباره فعال شد."


def admin_shop_owner_detail(owner, shop_bot, wallet_balance_toman: int) -> str:
    owner_name = f"{owner.first_name or ''} {owner.last_name or ''}".strip() or str(owner.telegram_id)
    lines = [f"👤 {owner_name}", f"آیدی تلگرام: {owner.telegram_id}"]
    if shop_bot:
        status = "فعال ✅" if shop_bot.is_active else f"غیرفعال ❌ ({shop_bot.disabled_reason or '—'})"
        lines.append(f"ربات فروشگاهی: @{shop_bot.bot_username} — {status}")
    else:
        lines.append("ربات فروشگاهی: هنوز وصل نشده")
    lines.append(wallet_status_text(wallet_balance_toman))
    return "\n".join(lines)


# --- اعطای اشتراک هدیه (این‌جلسه) ---
ADMIN_ASK_GIFT_AMOUNT = "چقدر اعتبارِ هدیه (به تومان) به کیف‌پولش اضافه کنیم؟ (عدد صحیح):"


def admin_gift_confirmation(owner_name: str, amount_toman: int) -> str:
    return f"🎁 {format_toman(amount_toman)} اعتبارِ هدیه به کیف‌پولِ {owner_name} اضافه شد."


def owner_gift_notification(amount_toman: int) -> str:
    return f"🎁 ادمین {format_toman(amount_toman)} اعتبار به کیف‌پولت هدیه داد! از پنل خودت می‌تونی موجودیِ جدیدت رو ببینی."


# --- استرداد/اصلاحِ تراکنشِ کیف‌پول (فازِ ۲-ب، زیربخشِ ۳) ---
def admin_wallet_correction_intro(owner_name: str, transactions: list) -> str:
    lines = [f"🧾 استرداد/اصلاحِ کیف‌پولِ {owner_name}."]
    if transactions:
        lines.append("\nتراکنش‌هایِ اخیرش (برایِ مرجع):")
        lines.extend(wallet_transaction_line(t) for t in transactions[:10])
    else:
        lines.append("\nاین فروشگاه‌دار هنوز هیچ تراکنشی نداره.")
    lines.append(
        "\nمبلغ رو به تومان بنویس: برایِ افزایش (استرداد) عددِ مثبت، برایِ "
        "کاهش (اصلاح) با - جلوش بنویس (مثلاً 50000 یا -50000):"
    )
    return "\n".join(lines)


ADMIN_INVALID_SIGNED_AMOUNT = "این عدد معتبر نیست. یه عددِ غیرصفر بنویس؛ برایِ کاهش، - رو جلوش بذار (مثلاً -50000)."
ADMIN_ASK_WALLET_CORRECTION_REASON = "دلیلِ این استرداد/اصلاح رو بنویس (توی دفترِ تراکنش‌ها و گزارشِ ممیزی ثبت می‌شه):"
ADMIN_WALLET_CORRECTION_EMPTY_REASON = "دلیل نمی‌تونه خالی باشه. لطفاً یه توضیحِ کوتاه بنویس."
ADMIN_WALLET_CORRECTION_REASON_TOO_LONG = "این توضیح خیلی طولانیه (حداکثر ۲۵۵ کاراکتر). یه‌کم کوتاه‌ترش کن."
ADMIN_WALLET_CORRECTION_INSUFFICIENT_BALANCE = (
    "موجودیِ فعلیِ این فروشگاه‌دار برایِ این مقدار کاهش کافی نیست. مبلغِ کوچیک‌تری امتحان کن."
)


def admin_wallet_correction_confirmation(owner_name: str, amount_toman: int, new_balance_toman: int) -> str:
    verb = "افزوده" if amount_toman > 0 else "کاسته"
    return (
        f"✅ {format_toman(abs(amount_toman))} از کیف‌پولِ {owner_name} {verb} شد.\n"
        f"موجودیِ جدیدش: {format_toman(new_balance_toman)}"
    )


def owner_wallet_correction_notification(amount_toman: int, note: str) -> str:
    if amount_toman > 0:
        return f"💳 ادمین {format_toman(amount_toman)} به کیف‌پولت اضافه کرد.\nدلیل: {note}"
    return f"⚠️ ادمین {format_toman(abs(amount_toman))} از کیف‌پولت کم کرد.\nدلیل: {note}"


# =============================================================================
# نگهبانِ محتوا (Moderation) و گزارشِ ممیزی (Audit Log)
# =============================================================================
MODERATION_MENU_INTRO = (
    "🛡 نگهبانِ محتوا\n\n"
    "قوانینِ زیر روی پیامِ *مشتری‌ها* (قبل از رسیدن به هوش‌مصنوعی) چک می‌شن. "
    "هروقت متنِ پیام با یه قانون مطابقت داشته باشه، بسته به نوعِ اکشن: فقط ثبت می‌شه (هشدار)، "
    "پاسخ داده نمی‌شه (مسدود)، یا پاسخ داده نمی‌شه و به فروشگاه‌دار خبر داده می‌شه که دستی بررسی کنه (نیازِ بازبینی)."
)
MODERATION_RULES_EMPTY = "هنوز هیچ قانونی تعریف نشده. با «➕ افزودنِ قانونِ جدید» شروع کن."
ASK_MODERATION_PATTERN = "کلیدواژه یا عبارتی که باید تشخیص داده بشه رو بنویس (حساس به regex نیست، فقط شاملِ متنِ ساده):"
ASK_MODERATION_ACTION = "وقتی این کلیدواژه دیده شد، چیکار کنیم؟"


def moderation_rule_added_confirmation(pattern: str, action) -> str:
    action_value = action.value if hasattr(action, "value") else action
    return f"✅ قانونِ جدید اضافه شد: «{pattern}» ({action_value})"


def moderation_rule_detail_text(rule) -> str:
    action_value = rule.action.value if hasattr(rule.action, "value") else rule.action
    status = "فعال 🟢" if rule.is_active else "غیرفعال ⚪️"
    return f"قانون: «{rule.pattern}»\nاکشن: {action_value}\nوضعیت: {status}"


MODERATION_RULE_DELETED = "🗑 قانون حذف شد."


def moderation_rule_toggled_confirmation(is_active: bool) -> str:
    return "✅ قانون فعال شد." if is_active else "⏸ قانون غیرفعال شد."


AUDIT_LOG_EMPTY = "هنوز هیچ رویدادی در گزارشِ ممیزی ثبت نشده."
AUDIT_LOG_INTRO = "📜 گزارشِ ممیزی — ۲۰ رویدادِ اخیر:"

AI_POOL_MENU_INTRO = (
    "🔑 استخرِ کلیدهایِ AI\n\n"
    "می‌تونی چند کلیدِ API ثبت کنی. هر فراخوانی از یه کلیدِ تصادفی شروع می‌کنه؛ اگه یکی شکست خورد "
    "(یا به‌خاطرِ شکست‌های پیاپیِ اخیر موقتاً کنار گذاشته شده بود)، خودکار میره سراغِ بعدی. "
    "اگه اینجا هیچ کلیدی ثبت نکنی، همون تنظیماتِ قدیمیِ «تنظیماتِ کلیدها» (ai_api_key) کار می‌کنه."
)
AI_POOL_EMPTY = "هنوز هیچ کلیدی به استخر اضافه نشده."
ASK_AI_POOL_ENTRY = (
    "اطلاعاتِ کلیدِ جدید رو توی ۵ خط بفرست (دقیقاً به همین ترتیب):\n\n"
    "برچسب (فقط برای خودت، مثلاً «GapGPT کلید ۱»)\n"
    "کلیدِ API\n"
    "نامِ مدل (مثلاً glm-4-flash)\n"
    "آدرسِ base_url کاملِ chat/completions\n"
    "نوع: chat یا vision یا both\n\n"
    "مثال:\n"
    "GapGPT کلید ۱\n"
    "sk-xxxxxxxxxxxx\n"
    "glm-4-flash\n"
    "https://api.gapgpt.app/v1/chat/completions\n"
    "chat"
)
AI_POOL_ENTRY_INVALID_FORMAT = "دقیقاً ۵ خط لازمه (برچسب، کلید، مدل، base_url، نوع). دوباره امتحان کن یا با «لغو» برگرد."
AI_POOL_ENTRY_INVALID_CAPABILITY = "خطِ آخر باید دقیقاً یکی از این‌ها باشه: chat یا vision یا both."
AI_POOL_ENTRY_DELETED = "🗑 کلید حذف شد."


def ai_pool_entry_added_confirmation(label: str) -> str:
    return f"✅ کلیدِ «{label}» اضافه شد."


def _mask_api_key(api_key: str) -> str:
    if len(api_key) <= 8:
        return "•" * len(api_key)
    return f"{api_key[:4]}…{api_key[-4:]}"


def ai_pool_entry_detail_text(entry) -> str:
    cap = entry.capability.value if hasattr(entry.capability, "value") else entry.capability
    status = "فعال 🟢" if entry.is_active else "غیرفعال ⚪️"
    return (
        f"برچسب: {entry.label}\n"
        f"کلید: {_mask_api_key(entry.api_key)}\n"
        f"مدل: {entry.model}\n"
        f"base_url: {entry.base_url}\n"
        f"نوع: {cap}\n"
        f"وضعیت: {status}"
    )


def ai_pool_entry_toggled_confirmation(is_active: bool) -> str:
    return "✅ کلید فعال شد." if is_active else "⏸ کلید غیرفعال شد."


ADMIN_ROLES_MENU_INTRO = (
    "👑 مدیریتِ ادمین‌ها\n\n"
    "ادمینِ عملیاتی می‌تونه صفِ پرداخت، فروشگاه‌دارها (شاملِ هدیه‌ی کیف‌پول)، پیامِ همگانی، "
    "کانال‌هایِ اجباری، نگهبانِ محتوا، آمار و گزارشِ ممیزی رو مدیریت کنه — ولی به تنظیماتِ "
    "قیمت/تخفیف، تنظیماتِ کلیدها، استخرِ کلیدهایِ AI، و همین بخش دسترسی نداره.\n"
    "اگه اینجا هیچ ادمینِ عملیاتی‌ای اضافه نکنی، همه‌چیز دقیقاً مثلِ قبل می‌مونه: فقط "
    "سوپرادمین‌هایِ .env به پنلِ ادمین دسترسی دارن."
)
ADMIN_ROLES_EMPTY = "هنوز هیچ ادمینِ عملیاتی‌ای اضافه نشده."
ASK_ADMIN_ROLE_TELEGRAM_ID = "آیدیِ عددیِ تلگرامِ فردی که می‌خوای ادمینِ عملیاتی بشه رو بفرست."
ADMIN_ROLE_INVALID_TELEGRAM_ID = "آیدیِ تلگرام باید یه عددِ صحیح باشه. دوباره امتحان کن یا با «لغو» برگرد."
ADMIN_ROLE_ALREADY_SUPER_ADMIN = "این آیدی همین الان هم سوپرادمینه (توی .env) — نیازی به افزودن نیست."
ADMIN_ROLE_ALREADY_OPERATOR = "این آیدی همین الان هم ادمینِ عملیاتیه."
ADMIN_ROLE_REVOKED = "🗑 دسترسیِ این ادمینِ عملیاتی حذف شد."


def admin_role_added_confirmation(telegram_id: int) -> str:
    return f"✅ آیدیِ {telegram_id} به‌عنوانِ ادمینِ عملیاتی اضافه شد."


def admin_role_detail_text(role) -> str:
    when = role.created_at.strftime("%Y-%m-%d %H:%M")
    return (
        f"آیدیِ تلگرام: {role.telegram_id}\n"
        f"نقش: ادمینِ عملیاتی\n"
        f"اضافه‌شده توسطِ: {role.granted_by_telegram_id}\n"
        f"تاریخ: {when}"
    )


_AUDIT_EVENT_LABELS = {
    "moderation_match": "🛡 تطبیقِ نگهبانِ محتوا",
    "admin_setting_changed": "⚙️ تغییرِ تنظیمات",
    "kill_switch_toggled": "🔀 تغییرِ سوییچ",
    "shop_suspended": "⛔️ تعلیقِ فروشگاه",
    "shop_unsuspended": "✅ رفعِ تعلیقِ فروشگاه",
    "payment_approved": "✅ تاییدِ پرداخت",
    "payment_rejected": "❌ ردِ پرداخت",
    "owner_gift_granted": "🎁 اعطای اعتبارِ هدیه",
    "operator_admin_granted": "👑 افزودنِ ادمینِ عملیاتی",
    "operator_admin_revoked": "👑 حذفِ ادمینِ عملیاتی",
}


def audit_log_entry_line(entry) -> str:
    event_value = entry.event_type.value if hasattr(entry.event_type, "value") else entry.event_type
    label = _AUDIT_EVENT_LABELS.get(event_value, event_value)
    when = entry.created_at.strftime("%Y-%m-%d %H:%M")
    line = f"{label} — {when}"
    if entry.actor_telegram_id:
        line += f" — کاربر: {entry.actor_telegram_id}"
    if entry.details:
        line += f"\n   {entry.details}"
    return line
