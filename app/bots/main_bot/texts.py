from __future__ import annotations

import datetime

from app.services.identity_service import display_name, display_user
from app.utils.validators import format_phone_display, format_toman

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
ASK_FIRST_NAME = "۱) فقط نامِ کوچکت رو بنویس."
REGISTRATION_CLOSED = "ثبت‌نامِ کاربرانِ جدید فعلاً موقتاً بسته‌ست. لطفاً بعداً دوباره امتحان کن یا با پشتیبانی در تماس باش."


def platform_support_lines(admin_settings) -> str:
    """پشتیبانیِ پلتفرم (D2) — فقط برایِ فروشگاه‌دار؛ اگه هیچ‌کدوم تنظیم نشده باشه رشته‌یِ خالی."""
    if admin_settings is None:
        return ""
    parts = []
    if getattr(admin_settings, "platform_support_username", None):
        parts.append(f"@{admin_settings.platform_support_username}")
    phone = format_phone_display(getattr(admin_settings, "platform_support_phone", None))
    if phone:
        parts.append(phone)
    text = getattr(admin_settings, "platform_support_text", None)
    if not parts and not text:
        return ""
    lines = ["📞 پشتیبانیِ پلتفرم: " + " · ".join(parts)] if parts else ["📞 پشتیبانیِ پلتفرم"]
    if text:
        lines.append(text)
    return "\n".join(lines)


def registration_closed_text(admin_settings=None) -> str:
    extra = platform_support_lines(admin_settings)
    return REGISTRATION_CLOSED + (f"\n\n{extra}" if extra else "")
ASK_LAST_NAME = "۲) حالا فقط نامِ خانوادگی‌ت رو بنویس."
ASK_PHONE = "شماره موبایلت رو بفرست (می‌تونی از دکمه‌ی زیر هم استفاده کنی):"
INVALID_PHONE = "شماره موبایل معتبر نیست. لطفاً یه شماره‌یِ موبایلِ ایرانیِ معتبر بفرست."
ASK_EMAIL = "ایمیلت رو بفرست:"
INVALID_EMAIL = "این ایمیل معتبر به‌نظر نمی‌رسه. لطفاً دوباره امتحان کن."
OTP_INVALID_OR_EXPIRED = "کد وارد شده اشتباهه یا منقضی شده. لطفاً دوباره امتحان کن."

# --- ویزاردِ ثبت‌نام v2 (A1/A3)
REG_BACK_BUTTON = "⬅️ برگشت"
REG_CANCEL_BUTTON = "❌ انصراف"
REG_ASK_MODE = (
    "یه سوالِ مهم قبل از شروع: کسب‌وکارت چه‌جوریه؟\n\n"
    "🛍 فروشگاهی: محصول داری و سفارش می‌گیری.\n"
    "💬 مشاوره‌ای: فقط گفتگو و راهنمایی، بدونِ فروشِ کالا.\n\n"
    "اگه بعداً نظرت عوض شد، از «👤 پروفایل من» می‌تونی تغییرش بدی."
)
REG_NAME_BAD_LENGTH = "نام باید بینِ ۲ تا ۳۰ حرف باشه. لطفاً دوباره بنویس:"
REG_NAME_BAD_CHARS = "نام نباید رقم، لینک یا @ داشته باشه. فقط خودِ نام رو بنویس:"
REG_PHONE_NOT_YOURS = "این شماره مالِ خودت نیست. لطفاً با دکمه‌یِ «📱 ارسال شماره تماس» شماره‌یِ خودت رو بفرست یا تایپش کن."
REG_PHONE_TAKEN = "این شماره قبلاً برایِ یه حسابِ دیگه ثبت شده. اگه مالِ خودته با پشتیبانی تماس بگیر؛ وگرنه یه شماره‌یِ دیگه بفرست."
REG_EMAIL_TAKEN = "این ایمیل قبلاً برایِ یه حسابِ دیگه ثبت شده. لطفاً یه ایمیلِ دیگه بفرست."
REG_OTP_HINT = "کد نرسید یا شماره/ایمیل رو اشتباه زدی؟ با «⬅️ برگشت» اصلاحش کن."
REG_CANCEL_ASK = "مطمئنی می‌خوای انصراف بدی؟ اطلاعاتی که تا الان وارد کردی ذخیره نمی‌شه و باید دوباره از اول شروع کنی."
REG_CANCELLED = "ثبت‌نام لغو شد و چیزی ذخیره نشد. هروقت خواستی با /start دوباره شروع کن."
REG_STALE_BUTTON = "این دکمه دیگه معتبر نیست (احتمالاً ربات ری‌استارت شده). برایِ ادامه /start رو بزن."
REG_INCOMPLETE = "یه بخشی از اطلاعاتت کامل نیست؛ بیا از اول ادامه بدیم."
REG_RESUME = "ثبت‌نامت نیمه‌کاره مونده بود؛ از همون‌جا ادامه می‌دیم 👇"


def reg_first_name_two_words(name: str) -> str:
    return f"این‌جا فقط نامِ کوچکت رو می‌خوام، ولی «{name}» دو کلمه‌ست.\nکدوم کار رو بکنم؟"


def reg_hint_previous(value: str | None) -> str:
    return f"\n\n(مقدارِ قبلی: {value})" if value else ""


def reg_review_text(data: dict) -> str:
    mode = _TENANT_MODE_LABELS.get(data.get("mode"), "—")
    phone = format_phone_display(data.get("phone_number")) or "—"
    phone_mark = "✅ تاییدشده" if data.get("phone_verified") else "⚠️ تاییدنشده"
    email_mark = "✅ تاییدشده" if data.get("email_verified") else "⚠️ تاییدنشده"
    return (
        "📋 مرورِ نهایی — اگه همه‌چیز درسته «✅ تایید و شروع» رو بزن:\n\n"
        f"نام: {data.get('first_name') or '—'}\n"
        f"نامِ خانوادگی: {data.get('last_name') or '—'}\n"
        f"موبایل: {phone} ({phone_mark})\n"
        f"ایمیل: {data.get('email') or '—'} ({email_mark})\n"
        f"نوعِ کسب‌وکار: {mode}\n\n"
        "برایِ اصلاحِ هر مورد روی دکمه‌یِ ✏️ همون مورد بزن."
    )


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



# =============================================================================
# محصولات (مرحله ۵)
# =============================================================================
PRODUCTS_EMPTY = "هنوز هیچ محصولی ثبت نکردی. با «➕ افزودن محصول جدید» شروع کن."
PRODUCTS_LIST_INTRO = "📦 فهرست محصولات فروشگاهت:"
ASK_PRODUCT_NAME = "نام محصول رو بنویس:"
ASK_PRODUCT_DESCRIPTION = "توضیحات محصول رو بنویس (یا اگه توضیحی نداری «⏭ رد کردن» رو بزن):"
ASK_PRODUCT_PRICE = "قیمت محصول به تومان رو بنویس (فقط عدد):"
INVALID_PRICE = "قیمت معتبر نیست. لطفاً فقط عدد بفرست (به تومان)."
ASK_PRODUCT_PHOTO = "اگه می‌خوای یه عکس برای محصول بفرستی الان بفرست، وگرنه «⏭ رد کردن» رو بزن."
ASK_PRODUCT_STOCK = (
    "موجودی این محصول رو (به تعداد) بنویس. اگه نمی‌خوای موجودی رو پیگیری کنی و "
    "همیشه در دسترس باشه، «⏭ رد کردن» رو بزن."
)
INVALID_STOCK = "موجودی باید یک عدد صحیح صفر یا بزرگ‌تر باشه. لطفاً دوباره امتحان کن."
PRODUCT_SKIP_STALE = "این دکمه دیگه معتبر نیست. دوباره «➕ افزودنِ محصول» رو بزن."



def product_added_confirmation(name: str) -> str:
    return f"✅ محصول «{name}» با موفقیت اضافه شد."


def product_detail_text(product) -> str:
    lines = [f"🏷 {product.name}", f"💰 {format_toman(product.price_toman)}"]
    if product.stock_quantity is not None:
        stock_line = "ناموجود" if product.stock_quantity <= 0 else f"{product.stock_quantity} عدد"
        lines.append(f"📦 موجودی: {stock_line}")
    lines.extend(product_kind_lines(product))
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

_FIELD_LABELS = {
    "name": "نام",
    "description": "توضیحات",
    "price": "قیمت",
    "photo": "عکس",
    "stock": "موجودی",
    "weight": "وزن",
    "delivery": "زمانِ تحویل",
    "returns": "شرایطِ مرجوعی",
    "ai": "دستورِ AI",
    "dlink": "لینک",
    "dinstr": "راهنما/متنِ تحویل",
    "dmax": "سقفِ دریافت",
    "dfile": "فایل",
    "codes": "کدها",
}


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


ASK_AI_INSTRUCTIONS = "دستور جدید رو بنویس؛ کوتاه و روشن بگو ربات چطور با مشتری حرف بزنه و چه چیزی را پیشنهاد بده:"
AI_INSTRUCTIONS_SAVED = "✅ دستور هوشمندسازی ذخیره شد."

PREVIEW_START_INTRO = "👀 حالت پیش‌نمایش فعال شد. هر پیامی بفرستی، دقیقاً همون‌طوری که مشتری‌هات جواب می‌گیرن جواب می‌گیری.\nبرای پایان، روی «🔚 پایان پیش‌نمایش» بزن."
PREVIEW_END_TEXT = "پیش‌نمایش تموم شد."
PREVIEW_GAP_NOTE = (
    "🧩 (ربات جوابِ این سوال رو نمی‌دونست؛ توی حالتِ واقعی سوالِ مشتری توی «🧩 سوال‌هایِ بی‌جواب» ثبت می‌شد. "
    "توی پیش‌نمایش ثبت نمی‌شه.)"
)
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
    "cart_edit": "🛒 ویرایشِ سبد با هوش مصنوعی",
    "crm_summary": "🧠 خلاصه‌یِ هوشمندِ مشتری",
    "owner_assistant": "💬 دستیارِ مدیریتی",
    "topup": "💳 شارژ",
    "trial": "🎁 اعتبارِ رایگانِ شروع",
    "referral_reward": "🤝 پاداشِ معرفی",
    "admin_grant": "🎁 هدیه‌ی ادمین",
    "admin_correction": "🧾 اصلاحِ ادمین",
    "expiry": "⌛️ انقضا",
}

WALLET_HISTORY_EMPTY = "هنوز هیچ تراکنشی در کیف‌پولت ثبت نشده."
WALLET_HISTORY_INTRO = "📜 تاریخچه‌ی تراکنش‌های کیف‌پول (۱۵ موردِ اخیر):"


def wallet_reason_label(reason) -> str:
    reason_value = reason.value if hasattr(reason, "value") else reason
    return _WALLET_REASON_LABELS.get(reason_value, reason_value)


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
INVALID_TOPUP_AMOUNT = "لطفاً فقط عدد بنویس (به تومان) و حداقل ۱۰٬۰۰۰ تومان باشه."
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
        # A7: چند تومانِ آخرِ مبلغ برایِ راحت‌تر شدنِ بررسیِ واریزها توسطِ مدیر است، نه «تشخیصِ خودکار».
        "⚠️ مبلغ را دقیقاً همین عدد واریز کن؛ این چند تومانِ اختلاف برایِ راحت‌تر شدنِ بررسیِ واریزها توسطِ مدیر است.\n"
        "بعد از واریز، عکسِ رسید یا متنِ رسید را همین‌جا بفرست."
    )


TOPUP_PAYMENT_GONE = (
    "این پرداخت دیگر در انتظارِ رسید نیست (یا پیدا نشد).\n"
    "برایِ دیدنِ پرداخت‌هایِ باز: «💰 کیف‌پول › 📂 پرداخت‌هایِ باز»."
)
ASK_TOPUP_RECEIPT = (
    "📎 رسیدِ واریز را بفرست:\n"
    "• عکسِ رسید، یا\n"
    "• متنِ رسید (کپی از اپِ بانک یا پیامک؛ دستِ‌کم ۸ نویسه و ۴ رقم)، یا\n"
    "• فقط شماره‌یِ پیگیری (دستِ‌کم ۶ رقم).\n\n"
    "اگر الان رسید را نداری، «⬅️ برگشت» را بزن؛ پرداختِ در انتظار می‌ماند و بعداً از «📂 پرداخت‌هایِ باز» ادامه می‌دهی."
)
TOPUP_RECEIPT_TEXT_INVALID = (
    "این متن به‌عنوانِ رسید پذیرفته نشد.\n"
    "متنِ رسید باید دستِ‌کم ۸ نویسه و ۴ رقم (مبلغ/تاریخ/پیگیری) داشته باشد، یا فقط شماره‌یِ پیگیریِ ۶رقمی یا بیشتر بفرست."
)
OPEN_TOPUP_PAYMENTS_EMPTY = "پرداختِ بازی (در انتظارِ رسید) نداری."


def _payment_label(payment) -> str:
    """برچسبِ کاربرپسندِ یک پرداخت: مبلغ + زمانِ ساخت (به وقتِ تهران). شناسه‌یِ عددیِ داخلی هرگز نشان داده نمی‌شود."""
    from app.utils.jalali import format_jalali_datetime
    from app.utils.validators import format_toman

    moment = getattr(payment, "created_at", None)
    when = f" — {format_jalali_datetime(moment)}" if moment is not None else ""
    return f"{format_toman(payment.final_amount)}{when}"


def open_topup_payments_text(payments) -> str:
    if not payments:
        return OPEN_TOPUP_PAYMENTS_EMPTY
    lines = ["📂 پرداخت‌هایِ باز (در انتظارِ رسید)\n"]
    for payment in payments:
        lines.append(f"• {_payment_label(payment)}")
    lines.append("\nروی هر کدام بزن تا رسیدِ همان را بفرستی.")
    return "\n".join(lines)


def topup_receipt_back_text(payment) -> str:
    return (
        f"⬅️ برگشتی. پرداختِ {_payment_label(payment)} در انتظارِ رسید باقی ماند و از بین نرفت.\n"
        "هر وقت واریز کردی، از «💰 کیف‌پول › 📂 پرداخت‌هایِ باز» رسیدش را بفرست."
    )


def topup_receipt_resume_text(payment) -> str:
    return (
        f"📎 رسیدِ پرداختِ {_payment_label(payment)} را بفرست:\n"
        "عکسِ رسید، یا متنِ رسید، یا فقط شماره‌یِ پیگیری."
    )


ASK_PAYMENT_RECEIPT = "لطفاً عکس رسید پرداخت رو بفرست."
RECEIPT_RECEIVED_PENDING_APPROVAL = "✅ رسیدت دریافت شد و برای بررسی به ادمین ارسال شد. بعد از تایید، بهت اطلاع می‌دیم."


def admin_new_payment_notification(payment, owner) -> str:
    owner_name = display_user(owner, "full")
    lines = [
        "🧾 درخواست پرداخت جدید:\n",
        f"فروشگاه‌دار: {owner_name}",
        f"مدت: {payment.duration_months} ماه",
        f"مبلغ: {format_toman(payment.final_amount)}",
    ]
    # A7: رسیدِ متنی و پرچمِ تکراری هم برایِ ادمین نمایش داده می‌شود (تصمیم همیشه با ادمین است).
    if getattr(payment, "receipt_tracking_ref", None):
        lines.append(f"شماره‌یِ پیگیری: {payment.receipt_tracking_ref}")
    if getattr(payment, "receipt_text", None):
        lines.append(f"\n📄 رسیدِ متنی:\n{payment.receipt_text}")
    if getattr(payment, "receipt_flags", None):
        labels = {"dup_file": "رسیدِ تکراری", "dup_tracking": "پیگیریِ تکراری"}
        found = [labels.get(flag, flag) for flag in str(payment.receipt_flags).split(",") if flag]
        if found:
            lines.append(f"\n⚠️ پرچم: {'، '.join(found)} — بررسی کن، خودکار رد نمی‌شود.")
    return "\n".join(lines)


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
    customer_name = display_user(customer, "full")
    text = (
        f"{type_label} (تاییدشده توسطِ مشتری)\n\n"
        f"مشتری: {customer_name}\n"
        f"خلاصه: {order.summary}"
    )
    if order.estimated_value_toman:
        text += f"\nارزش تخمینی: {format_toman(order.estimated_value_toman)}"
    # فیلدهای ساختاریافته (بازطراحیِ سفارش‌گیری) — قبلاً این دو تا داخلِ summary
    # چسبونده می‌شدن، حالا جدا و همیشه یه‌جای مشخص نشون داده می‌شن.
    if order.customer_phone:
        text += f"\n📞 تلفن: {order.customer_phone}"
    if order.customer_address:
        text += f"\n📍 آدرس: {order.customer_address}"
    return text


def cart_order_notification(
    customer, items_with_products, qa_pairs: list[tuple[str, str]], total_toman: int, offer=None
) -> str:
    """فازِ ۳ — سبدِ خرید: مشابهِ order_detected_notification بالا، ولی برایِ یه
    چک‌اوتِ چندآیتمی یه پیامِ ترکیبیِ واحد می‌سازه (نه یه پیام به‌ازایِ هر
    آیتم) — چون از دیدِ فروشگاه‌دار این یه «سفارش» با چند قلم کالاست.
    total_toman = مبلغِ نهایی (بعد از تخفیف). offer: campaign_service.Offer یا None —
    وقتی هست، جمعِ اقلام/تخفیفِ کمپین/جمعِ نهایی جدا نشون داده می‌شه."""
    customer_name = display_user(customer, "full")
    lines = [
        "🛒 سفارشِ جدید (از سبدِ خرید)\n",
        f"مشتری: {customer_name}\n",
        "اقلام:",
    ]
    for item, product in items_with_products:
        lines.append(f"• {product.name} × {item.quantity} = {format_toman(product.price_toman * item.quantity)}")
    if offer is not None:
        label = f"«{offer.campaign_name}»" + (f" (کدِ {offer.code})" if offer.code else "")
        lines.append(f"\nجمعِ اقلام: {format_toman(offer.list_total_toman)}")
        lines.append(f"🎁 تخفیفِ کمپین {label}: {format_toman(offer.discount_toman)}")
        lines.append(f"💰 جمعِ نهایی: {format_toman(total_toman)}")
    else:
        lines.append(f"\nجمعِ کل: {format_toman(total_toman)}")
    if qa_pairs:
        lines.append("")
        for question, answer in qa_pairs:
            lines.append(f"❔ {question}: {answer}")
    return "\n".join(lines)


# B8: سبدِ فیزیکی بدونِ هیچ روشِ ارسالِ فعال ثبت شد ⇒ هزینه‌یِ ارسال محاسبه نشده.
OWNER_NO_SHIPPING_METHOD_WARNING = (
    "⚠️ روشِ ارسالِ فعالی تعریف نکرده‌ای؛ هزینه‌یِ ارسال رویِ این سفارش محاسبه نشد.\n"
    "برایِ افزودن: «🚚 روش‌هایِ ارسال» در پنلِ فروشگاه."
)


def order_confirmed_stock_notification(product_name: str, remaining_stock: int) -> str:
    return f"✅ سفارش تایید شد و موجودی «{product_name}» کسر شد. موجودی باقی‌مانده: {remaining_stock} عدد."


ORDER_ALREADY_CONFIRMED = "این سفارش قبلاً تایید شده."
ORDER_CANNOT_REJECT = "این سفارش دیگه قابلِ ردکردن نیست (یا قبلاً تایید شده، یا رد/منقضی شده)."
CART_GROUP_CONFIRMED = "✅ کلِ سفارش تایید و موجودیِ اقلام کسر شد."
CART_GROUP_REJECTED = "سفارش رد شد."
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
    "awaiting_customer_confirmation": "🕓 منتظرِ تاییدِ مشتری",
    "awaiting_payment": "💳 منتظرِ پرداخت",
    "receipt_submitted": "🧾 رسید ارسال شد (در انتظارِ بررسی)",
    "paid": "💰 پرداخت‌شده",
    "refund_pending": "↩️ در انتظارِ استرداد",
    "refunded": "↩️ استردادشده",
}

_ORDER_NEXT_STATUS_LABEL = {
    "paid": "▶️ شروعِ پردازش",
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


def nightly_report_text(stats: dict) -> str:
    lines = [
        "🌙 گزارش شبانه‌ی امروز:\n",
        f"🛒 سفارش‌های جدید: {stats['new_orders_today']}",
        f"💬 مشاوره‌های جدید: {stats['new_consultations_today']}",
        f"👥 مشتریان جدید: {stats['new_customers_today']}",
    ]
    if stats["confirmed_revenue_today_toman"] > 0:
        lines.append(f"💰 برآوردِ فروشِ تاییدشده‌ی امروز: {format_toman(stats['confirmed_revenue_today_toman'])}")
    # فازِ ۴: فقط وقتی >۰ باشه؛ با N=۰ خروجی دقیقاً مثلِ قبله. .get = دیکشنری‌هایِ قدیمی هم کار می‌کنن.
    if stats.get("new_knowledge_gaps", 0) > 0:
        lines.append(f"🧩 {stats['new_knowledge_gaps']} سوالِ بی‌جوابِ جدید (از «🧩 سوال‌هایِ بی‌جواب» جوابشون رو بده)")
    if stats["pending_orders_count"] > 0:
        lines.append(f"\n⏳ {stats['pending_orders_count']} سفارش هنوز منتظرِ بررسیِ شماست.")
    return "\n".join(lines)


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
# پیام فروشگاه‌دار به مشتری‌ها (فازِ ۳) — جدا از پیامِ همگانیِ ادمین بالا
# =============================================================================
ASK_CUSTOMER_BROADCAST_MESSAGE = "متنِ پیامی که می‌خوای برایِ همه‌ی مشتری‌هات بفرستی رو بنویس:"
CUSTOMER_BROADCAST_NO_CUSTOMERS = "هنوز هیچ مشتری‌ای با ربات‌ات چت نکرده، پس چیزی برای ارسال نیست."
CUSTOMER_BROADCAST_CANCELLED = "ارسالِ پیام به مشتری‌ها لغو شد."
CUSTOMER_BROADCAST_BOT_OFFLINE = "ربات فروشگاهی‌ات الان آنلاین نیست (شاید توکنش نامعتبر شده)؛ نمی‌شه پیام فرستاد."


def customer_broadcast_preview(text: str, customer_count: int) -> str:
    return f"پیش‌نمایشِ پیام (برایِ {customer_count} مشتری فرستاده می‌شه):\n\n{text}\n\nارسال بشه؟"


def customer_broadcast_started(total: int) -> str:
    return f"⏳ در حالِ ارسال برایِ {total} مشتری... وقتی تموم شد یه پیام جدا بهت می‌دم."


def customer_broadcast_sent_confirmation(sent: int, total: int) -> str:
    if sent == total:
        return f"✅ پیام برایِ هر {total} مشتری با موفقیت ارسال شد."
    return f"✅ ارسال تموم شد: {sent} از {total} مشتری پیام رو گرفتن (بقیه احتمالاً ربات رو بلاک کرده بودن)."


# =============================================================================
# پرداختِ آنلاینِ سفارش از طریقِ بله‌پیِ خودِ فروشگاه (فازِ ۳)
# =============================================================================
def bale_provider_token_current(shop_bot, missing=()) -> str:
    """A1/B11: یک پیامِ واحد و عملی — هم وضعیتِ فعلی، هم اینکه دقیقاً چه چیزی کم است و چه باید بفرستی."""
    lines = [
        "💳 پرداختِ آنلاینِ سفارش‌ها (بله‌پی)",
        "",
        f"توکنِ درگاهِ فروشگاهِ تو: {_mask_secret(shop_bot.bale_provider_token)}",
    ]
    if missing:
        lines += ["", "⚠️ بله‌پی الان برایِ مشتریِ تو فعال نیست:"]
        lines += bale_missing_lines(missing)
    else:
        lines += ["", "✅ بله‌پی برایِ مشتری‌هایِ تو فعال است."]
    lines += [
        "",
        "«توکنِ درگاه» همان کدی است که از پنلِ پذیرندگانِ بله‌پی (یا @botfather در بله) می‌گیری و اجازه‌یِ ساختِ "
        "لینکِ پرداخت می‌دهد. اگر مدیرِ پلتفرم توکنِ سراسری گذاشته باشد، بدونِ آن هم کار می‌کند.",
        "پول مستقیم به حسابِ خودت می‌رود (پلتفرم نقشی در آن ندارد).",
        "",
        "👈 توکنِ درگاهِ خودت را بفرست، یا برایِ حذف بنویس «حذف».",
        "⚠️ این روش هنوز با تراکنشِ واقعی رویِ این پلتفرم تست نشده؛ اول با مبلغِ کوچک امتحانش کن.",
    ]
    return "\n".join(lines)


BALE_PROVIDER_TOKEN_INVALID = (
    "❌ این مقدار شبیهِ توکنِ درگاه نیست.\n"
    "باید یک تکه باشد (بدونِ فاصله و خطِ جدید) و دستِ‌کم ۲۰ نویسه.\n"
    "دوباره بفرست، یا برایِ حذف بنویس «حذف»."
)
BALE_PROVIDER_TOKEN_SAVED = "✅ ذخیره شد. از این به بعد، بعدِ تاییدِ سفارش توسطِ مشتری، گزینه‌ی پرداختِ آنلاین هم بهش نشون داده می‌شه."
BALE_PROVIDER_TOKEN_REMOVED = "کدِ درگاه حذف شد. دیگه گزینه‌ی پرداختِ آنلاین به مشتری‌ها نشون داده نمی‌شه."


def order_paid_online_notification(order) -> str:
    return f"💳 سفارش #{order.id} آنلاین پرداخت شد ({format_toman(order.estimated_value_toman)}). می‌تونی بدونِ نگرانی از بابتِ پول، پردازشش کنی."


def cart_paid_online_notification(order_count: int, total_toman: int) -> str:
    return f"💳 یه سفارشِ سبدِ خرید ({order_count} قلم) آنلاین پرداخت شد — مجموعاً {format_toman(total_toman)}. می‌تونی بدونِ نگرانی از بابتِ پول، پردازشش کنی."


# =============================================================================
# سوال‌هایِ چک‌اوتِ سبدِ خرید (فازِ ۳) — فروشگاه‌دار تعریف می‌کنه
# =============================================================================
DEFAULT_CHECKOUT_QUESTIONS_HINT = "(سوالِ اضافه‌ای تعریف نشده)"


def checkout_questions_current(shop_bot) -> str:
    if shop_bot.checkout_questions and shop_bot.checkout_questions.strip():
        current = shop_bot.checkout_questions.strip()
        label = "سوال‌هایِ فعلی (هر خط یه سوال)"
    else:
        current = DEFAULT_CHECKOUT_QUESTIONS_HINT
        label = "الان سوالِ اضافه‌ای نداری"
    return (
        f"{label}:\n{current}\n\n"
        "وقتی مشتری سبدِ خریدش رو نهایی می‌کنه، اول نام، موبایل، آدرس (برایِ کالایِ فیزیکی) و روشِ ارسال رو خودکار می‌پرسیم؛ "
        "بعدش این سوال‌هایِ اضافه رو یکی‌یکی می‌پرسیم و جواب‌ها همراهِ سفارش برات می‌رسه."
    )


ASK_CHECKOUT_QUESTIONS = (
    "سوال‌هایی که می‌خوای موقعِ نهایی‌کردنِ سبد از مشتری پرسیده بشه رو بفرست — "
    "هر خط یه سوال. نام، موبایل و آدرس رو لازم نیست بپرسی؛ ربات خودش می‌پرسه.\n"
    "برایِ حذفِ همه‌یِ سوال‌هایِ اضافه، فقط بنویس «حذف»."
)
CHECKOUT_QUESTIONS_SAVED = "✅ ذخیره شد. از این به بعد مشتری‌ها همین سوال‌ها رو موقعِ نهایی‌کردنِ سبد می‌بینن."
CHECKOUT_QUESTIONS_RESET = "سوال‌هایِ اضافه حذف شد (نام، موبایل و آدرس همچنان خودکار پرسیده می‌شن)."


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
    """کارتِ پروفایل (A2). آیدیِ عددیِ تلگرام نشون داده نمی‌شه (H2)."""
    name = f"{owner.first_name or ''} {owner.last_name or ''}".strip() or "—"
    phone = format_phone_display(owner.phone_number)
    phone_line = f"{phone} ({'✅ تاییدشده' if owner.phone_verified else '⚠️ تاییدنشده'})" if phone else "—"
    email_line = f"{owner.email} ({'✅ تاییدشده' if owner.email_verified else '⚠️ تاییدنشده'})" if owner.email else "—"
    lines = [
        "👤 پروفایل من\n",
        f"نام: {name}",
        f"موبایل: {phone_line}",
        f"ایمیل: {email_line}",
        f"یوزرنیم: @{owner.username}" if owner.username else "یوزرنیم: —",
        f"نوعِ کسب‌وکار: {_TENANT_MODE_LABELS.get(owner.business_mode, '—')}",
        f"کد معرف: {owner.referral_code}",
    ]
    if shop_bot is not None:
        status = "فعال ✅" if shop_bot.is_active else "غیرفعال ❌"
        lines.append(f"ربات فروشگاهی: @{shop_bot.bot_username} — {status}")
    else:
        lines.append("ربات فروشگاهی: هنوز وصل نشده")
    lines.append(wallet_status_text(wallet_balance_toman))
    return "\n".join(lines)


_PROFILE_FIELD_PROMPTS = {
    "first_name": "نامِ کوچکِ جدیدت رو بنویس (برایِ انصراف /cancel):",
    "last_name": "نامِ خانوادگیِ جدیدت رو بنویس (برایِ انصراف /cancel):",
    "phone": "شماره‌یِ موبایلِ جدیدت رو بنویس (برایِ انصراف /cancel):",
    "email": "ایمیلِ جدیدت رو بنویس (برایِ انصراف /cancel):",
}


def profile_ask(field: str) -> str:
    return _PROFILE_FIELD_PROMPTS[field]


PROFILE_UPDATED = "✅ ذخیره شد."
PROFILE_OTP_NOTE = "تا وقتی کد رو تایید نکنی، مقدارِ قبلی فعاله."
PROFILE_STALE = "این دکمه دیگه معتبر نیست. دوباره «👤 پروفایل من» رو بزن."
PROFILE_NOT_REGISTERED = "اول باید ثبت‌نامت رو کامل کنی؛ /start رو بزن."
PROFILE_SUPPORT_NOT_SET = "هنوز شناسه‌یِ پشتیبانیِ پلتفرم تنظیم نشده."
TENANT_MODE_BLOCKED = "تا وقتی سفارش/درخواستِ بازِ در انتظار داری نمی‌تونی نوعِ کسب‌وکار رو عوض کنی. اول وضعیتِ اون‌ها رو مشخص کن."


def tenant_mode_ask_text(current, target) -> str:
    cur = _TENANT_MODE_LABELS.get(current, current)
    tgt = _TENANT_MODE_LABELS.get(target, target)
    effect = (
        "• دستیارِ هوش‌مصنوعی دیگه محصول نمی‌فروشه؛ فقط گفتگو و مشاوره می‌کنه.\n"
        "• محصولات و سبدها پاک نمی‌شن؛ فقط دیگه به مشتری نشون داده نمی‌شن.\n"
        if target == "consultation"
        else "• دستیارِ هوش‌مصنوعی می‌تونه محصولات رو معرفی و بفروشه؛ محصول‌هات رو ثبت کن.\n"
    )
    return f"نوعِ کسب‌وکارِ فعلیت: {cur}\n\nاگه به «{tgt}» تغییرش بدی:\n{effect}• هیچ داده‌ای پاک نمی‌شه و هروقت خواستی می‌تونی برگردی."


def tenant_mode_confirm_text(target) -> str:
    return f"آخرین تایید: نوعِ کسب‌وکار به «{_TENANT_MODE_LABELS.get(target, target)}» تغییر کنه؟"


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
# A6: UIِ «طرح‌های اشتراک» از پنل حذف شد؛ جدول و سرویسِ داده سرِ جایشان ماندند.
ADMIN_PRICING_MENU_INTRO = "💰 تنظیمات قیمت و تخفیف:"


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
ADMIN_ASK_AI_BASE_URL = "آدرس Base URL سرویس هوش مصنوعی رو بفرست (سازگار با فرمت OpenAI):"
ADMIN_ASK_AI_FALLBACK_API_KEY = (
    "کلید API سرویسِ پشتیبانِ هوش مصنوعی رو بفرست (اختیاری — اگه سرویسِ اصلی قطع بود، خودکار به این سوییچ می‌کنه). "
    "برای پاک‌کردن، «خالی» بفرست:"
)
ADMIN_ASK_AI_FALLBACK_MODEL = "نامِ مدلِ سرویسِ پشتیبان رو بفرست. برای پاک‌کردن، «خالی» بفرست:"
ADMIN_ASK_AI_FALLBACK_BASE_URL = "آدرسِ Base URLِ سرویسِ پشتیبان رو بفرست. برای پاک‌کردن، «خالی» بفرست:"
ADMIN_ASK_ZARINPAL_MERCHANT_ID = "مرچنت آیدی زرین‌پال رو بفرست:"
ADMIN_INVALID_BALE_TOKEN = (
    "❌ این مقدار شبیهِ توکن نیست.\n"
    "توکن باید یک تکه باشد (بدونِ فاصله و خطِ جدید) و دستِ‌کم ۲۰ نویسه.\n"
    "اگر می‌خواهی پاکش کنی، «خالی» بفرست."
)
ADMIN_ASK_BALE_PROVIDER_TOKEN = (
    "🔵 توکنِ درگاهِ بله‌پی (provider_token) رو بفرست.\n"
    "این را از پنلِ پذیرندگانِ بله‌پی یا از @botfather در بله می‌گیری و مجوزِ ساختِ لینکِ پرداخت است.\n"
    "اگر فروشگاه‌دار توکنِ درگاهِ خودش را ثبت کرده باشد، اولویت با همان است و این مقدار پشتیبانِ سراسری می‌شود.\n"
    "برای پاک‌کردن، «خالی» بفرست:"
)
ADMIN_ASK_BALE_BOT_TOKEN = (
    "🔵 توکنِ رباتِ بله را بفرست.\n"
    "این توکنِ خودِ رباتِ بله‌ی پلتفرم است (همان چیزی که در .env با نامِ BALE_BOT_TOKEN می‌آمد) و برایِ "
    "ساختِ لینکِ پرداخت و دریافتِ رویدادهایِ پرداخت لازم است.\n"
    "مقدارِ همین پنل بر .env اولویت دارد و بدونِ ری‌استارتِ برنامه اعمال می‌شود.\n"
    "برای پاک‌کردن، «خالی» بفرست (در آن صورت از .env خوانده می‌شود):"
)
ADMIN_ASK_PLATFORM_CARD_NUMBER = "شماره کارت پلتفرم برای دریافت پرداخت‌های کارت‌به‌کارت رو بفرست:"
ADMIN_ASK_PLATFORM_CARD_HOLDER = "نام صاحب کارت رو بفرست:"
ADMIN_ASK_GRACE_PERIOD_HOURS = "چند ساعت مهلت (گریس‌پیریود) بعد از پایان اشتراک داده بشه؟"
ADMIN_ASK_RATE_LIMIT_MAX_MESSAGES = "حداکثر چند پیام از هر مشتری در بازه‌ی زمانی مجاز باشه؟"
ADMIN_ASK_RATE_LIMIT_WINDOW_SECONDS = "این محدودیت روی چند ثانیه اعمال بشه؟"
ADMIN_ASK_REPORT_FREQUENCY_DAYS = "گزارش دوره‌ای هر چند روز یک‌بار برای فروشگاه‌دارها ارسال بشه؟"
ADMIN_ASK_NIGHTLY_REPORT_HOUR = "گزارشِ شبانه سرِ چه ساعتی (به‌وقتِ UTC، عددِ ۰ تا ۲۳) فرستاده بشه؟ ساعتِ تهران سه ساعت و نیم جلوتر از UTC است."
ADMIN_ASK_REFERRAL_PERCENT = (
    "پورسانتِ معرف چند درصد از اولین شارژِ زیرمجموعه‌ش باشه؟ (فقط معرف می‌گیره؛ عدد ۰ یعنی غیرفعال):"
)
ADMIN_ASK_CONVERSATION_HISTORY_LIMIT = "حداکثر چند پیام از تاریخچه‌ی مکالمه به‌عنوان حافظه به هوش مصنوعی داده بشه؟"

ADMIN_ASK_WALLET_COST_PER_1K_TOKENS = "هزینه‌ی هر ۱۰۰۰ توکن (برای پاسخِ چت و تشخیصِ سفارش)، به تومان چقدر باشه؟ (یا از فرمولِ زیر با دکمه‌ی «محاسبه‌ی خودکار» بسازش)"
ADMIN_ASK_AI_COST_USD = "هزینه‌ی واقعیِ مدلِ AI به ازای هر ۱ میلیون توکن، به دلار چقدره؟ (عددِ اعشاری؛ همان نرخِ اعلامیِ سرویس‌دهنده):"
ADMIN_ASK_USD_TO_TOMAN_RATE = "نرخِ تبدیلِ دلار به تومان (که باید خودتون به‌روز نگهش دارید) چنده؟ (فقط عددِ صحیح):"
ADMIN_ASK_MARKUP_MULTIPLIER = "ضریبِ سودِ شما روی هزینه‌ی خامِ AI (که هزینه‌ی سرور هم توش لحاظ می‌شه) چند برابر باشه؟ (عددِ ۵ یعنی ۵ برابر):"
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
PAYMENT_EVENTS_EMPTY = "هنوز هیچ رویدادِ پرداختی ثبت نشده."

# P18 · A1/B11: کدِ داخلیِ «چه چیزی کم است» ← راهنمایِ عملیِ کاربرپسند.
BALE_MISSING_HINTS: dict[str, str] = {
    "bot_token": "توکنِ رباتِ بله تنظیم نشده — «🔑 تنظیمات کلیدها › 🔵 توکنِ رباتِ بله».",
    "provider_token": "توکنِ درگاهِ بله‌پی (provider) ثبت نشده — «🔑 تنظیمات کلیدها › 🔵 توکنِ درگاهِ بله‌پی».",
    "admin_disabled": "کلیدِ سراسریِ بله‌پی خاموش است — «⚙️ تنظیمات › 🔵 فعال/غیرفعالِ بله‌پی».",
    "shop_disabled": "کلیدِ بله‌پیِ خودِ فروشگاه خاموش است — «💳 پرداختِ آنلاینِ سفارش‌ها › 🔵 بله‌پی».",
}


def bale_missing_lines(missing) -> list[str]:
    return [f"• {BALE_MISSING_HINTS[code]}" for code in missing if code in BALE_MISSING_HINTS]


def bale_misconfigured_notice(missing) -> str:
    """B11: وقتی مشتری بله‌پی را زد و پیکربندی ناقص بود، *فروشگاه‌دار* این پیامِ روشن را می‌گیرد (نه مشتری)."""
    lines = ["⚠️ مشتریِ فروشگاهِ تو پرداختِ بله‌پی خواست، ولی پیکربندی کامل نیست:", ""]
    lines.extend(bale_missing_lines(missing))
    lines += ["", "تا این موارد کامل نشوند، دکمه‌یِ بله‌پی به مشتری نشان داده نمی‌شود و پیامِ فنی هم نمی‌بیند."]
    return "\n".join(lines)


def bale_platform_not_ready(missing) -> str:
    """A1: مسیرِ سراسری (شارژِ کیفِ پولِ فروشگاه‌دار نزدِ پلتفرم) — مخاطب خودِ فروشگاه‌دار/ادمین است، پس دلیل دقیق می‌آید."""
    lines = ["⚠️ پرداختِ بله‌پیِ پلتفرم آماده نیست:", ""]
    lines.extend(bale_missing_lines(missing))
    return "\n".join(lines)


BALE_ENABLED_WITHOUT_GLOBAL_PROVIDER = (
    "ℹ️ بله‌پی فعال شد، ولی توکنِ درگاهِ سراسری (provider) در پنلِ تو ثبت نشده.\n"
    "در این حالت فقط فروشگاه‌هایی بله‌پی دارند که توکنِ درگاهِ خودشان را در "
    "«💳 پرداختِ آنلاینِ سفارش‌ها» ثبت کرده باشند.\n"
    "برایِ سراسری‌کردنش: «🔑 تنظیمات کلیدها › 🔵 توکنِ درگاهِ بله‌پی»."
)



def bale_selftest_report(steps: list[tuple[str, bool, str]]) -> str:
    lines = ["🧪 نتیجه‌یِ آزمایشِ بله‌پی\n"]
    for title, ok, detail in steps:
        lines.append(f"{'✅' if ok else '❌'} {title}" + (f"\n    {detail}" if detail else ""))
    if all(ok for _t, ok, _d in steps):
        lines.append("\nهمه‌یِ مرحله‌ها درسته. تستِ نهایی: یه پرداختِ واقعیِ کم‌مبلغ بزن و بعدش «🔎 آخرین رویدادهایِ پرداخت» رو ببین.")
    else:
        lines.append("\nاولین ❌ رو رفع کن؛ متنِ خطا کامل در «🔎 آخرین رویدادهایِ پرداخت» هست.")
    return "\n".join(lines)


def bale_selftest_config_steps(
    *, bot_token_set: bool, bot_token_source: str, provider_set: bool, updates_mode: str, webhook_secret_set: bool
) -> list[tuple[str, bool, str]]:
    """A1(د): خودتشخیصی، هر پیش‌نیاز جدا. هیچ مقدارِ خامی نمایش داده نمی‌شود — فقط «تنظیم شده/نشده» و منبعش."""
    steps: list[tuple[str, bool, str]] = [
        (
            "توکنِ رباتِ بله",
            bot_token_set,
            f"منبع: {bot_token_source}"
            if bot_token_set
            else "در «🔑 تنظیمات کلیدها › 🔵 توکنِ رباتِ بله» بگذار (یا BALE_BOT_TOKEN در .env).",
        ),
        (
            "توکنِ درگاهِ بله‌پی (provider)",
            provider_set,
            "منبع: پنلِ ادمین (پشتیبانِ سراسری). فروشگاه‌دار هم می‌تواند توکنِ خودش را بگذارد که اولویت دارد."
            if provider_set
            else "در «🔑 تنظیمات کلیدها › 🔵 توکنِ درگاهِ بله‌پی» بگذار.",
        ),
    ]
    if updates_mode == "webhook":
        steps.append(
            (
                "رازِ وب‌هوکِ بله",
                webhook_secret_set,
                "خودکار ساخته و ذخیره شده — نیازی نیست دستی واردش کنی."
                if webhook_secret_set
                else "باید خودکار ساخته شود؛ یک‌بار دیگر این آزمایش را بزن.",
            )
        )
    else:
        steps.append(
            (
                "حالتِ دریافتِ رویدادها: polling",
                True,
                "در این حالت به رازِ وب‌هوک و آدرسِ عمومیِ HTTPS نیاز نداری.",
            )
        )
    return steps


def payment_events_text(events) -> str:
    if not events:
        return PAYMENT_EVENTS_EMPTY
    lines = ["🔎 آخرین رویدادهایِ پرداخت (جدید ← قدیم):\n"]
    for e in events:
        when = e.created_at.strftime("%m-%d %H:%M:%S") if e.created_at else "—"
        lines.append(f"{when} · {e.provider}/{e.direction} · {e.method} · {e.status or '—'}" + (f" · ref={e.reference}" if e.reference else ""))
    lines.append("\nجزئیاتِ خام در جدولِ payment_event_logs هست (توکن/شماره‌کارت ماسک شده).")
    return "\n".join(lines)
ADMIN_ASK_PROMPT_SALES = "دستورِ سراسریِ AI برایِ رباتِ «فروشگاهی» رو بفرست. اگه خالی بمونه، متنِ پیش‌فرضِ حرفه‌ای استفاده می‌شه. برایِ پاک کردن بنویس «خالی»."
ADMIN_ASK_PROMPT_CONSULTATION = "دستورِ سراسریِ AI برایِ رباتِ «مشاوره‌ای» رو بفرست. اگه خالی بمونه، متنِ پیش‌فرضِ حرفه‌ای استفاده می‌شه. برایِ پاک کردن بنویس «خالی»."
ADMIN_PROMPT_DEFAULT_LOADED = "✅ متنِ پیش‌فرض بارگذاری و ذخیره شد. می‌تونی از «👀 پیش‌نمایش ربات» نتیجه رو ببینی و ویرایشش کنی."
ADMIN_ASK_SUPPORT_USERNAME = "یوزرنیمِ پشتیبانی رو بفرست (با @ شروع می‌شه). برایِ پاک کردن بنویس «خالی». این شناسه فقط به فروشگاه‌دارها نشون داده می‌شه."
ADMIN_ASK_SUPPORT_PHONE = "شماره‌یِ موبایلِ پشتیبانی رو بفرست. برایِ پاک کردن بنویس «خالی»."
ADMIN_ASK_SUPPORT_TEXT = "متنِ پشتیبانی رو بفرست (ساعتِ پاسخگویی و…). برایِ پاک کردن بنویس «خالی»."
INVALID_SUPPORT_USERNAME = "یوزرنیم نامعتبره. با حرفِ لاتین شروع می‌شه و ۵ تا ۳۲ حرف/رقم/_ داره."
INVALID_SUPPORT_PHONE = "شماره نامعتبره. یه موبایلِ ایرانی بفرست."
SUPPORT_CLEAR_WORDS = ("خالی", "پاک کن", "-")
SUPPORT_NEEDS_CONTACT = "اول یه یوزرنیم یا تلفن برایِ پشتیبانی ثبت کن، بعد فعالش کن."
SUPPORT_SETTINGS_STALE = "این دکمه دیگه معتبر نیست. دوباره «⚙️ تنظیماتِ ربات فروشگاه» رو باز کن."
SUPPORT_ASK = {
    "username": "یوزرنیمِ پشتیبانیِ مشتری‌ها رو بفرست (با @ شروع می‌شه). برایِ پاک کردن بنویس «خالی».",
    "phone": "شماره‌یِ موبایلِ پشتیبانیِ مشتری‌ها رو بفرست. برایِ پاک کردن بنویس «خالی».",
    "text": "متنِ پشتیبانی رو بفرست (ساعتِ پاسخگویی، توضیح و…). برایِ پاک کردن بنویس «خالی».",
}


def shop_support_text(shop_bot) -> str:
    status = "✅ فعال" if shop_bot.support_enabled else "⛔️ خاموش"
    username = f"@{shop_bot.support_contact_username}" if shop_bot.support_contact_username else "—"
    phone = format_phone_display(shop_bot.support_contact_phone) or "—"
    return (
        "📞 پشتیبانیِ مشتری‌ها\n\n"
        "وقتی فعاله، مشتری‌هات دکمه‌یِ «📞 ارتباط با پشتیبانی» رو می‌بینن و همین اطلاعات بهشون نشون داده می‌شه.\n\n"
        f"وضعیت: {status}\nیوزرنیم: {username}\nتلفن: {phone}\nمتن: {shop_bot.support_contact_text or '—'}"
    )


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
        ("bale_bot_token", f"🔵 توکنِ رباتِ بله: {_mask_secret(admin_settings.bale_bot_token)}"),
        ("bale_provider_token", f"🔵 توکنِ درگاهِ بله‌پی: {_mask_secret(admin_settings.bale_provider_token)}"),
        ("platform_card_number", f"💳 شماره کارت پلتفرم: {_mask_secret(admin_settings.platform_card_number)}"),
        ("platform_card_holder_name", f"👤 صاحب کارت: {admin_settings.platform_card_holder_name or 'تنظیم‌نشده'}"),
        ("referral_reward_value", f"🎁 پورسانتِ معرف: {admin_settings.referral_reward_value}٪ از اولین شارژ"),
        ("grace_period_hours", f"⏳ مهلت گریس‌پیریود: {admin_settings.grace_period_hours} ساعت"),
        (
            "rate_limit",
            f"🚦 محدودیت پیام: {admin_settings.rate_limit_max_messages} پیام / {admin_settings.rate_limit_window_seconds} ثانیه",
        ),
        ("periodic_report_frequency_days", f"📈 بازه‌ی گزارش دوره‌ای: هر {admin_settings.periodic_report_frequency_days} روز"),
        (
            "nightly_report_hour_utc",
            f"🌙 ساعتِ گزارشِ شبانه: {admin_settings.nightly_report_hour_utc}:00 UTC (≈ {(admin_settings.nightly_report_hour_utc + 3) % 24}:30 تهران)",
        ),
        ("conversation_history_limit", f"💭 حافظه‌ی مکالمه: {admin_settings.conversation_history_limit} پیام"),
        ("wallet_cost_per_1k_tokens_toman", f"🪙 هزینه‌ی هر ۱۰۰۰ توکن: {format_toman(admin_settings.wallet_cost_per_1k_tokens_toman)}"),
        ("ai_cost_usd_per_1m_tokens", f"💵 هزینه‌ی خامِ AI: ${admin_settings.ai_cost_usd_per_1m_tokens}/۱M توکن"),
        ("usd_to_toman_rate", f"💱 نرخِ دلار: {format_toman(admin_settings.usd_to_toman_rate)}"),
        ("wallet_markup_multiplier", f"📈 ضریبِ سود: {admin_settings.wallet_markup_multiplier}×"),
        ("wallet_cost_photo_analysis_toman", f"🖼 هزینه‌ی تحلیلِ عکس: {format_toman(admin_settings.wallet_cost_photo_analysis_toman)}"),
        ("wallet_cost_receipt_analysis_toman", f"🧾 هزینه‌ی تحلیلِ رسید (مشورتی): {format_toman(admin_settings.wallet_cost_receipt_analysis_toman)}"),
        ("wallet_cost_voice_transcription_toman", f"🎙 هزینه‌ی رونویسیِ صوت: {format_toman(admin_settings.wallet_cost_voice_transcription_toman)}"),
        ("wallet_cost_order_detection_toman", f"🔎 هزینه‌ی پیش‌فرضِ تشخیصِ سفارش: {format_toman(admin_settings.wallet_cost_order_detection_toman)}"),
        ("wallet_topup_validity_months", f"📅 اعتبارِ هر شارژ: {admin_settings.wallet_topup_validity_months} ماه"),
        ("wallet_trial_credit_toman", f"🎁 اعتبارِ آزمایشیِ فروشگاه‌دارِ جدید: {format_toman(admin_settings.wallet_trial_credit_toman)}"),
        ("wallet_low_balance_warning_toman", f"🟡 آستانه‌ی هشدارِ کمبودِ موجودی: {format_toman(admin_settings.wallet_low_balance_warning_toman)}"),
        ("global_ai_system_prompt", f"🌍 دستور سراسری هوش مصنوعی: {global_prompt_label}"),
        ("global_ai_prompt_sales", f"🛍 دستورِ سراسری — فروشگاهی: {'تنظیم‌شده ✅' if admin_settings.global_ai_prompt_sales else 'پیش‌فرضِ حرفه‌ای'}"),
        ("global_ai_prompt_consultation", f"💬 دستورِ سراسری — مشاوره‌ای: {'تنظیم‌شده ✅' if admin_settings.global_ai_prompt_consultation else 'پیش‌فرضِ حرفه‌ای'}"),
        ("reference_channel_link", f"🔗 کانال مرجع: {reference_channel_label}"),
        ("platform_support_username", f"📞 پشتیبانیِ پلتفرم — یوزرنیم: {'@' + admin_settings.platform_support_username if admin_settings.platform_support_username else 'تنظیم‌نشده'}"),
        ("platform_support_phone", f"📞 پشتیبانیِ پلتفرم — تلفن: {format_phone_display(admin_settings.platform_support_phone) or 'تنظیم‌نشده'}"),
        ("platform_support_text", f"📞 پشتیبانیِ پلتفرم — متن: {'تنظیم‌شده ✅' if admin_settings.platform_support_text else 'خالی'}"),
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


_NO_SHOP_INFO = object()
OWNER_LABEL_MAX_LEN = 60


def admin_owner_list_item_label(owner, shop_bot=_NO_SHOP_INFO) -> str:
    """نامِ فروشگاه‌دار؛ اگه اطلاعاتِ ربات داده بشه: «✅ نام — @ربات» / «⛔️ …» (معلق) / «… — بدونِ ربات».
    بدونِ پارامترِ shop_bot رفتارِ قبلی (فقط نام) حفظ می‌شه."""
    name = display_name(owner) + (f" (@{owner.username})" if getattr(owner, "username", None) else "")
    if shop_bot is _NO_SHOP_INFO:
        return name
    if shop_bot is None:
        label = f"{name} — بدونِ ربات"
    else:
        icon = "✅" if shop_bot.is_active else "⛔️"
        label = f"{icon} {name} — @{shop_bot.bot_username}"
    if len(label) > OWNER_LABEL_MAX_LEN:
        label = label[: OWNER_LABEL_MAX_LEN - 1].rstrip() + "…"
    return label


def admin_shop_owners_intro(total: int, page: int, total_pages: int) -> str:
    return (
        f"👥 فهرستِ فروشگاه‌دارها — {total} نفر (صفحه‌یِ {page + 1} از {total_pages})\n"
        "✅ ربات فعال · ⛔️ ربات معلق · «بدونِ ربات» = هنوز رباتی وصل نکرده\n"
        "روی هر مورد بزن تا جزئیات و مدیریتش باز بشه:"
    )


ADMIN_OWNER_NO_SHOP_BOT = "این فروشگاه‌دار هنوز ربات فروشگاهی‌ای وصل نکرده."


def admin_owner_suspended_confirmation(owner_name: str) -> str:
    return f"⛔️ ربات فروشگاهی‌ِ {owner_name} معلق شد."


def admin_owner_unsuspended_confirmation(owner_name: str) -> str:
    return f"✅ ربات فروشگاهی‌ِ {owner_name} دوباره فعال شد."


def admin_shop_owner_detail(owner, shop_bot, wallet_balance_toman: int) -> str:
    lines = [f"👤 {display_user(owner, 'full')}"]
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
        "کاهش (اصلاح) با - جلوش بنویس:"
    )
    return "\n".join(lines)


ADMIN_INVALID_SIGNED_AMOUNT = "این عدد معتبر نیست. یه عددِ غیرصفر بنویس؛ برایِ کاهش، - رو جلوش بذار."
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
    "برچسب (فقط برایِ خودت، تا کلیدها رو از هم تشخیص بدی)\n"
    "کلیدِ API\n"
    "نامِ مدل\n"
    "آدرسِ base_url کاملِ chat/completions\n"
    "نوع: chat یا vision یا both"
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


def admin_role_added_confirmation(label: str) -> str:
    return f"✅ {label} به‌عنوانِ ادمینِ عملیاتی اضافه شد."


def admin_role_detail_text(role, label: str = "ادمین", granter_label: str = "سوپرادمین") -> str:
    """صفحه‌یِ مدیریتیِ نقش‌ها (فقط سوپرادمین): هویتِ متنی؛ شناسه‌یِ عددی فقط در خطِ «🔧 فنی» (استثنایِ مجازِ H2)."""
    when = role.created_at.strftime("%Y-%m-%d %H:%M")
    return (
        f"👤 {label}\n"
        f"نقش: ادمینِ عملیاتی\n"
        f"اضافه‌شده توسطِ: {granter_label}\n"
        f"تاریخ: {when}\n"
        f"🔧 شناسه‌یِ فنی: {role.telegram_id}"
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
    "admin_batch_executed": "📦 عملیاتِ گروهیِ ادمین (هدیه/تمدید)",
    "time_freeze_changed": "❄️ توقفِ زمان",
    "jobs_pause_changed": "⏸ توقفِ جاب‌هایِ زمان‌بندی",
    "operator_admin_granted": "👑 افزودنِ ادمینِ عملیاتی",
    "operator_admin_revoked": "👑 حذفِ ادمینِ عملیاتی",
    "wallet_ledger_exported": "📤 خروجیِ دفترِ کیف‌پول (اکسل)",
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



# =============================================================================
# کمپین‌ها — تخفیفِ مخصوصِ مشتری‌هایِ فروشگاه (فازِ ۳). منطقش توی campaign_service ـه.
# =============================================================================
CAMPAIGNS_EMPTY = (
    "هنوز کمپینی نساختی 🎯\n\n"
    "با کمپین می‌تونی برایِ مشتری‌هایِ خودت تخفیفِ درصدی یا مبلغ‌ثابت بذاری — با کد یا خودکار — "
    "و بعد با یه دکمه بهشون اعلامش کنی. مشتری تخفیف رو موقعِ «ثبتِ نهاییِ» سبدِ خرید می‌گیره."
)
CAMPAIGNS_LIST_INTRO = "🎯 کمپین‌هایِ تو (رویِ هرکدوم بزن تا جزئیات و مدیریتش رو ببینی):"
CAMPAIGN_NOT_FOUND = "این کمپین پیدا نشد (شاید قبلاً حذف شده)."
CAMPAIGN_ALREADY_ENDED = "مدتِ این کمپین تموم شده؛ دیگه نمی‌شه فعال/متوقفش کرد. اگه می‌خوای، یه کمپینِ جدید بساز."
CAMPAIGN_PAUSED_TOAST = "کمپین متوقف شد."
CAMPAIGN_RESUMED_TOAST = "کمپین دوباره فعال شد."
CAMPAIGN_DELETED_TOAST = "کمپین حذف شد."
CAMPAIGN_CANNOT_DELETE_USED = (
    "این کمپین قبلاً توی سفارش‌ها استفاده شده، برای همین حذف نمی‌شه (تا سوابقِ فروش و اکسلت سالم بمونه). "
    "فقط می‌تونی متوقفش کنی."
)
CAMPAIGN_ANNOUNCE_ONLY_ACTIVE = "اعلام فقط برایِ کمپینِ فعال ممکنه (متوقف/تمام‌شده/زمان‌بندی‌شده نه)."
CAMPAIGN_WIZARD_STALE = "این مرحله دیگه معتبر نیست. از «🎯 کمپین‌ها» دوباره شروع کن."
CAMPAIGN_USE_BUTTONS = "برایِ این مرحله از دکمه‌هایِ بالا استفاده کن 👆 (یا /cancel برایِ لغو)."
CAMPAIGN_CREATE_CANCELLED = "ساختِ کمپین لغو شد."

CAMPAIGN_ASK_NAME = "اسمِ کمپین چیه؟ — مشتری‌ها این اسم رو توی پیام‌ها می‌بینن.\n\nبرایِ لغو: /cancel"
CAMPAIGN_NAME_INVALID = "اسمِ کمپین باید بینِ ۱ تا ۶۰ حرف باشه. دوباره بنویس:"
CAMPAIGN_ASK_TYPE = "نوعِ تخفیف چیه؟"
CAMPAIGN_ASK_PERCENT = "چند درصد تخفیف؟ یه عددِ ۱ تا ۱۰۰ بفرست:"
CAMPAIGN_ASK_FIXED = "مبلغِ تخفیف چند تومانه؟ (به تومان):"
CAMPAIGN_PERCENT_INVALID = "درصد باید یه عددِ صحیحِ ۱ تا ۱۰۰ باشه. دوباره بفرست:"
CAMPAIGN_AMOUNT_INVALID = "مبلغ باید یه عددِ صحیحِ مثبت باشه (به تومان، حداکثر یک میلیارد). دوباره بفرست:"
CAMPAIGN_ASK_MAX_DISCOUNT = (
    "سقفِ مبلغِ تخفیف چنده؟ تخفیفِ هر سبد، هرچقدر هم سبد گران باشه، از این سقف بیشتر نمی‌شه.\n\n"
    "یه عدد (به تومان) بفرست یا «بدونِ سقف» رو بزن:"
)
CAMPAIGN_ASK_CODE_CHOICE = (
    "مشتری چطور از این تخفیف استفاده کنه؟\n\n"
    "🎟 با کد: مشتری موقعِ ثبتِ نهایی کد رو وارد می‌کنه.\n"
    "⚡ خودکار: بدونِ کد، برایِ همه اعمال می‌شه."
)
CAMPAIGN_ASK_CODE = (
    "کدِ تخفیف چی باشه؟ ۳ تا ۲۰ نویسه — حروف (فارسی یا لاتین)، رقم، _ و -. "
    "به حروفِ بزرگ/کوچیک و نوعِ رقم حساس نیست."
)
CAMPAIGN_CODE_INVALID = "کد باید ۳ تا ۲۰ نویسه باشه و فقط حروف، رقم، _ و - داشته باشه (بدونِ فاصله). دوباره بفرست:"
CAMPAIGN_CODE_TAKEN = "این کد قبلاً برایِ یه کمپینِ دیگه‌ی فروشگاهت استفاده شده. یه کدِ دیگه بفرست:"
CAMPAIGN_ASK_MIN_CART = "حداقلِ مبلغِ سبد برایِ استفاده از این تخفیف چقدر باشه؟ یه عدد (به تومان) بفرست یا «ندارد» رو بزن:"
CAMPAIGN_ASK_DURATION = "کمپین از همین الان شروع می‌شه. چند روز فعال باشه؟ یکی رو بزن یا یه عددِ ۱ تا ۳۶۵ بفرست:"
CAMPAIGN_DURATION_INVALID = "تعدادِ روز باید یه عددِ صحیحِ ۱ تا ۳۶۵ باشه. دوباره بفرست:"
CAMPAIGN_ASK_TOTAL_LIMIT = (
    "کلاً چندبار قابلِ استفاده باشه؟ (بعد از این تعداد، کد خودبه‌خود تموم می‌شه)\n\n"
    "یه عدد بفرست یا «نامحدود» رو بزن:"
)
CAMPAIGN_LIMIT_INVALID = "این باید یه عددِ صحیحِ مثبت باشه. دوباره بفرست:"
CAMPAIGN_ASK_PER_CUSTOMER = "هر مشتری چندبار می‌تونه از این تخفیف استفاده کنه؟"


def campaign_ask_min_cart_fixed(discount_toman: int) -> str:
    return (
        f"برایِ تخفیفِ مبلغ‌ثابت، «حداقلِ مبلغِ سبد» اجباریه و باید از خودِ تخفیف ({format_toman(discount_toman)}) "
        "بیشتر باشه — تا سفارشِ رایگان یا منفی پیش نیاد.\n\nحداقلِ مبلغِ سبد چقدر باشه؟ (به تومان):"
    )


def campaign_min_cart_too_low(discount_toman: int) -> str:
    return f"حداقلِ مبلغِ سبد باید از مبلغِ تخفیف ({format_toman(discount_toman)}) بیشتر باشه. دوباره بفرست:"


_CAMPAIGN_ERROR_TEXTS = {
    "bad_name": "اسمِ کمپین معتبر نیست.",
    "bad_value": "مقدارِ تخفیف معتبر نیست.",
    "bad_max_discount": "سقفِ مبلغِ تخفیف معتبر نیست.",
    "fixed_needs_min_cart": "برایِ تخفیفِ مبلغ‌ثابت، حداقلِ مبلغِ سبد اجباریه و باید از خودِ تخفیف بیشتر باشه.",
    "bad_min_cart": "حداقلِ مبلغِ سبد معتبر نیست.",
    "bad_duration": "مدتِ کمپین معتبر نیست.",
    "bad_limit": "سقفِ استفاده معتبر نیست.",
    "bad_code": "کدِ تخفیف معتبر نیست.",
    "code_taken": "این کد همین الان برایِ یه کمپینِ دیگه‌ی فروشگاهت ثبت شده.",
    "bad_type": "نوعِ تخفیف معتبر نیست.",
}


def campaign_create_error(code: str) -> str:
    return f"❌ کمپین ساخته نشد: {_CAMPAIGN_ERROR_TEXTS.get(code, 'ورودی‌ها معتبر نبودن.')}\nاز «🎯 کمپین‌ها» دوباره شروع کن."


def _limit_text(value: int | None, unit: str = "بار") -> str:
    return "نامحدود" if value is None else f"{value} {unit}"


def campaign_discount_description(discount_type, value: int, max_discount_toman: int | None) -> str:
    type_value = discount_type.value if hasattr(discount_type, "value") else discount_type
    if type_value == "percent":
        text = f"{value} درصد"
        if max_discount_toman:
            text += f" (حداکثر {format_toman(max_discount_toman)})"
        return text
    return format_toman(value)


def campaign_wizard_summary(data: dict, now: datetime.datetime) -> str:
    """خلاصه‌ی قبل از ساخت، به زبانِ ساده. data = FSM data ویزارد."""
    from app.utils.jalali import format_jalali_datetime

    kind = data["discount_type"]
    discount = campaign_discount_description(kind, data["discount_value"], data.get("max_discount_toman"))
    ends_at = now + datetime.timedelta(days=data["duration_days"])
    lines = [
        "📝 خلاصه‌ی کمپین — اگه درسته تایید کن:\n",
        f"اسم: {data['name']}",
        f"تخفیف: {discount} از جمعِ سبد",
    ]
    if data.get("code"):
        lines.append(f"نحوه‌ی استفاده: 🎟 با کدِ {data['code']}")
    else:
        lines.append("نحوه‌ی استفاده: ⚡ خودکار برایِ همه (بدونِ کد)")
    if data.get("min_cart_total_toman"):
        lines.append(f"حداقلِ مبلغِ سبد: {format_toman(data['min_cart_total_toman'])}")
    lines.append(f"مدت: {data['duration_days']} روز — از همین الان تا {format_jalali_datetime(ends_at)} (به وقتِ تهران)")
    lines.append(f"سقفِ کلِ استفاده: {_limit_text(data.get('total_usage_limit'))}")
    lines.append(f"سقفِ هر مشتری: {_limit_text(data.get('per_customer_limit'))}")
    if kind == "percent" and data["discount_value"] == 100:
        lines.append("\n⚠️ تخفیفِ ۱۰۰٪ یعنی سفارشِ رایگان!")
    lines.append("\nبعد از ساخت، تخفیف همون لحظه فعاله.")
    return "\n".join(lines)


def campaign_created(campaign, now: datetime.datetime) -> str:
    from app.utils.jalali import format_jalali_datetime

    return (
        f"✅ کمپینِ «{campaign.name}» ساخته و فعال شد.\n"
        f"تا {format_jalali_datetime(campaign.ends_at)} (به وقتِ تهران) معتبره.\n\n"
        "الان می‌تونی به مشتری‌هات اعلامش کنی:"
    )


_CAMPAIGN_STATUS_LABELS = {
    "active": "🟢 فعال",
    "paused": "⏸ متوقف",
    "scheduled": "🕓 زمان‌بندی‌شده",
    "ended": "⏹ تمام‌شده",
}


def campaign_detail_text(campaign, status: str, uses: int, discount_total_toman: int) -> str:
    from app.utils.jalali import format_jalali_datetime

    lines = [
        f"🎯 {campaign.name}",
        f"وضعیت: {_CAMPAIGN_STATUS_LABELS.get(status, status)}",
        f"تخفیف: {campaign_discount_description(campaign.discount_type, campaign.discount_value, campaign.max_discount_toman)}",
    ]
    if campaign.code:
        lines.append(f"نحوه‌ی استفاده: 🎟 با کدِ {campaign.code}")
    else:
        lines.append("نحوه‌ی استفاده: ⚡ خودکار برایِ همه (بدونِ کد)")
    if campaign.min_cart_total_toman:
        lines.append(f"حداقلِ مبلغِ سبد: {format_toman(campaign.min_cart_total_toman)}")
    lines.append(f"شروع: {format_jalali_datetime(campaign.starts_at)}")
    lines.append(f"پایان: {format_jalali_datetime(campaign.ends_at)} (به وقتِ تهران)")
    lines.append(f"سقفِ هر مشتری: {_limit_text(campaign.per_customer_limit)}")
    lines.append(f"سقفِ کلِ استفاده: {_limit_text(campaign.total_usage_limit)}")
    lines.append(f"\nاستفاده‌شده: {uses} بار — جمعِ تخفیفِ داده‌شده: {format_toman(discount_total_toman)}")
    if campaign.total_usage_limit is not None:
        lines.append(f"ظرفیتِ باقی‌مانده: {max(0, campaign.total_usage_limit - uses)} بار")
    lines.append("(سفارش‌هایی که ردشدن یا رزروشون منقضی شده، حساب نمی‌شن.)")
    return "\n".join(lines)


def campaign_announcement_text(campaign) -> str:
    """متنِ پیش‌فرضِ اعلامِ کمپین به مشتری‌ها — فروشگاه‌دار قبل از ارسال می‌بینه."""
    from app.utils.jalali import format_jalali_datetime

    type_value = campaign.discount_type.value if hasattr(campaign.discount_type, "value") else campaign.discount_type
    if type_value == "percent":
        offer_line = f"{campaign.discount_value} درصد تخفیف روی کلِ سبدِ خرید"
        if campaign.max_discount_toman:
            offer_line += f" (حداکثر {format_toman(campaign.max_discount_toman)} تخفیف)"
    else:
        offer_line = f"{format_toman(campaign.discount_value)} تخفیف روی سبدِ خرید"

    lines = [f"🎁 {campaign.name}", "", offer_line]
    if campaign.min_cart_total_toman:
        lines.append(f"برایِ سبدهایِ حداقل {format_toman(campaign.min_cart_total_toman)}")
    lines.append("")
    if campaign.code:
        lines.append(f"🎟 کدِ تخفیف: {campaign.code}")
    else:
        lines.append("این تخفیف خودکار برایِ همه اعمال می‌شه؛ لازم نیست کدی وارد کنی.")
    lines.append(f"⏳ تا {format_jalali_datetime(campaign.ends_at)} (به وقتِ تهران)")
    if campaign.per_customer_limit == 1:
        lines.append("هر نفر فقط یک‌بار می‌تونه استفاده کنه.")
    elif campaign.per_customer_limit:
        lines.append(f"هر نفر حداکثر {campaign.per_customer_limit} بار می‌تونه استفاده کنه.")
    lines.append("")
    if campaign.code:
        lines.append(
            "برایِ استفاده: محصولات رو از «🛍 محصولات» به «🛒 سبدِ خرید» اضافه کن؛ موقعِ ثبتِ نهایی دکمه‌ی "
            "«🎟 کد تخفیف دارم» رو بزن و کد رو وارد کن."
        )
    else:
        lines.append(
            "برایِ استفاده: محصولات رو از «🛍 محصولات» به «🛒 سبدِ خرید» اضافه کن؛ تخفیف موقعِ ثبتِ نهایی خودکار اعمال می‌شه."
        )
    return "\n".join(lines)


# =============================================================================
# فازِ ۴-الف/ب — سوال‌هایِ بی‌جواب و پرسش‌وپاسخ‌هایِ تاییدشده
# =============================================================================
GAPS_EMPTY = "🧩 فعلاً هیچ سوالِ بی‌جوابی نداری. هر وقت رباتت جوابِ سوالی رو ندونه، اینجا ثبتش می‌کنه."
GAPS_DETECTION_OFF_NOTE = "ℹ️ تشخیصِ سوال‌هایِ بی‌جواب فعلاً توسطِ مدیرِ پلتفرم خاموشه؛ سوالِ تازه‌ای ثبت نمی‌شه."
GAP_NOT_FOUND = "این مورد پیدا نشد (ممکنه حذف شده باشه)."
GAP_NOT_OPEN = "این سوال دیگه باز نیست (قبلاً جواب داده شده یا نادیده گرفته شده)."
GAP_DISMISSED = "🙈 سوال نادیده گرفته شد."
GAP_ANSWER_EMPTY = "جواب نمی‌تونه خالی باشه. لطفاً جواب رو بنویس."
GAP_ANSWER_TOO_LONG = "این جواب خیلی طولانیه (حداکثر ۵۰۰ حرف). یه‌کم کوتاه‌ترش کن."
GAP_SAVE_CANCELLED = "لغو شد؛ چیزی ذخیره نشد."
GAP_SAVED = "✅ ذخیره شد. از این به بعد رباتت برایِ سوال‌هایِ مشابه از جوابِ تو استفاده می‌کنه."
LEARNED_LIMIT_REACHED = "به سقفِ ۲۰۰ پرسش‌وپاسخِ تاییدشده رسیدی. اول یه چندتا از قدیمی‌ها رو حذف کن."
KNOWLEDGE_STALE_BUTTON = "این دکمه دیگه معتبر نیست. دوباره از منو شروع کن."


def gaps_page_text(gaps, total: int, page: int, page_size: int) -> str:
    """سوالِ مشتری غیرِ قابلِ اعتماده؛ همیشه متنِ ساده (بدونِ parse_mode) نمایش داده می‌شه."""
    lines = [f"🧩 سوال‌هایِ بی‌جواب ({total} مورد) — بیشترین تکرار اول:\n"]
    for index, gap in enumerate(gaps, start=page * page_size + 1):
        lines.append(f"{index}. «{gap.question_text}»\n   🔁 {gap.occurrences} بار پرسیده شده")
    return "\n".join(lines)


def gap_answer_prompt(question: str) -> str:
    return (
        f"سوالِ مشتری:\n«{question}»\n\n"
        "جوابِ درستِ این سوال رو بنویس (حداکثر ۵۰۰ حرف). رباتت برایِ سوال‌هایِ مشابه از همین جواب استفاده می‌کنه.\n"
        "برایِ انصراف /cancel رو بزن."
    )


def gap_answer_preview(question: str, answer: str) -> str:
    return (
        "این به‌عنوانِ پاسخِ تاییدشده ذخیره می‌شه و ربات ازش استفاده می‌کنه:\n\n"
        f"❓ سوال: {question}\n💬 جواب: {answer}\n\nذخیره بشه؟"
    )


LEARNED_EMPTY = "📚 هنوز پرسش‌وپاسخِ تاییدشده‌ای نداری. از «🧩 سوال‌هایِ بی‌جواب» یا با «➕ افزودنِ دستی» شروع کن."


def learned_list_text(total: int) -> str:
    return (
        f"📚 پرسش‌وپاسخ‌هایِ تاییدشده ({total} مورد)\n"
        "رباتت از ۲۰ موردِ جدیدترِ «فعال» برایِ جواب‌دادن استفاده می‌کنه."
    )


def learned_detail_text(item) -> str:
    status = "✅ فعال" if item.is_active else "⏸ غیرفعال (ربات ازش استفاده نمی‌کنه)"
    return f"❓ سوال: {item.question}\n\n💬 جواب: {item.answer}\n\nوضعیت: {status}"


ASK_LEARNED_NEW_ANSWER = "جوابِ جدید رو بنویس (حداکثر ۵۰۰ حرف). برایِ انصراف /cancel رو بزن."
LEARNED_ANSWER_UPDATED = "✅ جواب به‌روز شد."
LEARNED_TOGGLED_ON = "فعال شد ✅"
LEARNED_TOGGLED_OFF = "غیرفعال شد ⏸"
LEARNED_DELETE_ASK = "مطمئنی می‌خوای این پرسش‌وپاسخ رو برایِ همیشه حذف کنی؟"
LEARNED_DELETED = "🗑 حذف شد."
ASK_MANUAL_QUESTION = "سوال رو بنویس (حداکثر ۲۰۰ حرف). برایِ انصراف /cancel رو بزن."
MANUAL_QUESTION_EMPTY = "سوال نمی‌تونه خالی باشه. لطفاً بنویس."
MANUAL_QUESTION_TOO_LONG = "این سوال خیلی طولانیه (حداکثر ۲۰۰ حرف). کوتاه‌ترش کن."
ASK_MANUAL_ANSWER = "حالا جوابِ این سوال رو بنویس (حداکثر ۵۰۰ حرف):"


# =============================================================================
# فازِ ۴-ه — حسابداریِ فقط‌خواندنی
# =============================================================================
ACCOUNTING_NOTE = (
    "ℹ️ مبلغ‌ها بر اساسِ «ارزشِ ثبت‌شده‌یِ سفارش» (بعد از تخفیف) و فقط سفارش‌هایِ تاییدشده‌ان؛ "
    "ردشده/منقضی/لغوشده شمرده نمی‌شن. این گزارش فقط‌خواندنیه و چیزی رو تغییر نمی‌ده."
)
ACCOUNTING_TRUNCATED_NOTE = "⚠️ تعدادِ سفارش‌هایِ این بازه خیلی زیاده و گزارش فقط ۲۰٬۰۰۰ موردش رو در بر می‌گیره؛ عددها ناقص‌ان."
ACCOUNTING_EXCEL_READY = "📤 اکسلِ حسابداریِ این بازه آماده‌ست."
ADMIN_WALLET_LEDGER_READY = "📤 دفترِ کیف‌پولِ همه‌یِ فروشگاه‌دارها آماده‌ست (فقط‌خواندنی؛ جدیدترین تراکنش‌ها اول)."
_ACCOUNTING_STATUS_OVERRIDES = {"awaiting_customer_confirmation": "🕓 منتظرِ تاییدِ مشتری"}


def accounting_status_label(status) -> str:
    key = status.value if hasattr(status, "value") else status
    return _ACCOUNTING_STATUS_OVERRIDES.get(key) or order_status_label(key)


def accounting_report_text(report) -> str:
    import datetime as _dt

    from app.utils.jalali import format_jalali_date

    summary = report.summary
    period = summary.period
    first_day = format_jalali_date(period.start)
    last_day = format_jalali_date(period.end - _dt.timedelta(days=1))
    date_line = first_day if first_day == last_day else f"{first_day} تا {last_day}"

    lines = [
        f"🧮 حسابداری — {period.label}",
        f"📅 {date_line}",
        "",
        f"💰 فروشِ ناخالص: {format_toman(summary.gross_toman)}",
        f"🏷 جمعِ تخفیف‌ها: {format_toman(summary.discount_toman)}",
        f"✅ فروشِ خالص: {format_toman(summary.net_toman)}",
        f"🧾 سفارشِ تاییدشده: {summary.successful_count} — میانگینِ هر سفارش: {format_toman(summary.average_order_toman)}",
        f"💳 پرداختِ آنلاین: {summary.online_paid_count} مورد — {format_toman(summary.online_paid_toman)}",
    ]
    if summary.status_counts:
        lines.append("\n📋 وضعیتِ سفارش‌هایِ ثبت‌شده در این بازه:")
        lines.extend(f"  {accounting_status_label(status)}: {count}" for status, count in summary.status_counts.items())
    if report.pending_total > 0:
        lines.append(f"\n⏳ در حالِ حاضر کلاً {report.pending_total} سفارش منتظرِ بررسیِ شماست.")
    if summary.top_products:
        lines.append("\n🏆 پرفروش‌ترین‌ها:")
        for index, product in enumerate(summary.top_products, start=1):
            lines.append(f"  {index}. {product.name} — {product.units} عدد — {format_toman(product.net_toman)}")
    if summary.campaigns:
        lines.append("\n🎯 عملکردِ کمپین‌ها (سفارش‌هایِ تاییدشده):")
        for campaign in summary.campaigns:
            lines.append(
                f"  • {campaign.name}: {campaign.uses} بار مصرف — تخفیف {format_toman(campaign.discount_toman)}"
                f" — فروشِ خالص {format_toman(campaign.net_toman)}"
            )
    if report.truncated:
        lines.append(f"\n{ACCOUNTING_TRUNCATED_NOTE}")
    lines.append(f"\n{ACCOUNTING_NOTE}")
    return "\n".join(lines)


# =============================================================================
# فازِ ۴-ج — CRM
# =============================================================================
CRM_SEGMENT_LABELS = {
    "loyal": "💎 وفادار",
    "active": "🟢 فعال",
    "new": "🆕 جدید",
    "churning": "⚠️ در حالِ ریزش",
    "no_purchase": "💤 بدونِ خرید",
}
CRM_SEGMENT_HINTS = {
    "loyal": "۳ سفارشِ موفق یا بیشتر و فعالیت در ۴۵ روزِ اخیر",
    "active": "۱ یا ۲ سفارشِ موفق و فعالیت در ۴۵ روزِ اخیر",
    "new": "هنوز خرید نکرده و کمتر از ۷ روز از اولین حضورش گذشته",
    "churning": "حداقل یک خریدِ موفق داشته ولی بیش از ۴۵ روزه فعالیتی نداره",
    "no_purchase": "هنوز خریدِ موفقی نداشته و بیش از ۷ روز از اولین حضورش گذشته",
}
CRM_EMPTY = "👥 هنوز هیچ مشتری‌ای با رباتت چت نکرده. وقتی مشتری‌ها بیان، اینجا بخش‌بندی می‌شن."
CRM_TRUNCATED_NOTE = "⚠️ تعدادِ مشتری‌هایِ فروشگاهت خیلی زیاده و فقط ۵۰٬۰۰۰ تایِ اول بخش‌بندی شدن."
CRM_NOT_FOUND = "این مشتری پیدا نشد."
CRM_SEGMENT_EMPTY = "این بخش الان مشتری‌ای نداره."
CRM_STALE_BUTTON = "این دکمه دیگه معتبر نیست. دوباره از «👥 مشتری‌ها» شروع کن."
CRM_NOTE_ASK = "یادداشتت درباره‌یِ این مشتری رو بنویس (حداکثر ۱۰۰۰ حرف). فقط خودت می‌بینی. برایِ انصراف /cancel رو بزن."
CRM_NOTE_TOO_LONG = "این یادداشت بیشتر از ۱۰۰۰ حرفه. کوتاه‌ترش کن."
CRM_NOTE_SAVED = "✅ یادداشت ذخیره شد."
CRM_NOTE_CLEARED = "🗑 یادداشت پاک شد."
CRM_TAGS_ASK = (
    "برچسب‌ها رو بنویس؛ با ویرگول یا خطِ جدید جداشون کن (حداکثر ۵ برچسب، هر کدوم تا ۲۰ حرف). "
    "برایِ انصراف /cancel رو بزن."
)
CRM_TAG_TOO_LONG = "یکی از برچسب‌ها بیشتر از ۲۰ حرفه. کوتاه‌ترش کن."
CRM_TOO_MANY_TAGS = "حداکثر ۵ برچسب می‌تونی بذاری. کمتر بنویس."
CRM_TAGS_SAVED = "✅ برچسب‌ها ذخیره شد."
CRM_TAGS_CLEARED = "🗑 برچسب‌ها پاک شد."
CRM_BROADCAST_EMPTY = "این بخش الان مشتری‌ای نداره؛ چیزی برایِ ارسال نیست."


# ------------------------------------------------------------------ P18 · B4: بلاکِ مشتری و خواندنِ گفتگو
CRM_BLOCKED_BADGE = (
    "🚫 این مشتری بلاک است: ربات فقط یک پیامِ ادبی به او می‌دهد و هیچ هزینه‌یِ AI/سفارش/پرداختی برایت ندارد."
)
CRM_BLOCK_DONE = "🚫 بلاک شد."
CRM_UNBLOCK_DONE = "✅ رفعِ بلاک شد؛ ربات دوباره جوابش را می‌دهد."
CRM_CONVERSATION_EMPTY = "💬 این مشتری هنوز گفتگویی با ربات نداشته."
# محتوایِ گفتگو متنِ خودِ کاربر است: کوتاه می‌شود تا از سقفِ تلگرام رد نشود و همیشه بدونِ parse_mode می‌رود.
CONVERSATION_MESSAGE_MAX_CHARS = 400
CONVERSATION_TEXT_MAX_CHARS = 3500


def crm_conversation_text(customer_name: str, messages, page: int, total_pages: int, total: int) -> str:
    lines = [f"💬 گفتگو با {customer_name}", f"صفحه‌یِ {page + 1} از {total_pages} — در مجموع {total} پیام", ""]
    for item in messages:
        who = "👤 مشتری" if item.role == "user" else "🤖 ربات"
        body = " ".join((item.content or "").split())
        if len(body) > CONVERSATION_MESSAGE_MAX_CHARS:
            body = body[: CONVERSATION_MESSAGE_MAX_CHARS - 1] + "…"
        lines.append(f"{who} · {_crm_datetime(item.created_at)}\n{body}")
    text = "\n\n".join(lines).strip()
    if len(text) > CONVERSATION_TEXT_MAX_CHARS:
        text = text[: CONVERSATION_TEXT_MAX_CHARS - 1] + "…"
    return text


def crm_overview_text(counts: dict, total: int, truncated: bool) -> str:
    lines = [f"👥 مشتری‌هایِ فروشگاهت — کل: {total} نفر\n"]
    for key, label in CRM_SEGMENT_LABELS.items():
        lines.append(f"{label}: {counts.get(key, 0)} نفر\n   ↳ {CRM_SEGMENT_HINTS[key]}")
    lines.append("\nروی یه بخش بزن تا فهرستش رو ببینی.")
    if truncated:
        lines.append(f"\n{CRM_TRUNCATED_NOTE}")
    return "\n".join(lines)


def crm_customer_name(stat) -> str:
    """نام/یوزرنیمِ مشتری متنِ کاربره (غیرِ قابلِ اعتماد) → همیشه متنِ ساده، بدونِ parse_mode."""
    name = (stat.first_name or "").strip() or "بدونِ نام"
    return f"{name} (@{stat.username})" if stat.username else name


def crm_customer_label(customer) -> str:
    """همان قاعده‌یِ `crm_customer_name` ولی از رویِ خودِ ردیفِ `Customer` (B4: سرصفحه‌یِ گفتگو)."""
    name = " ".join(part for part in ((customer.first_name or "").strip(), (customer.last_name or "").strip()) if part)
    name = name or "بدونِ نام"
    return f"{name} (@{customer.username})" if customer.username else name


def _crm_date(moment) -> str:
    from app.utils.jalali import format_jalali_date

    return format_jalali_date(moment) if moment else "—"


def _crm_datetime(moment) -> str:
    from app.utils.jalali import format_jalali_datetime

    return format_jalali_datetime(moment) if moment else "—"


def crm_segment_text(segment_key: str, members, total: int, page: int, total_pages: int, page_size: int) -> str:
    label = CRM_SEGMENT_LABELS.get(segment_key, segment_key)
    lines = [f"{label} — {total} نفر (صفحه‌ی {page + 1} از {total_pages})\n"]
    for index, stat in enumerate(members, start=page * page_size + 1):
        lines.append(
            f"{index}. {crm_customer_name(stat)}\n"
            f"   🧾 {stat.success_count} سفارش — 💰 {format_toman(stat.net_toman)} — 📅 {_crm_date(stat.last_activity)}"
        )
    return "\n".join(lines)


def crm_card_text(stat, customer, orders) -> str:
    tags = [tag for tag in (customer.crm_tags or "").split(",") if tag]
    lines = [
        f"👤 {crm_customer_name(stat)}",
        f"بخش: {CRM_SEGMENT_LABELS.get(stat.segment, stat.segment)}",
        f"🧾 سفارشِ موفق: {stat.success_count} — 💰 خریدِ خالص: {format_toman(stat.net_toman)}",
        f"📅 اولین حضور: {_crm_date(stat.first_seen_at)} — آخرین فعالیت: {_crm_date(stat.last_activity)}",
        "🏷 برچسب‌ها: " + (" ".join(f"#{tag}" for tag in tags) if tags else "—"),
        "📝 یادداشت: " + (customer.crm_notes if customer.crm_notes else "—"),
    ]
    if customer.is_blocked:
        lines.append(CRM_BLOCKED_BADGE)
    if orders:
        lines.append("\nآخرین سفارش‌ها:")
        for index, order in enumerate(orders, start=1):
            what = order.product_name or ("مشاوره" if order.type == "consultation" else "سفارش")
            quantity = f" ×{order.quantity}" if order.quantity and order.quantity > 1 else ""
            value = f" — {format_toman(order.value_toman)}" if order.value_toman else ""
            lines.append(f"{index}. {order_status_label(order.status)} — {what}{quantity}{value} — {_crm_date(order.created_at)}")
    else:
        lines.append("\nهنوز سفارشی ثبت نکرده.")
    return "\n".join(lines)


def crm_broadcast_ask(label: str, count: int) -> str:
    return f"متنِ پیامی که می‌خوای برایِ {count} مشتریِ بخشِ «{label}» بفرستی رو بنویس:"


# --- خلاصه‌یِ هوشمند ---
CRM_SUMMARY_NO_FUNDS = "موجودیِ کیف‌پولت برایِ این کار کافی نیست. اول کیف‌پولت رو شارژ کن."
CRM_SUMMARY_RATE_LIMITED = "الان خیلی پشتِ‌هم خلاصه خواستی؛ چند دقیقه‌ی دیگه دوباره امتحان کن."
CRM_SUMMARY_BUSY = "خلاصه‌یِ این مشتری همین الان در حالِ ساخته‌شدنه؛ چند لحظه صبر کن."
CRM_SUMMARY_WORKING = "🧠 در حالِ ساختنِ خلاصه..."
CRM_SUMMARY_NO_CONVERSATION = (
    "از این مشتری هنوز مکالمه‌ای ثبت نشده (یا مکالمه‌هایِ قدیمی پاک شدن)، پس چیزی برایِ خلاصه‌کردن نیست. هزینه‌ای کسر نشد."
)
CRM_SUMMARY_EMPTY_REPLY = "هوش مصنوعی جوابِ قابلِ استفاده‌ای نداد. هزینه‌ای کسر نشد؛ دوباره امتحان کن."


def crm_summary_confirm_text(estimated_cost: int) -> str:
    return (
        "🧠 خلاصه‌یِ هوشمندِ این مشتری از روی آخرین ~۳۰ پیامِ مکالمه و آمارِ سفارش‌هاش ساخته می‌شه "
        "(فقط برایِ خودت؛ به مشتری چیزی نمی‌رسه).\n"
        f"💳 هزینه: حدودِ {format_toman(estimated_cost)} از کیف‌پولت، و فقط اگه موفق بشه کسر می‌شه.\n\nادامه بدم؟"
    )


def crm_summary_result(summary: str, cost: int) -> str:
    return f"🧠 خلاصه‌یِ هوشمند:\n\n{summary}\n\n💳 هزینه‌یِ این خلاصه: {format_toman(cost)}"


# =============================================================================
# فازِ ۴-د — دستیارِ مدیریتی (فقط‌خواندنی)
# =============================================================================
ASSISTANT_END_BUTTON = "🔚 پایان"
ASSISTANT_END_TEXT = "گفتگو با دستیارِ مدیریتی تموم شد."
ASSISTANT_NO_FUNDS = "موجودیِ کیف‌پولت برایِ این پرسش کافی نیست. اول کیف‌پولت رو شارژ کن."
ASSISTANT_RATE_LIMITED = "الان خیلی پشتِ‌هم پرسیدی؛ چند دقیقه‌ی دیگه دوباره امتحان کن."
ASSISTANT_TOO_LONG = "پرسشت خیلی طولانیه (حداکثر ۱۰۰۰ حرف). کوتاه‌ترش کن."
ASSISTANT_EMPTY_REPLY = "نتونستم جوابِ قابلِ استفاده‌ای بسازم. هزینه‌ای کسر نشد؛ دوباره امتحان کن."


def assistant_intro(estimated_cost: int) -> str:
    return (
        "💬 دستیارِ مدیریتی فعال شد. درباره‌یِ فروشگاهت بپرس؛ گزارشِ فروش، محصولِ پرفروش، وضعیتِ سفارش‌ها و مشتری‌ها.\n\n"
        "🔒 دستیار فقط می‌خونه و گزارش می‌ده؛ هیچ تغییری توی فروشگاهت نمی‌ده و اطلاعاتِ شخصیِ مشتری‌ها "
        "(نام، شماره، متنِ گفتگو) رو نمی‌بینه.\n"
        f"💳 هر پرسش حدودِ {format_toman(estimated_cost)} از کیف‌پولت کم می‌کنه (فقط اگه جواب بده).\n"
        "برایِ پایان «🔚 پایان» رو بزن."
    )


# =============================================================================
# فازِ ۶-الف — تنظیماتِ رباتِ فروشگاه (مدتِ تجمیعِ پیام‌ها)
# =============================================================================
SHOP_SETTINGS_BUTTON = "⚙️ تنظیماتِ ربات فروشگاه"
BATCH_SECONDS_ASK = "مدتِ تجمیعِ پیام‌ها رو به ثانیه بنویس (عددِ ۲ تا ۶۰). برایِ انصراف /cancel رو بزن."
BATCH_SECONDS_INVALID = "عدد نامعتبره. یه عددِ صحیح بینِ ۲ تا ۶۰ بنویس."
BATCH_SECONDS_SAVED = "✅ ذخیره شد."
BATCH_SECONDS_RESET = "↩️ به پیش‌فرضِ سیستم برگشت."
SHOP_SETTINGS_STALE = "این دکمه دیگه معتبر نیست. دوباره «⚙️ تنظیماتِ ربات فروشگاه» رو بزن."
BATCH_PRESETS = ((3, "⚡ ۳ ثانیه"), (8, "⚖️ ۸ ثانیه"), (15, "💰 ۱۵ ثانیه"), (30, "🐢 ۳۰ ثانیه"))

# ------------------------------------------------------------------ P18 · A5: مهلت‌ها و حافظه (per-shop)
ADMIN_SETTING_REMOVED = (
    "این تنظیم دیگر از پنلِ مدیرِ پلتفرم انجام نمی‌شود. "
    "اگر مربوط به خودِ فروشگاه است، در «⚙️ تنظیماتِ ربات فروشگاه › ⏱ مهلت‌ها و حافظه» پیدایش می‌کنی."
)
SHOP_PREFS_BUTTON = "⏱ مهلت‌ها و حافظه"
SHOP_PREFS_STALE = "این تنظیم شناخته‌شده نیست. دوباره «⚙️ تنظیماتِ ربات فروشگاه» رو بزن."
SHOP_PREF_SAVED = "✅ ذخیره شد."
SHOP_PREF_RESET_DONE = "↩️ به پیش‌فرضِ سراسری برگشت."
SHOP_PREF_RESET_BUTTON = "↩️ پیش‌فرضِ سراسری"
SHOP_PREF_CUSTOM_BUTTON = "✍️ مقدارِ دلخواه"
SHOP_PREF_BACK_BUTTON = "↩️ برگشت"

# برچسب / یکا / توضیحِ یک‌خطی. کلیدها با ستون‌هایِ `ShopBot` در `shop_prefs_service` یکی‌اند.
SHOP_PREF_LABELS = {
    "payment_reservation_minutes": (
        "⏱ رزروِ مبلغِ پرداخت",
        "دقیقه",
        "وقتی پرداختِ شارژِ کیف‌پول را با کارت‌به‌کارت شروع می‌کنی، همین‌قدر دقیقه همان مبلغ برای خودت رزرو می‌ماند.",
    ),
    "order_reservation_minutes": (
        "📦 رزروِ موجودیِ سفارش",
        "دقیقه",
        "بعد از ساخته‌شدنِ سفارش، موجودیِ محصول همین‌قدر دقیقه برای همان سفارش نگه داشته می‌شود و بعد آزاد می‌گردد.",
    ),
    "order_confirmation_timeout_minutes": (
        "⏳ مهلتِ تاییدِ مشتری",
        "دقیقه",
        "اگر مشتری سفارشِ تشخیص‌داده‌شده را همین‌قدر دقیقه تایید نکند، آن سفارش خودکار لغو می‌شود.",
    ),
    "conversation_retention_days": (
        "🧹 نگهداریِ گفتگو",
        "روز",
        "پیام‌های گفتگو بعد از این چند روز خودکار پاک می‌شوند. عدد ۰ یعنی هیچ‌وقت پاک نشوند.",
    ),
    "knowledge_items_limit": (
        "📚 حافظه‌ی کانالِ دانش",
        "پست",
        "حداکثر چند پستِ آخرِ کانالِ دانش‌افزایی به‌عنوان حافظه به هوش مصنوعی داده شود.",
    ),
}


def shop_prefs_text(shop_bot, admin_settings, prefs) -> str:
    from app.services import shop_prefs_service

    lines = [f"{SHOP_PREFS_BUTTON} — فقط برایِ همین فروشگاه", ""]
    for pref in prefs:
        label, unit, _help = SHOP_PREF_LABELS[pref.key]
        effective = shop_prefs_service.resolve(pref, shop_bot, admin_settings)
        origin = "خودت" if getattr(shop_bot, pref.key, None) is not None else "پیش‌فرضِ سراسری"
        lines.append(f"• {label}: {effective} {unit} ({origin})")
    lines.append("")
    lines.append("روی هر کدام بزن تا عوضش کنی. این‌ها سراسری نیستند و رویِ بقیه‌یِ فروشگاه‌ها اثر ندارند.")
    return "\n".join(lines)


def shop_pref_text(shop_bot, admin_settings, pref) -> str:
    from app.services import shop_prefs_service

    label, unit, help_text = SHOP_PREF_LABELS[pref.key]
    stored = getattr(shop_bot, pref.key, None)
    effective = shop_prefs_service.resolve(pref, shop_bot, admin_settings)
    origin = f"مقدارِ خودت: {stored} {unit}" if stored is not None else "هنوز تنظیم نکرده‌ای ⇒ پیش‌فرضِ سراسری"
    return (
        f"{label}\n\n"
        f"اثرِ فعلی: {effective} {unit}\n"
        f"{origin}\n"
        f"بازه‌یِ مجاز: {pref.low} تا {pref.high} {unit}\n\n"
        f"{help_text}"
    )


def shop_pref_ask(pref) -> str:
    _label, unit, _help = SHOP_PREF_LABELS[pref.key]
    return f"عددِ دلخواه را به {unit} بنویس ({pref.low} تا {pref.high}). برایِ انصراف /cancel رو بزن."


def shop_pref_invalid(pref) -> str:
    _label, unit, _help = SHOP_PREF_LABELS[pref.key]
    return f"عدد نامعتبره. یه عددِ صحیح بینِ {pref.low} تا {pref.high} {unit} بنویس."


# ------------------------------------------------------------------ P18 · B9: گام‌هایِ پیش‌فرضِ چک‌اوت
CHECKOUT_STEPS_BUTTON = "🧾 گام‌هایِ پیش‌فرضِ چک‌اوت"
CHECKOUT_STEP_LABELS = {
    "name": "👤 نامِ تحویل‌گیرنده",
    "phone": "📱 شماره‌یِ موبایل",
    "address": "🏠 آدرسِ تحویل",
    "shipping": "🚚 روشِ ارسال",
    "note": "📝 توضیحِ سفارش",
}
CHECKOUT_STEP_ON = "⛔️ خاموش‌کردن"
CHECKOUT_STEP_OFF = "✅ روشن‌کردن"
CHECKOUT_STEP_QUESTION_BUTTON = "✏️ متنِ پرسش"
CHECKOUT_STEPS_BACK_BUTTON = "↩️ برگشت"
CHECKOUT_STEPS_SAVED = "✅ ذخیره شد."
CHECKOUT_STEPS_STALE = "این دکمه دیگه معتبر نیست. دوباره از «🛒 سوال‌هایِ چک‌اوتِ سبد» شروع کن."
CHECKOUT_STEPS_GUARD = "🚫 آدرس و موبایل را نمی‌توانی هم‌زمان خاموش کنی؛ سفارش باید راهی برایِ تحویل داشته باشد."
CHECKOUT_STEP_QUESTION_ASK = (
    "متنِ پرسش را بنویس (حداکثر ۱۵۰ نویسه). برایِ برگشت به متنِ پیش‌فرض بنویس «خالی». برایِ انصراف /cancel رو بزن."
)
CHECKOUT_STEP_QUESTION_TOO_LONG = (
    "متنِ پرسش نباید بیشتر از ۱۵۰ نویسه باشه. کوتاه‌ترش کن یا «خالی» بنویس تا متنِ پیش‌فرض برگردد."
)
CHECKOUT_STEP_PHYSICAL_HINT = "🧾 این گام فقط وقتی در چک‌اوت می‌آید که سبد کالایِ فیزیکی داشته باشد."
CHECKOUT_SHIPPING_HINT = (
    "🧾 گامِ «روشِ ارسال» علاوه بر کالایِ فیزیکی، دستکم یک روشِ ارسالِ فعال هم لازم دارد. "
    "از «📦 محصولات › روش‌هایِ ارسال» بسازیش."
)


def checkout_steps_text(steps) -> str:
    """صفحه‌یِ گام‌هایِ چک‌اوت: وضعیتِ هر گام + اینکه آیا واقعاً در چک‌اوت ظاهر می‌شود."""
    from app.services import checkout_config_service

    lines = ["🧾 گام‌هایِ پیش‌فرضِ چک‌اوت — فقط برایِ همین فروشگاه", ""]
    for key in checkout_config_service.STEP_KEYS:
        step = steps[key]
        label = CHECKOUT_STEP_LABELS[key]
        state = "روشن" if step.enabled else "خاموش"
        marks = []
        if key in ("address", "shipping"):
            marks.append("فقط برایِ کالایِ فیزیکی")
        if step.question != checkout_config_service.DEFAULT_QUESTIONS[key]:
            marks.append("متنِ خودت")
        tail = f" ({' · '.join(marks)})" if marks else ""
        lines.append(f"• {label}: {state}{tail}")
    lines.append("")
    lines.append("گامی که خاموش باشد از مشتری پرسیده نمی‌شود و در سفارش هم ثبت نمی‌شود.")
    lines.append(CHECKOUT_STEP_PHYSICAL_HINT)
    return "\n".join(lines)


def checkout_step_text(steps, key) -> str:
    """جزئیاتِ یک گام: وضعیت، متنِ پرسشِ فعلی و متنِ پیش‌فرض."""
    from app.services import checkout_config_service

    step = steps[key]
    default = checkout_config_service.DEFAULT_QUESTIONS[key]
    label = CHECKOUT_STEP_LABELS[key]
    return (
        f"{label}\n\n"
        f"وضعیت: {'🟢 روشن' if step.enabled else '⛔️ خاموش'}\n\n"
        f"متنِ پرسش از مشتری:\n{step.question}\n"
        f"متنِ پیش‌فرض:\n{default}\n\n"
        f"بیشترین طولِ متن: {checkout_config_service.MAX_QUESTION_LENGTH} نویسه"
    )

# ------------------------------------------------------------------ P18 · B5: زمانِ گزارشِ دوره‌ای
REPORT_WEEKDAY_NAMES = ("شنبه", "یکشنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه")
REPORT_HOUR_PRESETS = ((9, "🌅 ۰۹:۰۰"), (13, "🕐 ۱۳:۰۰"), (18, "🌆 ۱۸:۰۰"), (21, "🌙 ۲۱:۰۰"))
REPORT_HOUR_ASK = "ساعتِ گزارش رو به وقتِ تهران بنویس (عددِ ۰ تا ۲۳). برایِ انصراف /cancel رو بزن."
REPORT_HOUR_INVALID = "ساعت نامعتبره. یه عددِ صحیح بینِ ۰ تا ۲۳ بنویس."
REPORT_SCHEDULE_SAVED = "✅ زمانِ گزارش ذخیره شد."


def shop_settings_text(shop_bot, default_seconds: int) -> str:
    current = shop_bot.message_batch_seconds
    current_line = f"{current} ثانیه" if current else f"{default_seconds} ثانیه (پیش‌فرضِ سیستم)"
    names = REPORT_WEEKDAY_NAMES
    report_line = (
        f"{names[int(shop_bot.weekly_report_weekday) % len(names)]} ساعتِ {int(shop_bot.weekly_report_hour):02d}:00"
        if shop_bot.weekly_report_enabled
        else "خاموش"
    )
    return (
        "⚙️ تنظیماتِ رباتِ فروشگاه\n\n"
        f"⏱ مدتِ تجمیعِ پیام‌ها: {current_line}\n"
        f"📈 گزارشِ دوره‌ای: {report_line}\n\n"
        "مشتری‌ها معمولاً یه جمله رو توی چند پیامِ پشتِ‌هم می‌فرستن. رباتت بعد از آخرین پیام این‌قدر صبر می‌کنه، "
        "همه‌یِ پیام‌ها رو یه‌جا می‌خونه و یک جواب می‌ده.\n"
        "• عددِ کوچک‌تر ⚡ جوابِ سریع‌تر، ولی احتمالِ چند جوابِ پشتِ‌هم و مصرفِ توکنِ بیشتر.\n"
        "• عددِ بزرگ‌تر 💰 پیام‌هایِ بیشتری یکی می‌شن و توکنِ کمتری مصرف می‌شه (هزینه‌یِ کم‌تر از کیف‌پولت)، "
        "ولی جوابِ ربات دیرتر میاد.\n"
        "توصیه: فروشگاهِ پرمکالمه ۸ تا ۱۵ ثانیه؛ پشتیبانیِ سریع ۳ تا ۵ ثانیه."
    )


def report_schedule_text(shop_bot) -> str:
    names = REPORT_WEEKDAY_NAMES
    day = names[int(shop_bot.weekly_report_weekday) % len(names)]
    state = "🟢 روشن" if shop_bot.weekly_report_enabled else "⛔️ خاموش"
    return (
        "📈 گزارشِ دوره‌ای\n\n"
        f"وضعیت: {state}\n"
        f"روزِ هفته: {day}\n"
        f"ساعت: {int(shop_bot.weekly_report_hour):02d}:00 (به وقتِ تهران)\n\n"
        "ربات هر هفته دقیقاً یک‌بار، سرِ همین روز و ساعت، خلاصه‌یِ فروش و فعالیتِ فروشگاهت رو برات می‌فرسته.\n"
        "اگه ربات سرِ اون لحظه خاموش باشه، اولین باری که بالا بیاد همون گزارشِ عقب‌افتاده رو یک‌بار می‌فرسته."
    )


# =============================================================================
# فازِ ۱ · P1-S3 (B2): محصولِ فیزیکی/دیجیتال + روش‌هایِ ارسال
# =============================================================================
DIGITAL_DELIVERY_LABELS = {
    "file": "📎 فایل",
    "link": "🔗 لینک",
    "text": "📝 متن",
    "code_pool": "🔑 کدِ یکتا (لایسنس/اکانت)",
}
DG_ONLY_SALES = "افزودنِ محصولِ دیجیتال فقط در مودِ «فروشگاهی» ممکنه."
DG_STALE = "این دکمه دیگه معتبر نیست. دوباره «💾 افزودنِ محصولِ دیجیتال» رو بزن."
DG_ASK_NAME = "💾 نامِ محصولِ دیجیتال رو بنویس:"
DG_ASK_MODE = (
    "روشِ تحویل بعد از تاییدِ سفارش چی باشه؟\n\n"
    "📎 فایل — همون فایل برایِ هر خرید فرستاده می‌شه (تا ۲۰ مگابایت)\n"
    "🔗 لینک — لینکِ دانلود/دسترسی\n"
    "📝 متن — یه متنِ ثابت (راهنما، آدرس و مانندِ آن)\n"
    "🔑 کدِ یکتا — هر خرید یکی از کدهایی که وارد می‌کنی (لایسنس یا اکانت)؛ تموم بشه محصول ناموجود می‌شه"
)
DG_ASK_FILE = "فایلِ محصول رو به‌صورتِ «فایل» (Document) بفرست. حداکثر ۲۰ مگابایت؛ فایلِ بزرگ‌تر رو از روشِ «لینک» استفاده کن."
DG_NEED_DOCUMENT = "لطفاً فایل رو به‌صورتِ «فایل/Document» بفرست (نه متن)."
DG_FILE_TOO_BIG = "این فایل بزرگ‌تر از ۲۰ مگابایته و ربات نمی‌تونه بفرستدش. از روشِ «لینک» استفاده کن."
DG_ASK_LINK = "لینکِ دانلود/دسترسی رو بفرست (با http:// یا https:// شروع بشه، بدونِ فاصله):"
DG_INVALID_LINK = "لینک معتبر نیست. باید با http:// یا https:// شروع بشه و فاصله نداشته باشه."
DG_ASK_TEXT = "متنی که بعد از تاییدِ سفارش به مشتری فرستاده می‌شه رو بنویس:"
DG_ASK_INSTRUCTIONS = "راهنمایِ استفاده برایِ مشتری رو بنویس. اختیاریه."
DG_ASK_MAX_DOWNLOADS = (
    "مشتری حداکثر چند بار می‌تونه محصول رو دریافت کنه؟ (ارسالِ اول هم جزوِ این عدد حساب می‌شه)\n"
    "اگه محدودیتی نمی‌خوای «⏭ رد کردن» رو بزن."
)
DG_INVALID_MAX = "یه عددِ صحیحِ بزرگ‌تر از صفر بنویس."
DG_ASK_CODES = (
    "کدها رو بفرست: هر خط یه کد (یا یه فایلِ txt با همین قالب). کدِ تکراری نادیده گرفته می‌شه.\n"
    "می‌تونی «⏭ رد کردن» رو بزنی و بعداً از «✏️ ویرایش ← 🔑 افزودنِ کد» اضافه کنی (تا وقتی کد نداری محصول ناموجوده)."
)
DG_CODES_BAD_FILE = "فایلِ کدها باید txt و کمتر از ۱ مگابایت باشه (یا کدها رو مستقیم تایپ کن)."
DG_CODES_EMPTY = "هیچ کدِ معتبری پیدا نشد. هر خط یه کد (حداکثر ۲۵۵ حرف) بفرست."
EDIT_NOT_FOR_KIND = "این گزینه برایِ این نوع محصول نیست."
ASK_NEW_WEIGHT = "وزنِ محصول رو به گرم بنویس (برایِ حذف «رد شدن»):"
INVALID_WEIGHT = "وزن باید یه عددِ صحیح (گرم) باشه. دوباره بنویس یا «رد شدن» بزن."
ASK_NEW_DELIVERY_NOTE = "زمانِ تحویل/ارسال رو بنویس (برایِ حذف «رد شدن»):"
ASK_NEW_RETURN_POLICY = "شرایطِ مرجوعی رو بنویس (برایِ حذف «رد شدن»):"
ASK_NEW_PRODUCT_AI = "دستورِ اختصاصیِ AI برایِ این محصول رو بنویس (کوتاه؛ برایِ حذف «رد شدن»):"
ASK_NEW_DG_LINK = "لینکِ جدید رو بفرست (http:// یا https://):"
ASK_NEW_DG_INSTRUCTIONS = "راهنما/متنِ جدید رو بنویس (برایِ حذف «رد شدن»؛ برایِ محصولِ «متن» نمی‌شه خالی بمونه):"
ASK_NEW_DG_MAX = "سقفِ دفعاتِ دریافت رو (عدد) بنویس یا «رد شدن» برایِ نامحدود:"
ASK_NEW_DG_FILE = "فایلِ جدید رو به‌صورتِ «فایل» بفرست (تا ۲۰ مگابایت):"
ASK_NEW_DG_CODES = "کدهایِ تازه رو بفرست (هر خط یه کد، یا فایلِ txt):"
DG_TEXT_CANNOT_BE_EMPTY = "متنِ تحویل نمی‌تونه خالی باشه."


def digital_product_added(name: str, delivery: str, codes_added: int | None = None) -> str:
    label = DIGITAL_DELIVERY_LABELS.get(delivery, delivery)
    line = f"✅ محصولِ دیجیتالِ «{name}» اضافه شد ({label})."
    if delivery == "code_pool":
        line += f"\n🔑 {codes_added or 0} کد در استخر هست."
        if not codes_added:
            line += " تا کد اضافه نکنی محصول ناموجوده."
    return line


def dg_codes_result(added: int, duplicates: int, ignored: int, available: int) -> str:
    lines = [f"✅ {added} کدِ جدید اضافه شد. موجودیِ فعلی: {available} کد."]
    if duplicates:
        lines.append(f"♻️ {duplicates} کدِ تکراری نادیده گرفته شد.")
    if ignored:
        lines.append(f"⚠️ {ignored} خط (تکراری/بیش‌ازحد بلند/خارج از سقفِ ۵۰۰۰تایی) نادیده گرفته شد.")
    return "\n".join(lines)


def digital_delivery_owner_note(status: str) -> str:
    return {
        "delivered": "💾 محصولِ دیجیتال به مشتری تحویل داده شد ✅",
        "insufficient": "⚠️ کدِ کافی برایِ تحویلِ این سفارش نیست. بعد از افزودنِ کد («✏️ ویرایش ← 🔑 افزودنِ کد») خودکار تحویل می‌شه.",
        "send_failed": "⚠️ ارسالِ محصولِ دیجیتال به مشتری ناموفق بود (شاید رباتِ فروشگاه رو بلاک کرده). تحویل ثبت شده؛ با مشتری هماهنگ کن.",
        "already": "💾 این سفارشِ دیجیتال قبلاً تحویل داده شده بود.",
    }.get(status, "")


def digital_pending_delivered_note(delivered: int, still_waiting: int) -> str:
    lines = []
    if delivered:
        lines.append(f"📬 {delivered} سفارشِ منتظر هم الان تحویل داده شد.")
    if still_waiting:
        lines.append(f"⏳ {still_waiting} سفارش هنوز منتظرِ کدِ بیشتره.")
    return "\n".join(lines)


def product_kind_lines(product) -> list[str]:
    """خط‌هایِ اضافه‌یِ صفحه‌یِ جزئیاتِ محصول؛ فیزیکیِ بدونِ فیلدِ اضافه = لیستِ خالی (خروجیِ قبلی دست‌نخورده)."""
    lines: list[str] = []
    if product.kind == "digital":
        lines.append(f"💾 دیجیتال — تحویل: {DIGITAL_DELIVERY_LABELS.get(product.digital_delivery or '', '؟')}")
        if product.digital_delivery == "link" and product.digital_link:
            lines.append(f"🔗 {product.digital_link}")
        if product.digital_delivery == "file" and product.digital_file_name:
            lines.append(f"📎 {product.digital_file_name}")
        if product.digital_max_downloads is not None:
            lines.append(f"📥 سقفِ دریافت: {product.digital_max_downloads} بار")
    else:
        if product.weight_grams is not None:
            lines.append(f"⚖️ وزن: {product.weight_grams} گرم")
        if product.delivery_note:
            lines.append(f"🚚 تحویل: {product.delivery_note}")
        if product.return_policy:
            lines.append(f"↩️ مرجوعی: {product.return_policy}")
    if product.ai_instructions:
        lines.append("🤖 دستورِ AI ثبت شده")
    return lines


# --- روش‌هایِ ارسال ---
SHIP_NONE = "هنوز روشِ ارسالی تعریف نکردی."
SHIP_STALE = "این دکمه دیگه معتبر نیست."
SHIP_LIMIT_REACHED = "به سقفِ ۱۰ روشِ ارسال رسیدی؛ اول یکی رو حذف کن."
ASK_SHIP_NAME = "نامِ روشِ ارسال رو بنویس:"
INVALID_SHIP_NAME = "نام باید ۱ تا ۶۴ حرف باشه."
ASK_SHIP_FEE = "هزینه‌یِ ارسال رو به تومان بنویس (برایِ رایگان «۰» بنویس):"
INVALID_SHIP_FEE = "یه عددِ صحیح (۰ یا بیشتر) بنویس."
ASK_SHIP_FREE_OVER = "ارسال از چه مبلغِ خریدی به بالا رایگان باشه؟ (تومان). اگه نمی‌خوای «⏭ رد کردن» رو بزن."
ASK_SHIP_ETA = "زمانِ تقریبیِ رسیدن رو بنویس. اگه نمی‌خوای «⏭ رد کردن» رو بزن."
SHIP_HINT = "ℹ️ هزینه‌یِ ارسال فقط برایِ کالایِ فیزیکی حساب می‌شه؛ سبدِ فقط‌دیجیتال ارسال نداره."


def shipping_list_text(methods) -> str:
    if not methods:
        # B8: هشدارِ روشن درباره‌یِ پیامدِ نبودِ روشِ ارسال (چک‌اوتِ فیزیکی بدونِ هزینه‌یِ ارسال ادامه می‌یابد).
        return (
            f"⚠️ روشِ ارسال تعریف نکرده‌ای\n\n{SHIP_NONE}\n"
            "در نتیجه سفارشِ کالایِ فیزیکی بدونِ هزینه‌یِ ارسال ثبت می‌شود و در هر سفارش هم به تو هشدار می‌دهیم.\n\n"
            f"{SHIP_HINT}"
        )
    lines = ["🚚 روش‌هایِ ارسال\n"]
    for method in methods:
        state = "✅" if method.is_active else "⏸"
        fee = "رایگان" if method.fee_toman == 0 else format_toman(method.fee_toman)
        extra = f" · رایگان بالایِ {format_toman(method.free_over_toman)}" if method.free_over_toman is not None else ""
        eta = f" · {method.eta_text}" if method.eta_text else ""
        lines.append(f"{state} {method.name} — {fee}{extra}{eta}")
    lines.append(f"\n{SHIP_HINT}")
    return "\n".join(lines)


def shipping_added(name: str) -> str:
    return f"✅ روشِ ارسالِ «{name}» اضافه شد."


# =============================================================================
# W2 — عملیاتِ گروهیِ سفارش (C4/C9/D5)
# =============================================================================
ORDER_REJECT_REASONS = (
    "موجودیِ کالا تموم شده",
    "اطلاعاتِ سفارش ناقص یا نادرسته",
    "امکانِ ارسال به آدرسِ مشتری نیست",
    "پرداخت تایید نشد",
)
ORDER_OPS_STALE = "این سفارش پیدا نشد یا دیگه به این عملیات نیاز نداره."
ORDER_OPS_ILLEGAL = "در وضعیتِ فعلیِ سفارش این کار مجاز نیست (شاید قبلاً انجام شده)."
ORDER_OPS_DONE_SUFFIX = "✅ وضعیتِ سفارش: {label}"
ORDER_ASK_REJECT_REASON = "دلیلِ ردِ سفارش رو انتخاب کن (مشتری همین رو می‌بینه):"
ORDER_ASK_REJECT_TEXT = "دلیل رو بنویس (حداکثر ۳۰۰ حرف). با /cancel منصرف شو."
ORDER_ASK_TRACKING_CODE = "کدِ رهگیری مرسوله رو بنویس (می‌تونی با «-» بدونِ کد بفرستی):"
ORDER_TRACKING_TOO_LONG = "کدِ رهگیری خیلی طولانیه (حداکثر ۱۰۰ حرف)."
ORDER_ASK_DIRECT_MESSAGE = "پیامت رو برایِ مشتری بنویس (حداکثر ۱۰۰۰ حرف). از رباتِ فروشگاه با برچسبِ «پیام از فروشگاه» می‌ره. /cancel = انصراف"
ORDER_DIRECT_TOO_LONG = "پیام خیلی طولانیه (حداکثر ۱۰۰۰ حرف)."
ORDER_DIRECT_SENT = "✅ پیام برایِ مشتری فرستاده شد."
ORDER_DIRECT_BLOCKED = "⚠️ پیام نرسید: مشتری رباتِ فروشگاهت رو مسدود کرده (یا ربات در دسترس نیست)."
ORDER_OPS_CANCELLED = "انصراف داده شد."
ORDER_CUSTOMER_NOTIFY_FAILED = "⚠️ وضعیت عوض شد ولی پیامش به مشتری نرسید (احتمالاً رباتِ فروشگاه رو مسدود کرده)."
ORDER_REFUND_GUIDE = (
    "↩️ استرداد ثبت شد. وجه رو خودت (کارت‌به‌کارت/روشِ پرداختِ مشتری) برگردون و بعد دکمه‌یِ "
    "«✅ استرداد انجام شد» رو بزن تا مشتری مطلع بشه."
)


def order_cancelled_by_customer_notification(rows, customer) -> str:
    from app.bots.shop_bot.texts import order_code

    return f"🚫 مشتری ({display_user(customer, 'short')}) سفارشِ {order_code(rows)} رو قبل از پرداخت لغو کرد؛ رزروِ موجودی آزاد شد."


# =============================================================================
# W3 — روش‌هایِ پرداختِ مشتری + تصمیم رویِ رسید (C5/C6)
# =============================================================================
RECEIPT_REJECT_REASONS = (
    "مبلغِ رسید با سفارش نمی‌خونه",
    "رسیدِ نامعتبر یا ناخوانا",
    "رسیدِ تکراری",
    "واریز در حسابم ننشسته",
)
PAYS_STALE = "این پرداخت پیدا نشد یا دیگه به این عملیات نیاز نداره."
PAYS_ILLEGAL = "در وضعیتِ فعلیِ پرداخت این کار مجاز نیست (شاید قبلاً تصمیم گرفته شده)."
PAYS_ASK_REJECT_REASON = "دلیلِ ردِ رسید رو انتخاب کن (مشتری همین رو می‌بینه):"
PAYS_ASK_REJECT_TEXT = "دلیل رو بنویس (حداکثر ۳۰۰ حرف). /cancel = انصراف"
PAYS_APPROVED_SUFFIX = "✅ پرداخت تایید شد و سفارش «پرداخت‌شده» است."
PAYS_REJECTED_SUFFIX = "❌ رسید رد شد؛ مشتری خبردار شد."
PAYS_CUSTOMER_NOTIFY_FAILED = "⚠️ تصمیم ثبت شد ولی پیام به مشتری نرسید (احتمالاً رباتِ فروشگاه رو مسدود کرده)."
PAYS_DONE = "ثبت شد."
PAYS_SAVED = "✅ ذخیره شد."
PAYS_INVALID_CARD = "شماره‌کارتِ معتبرِ ۱۶رقمی بفرست (فاصله/ارقامِ فارسی مشکلی نداره)."
PAYS_ASK_CARD_NUMBER = "شماره‌کارتِ ۱۶رقمیِ فروشگاه رو بفرست (برایِ مشتری نمایش داده می‌شه):"
PAYS_ASK_CARD_HOLDER = "نامِ صاحبِ کارت رو بنویس (برایِ رد کردن «-»):"
PAYS_ASK_CARD_BANK = "نامِ بانک رو بنویس (برایِ رد کردن «-»):"
PAYS_ASK_DEADLINE = "مهلتِ پرداخت (دقیقه) رو بفرست — بینِ ۵ و ۱۴۴۰. موجودی دقیقاً همین‌قدر رزرو می‌مونه:"
PAYS_ASK_HOLD = "مهلتِ بررسیِ رسید (دقیقه) — بینِ ۶۰ و ۴۳۲۰. بعد از ارسالِ رسید موجودی تا این مدت رزرو می‌مونه:"
PAYS_INVALID_NUMBER = "عددِ معتبر در بازه‌یِ مجاز بفرست."
PAYS_ASK_ZARINPAL = "مرچنت‌کدِ ۳۶نویسه‌ایِ زرین‌پالِ خودت رو بفرست (برایِ حذف «حذف»):"
PAYS_INVALID_MERCHANT = "مرچنت‌کد باید ۳۶ نویسه باشه (حروفِ انگلیسی/عدد/خط‌تیره)."
PAYS_NEEDS_SALES_MODE = "این بخش فقط برایِ فروشگاهِ فروشگاهی است."


def payments_menu_text(row, shop_bot, bale_missing=()) -> str:
    """`bale_missing` نتیجه‌یِ `bale_credentials_service.shop_status` است تا وضعیتِ نشان‌داده‌شده به فروشگاه‌دار
    دقیقاً همان چیزی باشد که مشتری تجربه می‌کند (B11: هرگز «✅ روشن» در حالی که مسیرِ مشتری بسته است)."""
    from app.services import bale_credentials_service as bale_creds
    from app.services import payment_settings_service as pss

    def flag(value) -> str:
        return "✅ روشن" if value else "⛔️ خاموش"

    card_number = pss.get_card_number(row)
    own_token = bool(shop_bot.bale_provider_token)
    using_global_provider = not own_token and bale_creds.MISSING_PROVIDER_TOKEN not in tuple(bale_missing)
    bale_line = (
        f"بله‌پی: {flag(not bale_missing)} — توکنِ درگاهِ فروشگاه: {'تنظیم شده' if own_token else 'تنظیم نشده'}"
        f"{' (توکنِ سراسریِ مدیر استفاده می‌شود)' if using_global_provider else ''}"
        f" — مهلت: {row.bale_deadline_minutes} دقیقه"
    )
    lines = [
        "💳 روش‌هایِ پرداختِ مشتری",
        "",
        f"کارت‌به‌کارت: {flag(row.card_enabled and bool(card_number))} — کارت: {pss.mask_card(card_number)} — مهلت: {row.card_deadline_minutes} دقیقه — نگهداریِ بررسیِ رسید: {row.receipt_review_hold_minutes} دقیقه",
        bale_line,
        f"زرین‌پال: {flag(row.zarinpal_enabled and bool(row.zarinpal_merchant_id_enc))} — مرچنت: {'تنظیم شده' if row.zarinpal_merchant_id_enc else 'تنظیم نشده'} — مهلت: {row.zarinpal_deadline_minutes} دقیقه",
        f"پرداختِ دستی/هماهنگی: {flag(row.manual_enabled)}",
        f"تاییدِ خودکارِ پرداختِ آنلاین: {flag(row.auto_accept_online)}",
        "",
        "اگه هیچ روشِ آنلاین/کارتی فعال نباشه، سفارش‌ها مثلِ قبل مستقیم برایِ تاییدِ دستیِ تو می‌آن.",
    ]
    if bale_missing:
        lines += ["", "⚠️ بله‌پی برایِ مشتری فعال نیست:"]
        lines += bale_missing_lines(bale_missing)
    return "\n".join(lines)


def receipt_submitted_notification(rows, payment, customer, total_toman: int) -> str:
    from app.bots.shop_bot.texts import order_code
    from app.utils.validators import format_toman

    lines = [
        f"🧾 رسیدِ کارت‌به‌کارت — سفارش {order_code(rows)}",
        f"مشتری: {display_user(customer, 'short')}",
        f"مبلغِ سفارش: {format_toman(total_toman)}",
        f"تلاشِ شماره‌یِ {payment.attempt_no}",
    ]
    if payment.tracking_ref:
        lines.append(f"شماره‌پیگیری: {payment.tracking_ref}")
    if getattr(payment, "receipt_text", None):
        lines.append(f"📝 متنِ رسید (از طرفِ مشتری):\n{payment.receipt_text[:700]}")
    if payment.flags:
        notes = {"dup_file": "فایل/متنِ رسید قبلاً هم ارسال شده", "dup_tracking": "شماره‌پیگیری قبلاً هم ثبت شده"}
        lines.append("⚠️ " + "؛ ".join(notes.get(f, f) for f in payment.flags.split(",")))
    lines.append("\nتصمیم با توئه؛ تایید یا رد کن:")
    return "\n".join(lines)


# =============================================================================
# W5 · 2.1/2.2 — حدودِ مهلت، تاییدِ دیرهنگام، هشدارِ بررسیِ رسید، برگشتِ موجودی
# =============================================================================
def pays_ask_deadline(low: int, high: int) -> str:
    return f"مهلتِ پرداخت (دقیقه) رو بفرست — بینِ {low} و {high}. موجودی دقیقاً همین‌قدر رزرو می‌مونه:"


def pays_ask_hold(low: int, high: int) -> str:
    return f"مهلتِ بررسیِ رسید (دقیقه) — بینِ {low} و {high}. بعد از ارسالِ رسید موجودی تا این مدت رزرو می‌مونه:"


def pays_range_hint(low: int, high: int, unit: str) -> str:
    return f"بازه‌یِ مجاز: {low} تا {high} {unit}"


PAYS_LATE_APPROVED_SUFFIX = "⏰ مهلتِ این سفارش تموم شده بود؛ با تاییدِ تو دوباره رزرو و «پرداخت‌شده» شد."
PAYS_LATE_OVERSOLD_SUFFIX = "⚠️ موجودیِ بعضی اقلام دیگه کافی نیست (فروشِ بیشتر از موجودی). با مشتری هماهنگ کن یا استرداد بده."


def receipt_review_warning(code: str, hours_left: float) -> str:
    return (
        f"⏰ رسیدِ سفارشِ {code} هنوز بررسی نشده و حدودِ {max(1, round(hours_left))} ساعتِ دیگه مهلتش تموم می‌شه "
        "(بعدش سفارش منقضی و موجودی آزاد می‌شه؛ البته بعدش هم می‌تونی با تایید دوباره فعالش کنی). لطفاً تایید یا رد کن."
    )


ORDER_RESTOCK_BUTTON = "📦 برگردانِ موجودی به انبار"
ORDER_RESTOCKED = "📦 موجودیِ اقلامِ این سفارش به انبار برگشت."
ORDER_RESTOCK_NOTHING = "چیزی برایِ برگشت به انبار نبود (محصولِ بدونِ موجودی یا قبلاً برگشته)."
ADMIN_ASK_WALLET_COST_RECEIPT_ANALYSIS = "هزینه‌یِ هر بار تحلیلِ هوشمندِ رسید (مشورتی)، به تومان چقدر باشه؟"
