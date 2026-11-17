from __future__ import annotations

import datetime

from app.services.identity_service import display_name, display_user
from app.utils.text_limits import clip
from app.utils.validators import fa_grouped, fa_number, fa_percent, fa_text, format_phone_display, format_toman

# =============================================================================
# عمومی
# =============================================================================
GENERIC_ERROR = "متاسفانه یه خطای غیرمنتظره پیش اومد. لطفاً دوباره امتحان کن."
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

# =============================================================================
# P19: رباتِ بله‌یِ خودِ فروشگاه (هوشمندسازی روی بله، با همان هزینه‌ها)
# =============================================================================
BALE_SHOP_BOT_BUTTON = "🟢 هوشمندسازیِ بله"
ASK_BALE_SHOP_BOT_TOKEN = (
    "توکنِ رباتِ بله‌ات را بفرست (همان چیزی که از @BaleBotFather می‌گیری).\n"
    "از این به بعد مشتری‌هایِ بله‌ای مثلِ تلگرام با رباتِ هوشمندیِ خودت حرف می‌زنن، سفارش می‌دن و پرداخت می‌کنن.\n\n"
    "هزینه‌یِ هر پاسخ دقیقاً مثلِ تلگرام از کیف‌پولِ همان فروشگاه کم می‌شود.\n"
    "برایِ انصراف /cancel رو بفرست."
)
INVALID_BALE_SHOP_BOT_TOKEN = "این توکن معتبر نیست یا نتونستم به سرویسِ بله وصل بشم. دوباره بررسی و بفرست."
BALE_SHOP_BOT_ALREADY_USED = "این رباتِ بله قبلاً به فروشگاهِ دیگری وصل شده. از @BaleBotFather یک رباتِ تازه بساز."
BALE_SHOP_BOT_SAVED = "✅ رباتِ بله‌ی شما وصل شد و از این به بعد پیام‌هایِ بله‌ای را جواب می‌دهد."
BALE_SHOP_BOT_REMOVED = "✅ اتصالِ بله حذف شد. رباتِ تلگرامت دست‌نخورده سرِ جاش است."
BALE_SHOP_BOT_ENABLED_AGAIN = "✅ هوشمندسازیِ بله روشن شد؛ رباتِ بله‌ات از این به بعد مثلِ تلگرام جواب می‌دهد."
BALE_SMARTEN_TURNED_OFF = "⏸ هوشمندسازیِ بله خاموش شد؛ توکن جایش می‌ماند و اگر توکنِ درگاه هم داشته باشی، پرداختِ بله‌پی همان‌طور کار می‌کند."
BALE_SHOP_BOT_NO_TRANSPORT = "اتصالِ بله همین الان فعال نیست (توکن مرده یا برنامه تازه بالا آمده). در پاسِ بعدی تلاش می‌شود."
BALE_SHOP_BOT_UNAVAILABLE = "این قابلیت فعلاً برایِ فروشگاهِ شما باز نیست. برایِ اطلاعاتِ بیشتر با پشتیبانیِ پلتفرم در تماس باش."
BALE_SHOP_BOT_TOKEN_INVALID_FORMAT = "توکن باید یک رشته‌یِ بدونِ فاصله و دست‌کم ۲۰ نویسه باشد."
# P36 → P39: پیشنهادِ اتصالِ بله درست بعد ازِ وصل‌شدنِ رباتِ تلگرام (همان خواستهٔ «علاوه بر توکنِ
# تلگرام، توکنِ رباتِ بله را هم بفرستم»). P39: هیچ دکمهٔ تازه‌ای ندارد — توکن همین‌جا در همان
# جریانِ «ثبتِ توکن» نوشته می‌شود و «بعداً» آن را می‌بندد (درخواستِ مالکِ محصول).
# P36 → P39 → P42: پیشنهادِ اتصالِ بله درست بعد ازِ وصل‌شدنِ رباتِ تلگرام. P42 (مواردِ ۱ و ۲۹):
# این دیگر «دکمهٔ سبزِ جدا» در منو نیست؛ همان‌جا در بخشِ «ثبتِ توکن» پرسیده می‌شود و هیچ اشاره‌ای
# به «پرداختِ آنلاینِ سفارش‌ها» ندارد — توکنِ رباتِ بله برایِ *هوشمندسازی* است، نه پرداخت.
BALE_SMARTEN_OFFER = (
    "🔵 رباتِ تلگرام وصل شد.\n\n"
    "اگر می‌خواهی همین رباتِ هوشمند رویِ بله هم باشد، توکنِ رباتِ بله‌ات را (که از @BaleBotFather "
    "گرفتی) همین‌جا بفرست: مشتری‌هایِ بله‌ای همان گفت‌وگو و سفارش را دارند و هزینه‌یِ هر پاسخ از "
    "همان کیف‌پولِ فروشگاه کم می‌شود.\n\n"
    "اگر فعلاً نمی‌خواهی «بعداً» بنویس. هر وقت خواستی از «🔑 ثبت/ویرایش توکن ربات» › «🟢 هوشمندسازیِ "
    "بله» می‌توانی توکنِ بله را بگذاری."
)
BALE_SMARTEN_SKIP_WORDS = ("بعداً", "بعدا", "رد", "نه", "انصراف", "بی‌خیال", "بیخیال")
BALE_SMARTEN_POSTPONED = (
    "باشه، هوشمندسازیِ بله برایِ الان ول شد. هر وقت خواستی از «🔑 ثبت/ویرایش توکن ربات» › «🟢 "
    "هوشمندسازیِ بله» روشنش کن."
)
BALE_SMARTEN_RELEASED = (
    "چیزی که فرستادی شبیهِ توکن نبود، پس سراغِ همان منویِ قبلی می‌رویم. هر وقت خواستی توکنِ "
    "رباتِ بله را از «🔑 ثبت/ویرایش توکن ربات» › «🟢 هوشمندسازیِ بله» بگذار."
)
# P42 · موردِ ۲: توکنی که در صفحهٔ «پرداختِ آنلاینِ سفارش‌ها» نوشته می‌شود فقط برایِ بله‌پی است
# و هرگز نباید رباتِ بله را هوشمند کند.
BALE_TOKEN_SAVED_FOR_PAY_ONLY = (
    "✅ توکنِ رباتِ بله ذخیره شد — فقط برایِ پرداختِ بله‌پی.\n"
    "رباتِ بله‌ات به مشتری‌ها پاسخِ هوشمند نمی‌دهد (هوشمندسازی روشن نشد). اگر آن را هم می‌خواهی، "
    "از «🔑 ثبت/ویرایش توکن ربات» › «🟢 هوشمندسازیِ بله» روشنش کن."
)
# P42 · موردِ ۱: بخشِ «ثبت/ویرایش توکن ربات» خودِ انتخاب را می‌پرسد (بدونِ دکمهٔ تازه در منو).
SHOP_BOT_TOKEN_CHOICE_TEXT = (
    "یکه توکنِ رباتت را انتخاب کن:\n\n"
    "• «🤖 رباتِ تلگرام» — همان توکنی که از @BotFather می‌گیری.\n"
    "• «🟢 هوشمندسازیِ بله» — توکنِ رباتِ بله از @BaleBotFather؛ با آن، همین رباتِ هوشمند رویِ "
    "بله هم فعال می‌شود."
)
# رونمایی/پنهان‌کردنِ ویژگی از پنلِ ادمین
BALE_SHOP_BOTS_REVEALED = "🟢 ویژگی رونمایی شد؛ «🟢 هوشمندسازیِ بله» در «🔑 ثبت/ویرایش توکن ربات» ظاهر شد و {count} فروشگاهِ آماده وصل شدند."
BALE_SHOP_BOTS_HIDDEN = "🙈 ویژگی دوباره پنهان شد. گزینه از «🔑 ثبت/ویرایش توکن ربات» حذف شد و هیچ هوشمندسازیِ بله‌ای باز نیست."


def bale_shop_bot_status_text(shop_bot, status=None) -> str:
    """P19 → P42: صفحهٔ «هوشمندسازیِ بله» — فقط توکنِ *رباتِ بله* و سوییچِ هوشمندسازی.

    P42 (مواردِ ۱ و ۲): پرداختِ بله‌پی مقصدِ دیگری دارد («💳 پرداختِ آنلاینِ سفارش‌ها» + توکنِ
    درگاهِ خودِ فروشگاه)؛ این‌جا تنها چیزی که روشن/خاموش می‌شود «پاسخِ هوشمند به مشتریِ بله‌ای»
    است، پس متن‌هایِ «پول کجا می‌نشیند» حذف شده‌اند تا دو مسیرِ بله دوباره قاتی نشوند.
    """
    from app.services import bale_bot_service

    has_bot = bale_bot_service.has_token(shop_bot)
    bot_label = f"@{shop_bot.bale_bot_username}" if shop_bot.bale_bot_username else "—"
    if not has_bot:
        connection = "—"
    elif shop_bot.bale_bot_enabled:
        connection = "روشن ✅"
    else:
        connection = "خاموش ⏸ (فقط پرداخت)"
    lines = [
        "🟢 رباتِ بله‌یِ فروشگاه — هوشمندسازی",
        "",
        f"توکنِ رباتِ بله: {bale_bot_service.token_masked(shop_bot)}",
        f"ربات: {bot_label} · هوشمندسازی: {connection}",
        "",
    ]
    if not has_bot:
        lines.append(
            "هنوز توکنِ رباتِ بله را ثبت نکردی. «🔑 توکنِ ربات بله» را بزن و توکنی که از "
            "@BaleBotFather گرفتی را بفرست."
        )
    elif shop_bot.bale_bot_enabled:
        lines.append("✅ رباتِ بله‌ات مثلِ تلگرام به مشتری‌ها پاسخِ هوشمند می‌دهد، سفارش می‌گیرد و پرداخت می‌کند.")
    else:
        lines.append(
            "⏸ توکن ثبت شده اما هوشمندسازی روشن نیست: رباتِ بله‌ات به پیامِ مشتری پاسخِ هوشمند "
            "نمی‌دهد و فقط برایِ پرداختِ بله‌پی کار می‌کند. با «✅ روشن‌کردنِ هوشمندسازیِ بله» روشنش کن."
        )
    lines += [
        "",
        "مشتری‌ها می‌تونن در بله همین ربات را پیدا کنند و مثلِ تلگرام با آن چت کنند، سفارش بدهند و پرداخت کنند.",
        "هزینه‌یِ هر پاسخ از کیف‌پولِ همین فروشگاه کم می‌شود (دقیقاً مثلِ تلگرام) و موجودیِ مشترک است.",
    ]
    if status is not None and not status.available:
        lines += ["", "⚠️ بله‌پی برایِ مشتریِ تو فعلاً فعال نیست:"]
        lines += bale_missing_lines(status.missing)
    return "\n".join(lines)


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
PRODUCT_SKIP_STALE = "این دکمه دیگه معتبر نیست. دوباره «➕ افزودن محصول جدید» رو بزن."



def product_added_confirmation(name: str) -> str:
    return f"✅ محصول «{name}» با موفقیت اضافه شد."


def product_detail_text(product) -> str:
    lines = [f"🏷 {product.name}", f"💰 {format_toman(product.price_toman)}"]
    category = getattr(product, "category", "") or ""
    if category:
        # فقط وقتی دسته نوشته شده این خط می‌آید ⇒ کارتِ محصولاتِ بی‌دسته بایت‌به‌بایت مثلِ قبل است.
        lines.append(f"🗂 دسته: {category}")
    if product.stock_quantity is not None:
        stock_line = "ناموجود" if product.stock_quantity <= 0 else f"{fa_number(product.stock_quantity)} عدد"
        lines.append(f"📦 موجودی: {stock_line}")
    lines.extend(product_kind_lines(product))
    if product.description:
        lines.append(f"\n{product.description}")
    return "\n".join(lines)


# پ۷۴ · خواستهٔ مالک: دسته‌بندیِ محصولات در مودِ فروشگاهی (پنلِ خودِ فروشگاه + کاتالوگِ مشتری).
CATEGORY_BUTTON = "🗂 دسته‌بندیِ محصولات"
CATEGORY_ASSIGN_BUTTON = "🗂 دستهٔ این محصول"
ASK_PRODUCT_CATEGORY = (
    "نامِ دسته را بنویس (مثلاً «پیراشکی» یا «نوشیدنی»). اگر چیزی ننویسی یا «خالی» بنویسی، این محصول "
    "بی‌دسته می‌ماند. حداکثر ۶۴ نویسه؛ دسته‌ای که بنویسی تازه باشد خودش ساخته می‌شود."
)
ASK_NEW_CATEGORY_NAME = "نامِ تازهٔ دسته را بنویس (همان دسته با این نام نشان داده می‌شود):"
CATEGORY_SAVED = "🗂 دستهٔ این محصول «{value}» شد."
CATEGORY_REMOVED = "🗂 این محصول از دسته‌بندی بیرون آمد (بی‌دسته شد)."
CATEGORY_RENAMED = "✏️ دستهٔ «{old}» به «{new}» تغییر نام یافت ({count} محصول)."
CATEGORY_CLEARED = "🗂 دسته از {count} محصول برداشته شد؛ خودِ محصولات حذف نشده‌اند."
CATEGORY_STALE = "این دسته دیگر در فهرست نیست؛ از «🗂 دسته‌بندیِ محصولات» دوباره باز کن."
CATEGORY_CONFIRM_CLEAR = (
    "مطمئنی می‌خوای دستهٔ «{name}» را از همهٔ این محصولات برداری؟ خودِ محصولات می‌مانند و فقط "
    "بی‌دسته می‌شوند."
)
CATEGORY_UNASSIGNED_STALE = "این محصول دیگر در فهرستِ بی‌دسته‌ها نیست؛ صفحه را تازه کن."
CATEGORY_EMPTY_SHOP = (
    "🗂 دسته‌بندیِ محصولات — فعلاً هیچ دسته‌ای نساخته‌ای.\n\n"
    "رویِ هر محصول که بروی دکمهٔ «🗂 دستهٔ این محصول» را می‌بینی؛ نامِ دسته را همان‌جا بنویس تا "
    "خودش ساخته شود. مشتری بعد ازِ آن در «🛍 محصولات» رباتِ تو می‌تواند دسته‌به‌دسته بگردد."
)
CATEGORY_UNCATEGORY_COUNT = "📦 محصولاتِ بی‌دسته: {count}"
CATEGORY_NO_UNCATEGORY = "📦 همهٔ محصولاتِ فعالِ تو دسته دارند."


def category_overview_text(categories: list[tuple[str, int]], unassigned: int, total: int) -> str:
    lines = [
        f"🗂 دسته‌بندیِ محصولات — {fa_number(len(categories))} دسته · "
        f"{fa_number(total - unassigned)} محصول دسته‌دار از {fa_number(total)}"
    ]
    if not categories:
        return CATEGORY_EMPTY_SHOP
    lines.append("")
    lines.extend(f"• {name} — {fa_number(count)} محصول" for name, count in categories)
    lines.append("")
    lines.append(CATEGORY_UNCATEGORY_COUNT.format(count=fa_number(unassigned)) if unassigned else CATEGORY_NO_UNCATEGORY)
    lines.append("")
    lines.append("با زدنِ هر دسته می‌توانی نامش را عوض کنی، محصولاتِ بی‌دسته را به آن اضافه کنی، یا دسته را از همه برداری.")
    return "\n".join(lines)


def category_view_text(name: str, products: list) -> str:
    lines = [f"🗂 {name} — {fa_number(len(products))} محصول", ""]
    lines.extend(f"• {clip(product.name, 40)} — {format_toman(product.price_toman)}" for product in products)
    if not products:
        lines.append("فعلاً محصولِ فعالی در این دسته نیست.")
    return "\n".join(lines)


def category_unassigned_text(products: list) -> str:
    lines = [f"📦 محصولاتِ بی‌دسته — {fa_number(len(products))}", ""]
    lines.append("رویِ هرکدام بزن تا دسته‌اش را بنویسی (دسته‌ای که تازه باشد خودش ساخته می‌شود).")
    return "\n".join(lines)


def category_assigned_bulk_text(name: str, product_name: str) -> str:
    return f"🗂 «{clip(product_name, 40)}» به دستهٔ «{name}» اضافه شد."


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
    return f"این فایل بیش از {fa_number(max_rows)} ردیف داره. لطفاً فایل رو به چند بخشِ کوچیک‌تر تقسیم کن و هر بخش رو جدا بفرست."


def _format_error_block(errors: list[str]) -> list[str]:
    shown = errors[:_PRODUCT_IMPORT_ERROR_DISPLAY_CAP]
    lines = [f"• {e}" for e in shown]
    remaining = len(errors) - len(shown)
    if remaining > 0:
        lines.append(f"...و {fa_number(remaining)} موردِ دیگه.")
    return lines


def product_import_no_valid_rows(errors: list[str]) -> str:
    lines = ["❌ هیچ ردیفِ معتبری توی فایل پیدا نشد."]
    if errors:
        lines.append("مشکلات:")
        lines.extend(_format_error_block(errors))
    lines.append("\nفایل رو اصلاح کن و دوباره بفرست.")
    return "\n".join(lines)


def product_import_preview(valid_count: int, errors: list[str]) -> str:
    lines = ["📊 بررسیِ فایل تموم شد.", f"✅ {fa_number(valid_count)} ردیفِ معتبر آماده‌ی افزودنه."]
    if errors:
        lines.append(f"\n⚠️ {fa_number(len(errors))} ردیف مشکل داشت و اضافه نمی‌شه:")
        lines.extend(_format_error_block(errors))
    lines.append(f"\nمی‌خوای همین {fa_number(valid_count)} محصولِ معتبر اضافه بشه؟")
    return "\n".join(lines)


def product_import_result_toast(count: int) -> str:
    return f"✅ {fa_number(count)} محصول با موفقیت اضافه شد."


# =============================================================================
# دستور هوشمندسازی و پیش‌نمایش (مرحله ۶)


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


WALLET_LOT_DISPLAY_LIMIT = 6  # حداکثرِ خط‌هایِ انقضا در صفحهٔ کیف‌پول (بقیه جمع بسته می‌شود)


def wallet_status_text(
    balance_toman: int,
    *,
    usable_toman: int | None = None,
    lots=(),
) -> str:
    """P20 → P39: موجودی، «چقدرش قابلِ خرج است» و انقضایِ *هر شارژ* جدا.

    باگِ ۴ (درخواستِ مالکِ محصول): پیش‌تر یک خطِ «تا ۳۰ روزِ دیگر» می‌گفت حتی وقتی شارژِ اولِ
    کاربر پنج روزِ دیگر می‌رفت. مصرف FIFO است، پس «ماندهٔ هر شارژ + روزهایِ باقی‌ماندهٔ همان
    شارژ» تنها نمایشِ درستی است که کاربر می‌تواند رویش حساب باز کند.
    """
    lines = [f"موجودیِ فعلیِ کیف‌پولت: {format_toman(balance_toman)}"]
    if usable_toman is not None and usable_toman < balance_toman:
        held = balance_toman - usable_toman
        lines.append(
            f"قابلِ استفاده برایِ شروعِ کارِ تازه: {format_toman(max(usable_toman, 0))} "
            f"({format_toman(held)} به‌خاطرِ کمیسیونِ سفارش‌هایِ باز در انتظار است)"
        )
    shown = [lot for lot in lots if lot.remaining_toman > 0]
    if shown:
        from app.utils.jalali import format_jalali_date

        lines += ["", "⏳ شارژها به ترتیبِ مصرف (اولِ همه قدیمی‌ترین):"]
        for lot in shown[:WALLET_LOT_DISPLAY_LIMIT]:
            when = f"{fa_number(lot.days_left)} روزِ دیگر" if lot.days_left > 0 else "امروز منقضی می‌شود"
            lines.append(f"• {format_toman(lot.remaining_toman)} — {when} · {format_jalali_date(lot.expires_at)}")
        rest = shown[WALLET_LOT_DISPLAY_LIMIT:]
        if rest:
            total = sum(lot.remaining_toman for lot in rest)
            last = rest[-1]
            lines.append(
                f"• و {fa_number(len(rest))} شارژِ دیگر — جمعِ {format_toman(total)} "
                f"(دیرترینِ انقضا: {fa_number(last.days_left)} روزِ دیگر)"
            )
    return "\n".join(lines)


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
    "receipt_analysis": "تحلیلِ رسید",
    "commission": "کمیسیونِ سفارش",
}

WALLET_HISTORY_EMPTY = "هنوز هیچ تراکنشی در کیف‌پولت ثبت نشده."
WALLET_HISTORY_INTRO = "تاریخچهٔ تراکنش‌های کیف‌پول، از جدیدترین به قدیمی‌ترین:"
WALLET_HISTORY_PAGE_EMPTY = "در این بخش تراکنشی وجود ندارد؛ از دکمهٔ ابتدای تاریخچه استفاده کن."
WALLET_HISTORY_INVALID = "این دکمه معتبر نیست؛ تاریخچهٔ کیف‌پول را دوباره باز کن."
WALLET_HISTORY_UNAVAILABLE = "برای دیدن تاریخچه، ابتدا وارد پنلِ فروشگاهت شو."
WALLET_HISTORY_NEWER = "تراکنش‌های جدیدتر"
WALLET_HISTORY_OLDER = "تراکنش‌های قدیمی‌تر"
WALLET_HISTORY_START = "ابتدای تاریخچه"
WALLET_HISTORY_EXPORT = "دریافت فایلِ تاریخچه"
WALLET_HISTORY_EXPORT_NEXT = "دریافت ادامهٔ فایل"
WALLET_HISTORY_EXPORT_SCOPE = "فقط تراکنش‌های کیف‌پولِ خودت، از جدیدترین به قدیمی‌ترین."
WALLET_HISTORY_EXPORT_CONTINUATION = "ادامهٔ تراکنش‌های قدیمی‌تر؛ ردیف‌های فایل‌های قبلی در این فایل نیستند."


def wallet_history_export_note(count: int, *, has_more: bool, continuation: bool = False) -> str:
    if not count:
        return "در این بخش تراکنشی وجود ندارد."
    if has_more:
        return "این فایل همهٔ تاریخچه نیست؛ تراکنش‌های قدیمی‌تر را با دکمهٔ دریافت ادامهٔ فایل بگیر."
    if continuation:
        return "این بخش به پایانِ تاریخچه رسید؛ تراکنش‌های جدیدتر در فایل‌های قبلی هستند."
    return "این فایل همهٔ تراکنش‌های موجود هنگام تهیه را در بر دارد."


def wallet_history_export_caption(count: int, *, has_more: bool, continuation: bool = False) -> str:
    lines = [WALLET_HISTORY_EXPORT_SCOPE, f"تعدادِ تراکنش‌های این فایل: {fa_number(count)}"]
    if continuation:
        lines.append(WALLET_HISTORY_EXPORT_CONTINUATION)
    lines.append(wallet_history_export_note(count, has_more=has_more, continuation=continuation))
    return "\n".join(lines)


def wallet_reason_label(reason) -> str:
    reason_value = reason.value if hasattr(reason, "value") else reason
    return _WALLET_REASON_LABELS.get(reason_value, "سایر تراکنش‌ها")


def wallet_transaction_line(transaction) -> str:
    from app.utils.jalali import format_jalali_datetime

    label = wallet_reason_label(transaction.reason)
    sign = "+" if transaction.amount_toman >= 0 else ""
    when = format_jalali_datetime(transaction.created_at) if transaction.created_at else "—"
    return f"{label}: {sign}{format_toman(transaction.amount_toman)} — {when}"


TOPUP_AMOUNT_PRESETS_TOMAN = [50_000, 100_000, 300_000, 500_000]


def topup_amount_button_label(amount_toman: int) -> str:
    return format_toman(amount_toman)


def topup_presets_for(minimum_toman: int) -> list[int]:
    """پیش‌فرض‌هایی که واقعاً از حداقلِ پلتفرم بالا هستند (اگر ادمین حداقل را ۲۰۰ هزار بگذارد، ۵۰ هزار نباید دیده شود)."""
    return [amount for amount in TOPUP_AMOUNT_PRESETS_TOMAN if amount >= minimum_toman]


ASK_TOPUP_AMOUNT = "می‌خوای چقدر شارژ کنی؟"


def custom_topup_prompt(minimum_toman: int) -> str:
    return f"مبلغِ موردنظرت رو به تومان بنویس (حداقل {format_toman(minimum_toman)}):"


def invalid_topup_amount(minimum_toman: int) -> str:
    return f"لطفاً فقط عدد بنویس (به تومان) و دستِ‌کم {format_toman(minimum_toman)} باشه."


INVALID_TOPUP_AMOUNT_FALLBACK = "این مبلغ قابلِ خواندن نبود 🙏 دوباره انتخاب کن."


def topup_below_minimum_toast(minimum_toman: int) -> str:
    return f"حداقلِ شارژِ کیف‌پول {format_toman(minimum_toman)} است."


ASK_DISCOUNT_CODE = "اگه کد تخفیف داری بفرست، وگرنه روی «⏭ رد شدن از کد تخفیف» بزن."
# P35: `validate_code` چهار علتِ رد دارد؛ متنِ قبلی سه‌تا را می‌گفت و «سقفِ استفاده» را نه،
# پس فروشگاه‌دار با کدی که واقعاً موجود است هم گیج می‌شد.
INVALID_DISCOUNT_CODE = (
    "این کد تخفیف کار نمی‌کند. یکی از این‌ها:\n"
    "• کد وجود ندارد، غیرفعال است یا منقضی شده\n"
    "• سقفِ تعدادِ استفاده‌اش پر شده\n"
    "• با همین کد قبلاً خرید کرده‌ای (هر کد برایِ هر فروشگاه یک‌بار قابلِ استفاده است)\n"
    "دوباره امتحان کن یا «⏭ رد شدن از کد تخفیف» را بزن."
)


def discount_applied_text(discount, final_price: int, base_price: int | None = None) -> str:
    """P35: درصدِ واقعیِ کد گفته می‌شود، نه فقط «اعمال شد».

    پنلِ ادمین از P25 فقط کدِ *درصدی* می‌سازد، ولی ردیف‌هایِ `FIXED` قدیمی ممکن است در دیتابیس
    باشند و `apply_discount` هر دو نوع را مصرف می‌کند ⇒ متن هم باید هر دو را درست بگوید.
    """
    kind = getattr(getattr(discount, "type", None), "value", getattr(discount, "type", None))
    try:
        value = float(getattr(discount, "value", 0) or 0)
    except (TypeError, ValueError):
        value = 0.0
    label = f"{_percent_label(value)} تخفیف" if kind == "percent" else f"{format_toman(int(value))} تخفیف"
    saved = ""
    if base_price:
        difference = max(0, int(base_price) - int(final_price))
        if difference:
            saved = f" — {format_toman(difference)} کم شد"
    return f"✅ کد «{discount.code}» اعمال شد ({label}{saved}).\nمبلغ نهایی: {format_toman(final_price)}"


ASK_PAYMENT_METHOD = "روش پرداخت رو انتخاب کن:"

ASK_COST_CALC_VOLUME = "روزانه حدوداً چند پیام از مشتری‌ها انتظار داری؟ (یه تخمینِ کلی کافیه)"

_COST_CALC_DAILY_ESTIMATES = {"low": 15, "medium": 60, "high": 300, "very_high": 700}


def cost_calc_result_text(volume_key: str, cost_per_message_toman: int) -> str:
    """موردِ ۶: پیشنهادِ «برایِ خیالِ راحت دو‌برابر شارژ کن» برداشته شد (درخواستِ صریحِ مالکِ
    محصول) و منبعِ عدد رویِ همان چیزی قرار گرفت که واقعاً مصرف می‌شود: قیمتِ هر پیامِ متنی از
    فرمولِ پنلِ ادمین و شمارشِ واقعیِ توکنِ خودِ فروشگاه. حرفه‌ای‌سازیِ کاملِ این تخمین (مبتنی بر
    پرامپتِ سیستمیِ فروشگاه و تجربهٔ ماه‌هایِ قبل) در گروهِ extra-high باقی مانده است."""
    daily = _COST_CALC_DAILY_ESTIMATES[volume_key]
    monthly_estimate = daily * 30 * cost_per_message_toman
    return (
        f"📊 با حدودِ {fa_number(daily)} پیامِ مشتری در روز، هزینه‌ی تقریبیِ ماهانه‌ت "
        f"حدودِ {format_toman(monthly_estimate)} خواهد بود.\n\n"
        "مبنایِ این عدد: قیمتِ هر هزارِ توکنِ تنظیم‌شده در پنلِ پلتفرم و میانگینِ طولِ پاسخ‌هایِ "
        "همین ربات. اگر تحلیلِ عکس یا رونویسیِ صدا هم داشته باشی، هزینه کمی بیشتر می‌شود؛ "
        "هزینه‌یِ واقعی از «📊 آمار» و «🧾 تاریخچه‌ی پرداخت» قابلِ مشاهده است."
    )


def card_to_card_payment_instructions(card_number: str, holder_name: str, amount: int) -> str:
    import html

    safe_card = html.escape(card_number)
    safe_name = html.escape(holder_name)
    return (
        "💳 لطفاً مبلغ دقیق زیر رو به شماره کارت زیر واریز کن:\n\n"
        f"شماره کارت: <code>{safe_card}</code>\n"
        f"به‌نام: {safe_name}\n"
        f"مبلغ دقیق: <code>{amount:,}</code> تومان\n\n"  # استثنایِ عمدی: رقمِ این بلوک باید برایِ «کپیِ مبلغ» لاتین بماند
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


RECEIPT_RECEIVED_PENDING_APPROVAL = "✅ رسیدت دریافت شد و برای بررسی به ادمین ارسال شد. بعد از تایید، بهت اطلاع می‌دیم."


def _duration_label(payment) -> str:
    """P42 · موردِ ۴: «مدت» فقط برایِ اشتراک معنا دارد؛ برایِ شارژِ کیف‌پول همان عدد
    «اعتبارِ هر شارژ» است (پیش از این ردیفِ شارژ «None ماه» نشان می‌داد)."""
    from app.database.models import PaymentPurpose

    months = getattr(payment, "duration_months", None)
    if months is None:
        return "—"
    if getattr(payment, "purpose", None) == PaymentPurpose.WALLET_TOPUP:
        return f"اعتبارِ شارژ: {fa_number(months)} ماه"
    return f"مدت: {fa_number(months)} ماه"


def admin_new_payment_notification(payment, owner) -> str:
    owner_name = display_user(owner, "full")
    lines = [
        "🧾 درخواست پرداخت جدید:\n",
        f"فروشگاه‌دار: {owner_name}",
        _duration_label(payment),
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
BALE_PAY_BOT_IDLE = (
    "🤖 این ربات، «رباتِ پرداخت» سرویسِ کسب‌وکار هوشمند است.\n"
    "برایِ پرداخت، لینکِ پرداخت را از رباتِ فروشگاه یا از «💰 کیف‌پول» رباتِ اصلی بزن — همان لینک "
    "این چت را باز می‌کند و صورتحسابِ بله همین‌جا می‌آید. این‌جا چیزی برایِ نوشتن نیست؛ اگر "
    "سوالی داری با پشتیبانیِ سرویس در تماس باش."
)
BALE_PAY_BOT_NOT_CONNECTED = (
    "🔵 پرداخت با بله‌پی فعلاً ممکن نیست: رباتِ پرداختِ بله هنوز شناخته نشده (نامِ کاربری‌اش از "
    "بله خوانده نشد). از «💳 کارت به کارت» یا زرین‌پال استفاده کن؛ مشکل معمولاً با یکِ «🧪 آزمایشِ "
    "بله‌پی» یا ذخیره‌یِ دوباره‌یِ توکنِ رباتِ بله حل می‌شود."
)


def bale_pay_handoff_text(amount_toman: int) -> str:
    """متنِ مرحلهٔ «برو به بله» — صادق دربارهٔ این‌که پرداخت کجا اتفاق می‌افتد."""
    return (
        f"💳 مبلغ: {format_toman(amount_toman)}\n"
        "بله هیچ آدرسِ پرداختِ وبی ندارد، پس این دکمه تو را در اپِ بله به چتِ رباتِ پرداخت می‌برد "
        "و صورتحسابِ خودِ بله همان‌جا می‌آید: دکمهٔ «پرداخت» را می‌زنی و با کیف‌پولِ بله تسویه "
        "می‌شود. بعد ازِ موفقیت، اعتبارِ تو خودکار شارژ می‌شود (نه دستی)."
    )
BALE_PAY_ERROR = "متأسفانه وصل‌شدن به بله‌پی ممکن نشد؛ بعداً دوباره امتحان کن یا از روشِ دیگری پرداخت کن."
# P26: پاسخِ `/start <payload>` وقتی صورتحسابی ساخته نمی‌شود. دو حالتِ جدا، چون راهِ‌حلِّ کاربر فرق
# دارد: لینکِ نامعتبر (از پنل دوباره «پرداخت» را بزن) و لینکِ درستِ تسویه‌شده (کاری نکن).
BALE_PAY_LINK_UNKNOWN = (
    "این لینکِ پرداخت را پیدا نکردم (منقضی شده). از پنلِ فروشگاه دوباره «پرداخت» را بزن تا لینکِ تازه بگیری."
)
BALE_PAY_ALREADY_SETTLED = (
    "این پرداخت قبلاً ثبت یا باطل شده است — چیزی از تو گرفته نمی‌شود. اگر مطمئن نیستی، وضعیتِ پرداختت را در همان رباتِ فروشگاه ببین."
)
# P34: دو حالتِ تازه که فقط با «رباتِ بلهٔ خودِ فروشگاه» ممکن می‌شود. در هر دو، صورتحساب ساخته
# نمی‌شود؛ چون فرستادنِ صورتحسابِ یک ربات با توکنِ درگاهِ رباتِ دیگر مقصدِ پول را عوض می‌کند.
BALE_PAY_LINK_STALE = (
    "این لینکِ پرداخت برایِ این ربات ساخته نشده، پس چیزی از تو گرفته نمی‌شود.\n"
    "به رباتِ فروشگاه برگرد و «پرداخت» را دوباره بزن تا لینکِ تازه بگیری."
)
BALE_PAY_NOT_CONFIGURED = (
    "این فروشگاه فعلاً پرداختِ بله‌پی ندارد (درگاه یا اتصالِ بله‌اش خاموش شده).\n"
    "به رباتِ فروشگاه برگرد و از «💳 کارت به کارت» یا پرداختِ دستی استفاده کن."
)
# P26: لینکِ پرداخت از «قالب» ساخته نمی‌شود، پس این پیام فقط یکِ علت دارد: پیامِ پرداخت در چت
# نشست (ردِ سمتِ تلگرام/بله). تراکنشی ساخته نشده و ردیفِ پرداخت هم باطل شده است.
BALE_PAY_LINK_SEND_FAILED = (
    "🔵 پیامِ پرداخت برایِ تو باز نشد (ارسالش از سمتِ ربات رد شد).\n"
    "تراکنشی ساخته نشده و این تلاشِ پرداخت باطل شد؛ هر وقت خواستی دوباره از «💰 کیف‌پول» امتحان کن، "
    "یا با «💳 کارت به کارت» / زرین‌پال پرداخت کن."
)
PAYMENT_FLOW_STALE = (
    "⏳ این مرحله از پرداخت تموم شده (مثلاً ربات ری‌استارت شده). «💰 کیف‌پول» را دوباره باز کن و "
    "از نو شروع کن؛ پرداخت‌هایِ بازِ تو از «📂 پرداخت‌هایِ باز» هم در دسترسن."
)
ZARINPAL_PAYMENT_SUCCESSFUL_PAGE = "پرداخت شما با موفقیت انجام شد ✅ می‌تونی به ربات تلگرام برگردی."
ZARINPAL_PAYMENT_FAILED_PAGE = "پرداخت ناموفق بود یا لغو شد ❌ می‌تونی به ربات تلگرام برگردی و دوباره امتحان کنی."


def payment_history_item(payment) -> str:
    from app.utils.jalali import format_jalali_date

    status = payment.status.value if hasattr(payment.status, "value") else payment.status
    status_labels = {"pending": "⏳ در انتظار بررسی", "approved": "✅ تایید شده", "rejected": "❌ رد شده"}
    return (
        f"{format_jalali_date(payment.created_at) if payment.created_at else '—'} — {_duration_label(payment)} — "
        f"{format_toman(payment.final_amount)} — {status_labels.get(status, status)}"
    )


PAYMENT_HISTORY_EMPTY = "هنوز هیچ پرداختی ثبت نکردی."


# =============================================================================
# آمار (مرحله ۹)
# =============================================================================
ADMIN_STATS_TITLE = "نمودارِ درآمدِ ماهانه"
ADMIN_STATS_12M_TITLE = "۱۲ ماهِ گذشته"
ADMIN_STATS_RANGE_TITLE = "بازهٔ دلخواه"
ADMIN_STATS_FROM_ASK = (
    "برایِ نمودارِ درآمد، تاریخِ شروع را بنویس (میلادی، به وقتِ گرینویچ):\n"
    "· نمونه: ۲۰۲۶-۰۱-۰۱ یا ۲۰۲۶-۰۱-۰۱ ۱۴:۰۰\n"
    "· برایِ بی‌حد بودنِ این سر بنویس «همه»\n"
    "· برایِ لغو «انصراف»"
)
ADMIN_STATS_TO_ASK = "حالا تاریخِ پایان را بنویس (همان قالب؛ «همه» یعنی تا همین لحظه)."
ADMIN_STATS_RANGE_SET = "✅ بازهٔ نمودار تنظیم شد."
ADMIN_STATS_RANGE_CLEARED = "↩️ بازهٔ دلخواه حذف شد؛ نمودار دوباره ۱۲ ماهِ گذشته را نشان می‌دهد."
ADMIN_STATS_INVALID_RANGE = "تاریخ را نفهمیدم. قالبِ درست: ۲۰۲۶-۰۱-۰۱ (یا ۲۰۲۶-۰۱-۰۱ ۱۴:۰۰) یا کلمهٔ «همه»."
ADMIN_STATS_CHART_BUTTON = "📈 نمودارِ ۱۲ ماهِ گذشته"
ADMIN_STATS_SUMMARY_BUTTON = "📊 خلاصهٔ کلِ دوره"
ADMIN_STATS_RANGE_BUTTON = "🗓 بازهٔ دلخواه"
ADMIN_STATS_RANGE_CLEAR_BUTTON = "✖️ حذفِ بازه"


def platform_revenue_chart_text(report: dict, *, title: str) -> str:
    """نمودارِ متنیِ درآمدِ ماهانه (موردِ ۴۴): تفکیکِ مشاوره/فروش + کمیسیون + نقدِ دریافتی.

    عمداً «نقدِ دریافتی» (شارژ و اشتراک) را جدا می‌نویسیم: آن پولی است که مشتریِ فروشگاهی
    به کیف‌پولش افزوده ولی هنوز مصرف نکرده، پس اگر با «فروشِ اعتبار» جمعش کنیم یکِ درآمدِ
    توهمی می‌سازیم. هر ستونِ نمودار یکِ ماهِ **جلالی** است.
    """
    from app.services.perf_report_service import sparkline
    from app.utils.validators import fa_grouped, fa_number

    totals = report.get("totals") or {}
    series = report.get("series") or []
    lines = [
        f"📈 {ADMIN_STATS_TITLE} — {title}",
        "",
        "جمعِ بازه:",
        f"🧠 فروشِ اعتبارِ هوش‌مصنوعی: {fa_grouped(totals.get('ai_total', 0))} تومان",
        f"   · 🛍 حالتِ فروش: {fa_grouped(totals.get('ai_sales', 0))} تومان",
        f"   · 💬 حالتِ مشاوره‌ای: {fa_grouped(totals.get('ai_consult', 0))} تومان",
        f"🧾 کمیسیونِ سفارش‌ها: {fa_grouped(totals.get('commission', 0))} تومان",
        f"💵 نقدِ دریافتی: شارژ {fa_grouped(totals.get('topup_cash', 0))} · اشتراک {fa_grouped(totals.get('subscription_cash', 0))} تومان",
        "   (این مبلغ هنوز مصرف نشده ⇒ با دو ردیفِ بالا جمعش نکن)",
        f"📦 سفارش و گفتگو: {fa_number(totals.get('orders', 0))} · 💬 پیامِ مشتری: {fa_number(totals.get('messages', 0))}",
    ]
    if not series:
        lines.append("\nدر این بازه هیچ رویدادی ثبت نشده است.")
        return "\n".join(lines)

    lines.append("")
    lines.append("نمودار (هر ستون = یکِ ماه):")
    for field, icon in (("ai_total", "🧠"), ("commission", "🧾"), ("topup_cash", "💵"), ("orders", "📦")):
        pairs = [(row["key"], row.get(field, 0)) for row in series]
        lines.append(f"{icon} {sparkline(pairs)}")
    lines.append("")
    lines.append("· " + " | ".join(f"{row['label']}: {fa_grouped(row.get('ai_total', 0))}" for row in series[-6:]))
    if len(series) > 6:
        lines.append(f"(فقط ۶ ماهِ آخر عددشان نوشته شده؛ ستون‌ها همه‌ی {fa_number(len(series))} ماه است)")
    return "\n".join(lines)


def shop_stats_text(stats: dict, consultation: bool = False) -> str:
    """C1: در مودِ مشاوره‌ای هیچ خطِ «سفارش» نمایش داده نمی‌شود؛ عددش هم برایِ مشاور معنایی ندارد."""
    title = "📊 آمار مخاطبان و مشاوره‌های تو:\n" if consultation else "📊 آمار فروشگاهت:\n"
    lines = [
        title,
        f"پیام‌های امروز: {fa_number(stats['messages_today'])}",
        f"پیام‌های هفته‌ی اخیر: {fa_number(stats['messages_week'])}",
        f"پیام‌های ماه اخیر: {fa_number(stats['messages_month'])}",
    ]
    if consultation:
        lines.append(f"\n💬 مشاوره‌ها: {fa_number(stats['consultations_count'])}")
    else:
        lines.append(f"\n🛒 سفارش‌ها: {fa_number(stats['orders_count'])}")
        lines.append(f"💬 مشاوره‌ها: {fa_number(stats['consultations_count'])}")
    if stats.get("success_rate") is not None:
        lines.append(f"\n✅ نرخ پاسخ‌گویی موفق: {fa_percent(stats['success_rate'], 1)}")
    if stats.get("top_products"):
        lines.append("\n🏆 پرطرفدارترین محصولات:")
        for name, count in stats["top_products"]:
            lines.append(f"  • {name} ({fa_number(count)} بار)")
    return "\n".join(lines)


def platform_stats_text(stats: dict) -> str:
    return (
        "📊 آمار سراسری پلتفرم:\n\n"
        f"👥 فروشگاه‌دارهای ثبت‌نام‌شده: {fa_number(stats['total_owners'])}\n"
        f"🤖 ربات‌های فعال: {fa_number(stats['total_active_bots'])}\n"
        f"💰 فروشگاه‌دارهای دارای موجودیِ کیف‌پول: {fa_number(stats['owners_with_wallet_balance'])}\n"
        f"💵 مجموع درآمد تاییدشده: {format_toman(stats['total_revenue_toman'])}\n"
        f"🛒 مجموع سفارش‌ها: {fa_number(stats['orders_count'])}\n"
        f"💬 مجموع مشاوره‌ها: {fa_number(stats['consultations_count'])}\n\n"
        "— اقتصادِ کیف‌پول —\n"
        f"📥 مجموع درآمدِ واقعی (شارژهای تاییدشده): {format_toman(stats['total_revenue_toman'])}\n"
        f"🎁 مجموعِ اعتبارِ رایگان (تراِیل/معرفی/هدیه): {format_toman(stats['total_given_away_toman'])}\n"
        f"🔥 مجموعِ اعتبارِ مصرف‌شده (هوش‌مصنوعی): {format_toman(stats['total_wallet_consumed_toman'])}\n"
        "(نکته: این هزینه‌ی واقعیِ ارزیِ ارائه‌دهنده‌ی هوش‌مصنوعی رو نشون نمی‌ده، فقط بر اساسِ قیمت‌گذاریِ خودِ پلتفرمه.)\n\n"
        "— درآمد به تفکیکِ منبع —\n"
        f"🧾 کمیسیونِ سفارش‌ها: {format_toman(stats['commission_revenue_toman'])}\n"
        f"🧠 فروشِ اعتبارِ هوش‌مصنوعی (API): {format_toman(stats['ai_api_revenue_toman'])}\n"
        f"🧮 جمعِ این دو: {format_toman(stats['commission_revenue_toman'] + stats['ai_api_revenue_toman'])}\n"
        "(این سه رقم *اعتبارِ مصرف‌شده* است، نه پولی که همین امروز نقد وارد شده؛ پولِ نقدی همان خطِ «درآمدِ واقعی» بالاست.)"
    )


PERF_RANGE_BUTTONS: tuple[tuple[str, str], ...] = (("24h", "🕐 ۲۴ ساعت"), ("7d", "📅 ۷ روز"))
PERF_FROM_ASK = (
    "برایِ گزارشِ همزمانی، تاریخِ شروع را بنویس (میلادی، به وقتِ گرینویچ):\n"
    "· نمونه: ۲۰۲۶-۱۱-۰۱ یا ۲۰۲۶-۱۱-۰۱ ۱۴:۰۰\n"
    "· تاریخِ شروع لازم است و باید در گذشته باشد؛ برایِ لغو «انصراف» بنویس."
)
PERF_TO_ASK = (
    "حالا تاریخِ پایان را بنویس (همان قالب؛ «همه» یعنی تا همین لحظه).\n"
    "پایان باید پس از شروع و حداکثر همین لحظه باشد؛ خودِ لحظهٔ پایان در بازه نیست.\n"
    "تاریخِ بدونِ ساعت یعنی ابتدایِ آن روز، نه پایانِ روز."
)
PERF_RANGE_INVALID = (
    "تاریخ را نفهمیدم یا ترتیبِ بازه درست نیست. قالبِ درست: ۲۰۲۶-۱۱-۰۱ یا ۲۰۲۶-۱۱-۰۱ ۱۴:۰۰.\n"
    "شروع باید در گذشته و پایان پس از شروع باشد؛ «همه» فقط برایِ پایان پذیرفته می‌شود."
)
PERF_RANGE_SET = "✅ بازهٔ گزارش تنظیم شد."
PERF_RANGE_CANCELLED = "↩️ لغو شد؛ بازهٔ گزارش عوض نشد."
PERF_RANGE_CLEARED = "✖️ بازهٔ دلخواه حذف شد؛ پنجرهٔ آماده برگشت."


def perf_report_text(data: dict) -> str:
    """گزارشِ همزمانی و عملکرد (P30) — متنِ تخت با نوارِ متنی."""
    from app.services import perf_report_service
    from app.utils.jalali import format_jalali_datetime

    lines = [f"📈 وضعیتِ همزمانی و عملکرد — {data['label']}:\n"]
    lines.append(f"همزمانیِ مشتریان در هر دانه: {perf_report_service.sparkline(data['series'])}")
    peak = data["peak_moment"]
    peak_label = format_jalali_datetime(peak) if peak else "—"
    lines.append(
        f"بیشینه: {fa_number(data['peak_customers'])} مشتریِ هم‌زمان در {peak_label} · "
        f"همین حالا ({fa_number(perf_report_service.NOW_WINDOW_MINUTES)} دقیقهٔ آخر): {fa_number(data['active_now'])} مشتری"
    )
    lines.append(
        f"\nدر این بازه: {fa_number(data['messages'])} پیامِ مشتری از {fa_number(data['customers'])} مشتری\n"
        f"🛒 سفارش: {fa_number(data['orders'])} · 💬 مشاوره: {fa_number(data['consultations'])} · "
        f"✅ پرداختِ انجام‌شده: {fa_number(data['payments_paid'])} · 🔵 رویدادِ درگاه: {fa_number(data['gateway_events'])}"
    )
    lines.append("\nبه تفکیکِ قابلیت (تعدادِ مصرف‌هایِ ثبت‌شده):")
    lines += [f"• {label}: {fa_number(count)}" for label, count in data["features"] if count]
    if not any(count for _label, count in data["features"]):
        lines.append("• هیچ مصرفِ اعتباری برایِ این قابلیت‌ها در بازه ثبت نشده.")
    channels = data.get("channels") or []
    if channels:
        names = {"telegram": "تلگرام", "bale": "بله", "instagram": "اینستاگرام"}
        lines.append("\nبه تفکیکِ کانال (مشتری / پیام):")
        lines += [f"• {names.get(str(platform), str(platform))}: {fa_number(customers)} مشتری · {fa_number(messages)} پیام" for platform, customers, messages in channels]

    top_shops = data.get("top_shops") or []
    if top_shops:
        lines.append("\nپرمشغله‌ترینِ فروشگاه‌ها (۵ تا):")
        lines += [f"• @{username}: {fa_number(customers)} مشتری · {fa_number(messages)} پیام" for username, customers, messages in top_shops]

    rate = float(data.get("messages_per_minute") or 0.0)
    rate_label = f"{rate:.4f}".rstrip("0").rstrip(".").translate(str.maketrans("0123456789.", "۰۱۲۳۴۵۶۷۸۹٫"))
    if 0 < rate < 0.0001:
        rate_label = "کمتر از ۰٫۰۰۰۱"
    needed = perf_report_service.ai_concurrency_estimate(rate)
    lines.append(
        f"\n⚙️ بارِ لازم برایِ هوشِ مصنوعی (تخمینی): {fa_number(needed)} درخواستِ هم‌زمان"
        f" — میانگینِ {rate_label} پیام در دقیقه؛ با فرضِ یک فراخوانی برایِ هر پیام و تأخیرِ ۵ ثانیه"
    )
    if data.get("custom_range"):
        lines.append(f"\n🗓 بازهٔ دلخواه: {data['label']} · دانه: {fa_number(data['bucket_minutes'])} دقیقه")
    lines.append("\nهمزمانی در نمودار یعنی مشتریِ متمایزِ پیام‌دهنده در هر دانه؛ نه تعدادِ درخواست‌هایِ واقعاً هم‌زمان.")
    lines.append("تخمینِ بالا میانگینِ بار است، نه ظرفیتِ تضمین‌شده یا بارِ اوج؛ تأخیرِ واقعیِ هوشِ مصنوعی سنجیده نشده.")
    lines.append("آمارِ همین حالا مستقل از بازهٔ انتخابی است؛ شمارشِ قابلیت‌ها از دفترِ مصرفِ اعتبار می‌آید.")
    return "\n".join(lines)


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
        lines.append(f"• {product.name} × {fa_number(item.quantity)} = {format_toman(product.price_toman * item.quantity)}")
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
    "⚠️ روشِ ارسالِ فعالی تعریف نکرده‌ای؛ به مشتری گفته شد «هماهنگیِ ارسال با فروشگاه» و هزینه‌یِ ارسال صفر ثبت شد.\n"
    "برایِ افزودن: «📦 محصولات» › «🚚 روش‌هایِ ارسال» (هزینه و مهلتِ تحویل را همان‌جا می‌گذاری؛ از این به بعد هزینه رویِ فاکتور می‌آید)."
)


def order_confirmed_stock_notification(product_name: str, remaining_stock: int) -> str:
    return f"✅ سفارش تایید شد و موجودی «{product_name}» کسر شد. موجودی باقی‌مانده: {fa_number(remaining_stock)} عدد."


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
def _percent_label(value) -> str:
    """«۱۲٪» یا «۱۲٫۵۰٪» — بدونِ ممیزِ لاتینِ وسطِ رقمِ فارسی (`fa_number(10.00)` ⇒ «۱۰.۰۰»)."""
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        number = 0.0
    return fa_percent(number, 0) if number == int(number) else fa_percent(number, 2)


def referral_code_text(code: str, stats: dict, bot_username: str, reward_percent=0) -> str:
    """P35: عددِ متن از تنظیمِ زندهٔ ادمین می‌آید، نه از ستونِ مردهٔ `referral_reward_wallet_toman`.

    کدِ واقعی (`referral_service.process_referral_reward`) درصدی از *اولینِ پرداختِ تأییدشده* را
    **فقط به معرف** می‌دهد؛ متنِ قبلی «۲۰٬۰۰۰ تومان به هر دوتون» می‌گفت که هم عددش ثابت بود هم
    مقصدش. (ستونِ `referral_reward_wallet_toman` در دیتابیس مانده — قاعدهٔ «حذفِ ستون نه» — ولی
    هیچ کدی آن را مصرف نمی‌کند.)
    """
    lines = [f"🎁 کد معرف تو: {code}\n"]
    try:
        percent = float(reward_percent or 0)
    except (TypeError, ValueError):
        percent = 0.0
    if percent > 0:
        lines.append(
            f"این کد رو با دیگران به اشتراک بذار! وقتی دعوت‌شده‌ت برایِ اولین بار کیف‌پولش رو شارژ کنه، "
            f"{_percent_label(reward_percent)} از همون مبلغ به کیف‌پولِ *خودت* اضافه می‌شه. "
            "این پاداش فقط به معرف می‌رسه، نه به هر دو طرف.\n"
        )
    else:
        lines.append(
            "این کد رو با دیگران به اشتراک بذار؛ فعلاً مدیرِ سرویس درصدِ پاداشِ معرف را صفر گذاشته، "
            "پس معرفی‌ای پاداش ندارد.\n"
        )
    lines.append(f"مجموع معرفی‌ها: {fa_number(stats['total'])}")
    lines.append(f"پاداش‌های دریافتی: {fa_number(stats['rewarded'])}\n")
    lines.append(f"لینک دعوتت:\nhttps://t.me/{bot_username}?start={code}")
    return "\n".join(lines)


def referrer_join_notification(name: str) -> str:
    """P42 · موردِ ۲۶: خبرِ ورود، جدا از خبرِ پاداش. بدونِ عددِ فنی و بدونِ شناسهٔ داخلی."""
    return f"👤 «{name}» با لینکِ دعوتِ تو واردِ ربات شد.\nاگر ثبت‌نام را تمام کند، پاداشِ معرفیِ تو فعال می‌شود."


def referrer_reward_notification(amount_toman: int, reward_percent=0) -> str:
    return (
        f"🎉 یکی از دعوت‌شده‌های تو برایِ اولین بار کیف‌پولش را شارژ کرد و "
        f"{format_toman(amount_toman)} ({_percent_label(reward_percent)}) به کیف‌پولت اضافه شد."
    )


# =============================================================================
# دوره‌ی مهلت / گریس‌پیریود (مرحله ۱۰)
# =============================================================================
def grace_period_reminder(hours: int) -> str:
    return (
        f"⏰ اشتراکت به پایان رسیده. تا {fa_number(hours)} ساعت دیگه فرصت داری تمدید کنی تا ربات فروشگاهیت "
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


# =============================================================================
# P43 · مواردِ ۳۰/۳۱/۱۰ — شاکلهٔ گزارشِ نگهبانِ محتوا
# =============================================================================
MODERATION_GUARD_BUTTON = "🛡 نگهبانِ محتوا"
MODERATION_REPORTS_EMPTY = "هیچِ گزارشِ بازِ نگهبانِ محتوا نداری. یعنی هیچ پیامی به قانونِ ممنوعه نخورده است."
MODERATION_REPORT_REVIEWED = "✅ گزارش بسته شد و از فهرستِ «باز» می‌رود. خودِ پیام و دفترِ ممیزی دست‌نخورده می‌مانند."
MODERATION_REPORT_NOT_FOUND = "این گزارش پیدا نشد یا به تو مربوط نیست."
MODERATION_BLOCK_RESULT = {True: "🚫 کاربر بلاک شد؛ رباتِ تو دیگر به پیام‌هایش پاسخ نمی‌دهد.", False: "✅ بلاکِ کاربر برداشته شد."}


def moderation_action_label(action: str) -> str:
    return {"warn": "🟡 هشدار (گفتگو ادامه پیدا کرد)", "block": "⛔️ مسدود (به گفتگو پایان داده شد)", "review": "🔎 نیازمندِ بررسیِ دستی (پاسخی داده نشد)"}.get(action, action)


def moderation_scope_label(scope: str) -> str:
    return "قانونِ خودت" if scope == "shop" else "قانونِ سراسریِ پلتفرم"


def moderation_report_card(report, customer_label: str, *, shop_line: str | None = None) -> str:
    """کارتِ گزارش — همان چیزی که برایِ فروشگاه‌دار (و برایِ ادمین با خطِ فروشگاه) می‌رود.

    هیچ شناسهٔ فنیِ داخلی در متن نیست؛ «کلمهٔ دیدنی» همان بریدهِ پیامِ مشتری است که برایِ
    تصمیم لازم است (درخواستِ مالکِ محصول: گزارش باید قابلِ فهم باشد، نه یکِ عددِ بی‌معنا).
    """
    lines = [
        "🛡 نگهبانِ محتوا: پیامِ یکِ مشتری به یکِ قانون خورد",
        "",
        f"مشتری: {customer_label}",
        f"کلمه یا الگوی دیدنی: «{report.pattern}»",
        f"اکشن: {moderation_action_label(report.action)}",
        f"منبعِ قانون: {moderation_scope_label(report.scope)}",
    ]
    if report.category:
        lines.append(f"دسته: {report.category}")
    if shop_line:
        lines.insert(1, shop_line)
    lines += ["", "📎 متنِ پیام (بریده):", report.excerpt or "—"]
    return "\n".join(lines)


def moderation_reports_list_text(reports, *, page: int, total_pages: int, total: int) -> str:
    lines = [
        f"🛡 گزارش‌هایِ بازِ نگهبانِ محتوا (صفحهٔ {fa_number(page + 1)} از {fa_number(max(total_pages, 1))} — جمعِ {fa_number(total)})",
        "",
    ]
    for report in reports:
        head = f"• «{report.pattern}» — {moderation_action_label(report.action).split(' ')[0]}"
        if report.scope == "shop":
            head += " · قانونِ خودت"
        lines.append(head)
    lines += ["", "یکِ گزارش را باز کن تا متنِ پیام، گفتگو و مشخصاتِ کاربر را ببینی."]
    return "\n".join(lines)


def moderation_report_list_button(report, index: int) -> str:
    mark = "🟡" if report.action == "warn" else ("⛔️" if report.action == "block" else "🔎")
    label = (report.excerpt or report.pattern)[:22]
    return f"{mark} {index}. «{report.pattern}» — {label}"


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
        urgency = f"{fa_number(days_left)} روزِ دیگه"
    return (
        f"⏳ بخشی از اعتبارِ کیف‌پولت ({format_toman(amount_toman)}) {urgency} منقضی می‌شه.\n"
        "اگه استفاده نکنیش از دست می‌ره — تا وقتش هست مصرفش کن.\n"
        "برایِ اعتبارِ تازه: منویِ «💰 کیف‌پول» › «💰 شارژ کیف‌پول»."
    )


# =============================================================================
# گزارش دوره‌ای (مرحله ۱۰)
# =============================================================================
def periodic_report_text(stats: dict, freq_days: int, consultation: bool = False) -> str:
    return f"📈 گزارش دوره‌ای ({fa_number(freq_days)} روز اخیر):\n\n" + shop_stats_text(stats, consultation)


def nightly_report_text(stats: dict, consultation: bool = False) -> str:
    """C1: در مودِ مشاوره‌ای «سفارش» و «مشتری» به «مشاوره» و «مخاطب» تبدیل می‌شوند."""
    lines = ["🌙 گزارش شبانه‌ی امروز:\n"]
    if not consultation:
        lines.append(f"🛒 سفارش‌های جدید: {fa_number(stats['new_orders_today'])}")
    lines.append(f"💬 مشاوره‌های جدید: {fa_number(stats['new_consultations_today'])}")
    lines.append(("👥 مخاطبان جدید: " if consultation else "👥 مشتریان جدید: ") + fa_number(stats["new_customers_today"]))
    if stats["confirmed_revenue_today_toman"] > 0:
        lines.append(f"💰 برآوردِ فروشِ تاییدشده‌ی امروز: {format_toman(stats['confirmed_revenue_today_toman'])}")
    # فازِ ۴: فقط وقتی >۰ باشه؛ با N=۰ خروجی دقیقاً مثلِ قبله. .get = دیکشنری‌هایِ قدیمی هم کار می‌کنن.
    if stats.get("new_knowledge_gaps", 0) > 0:
        lines.append(f"🧩 {fa_number(stats['new_knowledge_gaps'])} سوالِ بی‌جوابِ جدید (از «🧩 سوال‌هایِ بی‌جواب» جوابشون رو بده)")
    if stats["pending_orders_count"] > 0 and not consultation:
        lines.append(f"\n⏳ {fa_number(stats['pending_orders_count'])} سفارش هنوز منتظرِ بررسیِ شماست.")
    return "\n".join(lines)


# =============================================================================
# پیام همگانی / Broadcast (مرحله ۱۰)
# =============================================================================
ASK_BROADCAST_MESSAGE = "متن پیام همگانی رو بنویس:"


def broadcast_preview(text: str) -> str:
    return f"پیش‌نمایش پیام همگانی:\n\n{text}\n\nارسال بشه؟"


def broadcast_sent_confirmation(count: int) -> str:
    return f"✅ پیام همگانی برای {fa_number(count)} فروشگاه‌دار ارسال شد."


def admin_broadcast_started(count: int) -> str:
    """P24: ارسال در پس‌زمینه ادامه دارد؛ خلاصهٔ «چندتا واقع رفت» در پایان یک پیام جدا می‌آید."""
    return f"⏳ ارسالِ پیام همگانی برایِ {fa_number(count)} فروشگاه‌دار در پس‌زمینه شروع شد. وقتی تمام شد، نتیجه را می‌فرستم."


BROADCAST_CANCELLED = "ارسال پیام همگانی لغو شد."


# =============================================================================
# پیام فروشگاه‌دار به مشتری‌ها (فازِ ۳) — جدا از پیامِ همگانیِ ادمین بالا
# =============================================================================
ASK_CUSTOMER_BROADCAST_MESSAGE = "متنِ پیامی که می‌خوای برایِ همه‌ی مشتری‌هات بفرستی رو بنویس:"
CUSTOMER_BROADCAST_NO_CUSTOMERS = "هنوز هیچ مشتری‌ای با ربات‌ات چت نکرده، پس چیزی برای ارسال نیست."
# P42 · موردِ ۳۳: در پنلِ مشاوره‌ای «مشتری» نمی‌گوییم — مخاطب، کاربرِ همان جلسه است.
BROADCAST_SALES_BUTTON = "📣 پیام به مشتری‌ها"
BROADCAST_CONSULT_BUTTON = "📣 پیام به کاربران"
CUSTOMER_BROADCAST_CANCELLED = "ارسالِ پیام به مشتری‌ها لغو شد."
CUSTOMER_BROADCAST_BOT_OFFLINE = "ربات فروشگاهی‌ات الان آنلاین نیست (شاید توکنش نامعتبر شده)؛ نمی‌شه پیام فرستاد."


def customer_broadcast_preview(text: str, customer_count: int) -> str:
    return f"پیش‌نمایشِ پیام (برایِ {fa_number(customer_count)} مشتری فرستاده می‌شه):\n\n{text}\n\nارسال بشه؟"


def customer_broadcast_started(total: int) -> str:
    return f"⏳ در حالِ ارسال برایِ {fa_number(total)} مشتری... وقتی تموم شد یه پیام جدا بهت می‌دم."


def customer_broadcast_sent_confirmation(sent: int, total: int) -> str:
    if sent == total:
        return f"✅ پیام برایِ هر {fa_number(total)} مشتری با موفقیت ارسال شد."
    return f"✅ ارسال تموم شد: {fa_number(sent)} از {fa_number(total)} مشتری پیام رو گرفتن (بقیه احتمالاً ربات رو بلاک کرده بودن)."


# =============================================================================
# پرداختِ آنلاینِ سفارش از طریقِ بله‌پیِ خودِ فروشگاه (فازِ ۳)
# =============================================================================
def bale_provider_token_current(shop_bot, missing=(), asking: str | None = None) -> str:
    """A1/B11 → P35 → P39: صفحهٔ «پرداختِ آنلاین» با *هر دو* ورودیِ بله‌پی.

    P39 (درخواستِ مالکِ محصول): همین صفحه باید هم توکنِ رباتِ بله و هم توکنِ درگاه را بگیرد،
    چون توکنِ درگاه برایِ یک رباتِ خاص صادر می‌شود و با یکی از دو خانه، پول به کیف‌پولِ خودِ
    فروشگاه نمی‌نشیند. `asking` مشخص می‌کند همین الان کدام خانه پرسیده می‌شود.
    """
    from app.services import bale_bot_service

    has_bot = bool(bale_bot_service.raw_token(shop_bot))
    own_provider = bool((shop_bot.bale_provider_token or "").strip())
    lines = [
        "💳 پرداختِ آنلاینِ سفارش‌ها با بله‌پی",
        "",
        f"۱) توکنِ رباتِ بله: {bale_bot_service.token_masked(shop_bot)}",
        f"۲) توکنِ درگاهِ بله‌پی: {_mask_secret(shop_bot.bale_provider_token)}",
        "",
    ]
    if missing:
        lines += ["⚠️ بله‌پی برایِ مشتریِ تو فعال نیست:", *bale_missing_lines(missing)]
    elif has_bot and own_provider:
        lines.append("✅ هر دو خانه پر است: صورتحساب در چتِ رباتِ خودت می‌آید و پول مستقیم به "
                     "کیف‌پولِ بله‌پیِ خودت می‌نشیند.")
    else:
        # P41: با جفتِ ناقص دیگر پرداختی ساخته نمی‌شود؛ پولِ مشتری هرگز در کیف‌پولِ پلتفرم
        # نمی‌نشیند و لازم نیست بعداً با پشتیبانی هماهنگ کنی.
        lines.append("⚠️ تا هر دو خانه پر نشود، دکمهٔ «پرداخت با بله‌پی» به مشتری نشان داده نمی‌شود — "
                     "پولِ مشتری در کیف‌پولِ پلتفرم نمی‌نشیند.")
    if asking == "bot":
        lines += [
            "",
            "👈 اول توکنِ رباتِ بله‌ات را بفرست (از @BaleBotFather)؛ بعد سراغِ توکنِ درگاه می‌رویم.",
            "برایِ انصراف /cancel رو بفرست.",
        ]
    elif asking == "info":
        lines += ["", "👈 برایِ تغییرِ هر خانه همین دکمه را دوباره بزن؛ برایِ حذفِ درگاه «حذف» بنویس."]
    else:
        lines += [
            "",
            "👈 توکنِ درگاه را از پنلِ پذیرندگانِ بله‌پی می‌گیری و مشخص می‌کند پولِ مشتری در کیف‌پولِ چه کسی بنشیند.",
            "توکنِ درگاهِ خودت را بفرست، یا برایِ حذف بنویس «حذف».",
        ]
    return "\n".join(lines)


BALE_PROVIDER_TOKEN_INVALID = (
    "❌ این مقدار شبیهِ توکنِ درگاه نیست.\n"
    "باید یک تکه باشد (بدونِ فاصله و خطِ جدید) و دستِ‌کم ۲۰ نویسه.\n"
    "دوباره بفرست، یا برایِ حذف بنویس «حذف»."
)
# P34 → P39: مقصدِ پول به «جفتِ» دو ورودی وابسته است، نه فقط به توکنِ درگاه. هر دو خانه در همان
# صفحهٔ «💳 پرداختِ آنلاینِ سفارش‌ها» گرفته می‌شوند (دکمهٔ جدا برایِ توکنِ بله حذف شد).
def bale_provider_saved_text(shop_bot) -> str:
    from app.services import bale_bot_service  # import محلی: چرخه‌یِ import نسازد

    if bale_bot_service.connectable(shop_bot):
        return (
            "✅ توکنِ درگاه ذخیره شد و رباتِ بله‌ات هم ثبت است: صورتحسابِ سفارش در چتِ رباتِ خودت "
            "ساخته می‌شود و پول مستقیم به کیف‌پولِ خودت می‌نشیند (اگر کلیدِ بله‌پی روشن باشد، "
            "گزینهٔ «پرداخت با بله‌پی» به مشتری نشان داده می‌شود)."
        )
    return (
        "✅ توکنِ درگاه ذخیره شد، اما رباتِ بله‌یِ خودت هنوز ثبت نشده است.\n"
        "تا هر دو خانه پر نشود دکمهٔ «پرداخت با بله‌پی» به مشتری نشان داده نمی‌شود (پول به "
        "کیف‌پولِ پلتفرم نمی‌نشیند). توکنِ رباتِ بله را هم در همین صفحه می‌توانی بگذاری."
    )
# P26 → P41: حذفِ توکنِ درگاه همیشه گزینه را خاموش می‌کند. پیش از این اگر پلتفرم توکنِ سراسری
# داشت، مسیر با همان درگاه باز می‌ماند و پولِ مشتری در کیف‌پولِ پلتفرم می‌نشست؛ از P41 پرداختِ
# سفارش فقط با جفتِ کاملِ خودِ فروشگاه ساخته می‌شود، پس این پیام دیگر دو حالت ندارد.
BALE_PROVIDER_TOKEN_REMOVED = (
    "✅ توکنِ درگاه حذف شد.\n"
    "از این لحظه دکمهٔ «🔵 پرداخت با بله‌پی» به مشتری‌هایِ تو نشان داده نمی‌شود (روش‌هایِ دیگرِ "
    "پرداخت مثلِ کارت‌به‌کارت و زرین‌پال بازاند).\n"
    "هر وقت دوباره توکنِ درگاه و توکنِ رباتِ بله‌ات را در «💳 پرداختِ آنلاینِ سفارش‌ها» بگذاری، "
    "بله‌پی فعال می‌شود و پول مستقیم به کیف‌پولِ خودت می‌نشیند."
)


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

# پ۵۴ · موردِ ۱۲: صفِ حرفه‌ایِ پرداخت‌ها (فهرستِ صفحه‌بندی‌شده + کارتِ جزئیات).
PAYMENT_QUEUE_INVALID = "این درخواست دیگر در صفِ پرداخت نیست؛ صف را دوباره باز کن."
_PAYMENT_QUEUE_PURPOSE_LABELS = {"wallet_topup": "شارژِ کیف‌پول", "subscription": "اشتراک"}
_PAYMENT_QUEUE_METHOD_LABELS = {"card_to_card": "کارت‌به‌کارت", "zarinpal": "زرین‌پال", "bale": "بله"}


def payment_queue_purpose_label(purpose) -> str:
    value = purpose.value if hasattr(purpose, "value") else purpose
    return _PAYMENT_QUEUE_PURPOSE_LABELS.get(value, "پرداخت")


def payment_queue_method_label(method) -> str:
    value = method.value if hasattr(method, "value") else method
    return _PAYMENT_QUEUE_METHOD_LABELS.get(value, "پرداخت")


def admin_payment_queue_intro(total: int, page: int, total_pages: int) -> str:
    """شمارِ همین دامنه + شمارهٔ صفحه؛ دامنه پیش از صفحه‌بندی فیلتر شده، پس این عدد
    چیزی را که ادمینِ عملیاتی اجازهٔ دیدنش را ندارد لو نمی‌دهد (قاعدهٔ P21-E)."""
    head = f"{ADMIN_PENDING_PAYMENTS_INTRO}\n{fa_number(total)} پرداخت در انتظار بررسی"
    if total_pages > 1:
        head += f" — صفحهٔ {fa_number(page + 1)} از {fa_number(total_pages)}"
    return head + "\n\n• روی هر پرداخت بزنی جزئیات و دکمه‌های تایید/رد را می‌بینی."


def admin_payment_queue_line(payment, owner) -> str:
    return (
        f"• {display_user(owner, 'full')} · {payment_queue_purpose_label(payment.purpose)} · "
        f"{format_toman(payment.final_amount)} · {payment_queue_method_label(payment.method)}"
    )


def admin_payment_queue_button(payment, owner, index: int) -> str:
    """برچسبِ کوتاهِ دکمه (سقفِ ۶۴ نویسهٔ تلگرام): شماره + نامِ کوتاه، نه مبلغِ کامل."""
    name = clip(display_user(owner, "short"), 34) if owner is not None else "پرداخت"
    return f"{fa_number(index)} · {name}"


def admin_payment_detail_text(payment, owner, *, page: int) -> str:
    from app.utils.jalali import format_jalali_datetime

    lines = [
        "🧾 جزئیاتِ پرداخت",
        "",
        f"فروشگاه‌دار: {display_user(owner, 'full')}",
        f"هدف: {payment_queue_purpose_label(payment.purpose)}",
        f"روش: {payment_queue_method_label(payment.method)}",
        f"مبلغِ درخواستی: {format_toman(payment.base_amount)}",
        f"مبلغی که باید واریز شده باشد: {format_toman(payment.final_amount)}",
        _duration_label(payment),
        f"زمانِ ثبت: {format_jalali_datetime(payment.created_at) if payment.created_at else '—'}",
        f"مهلتِ رزرو تا: {format_jalali_datetime(payment.reserved_until) if payment.reserved_until else '—'}",
    ]
    if getattr(payment, "receipt_tracking_ref", None):
        lines.append(f"شماره‌یِ پیگیری: {payment.receipt_tracking_ref}")
    if getattr(payment, "receipt_text", None):
        lines.append(f"\n📄 رسیدِ متنی (فقط برایِ تو):\n{clip(payment.receipt_text, 900)}")
    if getattr(payment, "receipt_flags", None):
        labels = {"dup_file": "رسیدِ تکراری", "dup_tracking": "پیگیریِ تکراری"}
        found = [labels.get(flag, flag) for flag in str(payment.receipt_flags).split(",") if flag]
        if found:
            lines.append(f"\n⚠️ پرچم: {'، '.join(found)} — بررسی کن، خودکار رد نمی‌شود.")
    lines.append(f"\nبا «🧾 بازگشت به صف» به صفحهٔ {fa_number(page + 1)} برمی‌گردی.")
    return "\n".join(lines)


# پ۵۵ · موردِ ۲۳: رتبه‌بندیِ مصرفِ هوشِ مصنوعی به‌ازایِ هر کاربر + سه اهرمِ مدیریتی.
# پ۶۱ · خواستهٔ مالکِ محصول: درصدِ مصرفِ ظرفیتِ API و فشارِ سرور در پنلِ ادمین.
CAPACITY_BUTTON = "📡 ظرفیت و فشارِ سرور"
CAPACITY_REFRESH = "🔄 تازه‌سازی"
CAPACITY_NO_KEYS = "هیچِ کلیدِ فعالی برایِ پاسخِ متنی در استخر نیست؛ تا تنظیماتِ هوشِ مصنوعی خالی باشد هیچ پاسخی ساخته نمی‌شود."
CAPACITY_NOT_RUN_NOTE = (
    "⚠️ این اعداد زندهٔ همین پروسه است (از زمانِ بالا آمدنِ ربات). سقفِ واقعیِ سرویسِ "
    "ارائه‌دهندهٔ هوشِ مصنوعی هنوز سنجیده نشده و ادعا نمی‌شود — فقط سقفِ تنظیمیِ خودمان نشان داده می‌شود."
)


def capacity_text(snapshot: dict) -> str:
    ai, db, system = snapshot["ai"], snapshot["db"], snapshot["system"]
    lines = ["📡 ظرفیت و فشارِ سرور"]
    lines.append(
        f"\n🤖 پاسخِ مشتری — {fa_number(ai['inflight_total'])} درخواستِ در حالِ اجرا از "
        f"ظرفیتِ قابلِ استفاده {fa_number(ai['usable'])} ({fa_percent(ai['percent'])})"
    )
    if ai["keys"]:
        for load in ai["keys"]:
            lines.append(
                f"• {load.label}: {fa_number(load.inflight)} از {fa_number(load.cap)} ({fa_percent(load.percent)})"
            )
        bottleneck = "جمعِ سقفِ کلیدها" if ai["bottleneck"] == "keys" else "سقفِ پلتفرم"
        lines.append(
            f"گلوگاهِ فعلی: {bottleneck} — جمعِ سقفِ کلیدها {fa_number(ai['sum_caps'])}، "
            f"سقفِ پلتفرم {fa_number(ai['platform_ceiling'])}"
        )
    else:
        lines.append(CAPACITY_NO_KEYS)
    voice = ai["voice"]
    if voice["count"]:
        lines.append(
            f"🎙 صوت — {fa_number(voice['count'])} کلید · {fa_number(voice['inflight'])} درخواستِ در حالِ اجرا "
            f"از {fa_number(voice['sum_caps'])}"
        )
    if db.get("mode") == "null":
        lines.append("\n🗄 دیتابیس — بدونِ استخر (هر اتصال موقعِ برگشت بسته می‌شود)")
    else:
        lines.append(
            f"\n🗄 دیتابیس — {fa_number(db['checked_out'])} اتصالِ در کار از {fa_number(db['capacity'])} "
            f"({fa_percent(db['percent'])}) · اتصال‌هایِ اضافه {fa_number(db['overflow'])}"
        )
    load1 = system["load1"]
    if load1 is None:
        lines.append("\n🖥 سرور — بارِ میانگین در این محیط خوانده نشد")
    else:
        lines.append(
            f"\n🖥 سرور — بارِ میانگینِ ۱ دقیقه {fa_number(f'{load1:.2f}'.replace('.', '٫'))} رویِ "
            f"{fa_number(system['cores'])} هسته ({fa_percent(system['load_percent'])})"
        )
    memory = system["memory_used_percent"]
    disk = system["disk_used_percent"]
    lines.append(
        f"• رمِ استفاده‌شده: {fa_percent(memory) if memory is not None else 'خوانده نشد'} · "
        f"دیسکِ {system['disk_label']}: {fa_percent(disk) if disk is not None else 'خوانده نشد'}"
    )
    counters = snapshot["counters"]
    if counters:
        # پ۷۹ · شمارنده‌ها دیگر فقط سهمِ یکِ پروسه نیستند؛ پنل می‌گوید چند پروسه جمع شده‌اند.
        processes = int(snapshot.get("processes") or 1)
        stale = int(snapshot.get("stale_processes") or 0)
        scope = (
            "جمعِ شمارنده‌ها از " + fa_number(processes) + " پروسهٔ زنده"
            if processes > 1
            else "از شروعِ این پروسه"
        )
        if stale:
            scope += " · " + fa_number(stale) + " پروسهٔ بی‌ضربان شمرد نشد"
        lines.append(f"\n📚 شمارنده‌ها ({scope}):")
        for label, value in counters[:12]:
            lines.append(f"• {label}: {fa_number(value)}")
    lines.append("\n" + CAPACITY_NOT_RUN_NOTE)
    return "\n".join(lines)


# پ۶۲ · خواستهٔ مالکِ محصول: ایجنتی که لاگ و وضعیتِ سرور را بخواند و مشکل را بگوید.
DOCTOR_BUTTON = "🩺 عیب‌یابِ سرور"
# پ۷۰: این دکمه رویِ صفحهٔ عیب‌یاب «محل» می‌رود، نه «تازه‌سازی» ⇒ نامِ خودِ پنل را می‌گیرد
# (برچسبِ «🔄 تازه‌سازی» رویِ این دکمه باعث شد مالکِ محصول فکر کند همان تازه‌سازیِ بازرسی است).
DOCTOR_OPEN_CAPACITY = CAPACITY_BUTTON
DOCTOR_THRESH_BUTTON = "⚖️ آستانه‌هایِ عیب‌یاب"
DOCTOR_THRESH_STALE = "این دکمهٔ آستانه دیگر معتبر نیست؛ از «🩺 عیب‌یابِ سرور» دوباره باز کن."
DOCTOR_THRESH_RESET = "♻️ بازگشت به همهٔ پیش‌فرض‌ها"
DOCTOR_THRESH_INTRO = (
    "⚖️ آستانه‌هایِ عیب‌یاب — فقط برایِ همین پلتفرم\n\n"
    "یافته‌ها از مقایسهٔ عددِ زنده با همین آستانه‌ها ساخته می‌شود. هر عدد بیرونِ کرانِ خودش "
    "ذخیره نمی‌شود، و هیچ‌کدام رویِ رفتارِ ربات اثر ندارد: فقط *تشخیص* را حساس یا بی‌حس می‌کند."
)
DOCTOR_THRESH_ASK = (
    "عددِ تازه را بنویس (بینِ {low} تا {high}). برایِ انصراف /cancel را بزن.\n"
    "مثالِ درست: {example}"
)
DOCTOR_THRESH_INVALID = (
    "این عدد قابلِ استفاده نیست. فقط رقم بنویس{between} — بیرونِ کران ذخیره نمی‌شود."
)
DOCTOR_THRESH_SAVED = "✅ آستانهٔ «{label}» رویِ {value} تنظیم شد و در ممیزی ثبت شد."
DOCTOR_THRESH_RESET_DONE = "♻️ همهٔ آستانه‌ها به پیش‌فرضِ نسخه برگشت."
DOCTOR_THRESH_WINDOW_NOTE = (
    "⏱ شمارنده‌ها در پنجرهٔ زمانی قضاوت می‌شوند؛ اگر جاب تازه روشن شده باشد یا آخرین بازرسی "
    "بیش از دو پنجره فاصله داشته باشد، خودِ جمعِ کل با برچسبِ «از شروعِ این پروسه» نشان داده می‌شود."
)


def doctor_threshold_value_text(key: str, value: float, spec) -> str:
    """نمایشِ عددِ آستانه با نوعش: درصد یا شمارش."""
    default, low, high, kind, label = spec
    if kind == "percent":
        shown = fa_percent(value)
        bounds = f"{fa_percent(low)} تا {fa_percent(high)}"
    else:
        shown = fa_number(int(value))
        bounds = f"{fa_number(int(low))} تا {fa_number(int(high))}"
    mark = "" if value == default else " (خودت)"
    return f"{label}: {shown}{mark} · کران {bounds}"


def doctor_thresholds_text(limits: dict, specs: dict) -> str:
    lines = [DOCTOR_THRESH_INTRO, ""]
    for key, spec in specs.items():
        lines.append("• " + doctor_threshold_value_text(key, limits[key], spec))
    lines += ["", DOCTOR_THRESH_WINDOW_NOTE]
    return "\n".join(lines)


def doctor_threshold_ask_text(spec) -> str:
    _default, low, high, kind, _label = spec
    example = "۹۰" if kind == "percent" else "۲۰"
    return DOCTOR_THRESH_ASK.format(low=fa_number(int(low)), high=fa_number(int(high)), example=example)


def doctor_threshold_invalid_text(spec) -> str:
    _default, low, high, kind, _label = spec
    if kind == "percent":
        between = f" و بینِ {fa_percent(low)} تا {fa_percent(high)}"
    else:
        between = f" و بینِ {fa_number(int(low))} تا {fa_number(int(high))}"
    return DOCTOR_THRESH_INVALID.format(between=between)


DOCTOR_REFRESH = "🔄 تازه‌سازیِ بازرسی"
DOCTOR_CLEAN = "✅ هیچِ موردِ غیرعادی پیدا نشد: فشارِ سرور، استخرِ دیتابیس، استخرِ کلیدهایِ " \
               "هوشِ مصنوعی و لاگِ همین پروسه همه در محدوده‌اند."
DOCTOR_NO_ACTION_NOTE = (
    "این صفحه فقط تشخیص می‌دهد و هیچ چیزی را عوض نمی‌کند؛ هر اقدام از همان دکمه‌هایِ خودِ "
    "پنل انجام می‌شود و در «📜 گزارشِ ممیزی» ثبت می‌گردد."
)


def doctor_line(finding) -> str:
    """یکِ یافته: شدت + عنوان + عددِ دقیق + جایِ اقدام (بدونِ هیچ شناسهٔ فنیِ بی‌معنا)."""
    from app.services.server_doctor import SEVERITY_ICON

    icon = SEVERITY_ICON.get(finding.severity, "🔵")
    return f"{icon} {finding.title}\n{finding.detail}\n➖ اقدام: {finding.suggestion}"


def doctor_screen_text(findings: list, moment) -> str:
    from app.utils.jalali import format_jalali_datetime

    lines = [f"🩺 عیب‌یابِ سرور — {format_jalali_datetime(moment)}"]
    if not findings:
        lines.append("\n" + DOCTOR_CLEAN)
    else:
        counts: dict[str, int] = {}
        for finding in findings:
            counts[finding.severity] = counts.get(finding.severity, 0) + 1
        lines.append(
            "\n"
            + f"{fa_number(len(findings))} مورد: "
            + f"🔴 {fa_number(counts.get('error', 0))} · "
            + f"🟠 {fa_number(counts.get('warn', 0))} · "
            + f"🔵 {fa_number(counts.get('info', 0))}"
        )
        for finding in findings:
            lines.append("\n" + doctor_line(finding))
    lines.append("\n" + DOCTOR_NO_ACTION_NOTE)
    return "\n".join(lines)


def doctor_alert_text(findings: list, moment) -> str:
    from app.utils.jalali import format_jalali_datetime

    lines = [
        "🩺 عیب‌یابِ سرور: "
        + f"{fa_number(len(findings))} موردِ تازه — {format_jalali_datetime(moment)}"
    ]
    for finding in findings:
        lines.append("\n" + doctor_line(finding))
    lines.append("\nبرایِ دیدنِ همه‌چیز: پنلِ ادمین ⇒ «🩺 عیب‌یابِ سرور» یا «📡 ظرفیت و فشارِ سرور».")
    return "\n".join(lines)


AI_USAGE_BUTTON = "📊 مصرفِ کاربران"
AI_USAGE_WINDOWS: tuple[tuple[str, str], ...] = (("24h", "۲۴ ساعت"), ("7d", "۷ روز"), ("30d", "۳۰ روز"))
AI_USAGE_HISTORY_NOTE = "شمارش از همین نسخه شروع می‌شود؛ در ردیف‌هایِ قدیمیِ دفتر، مصرف به کاربرِ خاصی وصل نبود."
AI_USAGE_EMPTY = "در این بازه هیچ مصرفِ ثبت‌شده‌ای به کاربری وصل نبود."
AI_USAGE_INVALID = "این کاربر در فهرست نیست؛ فهرستِ مصرفِ کاربران را دوباره باز کن."
AI_USAGE_LIMIT_ASK = (
    "سقفِ مصرفِ این کاربر در ۲۴ ساعتِ گذشته چقدر باشد (به تومان)؟\n"
    "· نمونه: ۵۰۰۰۰\n"
    "· برایِ برداشتنِ سقف بنویس «بدونِ سقف»؛ برایِ لغو «انصراف»."
)
AI_USAGE_LIMIT_INVALID = "عددِ معتبر نبود. مبلغِ تومان بنویس (مثلاً ۵۰۰۰۰) یا «بدونِ سقف»."
AI_USAGE_CANCELLED = "↩️ لغو شد؛ چیزی برایِ این کاربر عوض نشد."


def ai_usage_limit_saved(amount_toman: int | None) -> str:
    if amount_toman is None:
        return "✅ سقفِ مصرفِ این کاربر برداشته شد؛ مثلِ قبل آزاد است."
    return f"✅ سقفِ مصرفِ این کاربر: {format_toman(amount_toman)} در ۲۴ ساعت."


def ai_usage_pause_saved(hours: int | None) -> str:
    if hours is None:
        return "▶️ پاسخِ خودکار برایِ این کاربر آزاد شد."
    return f"⏸ پاسخِ خودکارِ این کاربر تا {fa_number(hours)} ساعتِ دیگر متوقف است."


def ai_usage_intro(total_users: int, window_label: str, page: int, total_pages: int) -> str:
    head = f"📊 پرمصرف‌ترینِ کاربرانِ هوشِ مصنوعی — {window_label}\n{fa_number(total_users)} کاربر مصرفِ ثبت‌شده دارد"
    if total_pages > 1:
        head += f" — صفحهٔ {fa_number(page + 1)} از {fa_number(total_pages)}"
    return head + "\n\n• روی هر کاربر بزن تا جزئیات و دکمه‌هایِ محدودیت/توقف/بلاک را ببینی."


def ai_usage_line(index: int, user_name: str, shop_username: str, spent_toman: int, calls: int) -> str:
    shop = f"@{shop_username}" if shop_username else "بدونِ نامِ کاربری"
    return (
        f"{fa_number(index)}) {user_name} · {shop} · "
        f"{format_toman(spent_toman)} · {fa_number(calls)} کسرِ اعتبار"
    )


def owner_ai_usage_line(index: int, user_name: str, spent_toman: int, calls: int) -> str:
    """پ۷۰: خطِ فهرستِ صاحبِ فروشگاه — ستونِ فروشگاه حذف شده (همه یکِ فروشگاه‌اند)."""
    return (
        f"{fa_number(index)}) {user_name} · {format_toman(spent_toman)} · {fa_number(calls)} کسرِ اعتبار"
    )


def ai_usage_detail_text(
    customer, shop_username: str, *, spent_toman: int, calls: int, window_label: str, page: int
) -> str:
    from app.utils.jalali import format_jalali_datetime

    limit = customer.ai_daily_limit_toman
    paused_until = customer.ai_paused_until
    # توقفِ تمام‌شده نباید «متوقف» نشان داده شود؛ دکمهٔ کنارش هم «آزادکردن» نمی‌گوید.
    still_paused = paused_until is not None and (
        paused_until.replace(tzinfo=datetime.timezone.utc)
        if paused_until.tzinfo is None
        else paused_until.astimezone(datetime.timezone.utc)
    ) > datetime.datetime.now(datetime.timezone.utc)
    status = f"⏸ متوقف تا {format_jalali_datetime(paused_until)}" if still_paused else "✅ پاسخِ خودکار فعال است"
    lines = [
        "📊 مصرفِ هوشِ مصنوعیِ یکِ کاربر",
        "",
        f"کاربر: {display_user(customer, 'full')}",
        f"فروشگاه: @{shop_username}" if shop_username else "فروشگاه: —",
        f"مصرفِ این بازه ({window_label}): {format_toman(spent_toman)}",
        f"تعدادِ کسرِ اعتبار در این بازه: {fa_number(calls)}",
        f"سقفِ مصرف در ۲۴ ساعت: {format_toman(limit) if limit else 'بدونِ سقف'}",
        f"وضعیت: {status}",
        f"آخرین پیام: {format_jalali_datetime(customer.last_message_at) if customer.last_message_at else '—'}",
        AI_USAGE_HISTORY_NOTE,
        "\nاین صفحه مصرف را نشان می‌دهد و مبلغی از کسی کم یا به کسی اضافه نمی‌کند.",
    ]
    if customer.is_blocked:
        lines.append("این کاربر از سویِ فروشگاه بلاک شده است.")
    lines.append(f"با «📊 بازگشت به فهرست» به صفحهٔ {fa_number(page + 1)} برمی‌گردی.")
    return "\n".join(lines)


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
# P25: «مبلغ ثابت» از پنلِ ادمین حذف شد؛ جریانِ ساختِ کد فقط درصد می‌پرسد.
ADMIN_ASK_DISCOUNT_VALUE = "مقدارِ تخفیف را به درصد بنویس (عددی بین ۱ تا ۱۰۰):"
ADMIN_DISCOUNT_TYPE_REMOVED = (
    "🏷 «مبلغ ثابت» از پنلِ ادمین حذف شد؛ هر کدِ تازه‌ای که بسازی درصدی است.\n"
    "کدهایِ مبلغ‌ثابتِ قدیمی همچنان کار می‌کنند و در فهرست می‌بینشانیشان (با برچسبِ «قدیمی»)، "
    "ولی ساختنِ آن‌ها ممکن نیست. برایِ کدِ تازه: «🏷 کدهای تخفیف › ➕ افزودن کد جدید»."
)
ADMIN_ASK_DISCOUNT_MAX_USES = "حداکثر تعداد استفاده چقدر باشه؟ (برای نامحدود بنویس «نامحدود»):"


def admin_discount_code_saved(code: str) -> str:
    return f"✅ کدِ تخفیفِ درصدی «{code}» ساخته شد."


# --- تنظیمات کلیدها ---
ADMIN_SETTINGS_MENU_INTRO = "🔑 تنظیمات کلیدها و پیکربندی پلتفرم:"
ADMIN_ASK_SMS_API_KEY = "کلید API سرویس پیامک (کاوه‌نگار) رو بفرست:"
ADMIN_ASK_SMS_SENDER = "سرشماره‌یِ پیامک (خطِ سرویسِ کاوه‌نگار) رو بفرست. برایِ پاک کردن «خالی» بنویس:"
ADMIN_ASK_SMS_TEMPLATE = "نامِ قالبِ OTP در کاوه‌نگار رو بفرست. برایِ پاک کردن «خالی» بنویس تا «registerotp» استفاده بشه:"
ADMIN_INVALID_SMS_SENDER = "سرشماره نامعتبره. فقط رقم (با + اولِ آن) و ۵ تا ۲۰ نویسه."
ADMIN_INVALID_SMS_TEMPLATE = "نامِ قالب نامعتبره. فقط حروفِ لاتین، رقم، _ و -، حداکثر ۶۴ نویسه."
SMS_ENABLED_WITHOUT_KEY = (
    "⚠️ پیامک روشن شد ولی هنوز کلیدِ API تنظیم نشده. تا وقتی کل نگذاری، کد در همان چت نشان داده "
    "می‌شود و ثبت‌نام نمی‌خوابد."
)
SMS_SENT_VOLUME_LINE = "📮 حجمِ پیامک‌هایِ ارسالی در {days} روز اخیر: {count} پیامک"

# ------------------------------------------------------------------ P18 · A2: بیوگرافی/برندینگِ رباتِ فروشگاه
ADMIN_ASK_BRANDING_TEXT = (
    "متنِ برندینگِ بیوگرافیِ همه‌یِ ربات‌هایِ فروشگاهی رو بنویس (حداکثر ۶۰ نویسه). "
    "برایِ پاک کردن «خالی» بنویس."
)
ADMIN_INVALID_BRANDING_TEXT = "این متن باید ۱ تا ۶۰ نویسه باشد."
BRANDING_SAVED_WITH_BOTS = "✅ ذخیره شد. بیوگرافیِ {count} رباتِ فروشگاهی بررسی و در صورتِ نیاز به‌روز شد."
BRANDING_SAVED_NO_BOTS = "✅ ذخیره شد. ربات‌هایی که بعداً وصل بشن هم همین متن را می‌گیرند."
BRANDING_SYNC_RESULT = (
    "🧴 بیوگرافی: {shops} فروشگاه ({total} ربات) · {applied} تنظیم‌شده · {tampered} جایگزینیِ‌دست‌کاری · "
    "{removed} بازگردانیِ‌حذف · {unchanged} درست · {skipped} بی‌متن · {error} خطا"
)
BRANDING_SYNC_FAILED = "🧴 {error} ربات به‌دلیلِ خطایِ شبکه در پاسِ بعدی دوباره تلاش می‌شود."
BOT_BIO_TAMPERED_ALERT = (
    "🧴 بیوگرافیِ رباتت دستکاری شده بود و ما آن را به «متنِ خودت — متنِ پلتفرم» برگرداندیم.\n"
    "اگر خودت آن را عوض کرده‌ای، در بازرسیِ بعدی هم دوباره همین متن جایگزین می‌شود."
)
BOT_BIO_REMOVED_ALERT = (
    "🧴 بیوگرافیِ رباتت حذف شده بود؛ ما متنِ «متنِ خودت — متنِ پلتفرم» را دوباره جای آن گذاشتیم.\n"
    "اگر خودت پاک کرده‌ای، در بازرسیِ بعدی هم دوباره نوشته می‌شود — برایِ حذفِ دائمی، متنِ خودت را از همین صفحه خالی کن."
)
ADMIN_ASK_BRANDING_CHECK_MINUTES = (
    "فاصله‌یِ بازرسیِ بیوگرافیِ ربات‌ها چند دقیقه باشه؟ (۵ تا ۱۴۴۰)\n"
    "هر دور، متنِ خودت و متنِ پلتفرم رویِ رباتِ تلگرام و بله‌یِ هر فروشگاه خوانده و در صورتِ حذف/دستکاری برگردانده می‌شود."
)
BRANDING_CHECK_NOW_BUTTON = "🔄 بازبینیِ همین الان"
BRANDING_CHECK_HEALTHY = "✅ بیوگرافیِ رباتت دقیقاً همان متنی است که باید باشد (رویِ هر پلتفرمی که وصل هست)."
BRANDING_CHECK_RESTORED = "🔄 بیوگرافیِ رباتت بازبینی شد و متنِ درست جایگزین شد."
BRANDING_CHECK_REMOVED = "🧴 بیوگرافیِ رباتت حذف شده بود؛ متنِ «متنِ خودت — متنِ پلتفرم» دوباره نوشته شد."
BRANDING_CHECK_TAMPERED = "⚠️ بیوگرافیِ رباتت دستکاری شده بود؛ همان لحظه به «متنِ خودت — متنِ پلتفرم» برگردانده شد."
BRANDING_CHECK_NO_TEXT = "متنی برایِ بازبینی تنظیم نشده؛ اول «متنِ خودت» را بنویس."
BRANDING_CHECK_NOT_CONNECTED = "رباتِ این فروشگاه فعلاً به این سرویس وصل نیست؛ متن ذخیره شد و در اولین اتصال اعمال می‌شود."
BRANDING_CHECK_ERROR = "🧴 بازبینی ممکن نشد (خطایِ شبکه). در دورِ بعدی دوباره تلاش می‌شود."
BRANDING_REPORT_EMPTY = (
    "🧴 هیچ رباتی تا حالا بیویش دستکاری یا حذف نشده است.\n\n"
    "بازرسیِ خودکار هر {minutes} دقیقه انجام می‌شود و فاصله‌اش را از همین دسته می‌توانی عوض کنی."
)
BRANDING_REPORT_TITLE = "🧴 گزارشِ دستکاریِ بیوگرافی (فاصلهٔ بازرسی: هر {minutes} دقیقه)\n\n"
BRANDING_REPORT_ITEM = "• {username}: {count} بار · آخرینِ بازبینی: {checked}"
BRANDING_REPORT_NEVER = "هنوز بازبینی نشده"

# P21-C (F3 و F4): قیمت‌گذاریِ منصفانه و طلبِ کمیسیون
ADMIN_ASK_WALLET_COST_VOICE_PER_MINUTE = (
    "هزینه‌یِ «هر دقیقه‌یِ صوت» (تومان) چقدر باشه؟ ۰ = همان نرخِ ثابتِ فعلی.\n"
    "فرمول: max(کفِ فعلی, دقیقه_گرد_بالا × این نرخ) ⇒ ویسِ کوتاه ارزان‌تر از امروز نمی‌شود، ویسِ بلند گران‌تر."
)
ADMIN_ASK_WALLET_COST_RECEIPT_PER_1K_TOKENS = (
    "هزینه‌یِ هر ۱۰۰۰ توکنِ تحلیلِ رسید (تومان) چقدر باشه؟ ۰ = همان نرخِ ثابتِ فعلی."
)
# P33-C: بدهیِ مصرفِ هوش مصنوعی (کنارِ طلبِ کمیسیون در همان صفحهٔ ادمین).
AI_DEBT_REPORT = (
    "🧠 بدهیِ مصرفِ هوش مصنوعی\n\n"
    "ردیف‌هایِ باز: {count} — جمع: {toman}\n"
    "بخشوده‌شده: {waived_count}\n\n"
    "{items}"
)
AI_DEBT_ITEM = "• {owner}: {toman} · {reason}"
COMMISSION_DEBT_EMPTY = (
    "🧾 طلبِ کمیسیونی ثبت نشده است — هر کمیسیونِ نهایی در همان لحظه از کیف‌پول گرفته شده.\n\n"
    "فاصلهِ بازرسیِ جمع‌آوری: هر دورِ جابِ «کیف‌پول» (پیش‌فرض ۳۰ دقیقه) بررسی می‌شود."
)
COMMISSION_DEBT_REPORT = (
    "🧾 طلبِ کمیسیونِ پلتفرم\n\n"
    "💰 باز: {count} مورد · {toman}\n"
    "✅ وصول‌شده: {settled_count} مورد\n\n"
    "{items}\n\n"
    "با هر شارژِ کافی، خودکار وصول می‌شود (دیگر گم نمی‌شود)."
)
COMMISSION_DEBT_ITEM = "• {owner}: {toman} · {note}"
BRANDING_OWNER_ASK = (
    "متنِ خودت برایِ بیوگرافیِ ربات رو بنویس (حداکثر ۱۲۰ نویسه؛ کنارِ متنِ پلتفرم نمایش داده می‌شود).\n"
    "برایِ پاک کردن «خالی» بنویس. برایِ انصراف /cancel رو بزن."
)
BRANDING_OWNER_INVALID = "متنِ بیوگرافی نباید بیشتر از ۱۲۰ نویسه باشد."
BRANDING_OWNER_SAVED = "✅ ذخیره شد؛ بیوگرافیِ رباتت همین الان به‌روز شد."
BRANDING_OWNER_SAVED_NOT_CONNECTED = (
    "✅ متنِ بیوگرافی ذخیره شد.\n"
    "رباتت الان به سرویس متصل نیست، پس بیوگرافی در اولین اتصالِ خودکار اعمال می‌شود."
)
BRANDING_OWNER_SAVE_RETRY = "✅ متنِ بیوگرافی ذخیره شد، ولی تلگرام آن را همین الان نپذیرفت (خطایِ شبکه). در بازرسیِ بعدی دوباره تلاش می‌شود."
BRANDING_NOT_CONFIGURED = (
    "پلتفرم هنوز متنِ برندینگِ اجباری را تنظیم نکرده، پس بیوگرافیِ ربات دست‌نخورده می‌ماند.\n"
    "متنِ خودت ذخیره می‌شود و به‌محضِ تنظیمِ متنِ پلتفرم اعمال می‌گردد."
)


def branding_owner_text(shop_bot, admin_text: str | None) -> str:
    from app.services import bot_branding_service
    from app.utils.jalali import format_jalali_datetime

    composed = bot_branding_service.compose(shop_bot.branding_owner_text, admin_text)
    owner = (shop_bot.branding_owner_text or "").strip()
    lines = ["🧴 بیوگرافیِ ربات (short description)", ""]
    lines.append(f"متنِ پلتفرم (اجباری): {admin_text}" if admin_text else "متنِ پلتفرم: ادمین هنوز برندِ سراسری ننوشته است.")
    lines.append(f"متنِ خودت: {owner or '—'}")
    lines.append(f"متنِ نهایی رویِ ربات: {composed or '—'}")
    if composed:
        lines.append(f"جایِ باقی‌مانده از سقفِ {fa_number(bot_branding_service.BIO_LIMIT)}: {fa_number(max(0, bot_branding_service.BIO_LIMIT - len(composed)))} نویسه")
    lines.append("")
    if composed:
        lines.append("اگر جا نشود، متنِ خودت کوتاه می‌شود — متنِ پلتفرم همیشه کامل می‌ماند.")
        lines.append("این متن رویِ رباتِ تلگرام و رباتِ بله‌ات کنترل و در صورتِ نیاز بازگردانی می‌شود.")
    else:
        lines.append(BRANDING_NOT_CONFIGURED)
    if shop_bot.branding_tamper_count:
        lines.append(f"⚠️ {fa_number(shop_bot.branding_tamper_count)} بار بیوگرافی دستکاری/حذف شده و خودکار برگردانده شد.")
    checked = shop_bot.branding_checked_at
    lines.append(f"🕓 آخرینِ بازبینی: {format_jalali_datetime(checked) if checked else '— (هنوز بازبینی نشده)'}")
    return "\n".join(lines)
OTP_RATE_LIMITED = "📮 برایِ این شماره اخیراً پیامکِ زیادی رفته. حدودِ یک ساعتِ دیگر دوباره شماره را بفرست."

ADMIN_ASK_AI_MODEL = "نام مدل هوش مصنوعی رو بفرست:"
ADMIN_ASK_AI_BASE_URL = "آدرس Base URL سرویس هوش مصنوعی رو بفرست (سازگار با فرمت OpenAI):"
# P24 (امنیت): این آدرس با هدرِ کلیدِ AI درخواست می‌زند؛ رویِ هاستِ داخلی یعنی نشتِ کلید + SSRF.
ADMIN_INVALID_AI_URL = (
    "❌ این آدرس را ذخیره نکردم. باید با «https://» شروع شود (نه http)، میزبان داشته باشد و "
    "به شبکه‌یِ داخلیِ سرور نرود (localhost، 127.x، 10.x، 192.168.x، 172.16-31.x، 169.254.x و "
    "آدرس‌هایِ IPِ داخلی مجاز نیستند). کلیدِ هوش مصنوعی در headerِ همین درخواست می‌رود."
)
ADMIN_ASK_ZARINPAL_MERCHANT_ID = "مرچنت آیدی زرین‌پال رو بفرست:"
ADMIN_INVALID_BALE_TOKEN = (
    "❌ این مقدار شبیهِ توکن نیست.\n"
    "توکن باید یک تکه باشد (بدونِ فاصله و خطِ جدید) و دستِ‌کم ۲۰ نویسه.\n"
    "اگر می‌خواهی پاکش کنی، «خالی» بفرست."
)
ADMIN_ASK_BALE_PROVIDER_TOKEN = (
    "🔵 توکنِ درگاهِ بله‌پی (provider_token) رو بفرست.\n"
    "این را از پنلِ پذیرندگانِ بله‌پی یا از @botfather در بله می‌گیری و تعیین می‌کند پول به کیف‌پولِ "
    "چه کسی می‌نشیند (هیچ ربطی به نامِ کاربریِ ربات ندارد).\n"
    "اگر فروشگاه‌دار توکنِ درگاهِ خودش را ثبت کرده باشد، اولویت با همان است و این مقدار پشتیبانِ سراسری می‌شود.\n"
    "برای پاک‌کردن، «خالی» بفرست:"
)
ADMIN_ASK_BALE_BOT_TOKEN = (
    "🔵 توکنِ رباتِ بله را بفرست.\n"
    "این ربات همان «رباتِ پرداخت» است: از P26 لینکِ پرداخت یعنیِ چتِ همین ربات در اپِ بله "
    "(https://ble.ir/<نامِ‌کاربری>?start=…) و صورتحسابِ خودِ بله در همان چت فرستاده می‌شود؛ پس "
    "نامِ کاربریِ آن به‌صورتِ خودکار از `getMe` خوانده و در فهرستِ تنظیمات نشان داده می‌شود.\n"
    "این توکن همچنین رویدادهایِ پرداخت (pre_checkout و successful_payment) را می‌گیرد.\n"
    "مقدارِ همین پنل بر .env اولویت دارد و بدونِ ری‌استارتِ برنامه اعمال می‌شود.\n"
    "برای پاک‌کردن، «خالی» بفرست (در آن صورت از .env خوانده می‌شود):"
)
ADMIN_ASK_PLATFORM_CARD_NUMBER = "شماره کارت پلتفرم برای دریافت پرداخت‌های کارت‌به‌کارت رو بفرست:"
ADMIN_ASK_PLATFORM_CARD_HOLDER = "نام صاحب کارت رو بفرست:"
ADMIN_ASK_GRACE_PERIOD_HOURS = "چند ساعت مهلت (گریس‌پیریود) بعد از پایان اشتراک داده بشه؟"
ADMIN_ASK_REPORT_FREQUENCY_DAYS = "گزارش دوره‌ای هر چند روز یک‌بار برای فروشگاه‌دارها ارسال بشه؟"
ADMIN_ASK_NIGHTLY_REPORT_HOUR = "گزارشِ شبانه سرِ چه ساعتی (به‌وقتِ UTC، عددِ ۰ تا ۲۳) فرستاده بشه؟ ساعتِ تهران سه ساعت و نیم جلوتر از UTC است."
ADMIN_ASK_REFERRAL_PERCENT = (
    "پورسانتِ معرف چند درصد از اولین شارژِ زیرمجموعه‌ش باشه؟ (فقط معرف می‌گیره؛ عدد ۰ یعنی غیرفعال):"
)

ADMIN_ASK_WALLET_COST_PER_1K_TOKENS = "هزینه‌ی هر ۱۰۰۰ توکن (برای پاسخِ چت و تشخیصِ سفارش)، به تومان چقدر باشه؟ (یا از فرمولِ زیر با دکمه‌ی «محاسبه‌ی خودکار» بسازش)"
ADMIN_ASK_AI_COST_USD = "هزینه‌ی واقعیِ مدلِ AI به ازای هر ۱ میلیون توکن، به دلار چقدره؟ (عددِ اعشاری؛ همان نرخِ اعلامیِ سرویس‌دهنده):"
ADMIN_ASK_USD_TO_TOMAN_RATE = "نرخِ تبدیلِ دلار به تومان (که باید خودتون به‌روز نگهش دارید) چنده؟ (فقط عددِ صحیح):"
ADMIN_ASK_MARKUP_MULTIPLIER = "ضریبِ سودِ شما روی هزینه‌ی خامِ AI (که هزینه‌ی سرور هم توش لحاظ می‌شه) چند برابر باشه؟ (عددِ ۵ یعنی ۵ برابر):"
# PHASE 5D — کمیسیونِ درصدیِ سفارشِ موفق
ADMIN_ASK_COMMISSION_PERCENT = (
    "درصدِ کمیسیونِ پلتفرم از هر سفارشِ موفق چقدر باشه؟ (۰ تا ۱۰۰؛ اعشاری مجازه: ۰٫۵ یعنی نیم‌درصد)\n\n"
    "مبنای محاسبه: جمعِ ارزشِ اقلامِ همان گروه «پس از تخفیف و بدونِ هزینه‌ی ارسال».\n"
    "کمیسیون فقط بعد از تاییدِ پرداخت و از کیف‌پولِ خودِ فروشگاه‌دار کسر می‌شود."
)
COMMISSION_TOGGLED_ON = "🧾 کمیسیون روشن شد ✅ — {percent}٪ از هر سفارشِ موفق"
COMMISSION_TOGGLED_OFF = "🧾 کمیسیون خاموش شد ⏸ — دیگر از سفارش‌هایِ تازه گرفته نمی‌شود"
# P18 · A4: «هزینه‌ی تحلیلِ عکس» برداشته شد — تحلیلِ عکس فقط برایِ رسیدِ پرداخت است و هزینه‌یِ خودش را دارد.
ADMIN_ASK_WALLET_COST_VOICE_TRANSCRIPTION = "هزینه‌ی هر بار رونویسیِ پیامِ صوتی، به تومان چقدر باشه؟"
ADMIN_ASK_WALLET_COST_ORDER_DETECTION = "هزینه‌ی پیش‌فرضِ تشخیصِ سفارش (وقتی تعدادِ توکنِ واقعی در دسترس نباشه)، به تومان چقدر باشه؟"
ADMIN_ASK_WALLET_TOPUP_VALIDITY_MONTHS = "هر بار شارژِ کیف‌پول، چند ماه اعتبار داشته باشه؟"
# PHASE 5A
ADMIN_ASK_MIN_TOPUP_AMOUNT = "کمترینِ مبلغِ «شارژِ کیف‌پول» چقدر باشه؟ (تومان، ۱ تا ۱۰٬۰۰۰٬۰۰۰):"
ADMIN_ASK_WALLET_TRIAL_CREDIT = "اعتبارِ آزمایشیِ رایگانِ فروشگاه‌دارهای جدید، به تومان چقدر باشه؟"
ADMIN_ASK_WALLET_LOW_BALANCE_WARNING = "از چه موجودی‌ای (به تومان) به پایین‌تر، به فروشگاه‌دار هشدارِ «موجودی کم داره» بدیم؟"
# P30: سقفِ بدهیِ کمیسیون برایِ «ادامهٔ سفارش با اعتبارِ صفر».
ADMIN_ASK_COMMISSION_DEBT_CEILING = (
    "سقفِ بدهیِ هر فروشگاه چقدر باشد (تومان)؟ تا این مبلغ فروشگاه می‌تواند با "
    "اعتبارِ صفر هم سفارش بگیرد؛ بعد از آن دکمه‌هایِ سفارش و پرداختِ آنلاین می‌ایستند "
    "(چت باز می‌ماند).\n"
    "عددِ ۰ یعنی بی‌سقف."
)
ADMIN_ASK_GLOBAL_SYSTEM_PROMPT = (
    "دستور سراسری هوش مصنوعی رو بنویس (این روی دستور هر فروشگاه هم اضافه می‌شه). "
    "برای پاک کردنش، بنویس «خالی»."
)
ADMIN_ASK_REFERENCE_CHANNEL_LINK = "لینک کانال مرجع (که قبل از فعال‌سازی آزمایشی نمایش داده می‌شه) رو بفرست. برای پاک کردنش، بنویس «خالی»."
ADMIN_SETTING_SAVED = "✅ ذخیره شد."
PAYMENT_EVENTS_EMPTY = "هنوز هیچ رویدادِ پرداختی ثبت نشده."

# P18 · A1/B11: کدِ داخلیِ «چه چیزی کم است» ← راهنمایِ عملیِ کاربرپسند.
BALE_MISSING_HINTS: dict[str, str] = {
    "bot_token": "توکنِ رباتِ بله تنظیم نشده — «🔑 تنظیمات کلیدها › 🔵 توکن‌هایِ بله › 🔵 توکنِ رباتِ بله…».",
    "provider_token": "توکنِ درگاهِ بله‌پی (provider) ثبت نشده — «🔑 تنظیمات کلیدها › 🔵 توکن‌هایِ بله › 🔵 توکنِ درگاهِ بله‌پی…».",
    "admin_disabled": "کلیدِ سراسریِ بله‌پی خاموش است — «🔑 تنظیمات کلیدها › ✅ روشن‌کردنِ بله‌پی از فروشگاه‌دارها».",
    "shop_disabled": "کلیدِ بله‌پیِ خودِ فروشگاه خاموش است — «💳 پرداختِ آنلاینِ سفارش‌ها › ⚙️ روش‌هایِ پرداختِ مشتری › ✅ روشن‌کردنِ بله‌پی».",
    # P41: پولِ سفارش فقط با جفتِ کاملِ خودِ فروشگاه حرکت می‌کند؛ این دو علت یعنی آن جفت ناقص است.
    "shop_bale_bot_token": (
        "توکنِ رباتِ بله‌یِ خودت ثبت نشده — «💳 پرداختِ آنلاینِ سفارش‌ها»، خانه‌یِ ۱. بدونِ آن "
        "صورتحساب در چتِ خودت ساخته نمی‌شود."
    ),
    "shop_provider_token": (
        "توکنِ درگاهِ بله‌پیِ خودت ثبت نشده — «💳 پرداختِ آنلاینِ سفارش‌ها»، خانه‌یِ ۲ (از پنلِ "
        "پذیرندگانِ بله‌پی)."
    ),
    # P26: لینکِ پرداخت یعنیِ چتِ رباتِ بله؛ بیِ نامِ کاربری (از getMe) هیچ لینکی ساخته نمی‌شود.
    "pay_bot_username": (
        "رباتِ پرداختِ بله هنوز شناخته نشده (نامِ کاربری‌اش از بله خوانده نشد) — «🔑 تنظیمات کلیدها › "
        "🔵 توکن‌هایِ بله › 🔵 توکنِ رباتِ بله…» را یک‌بار دوباره ذخیره کن؛ اگر باز هم نشد، اینترنتِ سرور به tapi.bale.ai "
        "دسترسی ندارد."
    ),
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
    "ℹ️ بله‌پی روشن شد، ولی توکنِ درگاهِ سراسری (provider) در پنلِ تو ثبت نشده.\n"
    "از P41 این دیگر مانعِ هیچ فروشنده‌ای نیست: پرداختِ سفارش فقط با «توکنِ رباتِ بله + توکنِ "
    "درگاه» *خودِ فروشگاه* ساخته می‌شود و پول مستقیم به کیف‌پولِ او می‌نشیند؛ فروشگاه‌هایی که "
    "هر دو را در «💳 پرداختِ آنلاینِ سفارش‌ها» نگذاشته‌اند دکمهٔ بله‌پی را به مشتری نشان نمی‌دهند "
    "(نه این‌که پول پیشِ پلتفرم بنشیند).\n"
    "برایِ سراسری‌کردنش: «🔑 تنظیمات کلیدها › 🔵 توکن‌هایِ بله › 🔵 توکنِ درگاهِ بله‌پی…»."
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
            else "در «🔑 تنظیمات کلیدها › 🔵 توکن‌هایِ بله › 🔵 توکنِ رباتِ بله…» بگذار (یا BALE_BOT_TOKEN در .env).",
        ),
        (
            "توکنِ درگاهِ بله‌پی (provider)",
            provider_set,
            "منبع: پنلِ ادمین (پشتیبانِ سراسری). فروشگاه‌دار هم می‌تواند توکنِ خودش را بگذارد که اولویت دارد."
            if provider_set
            else "در «🔑 تنظیمات کلیدها › 🔵 توکن‌هایِ بله › 🔵 توکنِ درگاهِ بله‌پی…» بگذار.",
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
    from app.utils.jalali import format_jalali_datetime

    if not events:
        return PAYMENT_EVENTS_EMPTY
    lines = ["🔎 آخرین رویدادهایِ پرداخت (جدید ← قدیم):\n"]
    for e in events:
        when = format_jalali_datetime(e.created_at) if e.created_at else "—"
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


# P19 · مرتب‌سازیِ پنلِ ادمین: چهلِ تنظیمِ تخت در یک صفحه ⇒ هیچ‌کس پیدایشان نمی‌کند.
# حالا صفحه‌یِ اصلی فقط کلیدهایِ روشن/خاموش + چند دسته است و مقدارها داخلِ دسته‌ها ویرایش می‌شوند.
ADMIN_SETTINGS_GROUPS: tuple[tuple[str, str], ...] = (
    ("ai", "🤖 هوش مصنوعی و دستورِ سراسری"),
    ("pricing", "🪙 نرخ‌گذاریِ مصرفِ AI"),
    ("payments", "💳 پرداخت، کارت و شارژ"),
    ("bale", "🔵 توکن‌هایِ بله"),
    # P49-الف: کانالِ سوم، دستهٔ اختصاصیِ خودش (سوییچِ رونمایی + سه مقدارِ احرازِ متا).
    ("instagram", "🟣 اینستاگرام"),
    ("messaging", "📩 پیامک و پشتیبانیِ پلتفرم"),
    ("shops", "🏪 فروشگاه‌دارها و گزارش‌ها"),
    ("branding", "🧴 بیوگرافیِ ربات‌ها"),
    ("ops", "🗄 بکاپ و نگهداریِ دیتابیس"),
)

ADMIN_SETTINGS_GROUP_LABELS: dict[str, str] = dict(ADMIN_SETTINGS_GROUPS)
ADMIN_SETTINGS_GROUP_KEYS: frozenset[str] = frozenset(ADMIN_SETTINGS_GROUP_LABELS)

# P47: درِ «کلیدها» حالا یکی است: کلید ۱ تا کلید ۱۰، هرِ کلید با مدل/آدرس/سقفِ همزمانیِ خودش.
ADMIN_AI_GROUP_KEYS_POINTER = (
    "🔑 برایِ واردکردنِ کلیدِ API به منویِ «🔑 استخرِ کلیدهایِ AI» برو: تا ۱۰ کلید، هرِ کلید با "
    "مدل، آدرس و سقفِ همزمانیِ خودش. دو مقدارِ این صفحه فقط پیش‌فرضِ سراسری هستند."
)

ADMIN_SETTING_GROUP: dict[str, str] = {
    # P47: چهار کلید/آدرسِ «اصلی و پشتیبان» از این صفحه رفتند؛ جایِ آن‌ها «کلید ۱ … کلید ۱۰» است
    # (هرِ کلید با مدل، آدرس و سقفِ همزمانیِ خودش). این دو پیش‌فرضِ سراسری می‌مانند تا نصبی که
    # استخر نسازد دقیقاً مثلِ قبل کار کند.
    "ai_model": "ai",
    "ai_base_url": "ai",
    "global_ai_system_prompt": "ai",
    "global_ai_prompt_sales": "ai",
    "global_ai_prompt_consultation": "ai",
    "reference_channel_link": "ai",
    "wallet_cost_per_1k_tokens_toman": "pricing",
    "ai_cost_usd_per_1m_tokens": "pricing",
    "usd_to_toman_rate": "pricing",
    "wallet_markup_multiplier": "pricing",
    "wallet_cost_receipt_analysis_toman": "pricing",
    "wallet_cost_voice_per_minute_toman": "pricing",
    "wallet_cost_receipt_per_1k_tokens": "pricing",
    "wallet_cost_voice_transcription_toman": "pricing",
    "wallet_cost_order_detection_toman": "pricing",
    "commission_percent": "pricing",
    "zarinpal_merchant_id": "payments",
    "platform_card_number": "payments",
    "platform_card_holder_name": "payments",
    "min_topup_amount_toman": "payments",
    "wallet_topup_validity_months": "payments",
    "wallet_trial_credit_toman": "payments",
    "wallet_low_balance_warning_toman": "payments",
    "commission_debt_ceiling_toman": "payments",
    "bale_bot_token": "bale",
    "bale_provider_token": "bale",
    # P49-الف: سه مقدارِ متا که بدونِ هیچ‌کدام اتصال ممکن نیست (دستهٔ «🟣 اینستاگرام»).
    "instagram_app_id": "instagram",
    "instagram_platform_instructions": "instagram",
    "instagram_app_secret": "instagram",
    "instagram_webhook_verify_token": "instagram",
    "sms_api_key": "messaging",
    "sms_sender_number": "messaging",
    "sms_otp_template": "messaging",
    "platform_support_username": "messaging",
    "platform_support_phone": "messaging",
    "platform_support_text": "messaging",
    "referral_reward_value": "shops",
    "grace_period_hours": "shops",
    "periodic_report_frequency_days": "shops",
    "nightly_report_hour_utc": "shops",
    "branding_text": "branding",
    "branding_check_minutes": "branding",
    # P44 · موردِ ۵۱: «ماه» چند روز باشد + نگهداریِ فایل‌هایِ بکاپ — هر دو در دستهٔ تازهٔ «ops».
    "month_length_days": "ops",
    "backup_retention_days": "ops",
}

ADMIN_SETTINGS_STALE_GROUP = "این دسته باز نیست. «🔑 تنظیمات کلیدها» را دوباره باز کن."

# =============================================================================
# P49-الف — کانالِ اینستاگرام (فقط APIِ رسمیِ متا)
# =============================================================================
# دو بخش دارد: آنچه ادمینِ پلتفرم تنظیم می‌کند (بالا) و آنچه فروشگاه‌دار در پنل خودش می‌بیند
# (پایین). متن‌ها عمداً کوتاه‌اند و هر صفحه می‌گوید بعدیِ کار چیست؛ راهنمایِ بلند در P49-پ می‌آید.
INSTAGRAM_BUTTON = "🟣 اینستاگرام"
INSTAGRAM_TOGGLED_ON = "کانالِ اینستاگرام روشن شد؛ دکمهٔ «🟣 اینستاگرام» در پنلِ فروشگاه‌دارها دیدنی شد."
INSTAGRAM_TOGGLED_OFF = "کانالِ اینستاگرام خاموش شد؛ دکمه‌یِ پنل هم رفت و هیچ پیامی پاسخ داده نمی‌شود."
# پ۱۱۴ · سوئیچِ دیدنی‌بودنِ دکمهٔ «🌐 پنلِ وب» (دیدنی‌بودن = این سوئیچ + تنظیم‌شدنِ رازِ پنجرهٔ وب)
WEB_PANEL_TOGGLED_ON = "دکمهٔ «🌐 پنلِ وب» در پنلِ فروشگاه‌دارها دیدنی شد (اگر رازِ پنجرهٔ وب هم تنظیم شده باشد)."
WEB_PANEL_TOGGLED_OFF = "دکمهٔ «🌐 پنلِ وب» از پنلِ فروشگاه‌دارها محو شد؛ لینک‌هایِ صادرشده‌یِ قبلی همچنان کار می‌کنند تا خودشان منقضی یا ابطال شوند."

# پ۶۰ · خواستهٔ مالکِ محصول: متنِ سراسریِ هوشمندسازیِ اینستاگرام (فقط سوپرادمین)
ADMIN_ASK_INSTAGRAM_PLATFORM_INSTRUCTIONS = (
    "متنِ پیش‌فرضِ سراسریِ اینستاگرام رو بنویس (حداکثر ۲۰۰۰ حرف).\n\n"
    "این متن به همهٔ فروشگاه‌هایی اضافه می‌شه که اینستاگرامشون هوشمند شده — کنارِ متنِ "
    "خودِ فروشگاه، نه جایِ آن. برایِ پاک‌کردن «خالی» بنویس."
)
ADMIN_INVALID_INSTAGRAM_PLATFORM_INSTRUCTIONS = "این متن نباید بیشتر از ۲۰۰۰ حرف باشد."


ADMIN_ASK_INSTAGRAM_APP_ID = (
    "«App ID» اپلیکیشنِ متا را بفرست (از developers.facebook.com ⇒ اپِ خودت ⇒ Settings ⇒ Basic).\n\n"
    "این عدد راز نیست و در لینکِ اتصال هم نوشته می‌شود. فقط رقم و حروفِ انگلیسی باشد."
)
ADMIN_ASK_INSTAGRAM_APP_SECRET = (
    "«App Secret» همان اپِ متا را بفرست.\n\n"
    "این راز است: رمزنگاری‌شده ذخیره می‌شود، فقط ماسک‌شده نمایش داده می‌شود و با آن امضایِ "
    "درخواست‌هایِ متا بررسی می‌شود. در پنلِ متا در Settings ⇒ Basic ⇒ App Secret می‌بینیش."
)
ADMIN_ASK_INSTAGRAM_VERIFY_TOKEN = (
    "یکِ توکنِ تأییدِ خودساخته بنویس (مثلاً یکِ رشتهٔ بلندِ تصادفی).\n\n"
    "همین رشته را باید در پنلِ متا در بخشِ Webhooks ⇒ Instagram ⇒ Verify token هم وارد کنی؛ "
    "متا با آن ثابت می‌کند که تو صاحبِ این سرویس هستی. اگر اشتباه بنویسی، متا وب‌هوک را فعال نمی‌کند."
)
INSTAGRAM_WEBHOOK_PATH_TEXT = "🌐 آدرسِ وب‌هوک برایِ پنلِ متا:"
INSTAGRAM_WEBHOOK_PATH_MISSING = (
    "🌐 برایِ دیدنِ آدرسِ وب‌هوک، مقدارِ INSTAGRAM_PUBLIC_BASE_URL را در فایلِ تنظیماتِ سرور پر کن "
    "(آدرسِ HTTPSِ همین سرویس)."
)
ADMIN_INVALID_INSTAGRAM_APP_ID = (
    "App ID باید فقط رقم یا حروفِ انگلیسی باشد (۲ تا ۶۴ نویسه، بدونِ فاصله). همان چیزی است "
    "در Settings ⇒ Basic ⇒ App ID می‌بینی."
)
ADMIN_INVALID_INSTAGRAM_SECRET = (
    "این مقدار ۸ تا ۵۱۲ نویسه بدونِ فاصله باشد (همان رشته‌ای که خودت ساختی یا در پنلِ متا "
    "می‌بینی). چیزی جز رقم، حرف، نقطه، خطِ تیره و زیرخط نگذار."
)

# --- صفحهٔ فروشگاه‌دار ---
INSTAGRAM_NOT_CONNECTED = "🟣 اینستاگرام: هنوز اکانتی وصل نکرده‌ای."
INSTAGRAM_CONNECTED_AS = "🟣 اینستاگرام: وصل است — {username}"
INSTAGRAM_REPLY_ON_TOAST = "پاسخ‌گوییِ خودکار در اینستاگرام روشن شد"
INSTAGRAM_REPLY_OFF_TOAST = "پاسخ‌گوییِ خودکار در اینستاگرام خاموش شد؛ پیام‌ها خوانده می‌شوند ولی جواب نمی‌روند"
INSTAGRAM_UNBOUND_TOAST = "اتصالِ اینستاگرام حذف شد؛ توکن از سرور پاک شد و پاسخ‌گویی می‌ایستد"
INSTAGRAM_NO_APP_ID = (
    "فعلاً نمی‌شود اتصال را شروع کرد: ادمینِ پلتفرم هنوز «App ID» و «App Secret» را در "
    "تنظیماتِ اینستاگرام وارد نکرده است."
)
INSTAGRAM_NO_PUBLIC_URL = (
    "فعلاً نمی‌شود اتصال را شروع کرد: آدرسِ عمومیِ HTTPSِ این سرویس در تنظیماتِ سرور "
    "(INSTAGRAM_PUBLIC_BASE_URL) وارد نشده، پس متا جایی برایِ بازگشتِ تو ندارد."
)
INSTAGRAM_LINK_SENT = (
    "🔗 این لینک را در مرورگر باز کن، واردِ اکانتِ اینستاگرامِ خودت بشو و «Allow Access» را بزن.\n\n"
    "{link}\n\n"
    "بعد ازِ تأیید، یکِ صفحهٔ کوتاه می‌بینی و همین‌جا در پنل وضعیت «وصل است» می‌شود."
)
# پ۶۰ · متنِ هوشمندسازیِ اینستاگرامِ خودِ فروشگاه
INSTAGRAM_INSTRUCTIONS_BUTTON = "📝 متنِ هوشمندسازیِ اینستاگرام"
INSTAGRAM_INSTRUCTIONS_ASK = (
    "✍️ بنویس رباتت در اینستاگرام چطور جواب بده (حداکثر ۱۵۰۰ حرف).\n\n"
    "مثلاً: لحنِ صمیمی، ساعتِ پاسخ‌گویی، چه سؤالاتی را جواب ندهد، چه چیزی را به دایرکت بکشاند.\n"
    "این متن جایِ دستورِ اصلیِ فروشگاه را نمی‌گیرد، کنارِ آن می‌نشیند.\n"
    "برایِ پاک‌کردن بنویس: «خالی»"
)
INSTAGRAM_INSTRUCTIONS_SAVED = "متنِ هوشمندسازیِ اینستاگرام ذخیره شد ✅"
INSTAGRAM_INSTRUCTIONS_CLEARED = "متنِ هوشمندسازیِ اینستاگرام پاک شد؛ فقط تنظیماتِ عمومی اجرا می‌شه."
INSTAGRAM_INSTRUCTIONS_TOO_LONG = "این متن بیشتر از ۱۵۰۰ حرف است؛ کوتاه‌ترش کن."
INSTAGRAM_INSTRUCTIONS_LINE = "• متنِ هوشمندسازیِ اینستاگرام: {state}"


INSTAGRAM_GREETING_ASK = (
    "✍️ متنِ خوشآمدِ اینستاگرام را بنویس (حداکثر ۵۰۰ حرف).\n\n"
    "برایِ پاک‌کردن بنویس: «خالی»"
)
INSTAGRAM_GREETING_SAVED = "متنِ خوشآمد ذخیره شد ✅"
INSTAGRAM_GREETING_CLEARED = "متنِ خوشآمد پاک شد."
INSTAGRAM_GREETING_MISSING = "اول از «👋 متنِ خوشآمد» یکِ متن بنویس."
INSTAGRAM_TEST_SENT = (
    "🧪 پیامِ تست به متا فرستاده شد. اگر چند لحظه در دایرکتِ خودت ندیدیش، «آخرین خطا»یِ همین "
    "صفحه را بخون (متا فقط تا ۲۴ ساعت بعدِ آخرین پیامِ مشتری اجازهٔ ارسال می‌دهد)."
)
INSTAGRAM_TEST_REJECTED = "🧪 متا پیامِ تست را نپذیرفت؛ دلیلش را در «آخرین خطا»یِ همین صفحه می‌بینی."
INSTAGRAM_LAST_ERROR = "⚠️ آخرین خطا: {error}"
INSTAGRAM_DM_RULE_TEXT = (
    "⏱ قاعدهٔ متا: تا ۲۴ ساعت بعدِ آخرین پیامِ مشتری می‌توانی جواب بفرستی؛ بعد از آن پنجره بسته "
    "می‌شود و ربات پیامِ تازه‌ای نمی‌فرستد."
)
INSTAGRAM_PAYMENTS_NOTE = (
    "💳 پرداخت: همان لینکِ بله‌پی و همان کارت‌به‌کارتِ امروز، بدونِ هیچ مسیرِ تازه‌ای. "
    "اگر بله‌پیِ فروشگاه کامل باشد مشتری لینکِ پرداخت را در دایرکت می‌گیرد؛ اگر نباشد "
    "دستورالعملِ کارت‌به‌کارتِ خودت را می‌بیند."
)
INSTAGRAM_GUIDE_INTRO = (
    "🟣 اینستاگرام — راهنمایِ فعال‌سازی (کوتاه)\n\n"
    "این کانال فقط با APIِ رسمیِ متا کار می‌کند. هیچ‌وقت رمزِ اکانتت را به کسی (حتی به ما) نمی‌دهی؛ "
    "تو در صفحهٔ خودِ اینستاگرام/فیس‌بوک اجازه می‌دهی و تمام. مسیرِ غیررسمی استفاده نمی‌شود، چون "
    "هم رمزِ تو را می‌خواهد هم خطرِ بستنِ اکانت دارد.\n\n"
    "۱) اکانتِ اینستاگرام را Professional (تجاری/کریتور) کن — از تنظیماتِ خودِ اینستاگرام.\n"
    "۲) آن را به یکِ صفحهٔ فیس‌بوک وصل کن.\n"
    "۳) ادمینِ پلتفرم این سه مقدار را در «🟣 اینستاگرام»ِ پنلِ ادمین پر کند: App ID، App Secret، "
    "توکنِ تأیید. اگر پر نبود، دکمهٔ اتصال کار نمی‌کند.\n"
    "۴) اینجا «🔗 اتصالِ اکانت اینستاگرام» را بزن، وارد شو و اجازه بده؛ وضعیت «وصل است» می‌شود.\n"
    "۵) بعد ازِ اتصال، ادمین در پنلِ متا ⇒ Webhooks ⇒ Instagram، آدرسِ وب‌هوک را وارد و توکنِ تأیید "
    "را ست می‌کند و رویِ «Instagram Direct» تیک می‌زند.\n\n"
    "راهنمایِ بلندِ مرحله‌به‌مرحله (با تصویر) در فازِ بعد اضافه می‌شود."
)
INSTAGRAM_STEPS_CHECKLIST = (
    "برایِ اتصالِ اینستاگرام این چهار کار لازم است:\n\n"
    "۱) اکانتِ اینستاگرام Professional باشد\n"
    "۲) به یکِ صفحهٔ فیس‌بوک وصل باشد\n"
    "۳) به ما بگو تا لینکِ اتصال را بدهیم («🔗 اتصالِ اکانت اینستاگرام»)\n"
    "۴) بعد ازِ اتصال، ادمین وب‌هوک را در پنلِ متا با توکنِ تأیید فعال کند"
)
INSTAGRAM_SCREEN_INTRO = "🟣 اینستاگرام — پیام‌هایِ دایرکتِ فروشگاه تو با همان هوشِ مصنوعی و همان کیف‌پول پاسخ داده می‌شوند."


# پ۶۳ · خواستهٔ مالکِ محصول: «پنلِ ویژهٔ مدیریتیِ اینستاگرام» در پنلِ خودِ فروشگاه — اولینِ حلقه:
# خاموش‌سازیِ *زمان‌دارِ* کانال (بی‌قطعِ اتصال) و گزارشِ فعالیتِ دایرکت از دیتابیسِ خودمان.
INSTAGRAM_MUTE_BUTTON = "⏸ خاموش‌سازیِ موقت"
INSTAGRAM_ACTIVITY_BUTTON = "📊 فعالیتِ اینستاگرام"
INSTAGRAM_MUTE_TITLE = "⏸ خاموش‌سازیِ موقتِ اینستاگرام"
INSTAGRAM_MUTE_INTRO = (
    "در این مدت هیچ پاسخی برایِ دایرکت و کامنت ساخته نمی‌شود، ولی اتصال، توکن و بقیهٔ تنظیماتِ تو "
    "دست‌نخورده می‌مانند و بعد ازِ پایانِ مهلت همه‌چیز خودش برمی‌گردد."
)
INSTAGRAM_MUTE_ON_TOAST = "⏸ اینستاگرام موقتاً خاموش شد"
INSTAGRAM_MUTE_OFF_TOAST = "▶️ اینستاگرام دوباره روشن شد"
INSTAGRAM_MUTE_INVALID = "آن گزینه در فهرستِ مهلت‌ها نیست."
INSTAGRAM_MUTED_LINE = "• ⏸ خاموش تا: {until} (پاسخِ خودکار متوقف است)"
INSTAGRAM_LIVE_LINE = "• وضعیتِ کانال: ✅ روشن"
INSTAGRAM_ACTIVITY_TITLE = "📊 فعالیتِ اینستاگرام — {when}"
INSTAGRAM_ACTIVITY_NOTE = (
    "کامنت‌ها در دیتابیسِ ما ذخیره نمی‌شوند (متا فقط رویداد می‌دهد و پاسخ زیرِ همان کامنت می‌نشیند)، "
    "پس این صفحه فقط گفتگوهایِ دایرکت را می‌شمارد. اگر نگهبانِ محتوا کامنتی را گرفته باشد، ردیفش در "
    "«📜 گزارشِ ممیزی» هست."
)


def instagram_mute_line(account) -> str:
    from app.services import instagram_service
    from app.utils.jalali import format_jalali_datetime

    until = instagram_service.mute_until(account)
    if until is None:
        return INSTAGRAM_LIVE_LINE
    return INSTAGRAM_MUTED_LINE.format(until=format_jalali_datetime(until))


def instagram_mute_screen_text(account) -> str:
    lines = [INSTAGRAM_MUTE_TITLE, "", INSTAGRAM_MUTE_INTRO, "", instagram_mute_line(account)]
    lines.append("")
    lines.append("• اتصالِ اکانت و متنِ هوشمندسازی با خاموش‌کردنِ موقت پاک نمی‌شوند.")
    return "\n".join(lines)


def instagram_activity_text(summary: dict, account) -> str:
    from app.utils.jalali import format_jalali_datetime

    lines = [INSTAGRAM_ACTIVITY_TITLE.format(when=format_jalali_datetime(summary["at"]))]
    lines.append(f"• گفتگوهایِ دایرکت در ۷ روز: {fa_number(summary['chats_7d'])}")
    lines.append(f"• پیامِ مشتری در ۲۴ ساعت: {fa_number(summary['since_24h'])}")
    lines.append(f"• پیامِ مشتری در ۷ روز: {fa_number(summary['since_7d'])}")
    lines.append(instagram_mute_line(account))
    if account is not None and account.last_error:
        lines.append(INSTAGRAM_LAST_ERROR.format(error=account.last_error))
    lines += ["", INSTAGRAM_ACTIVITY_NOTE]
    return "\n".join(lines)


# پ۷۳ · خواستهٔ مالک (حلقهٔ سومِ اینستاگرام): «چند کامنت آمد، به چندتا جواب دادیم، خرجش چقدر بود».
INSTAGRAM_COMMENTS_BUTTON = "🗨 گزارشِ کامنت‌ها"
INSTAGRAM_COMMENTS_INVALID = "آن بازه یا صفحه در فهرست نیست."
INSTAGRAM_COMMENTS_TITLE = "🗨 گزارشِ کامنت‌ها — {when}"
INSTAGRAM_COMMENTS_SUMMARY = (
    "• {label}: {total} کامنت · ✅ {replied} جواب رفت · ⏸ {skipped} جواب نرفت · ⚠️ {failed} بی‌نتیجه"
)
INSTAGRAM_COMMENTS_SPEND = "• خرجِ هوشِ مصنوعیِ همین کامنت‌ها: {cost} · {tokens} توکن"
INSTAGRAM_COMMENTS_SPEND_ZERO = "• کامنت‌هایِ جواب‌رفته هزینه‌ای در کیف‌پول نساخته‌اند (صفر تومان)."
INSTAGRAM_COMMENTS_REASONS = "• دلیلِ جواب‌نرفتن: {text}"
INSTAGRAM_COMMENTS_EMPTY = (
    "در این بازه هیچِ کامنتی دیده نشد. اگر پاسخِ خودکار به کامنت‌ها یا کانال خاموش باشد، "
    "کامنت‌ها فقط خوانده و رد می‌شوند — و همان‌جا در این فهرست ثبت می‌شوند."
)
INSTAGRAM_COMMENTS_LIST = "آخرینِ کامنت‌ها (صفحهٔ {page} از {pages}):"
INSTAGRAM_COMMENTS_NOTE = (
    "• این شمارش از همین نسخه به این سو است: پیش ازِ این کامنت هیچ‌جا ذخیره نمی‌شد، پس بازه‌هایِ "
    "قدیمی صفر می‌ماند (عددِ ساختگی نیست). مبلغِ «خرج» همان چیزی است که از کیف‌پولِ خودت کم شده، "
    "نه تخمینِ جدا. کامنت‌ها مشتریِ CRM نمی‌شوند."
)
COMMENT_REASON_LABELS: dict[str, str] = {
    "account_off": "اتصالِ اینستاگرام غیرفعال بود",
    "comments_off": "پاسخِ خودکار به کامنت خاموش بود",
    "muted": "کانال موقتاً خاموش بود",
    "sender_blocked": "این حساب در فهرستِ «جواب نده» است",
    "shop_inactive": "فروشگاه یا حالتِ نگهداری خاموش بود",
    "no_owner": "صاحبِ فروشگاه پیدا نشد",
    "moderation_block": "نگهبانِ محتوا کامنت را مسدود کرد",
    "no_ai_key": "کلیدِ هوشِ مصنوعی تنظیم نشده است",
    "no_ai_pool": "هیچِ کلیدِ فعالی در استخر نبود",
    "no_access": "اعتبار یا دسترسیِ چت کافی نبود",
    "empty_reply": "پاسخِ ساخته‌شده خالی بود",
    "ai_error": "هوشِ مصنوعی جواب نداد",
    "send_failed": "پاسخ به اینستاگرام نرسید",
    "unknown": "بدونِ دلیلِ ثبت‌شده",
}
COMMENT_OUTCOME_ICONS = {"replied": "✅", "skipped": "⏸", "failed": "⚠️", "received": "⏳"}


def comment_window_label(window: str) -> str:
    from app.services.instagram_service import COMMENT_WINDOWS

    return next((label for key, _days, label in COMMENT_WINDOWS if key == window), window)


def comment_reason_label(reason: str | None) -> str:
    return COMMENT_REASON_LABELS.get(reason or "unknown", reason or COMMENT_REASON_LABELS["unknown"])


def instagram_comment_line(index: int, row) -> str:
    """یکِ خطِ فهرست: نتیجه، متنِ کوتاه‌شده، چه‌کسی و کِی — بدونِ هیچ شناسهٔ فنی."""
    from app.utils.jalali import format_jalali_datetime

    icon = COMMENT_OUTCOME_ICONS.get(getattr(row, "outcome", "") or "", "•")
    who = "@" + (row.username or "بی‌نام") if getattr(row, "username", "") else "بی‌نام"
    body = clip((row.text or "").replace("\n", " ") or "—", 64)
    when = format_jalali_datetime(row.created_at) if getattr(row, "created_at", None) else "—"
    tail = "" if row.outcome == "replied" else f" · {comment_reason_label(row.reason)}"
    return f"{fa_number(index)}. {icon} «{body}» — {who} · {when}{tail}"


def instagram_comments_text(report: dict) -> str:
    from app.utils.jalali import format_jalali_datetime

    lines = [INSTAGRAM_COMMENTS_TITLE.format(when=format_jalali_datetime(report["at"])), ""]
    lines.append(
        INSTAGRAM_COMMENTS_SUMMARY.format(
            label=comment_window_label(report["window"]),
            total=fa_number(report["total"]),
            replied=fa_number(report["replied"]),
            skipped=fa_number(report["skipped"]),
            failed=fa_number(report["failed"]),
        )
    )
    if report["replied"] or report["cost"]:
        if report["cost"]:
            lines.append(
                INSTAGRAM_COMMENTS_SPEND.format(cost=format_toman(report["cost"]), tokens=fa_grouped(report["tokens"]))
            )
        else:
            lines.append(INSTAGRAM_COMMENTS_SPEND_ZERO)
    reasons = [f"{comment_reason_label(reason)} {fa_number(count)}" for reason, count in report["reasons"]]
    if reasons:
        lines.append(INSTAGRAM_COMMENTS_REASONS.format(text=" · ".join(reasons)))
    if not report["items"]:
        lines += ["", INSTAGRAM_COMMENTS_EMPTY]
    else:
        first = report["page"] * report["page_size"] + 1
        lines += ["", INSTAGRAM_COMMENTS_LIST.format(page=fa_number(report["page"] + 1), pages=fa_number(report["pages"]))]
        lines += [instagram_comment_line(first + offset, row) for offset, row in enumerate(report["items"])]
    lines += ["", INSTAGRAM_COMMENTS_NOTE]
    return "\n".join(lines)


# ------------------------------------------------------------------ پ۷۷ · «به این حساب جواب نده» + فایلِ اکسل
INSTAGRAM_BLOCKS_BUTTON = "🚫 حساب‌هایِ جواب‌نده"
INSTAGRAM_EXPORT_BUTTON = "📥 فایلِ اکسلِ کامنت‌ها"
INSTAGRAM_EXPORT_FILENAME = "کامنت-های-اینستاگرام.xlsx"
INSTAGRAM_BLOCKS_TITLE = "🚫 حساب‌هایی که ربات به آن‌ها جواب نمی‌دهد"
INSTAGRAM_BLOCKS_EMPTY = (
    "فهرست خالی است. از «🗨 گزارشِ کامنت‌ها» می‌توانی رویِ هر کامنت بزنی تا آن حساب در این فهرست "
    "بماند؛ هر وقت هم خواستی از همین‌جا آزادش می‌کنی."
)
INSTAGRAM_BLOCKS_LIST = "• {name} — افزوده‌شده در {when}"
INSTAGRAM_BLOCKS_NOTE = (
    "• این فهرست فقط به پاسخِ خودکارِ کامنت‌ها دست می‌زند: کامنت خوانده و در گزارش ثبت می‌شود، "
    "ولی پاسخی نمی‌رود و هزینه‌ای هم نمی‌سازد. دایرکت و پرداختِ سفارش عوض نمی‌شوند."
)
INSTAGRAM_BLOCKS_ADD_ASK = (
    "نامِ کاربری را بنویس (بدونِ @ هم قبول می‌شود). برایِ بی‌خیال شدن «خالی» را بزن."
)
INSTAGRAM_BLOCK_ADDED = "به فهرستِ «جواب نده» افزوده شد."
INSTAGRAM_BLOCK_EXISTS = "این حساب از پیش در فهرست است."
INSTAGRAM_BLOCK_REMOVED = "از فهرستِ «جواب نده» برداشته شد."
INSTAGRAM_BLOCK_INVALID = "آن نامِ کاربری قابلِ ذخیره نیست."
INSTAGRAM_BLOCKS_ADD_CANCELLED = "افزودن لغو شد؛ چیزی عوض نشد."
INSTAGRAM_BLOCK_FULL = "فهرست پر است (سقفِ هر فروشگاه دویست حساب است)."
INSTAGRAM_BLOCK_NO_USER = "این کامنت نامِ کاربری ندارد؛ پس نمی‌توان آن را مسدود کرد."
INSTAGRAM_EXPORT_EMPTY = "در این بازه کامنتی نبود که فایلش ساخته شود."
INSTAGRAM_EXPORT_READY = "فایلِ کامنت‌هایِ {label} آماده شد ({count} ردیف)."
INSTAGRAM_EXPORT_TRUNCATED = "• بازه بزرگ‌تر از سقفِ فایل بود؛ فقط {limit} ردیفِ جدیدتر در فایل است."
INSTAGRAM_BLOCK_ERASE_BUTTON = "🗑 حذفِ دادهٔ این حساب"
INSTAGRAM_ERASE_TITLE = "🗑 حذفِ داده‌هایِ @{name}"
INSTAGRAM_ERASE_ASK = (
    "در این فروشگاه {events} کامنت از این حساب دیده شده است. با تایید، همان ردیف‌هایِ کامنت و ردیفِ این "
    "حساب در فهرستِ «جواب نده» پاک می‌شوند. برگشتی ندارد."
)
INSTAGRAM_ERASE_SCOPE = (
    "• آنچه اینجا پاک می‌شود فقط رویدادهایِ کامنت و ردیفِ فهرستِ «جواب نده» است. متنِ گفتگوهایِ "
    "دایرکت و دادهٔ آن مخاطب در «🧾 دادهٔ دایرکت» پاک می‌شود؛ سفارش‌ها و دفترِ کیف‌پول همیشه می‌مانند."
)
INSTAGRAM_ERASE_CONFIRM_BUTTON = "✅ بله، پاک کن"
INSTAGRAM_ERASE_CANCEL_BUTTON = "⬅️ بی‌خیال، چیزی پاک نشود"
INSTAGRAM_ERASE_DONE = "پاک شد: {events} رویدادِ کامنت · {blocks} ردیفِ فهرستِ جواب‌نده."
INSTAGRAM_ERASE_NOTHING = "هیچ کامنتی از این حساب ثبت نشده بود؛ فقط ردیفِ فهرست برداشته شد."
INSTAGRAM_ERASE_INVALID = "آن حساب در فهرستِ این فروشگاه نیست."

# پ۱۱۲ · حقِ فراموشی رویِ کانالِ دایرکت (ادامهٔ پ۸۴، که فقط کامنت‌ها را پوشش می‌داد)
INSTAGRAM_DM_BUTTON = "🧾 دادهٔ دایرکت"
INSTAGRAM_DM_TITLE = "🧾 دادهٔ دایرکتِ اینستاگرام — {count} مخاطب"
INSTAGRAM_DM_EMPTY = "هنوز هیچ گفتگویِ دایرکتی برایِ این فروشگاه ثبت نشده است."
INSTAGRAM_DM_NOTE = (
    "• شمارِ پیام رویِ هر دکمه همان چیزی است که پاک می‌شود؛ متنِ پیام‌ها در این صفحه نمایش داده "
    "نمی‌شود. هر حذف در دفترِ ممیزی ثبت می‌شود."
)
INSTAGRAM_DM_ASK = (
    "این مخاطب {messages} پیام دارد. با تایید، متنِ همهٔ پیام‌هایش پاک می‌شود و نام، نامِ کاربری، "
    "شماره، یادداشت و برچسب‌هایِ CRMِ او بی‌نام می‌گردد. برگشتی ندارد."
)
INSTAGRAM_DM_SCOPE = (
    "• آنچه پاک *نمی‌شود*: ردیفِ مشتری، سفارش‌ها، سبد، کمیسیون و دفترِ کیف‌پول — حذفِ آن‌ها "
    "زنجیرهٔ مالی را می‌شکند (همان تصمیمِ «حذفِ حساب» در پ۶۵)."
)
INSTAGRAM_DM_DONE = "پاک شد: {messages} پیامِ گفتگو · هویت و CRMِ این مخاطب بی‌نام شد."
INSTAGRAM_DM_NOTHING = "این مخاطب پیامی برایِ پاک‌کردن نداشت؛ فقط هویت و CRM بی‌نام شد."
INSTAGRAM_DM_INVALID = "این مخاطب در فروشگاهِ تو پیدا نشد (یا مشتریِ همین کانالِ اینستاگرام نیست)."


def instagram_blocks_text(rows: list) -> str:
    from app.utils.jalali import format_jalali_datetime

    lines = [INSTAGRAM_BLOCKS_TITLE, ""]
    if not rows:
        lines.append(INSTAGRAM_BLOCKS_EMPTY)
    else:
        for row in rows:
            lines.append(
                INSTAGRAM_BLOCKS_LIST.format(
                    name="@" + (row.username or ""), when=format_jalali_datetime(row.created_at)
                )
            )
    lines += ["", INSTAGRAM_BLOCKS_NOTE]
    return "\n".join(lines)


def instagram_status_text(account, admin_settings) -> str:
    """صفحهٔ فروشگاه‌دار: وضعیتِ اتصال + وضعیتِ سراسری + خطایِ آخر + قاعدهٔ ۲۴ ساعت."""
    lines = [INSTAGRAM_SCREEN_INTRO, ""]
    if account is None:
        lines.append(INSTAGRAM_NOT_CONNECTED)
        lines.append("")
        lines.append(INSTAGRAM_STEPS_CHECKLIST)
    else:
        lines.append(INSTAGRAM_CONNECTED_AS.format(username="@" + (account.ig_username or "—")))
        lines.append(f"• پاسخ‌گوییِ خودکار: {'روشن' if account.auto_reply_dm else 'خاموش'}")
        lines.append(instagram_mute_line(account))
        lines.append(
            INSTAGRAM_INSTRUCTIONS_LINE.format(
                state="دارد" if (account.instructions or "").strip() else "ندارد (فقط تنظیماتِ عمومی)"
            )
        )
    lines += ["", INSTAGRAM_DM_RULE_TEXT, INSTAGRAM_PAYMENTS_NOTE]
    if account is not None and account.last_error:
        lines += ["", INSTAGRAM_LAST_ERROR.format(error=account.last_error)]
    if admin_settings is not None and not (getattr(admin_settings, "instagram_app_id", "") or "").strip():
        lines += ["", INSTAGRAM_NO_APP_ID]
    return "\n".join(lines)


def instagram_connect_page_link(link: str) -> str:
    return INSTAGRAM_LINK_SENT.format(link=link)


INSTAGRAM_CONNECT_OK_PAGE = (
    "<div dir='rtl' style='font-family:Tahoma;padding:24px;text-align:center'>"
    "<h2>✅ اتصال برقرار شد</h2><p>به پنلِ ربات برگرد؛ وضعیتِ اینستاگرام همان‌جا «وصل است» می‌شود.</p></div>"
)
INSTAGRAM_CONNECT_CANCELLED_PAGE = (
    "<div dir='rtl' style='font-family:Tahoma;padding:24px;text-align:center'>"
    "<h2>اتصال کامل نشد</h2><p>لینک را دوباره از پنل بزن («🔗 اتصالِ اکانت اینستاگرام»).</p></div>"
)
INSTAGRAM_CONNECT_UNAVAILABLE_PAGE = (
    "<div dir='rtl' style='font-family:Tahoma;padding:24px;text-align:center'>"
    "<h2>این سرویس در دسترس نیست</h2><p>کمی دیگر دوباره امتحان کن.</p></div>"
)


def instagram_connect_failed_page(error: str) -> str:
    """صفحهٔ شکستِ اتصال. `error` از همین‌جا کوتاه می‌شود؛ متن‌هایِ سرویس خودشان ماسک‌شده‌اند."""
    safe = (error or "")[:220].replace("<", "").replace(">", "")
    return (
        "<div dir='rtl' style='font-family:Tahoma;padding:24px'>"
        "<h2>❌ اتصال کامل نشد</h2>"
        f"<p>{safe}</p>"
        "<p>از پنلِ ربات دوباره «🔗 اتصالِ اکانت اینستاگرام» را بزن. اگر باز هم نشد، متنِ «آخرین خطا» "
        "در همان صفحه را برایِ پشتیبانی بفرست.</p></div>"
    )

# --- P44 · موردِ ۵۱: «ماه» چند روز باشد + بکاپِ خودکارِ دیتابیس ---
MONTH_LENGTH_CHOICES: tuple[int, ...] = (0, 30, 31)
MONTH_LENGTH_LABELS: dict[int, str] = {
    0: "تقویمی (همان رفتارِ امروز)",
    30: "دقیقاً ۳۰ روزِ کامل",
    31: "دقیقاً ۳۱ روزِ کامل",
}


def month_length_label(value: int | None) -> str:
    return MONTH_LENGTH_LABELS.get(int(value or 0), "نامعتبر — دوباره انتخاب کن")


ADMIN_ASK_MONTH_LENGTH_DAYS = (
    "«ماهِ اعتبار» چند روز باشد؟\n\n"
    "· ۰ = تقویمی: ۱ مهر + ۱ ماه ⇒ ۱ آبان (در ماهِ ۳۱ روزه هم ۳۱ روز می‌شود)\n"
    "· ۳۰ = همیشه ۳۰ روزِ ۲۴ ساعته\n"
    "· ۳۱ = همیشه ۳۱ روزِ ۲۴ ساعته\n\n"
    "این عدد فقط رویِ شارژ یا اشتراکی اثر می‌گذارد که از این به بعد ساخته می‌شود؛ "
    "اعتبارِ فعلیِ هیچ فروشگاه‌داری جلو نمی‌افتد."
)
ADMIN_INVALID_MONTH_LENGTH = "فقط ۰، ۳۰ یا ۳۱. (۰ یعنی تقویمی)"
ADMIN_ASK_BACKUP_RETENTION_DAYS = (
    "فایل‌هایِ بکاپ چند روز نگه داشته شوند؟ (۱ تا ۶۰)\n\n"
    "قدیمی‌تر از این را ربات خودش پاک می‌کند تا دیسکِ سرور پر نشود."
)
ADMIN_BACKUP_TOO_LARGE_TEXT = (
    "📦 فایلِ بکاپ ساخته شده ولی {size_mb} مگابایت است و ربات نمی‌تواند چنین فایلی را بفرستد.\n\n"
    "فایل رویِ سرور سالم است؛ برایِ برداشتنش راهنمایِ استقرار §بکاپ را ببین."
)


def admin_backup_caption(file_name: str, size_bytes: int, manual: bool = False) -> str:
    size_mb = max(1, round(int(size_bytes) / (1024 * 1024)))
    head = "📦 بکاپی که خودت خواستی" if manual else "📦 بکاپِ شبانهٔ دیتابیس"
    return f"{head}\n• فایل: {file_name}\n• اندازه: {fa_number(size_mb)} مگابایت"


def admin_backup_result_text(result: dict) -> str:
    status = result.get("status")
    if status == "sent":
        return (
            "📦 بکاپ ارسال شد.\n"
            f"• فایل: {result.get('file', '—')}\n"
            f"• برایِ {fa_number(int(result.get('sent', 0)))} ادمین"
        )
    if status == "no-file":
        return "📦 هنوز هیچ فایلِ بکاپی در پوشه نیست؛ سرویسِ بکاپ را روشن کن (راهنمایِ استقرار §بکاپ)."
    if status == "off":
        return "📦 ارسالِ خودکار خاموش است."
    if status == "no-admin":
        return "📦 فایل هست ولی هیچ ادمینی برایِ ارسال تنظیم نشده."
    if status == "already-sent":
        return "📦 این فایل پیش‌تر ارسال شده و فایلِ تازه‌ای ساخته نشده."
    return "📦 ارسال ناموفق بود؛ فایل رویِ سرور سالم است و دوباره قابلِ درخواست است."


def admin_backup_toast(result: dict) -> str:
    if result.get("status") == "sent":
        return f"بکاپ برایِ {fa_number(int(result.get('sent', 0)))} ادمین ارسال شد"
    return {"no-file": "فایلی نیست", "off": "خاموش است", "no-admin": "ادمینی تنظیم نشده",
            "already-sent": "قبلاً رفته"}.get(str(result.get("status")), "ناموفق بود")


def admin_settings_group_intro(group: str) -> str:
    return f"{ADMIN_SETTINGS_GROUP_LABELS.get(group, '⚙️ تنظیمات')}\n\nروی هر مورد بزن تا مقدارش را عوض کنی."


def _bale_bot_token_label(raw_token: str | None) -> str:
    """برچسبِ توکنِ رباتِ بله + نامِ کاربریِ همان ربات (از getMe) — تا ادمین بداند پرداخت‌ها
    به کدام ربات می‌روند، چون لینکِ پرداخت همان چت است (`https://ble.ir/<username>?start=…`)."""
    from app.services import bale_credentials_service  # لازیم؛ وابستگیِ متن به سرویسِ اعتبارها

    base = f"🔵 توکنِ رباتِ بله: {_mask_secret(raw_token)}"
    username = bale_credentials_service.bot_username()
    if not username:
        return f"{base} (رباتِ پرداخت هنوز شناخته نشده)"
    return f"{base} — رباتِ پرداخت: @{username}"


def admin_settings_button_labels(admin_settings, group: str | None = None) -> list[tuple[str, str]]:
    from app.services.sms_service import DEFAULT_OTP_TEMPLATE

    global_prompt_label = "تنظیم‌شده ✅" if admin_settings.global_ai_system_prompt else "خالی"
    reference_channel_label = admin_settings.reference_channel_link or "تنظیم‌نشده"

    labels = [
        ("sms_api_key", f"📲 کلید پیامک (کاوه‌نگار): {_mask_secret(admin_settings.sms_api_key)}"),        ("sms_sender_number", f"📲 سرشماره‌یِ پیامک: {admin_settings.sms_sender_number or 'تنظیم‌نشده'}"),
        ("sms_otp_template", f"📲 قالبِ OTP: {admin_settings.sms_otp_template or DEFAULT_OTP_TEMPLATE + ' (پیش‌فرض)'}"),
        ("ai_model", f"🧠 مدل هوش مصنوعی (پیش‌فرضِ سراسری): {admin_settings.ai_model}"),
        ("ai_base_url", f"🌐 آدرس سرویس هوش مصنوعی (پیش‌فرضِ سراسری): {admin_settings.ai_base_url}"),
        ("zarinpal_merchant_id", f"🏦 مرچنت آیدی زرین‌پال: {_mask_secret(admin_settings.zarinpal_merchant_id)}"),
        ("bale_bot_token", _bale_bot_token_label(admin_settings.bale_bot_token)),
        ("bale_provider_token", f"🔵 توکنِ درگاهِ بله‌پی: {_mask_secret(admin_settings.bale_provider_token)}"),
        # P49-الف: سه مقدارِ متا؛ دو موردِ آخر رازند و فقط ماسک‌شده نمایش داده می‌شوند.
        (
            "instagram_app_id",
            f"🟣 App ID اپِ متا: {admin_settings.instagram_app_id or 'تنظیم‌نشده'}",
        ),
        (
            "instagram_app_secret",
            f"🔐 App Secret (برایِ امضایِ وب‌هوک): {_mask_secret(admin_settings.instagram_app_secret)}",
        ),
        (
            "instagram_webhook_verify_token",
            f"🔐 توکنِ تأییدِ وب‌هوک: {_mask_secret(admin_settings.instagram_webhook_verify_token)}",
        ),
        # پ۶۰ · خواستهٔ مالکِ محصول: متنِ سراسریِ هوشمندسازیِ اینستاگرام (رِاز نیست، متنِ کامل نشان داده می‌شود)
        (
            "instagram_platform_instructions",
            "🟣 متنِ سراسریِ هوشمندسازیِ اینستاگرام: "
            + ("تنظیم‌شده ✅" if (admin_settings.instagram_platform_instructions or "").strip() else "خالی"),
        ),
        ("platform_card_number", f"💳 شماره کارت پلتفرم: {_mask_secret(admin_settings.platform_card_number)}"),
        ("platform_card_holder_name", f"👤 صاحب کارت: {admin_settings.platform_card_holder_name or 'تنظیم‌نشده'}"),
        # P18 · A2: متنِ اجباریِ بیویِ ربات‌هایِ فروشگاهی + دکمه‌یِ همگام‌سازیِ فوری.
        ("branding_text", f"🪪 بیوگرافیِ اجباریِ ربات‌ها: {admin_settings.branding_text or 'تنظیم‌نشده'}"),
        ("branding_check_minutes", f"⏱ فاصلهِ بازرسیِ بیو: هر {fa_number(admin_settings.branding_check_minutes)} دقیقه"),
        ("referral_reward_value", f"🎁 پورسانتِ معرف: {_percent_label(admin_settings.referral_reward_value)} از اولین شارژ (فقط به معرف)"),
        ("grace_period_hours", f"⏳ مهلت گریس‌پیریود: {fa_number(admin_settings.grace_period_hours)} ساعت"),
        ("periodic_report_frequency_days", f"📈 بازه‌ی گزارش دوره‌ای: هر {fa_number(admin_settings.periodic_report_frequency_days)} روز"),
        (
            "nightly_report_hour_utc",
            f"🌙 ساعتِ گزارشِ شبانه: {fa_number(admin_settings.nightly_report_hour_utc)}:00 UTC (≈ {fa_number((admin_settings.nightly_report_hour_utc + 3) % 24)}:30 تهران)",
        ),
        ("wallet_cost_per_1k_tokens_toman", f"🪙 هزینه‌ی هر ۱۰۰۰ توکن: {format_toman(admin_settings.wallet_cost_per_1k_tokens_toman)}"),
        ("ai_cost_usd_per_1m_tokens", f"💵 هزینه‌ی خامِ AI: ${admin_settings.ai_cost_usd_per_1m_tokens}/۱M توکن"),
        ("usd_to_toman_rate", f"💱 نرخِ دلار: {format_toman(admin_settings.usd_to_toman_rate)}"),
        ("wallet_markup_multiplier", f"📈 ضریبِ سود: {admin_settings.wallet_markup_multiplier}×"),
        # PHASE 5D
        (
            "commission_percent",
            f"🧾 کمیسیون: {fa_number(admin_settings.commission_percent)}٪ ({'روشن' if admin_settings.commission_enabled else 'خاموش'})",
        ),
        ("wallet_cost_receipt_analysis_toman", f"🧾 هزینه‌ی تحلیلِ رسید (مشورتی): {format_toman(admin_settings.wallet_cost_receipt_analysis_toman)}"),
        ("wallet_cost_voice_transcription_toman", f"🎙 هزینه‌ی رونویسیِ صوت: {format_toman(admin_settings.wallet_cost_voice_transcription_toman)}"),
        # P21-C (F3): قیمت‌گذاریِ منصفانه — هر دو با ۰ یعنی «همان نرخِ ثابتِ قبل».
        (
            "wallet_cost_voice_per_minute_toman",
            f"🎙 نرخِ هر دقیقهٔ صوت: {('خاموش (نرخ ثابت)' if not admin_settings.wallet_cost_voice_per_minute_toman else format_toman(admin_settings.wallet_cost_voice_per_minute_toman))}",
        ),
        (
            "wallet_cost_receipt_per_1k_tokens",
            f"🧾 هر ۱۰۰۰ توکنِ تحلیلِ رسید: {('خاموش (نرخ ثابت)' if not admin_settings.wallet_cost_receipt_per_1k_tokens else format_toman(admin_settings.wallet_cost_receipt_per_1k_tokens))}",
        ),
        ("wallet_cost_order_detection_toman", f"🔎 هزینه‌ی پیش‌فرضِ تشخیصِ سفارش: {format_toman(admin_settings.wallet_cost_order_detection_toman)}"),
        ("wallet_topup_validity_months", f"📅 اعتبارِ هر شارژ: {admin_settings.wallet_topup_validity_months} ماه"),
        # P44 · موردِ ۵۱: «چند روزِ کامل» یا «تقویمی» — فقط رویِ شارژ/اشتراکِ تازه اثر می‌گذارد.
        ("month_length_days", f"📐 طولِ ماهِ اعتبار: {month_length_label(admin_settings.month_length_days)}"),
        ("backup_retention_days", f"🗄 نگه‌داشتنِ فایلِ بکاپ: {fa_number(int(admin_settings.backup_retention_days))} روز"),
        ("min_topup_amount_toman", f"🧾 کمترینِ شارژِ کیف‌پول: {format_toman(admin_settings.min_topup_amount_toman)}"),
        ("wallet_trial_credit_toman", f"🎁 اعتبارِ آزمایشیِ فروشگاه‌دارِ جدید: {format_toman(admin_settings.wallet_trial_credit_toman)}"),
        ("wallet_low_balance_warning_toman", f"🟡 آستانه‌ی هشدارِ کمبودِ موجودی: {format_toman(admin_settings.wallet_low_balance_warning_toman)}"),
        (
            "commission_debt_ceiling_toman",
            f"🟡 سقفِ بدهیِ کمیسیون: {('بی‌سقف' if not admin_settings.commission_debt_ceiling_toman else format_toman(admin_settings.commission_debt_ceiling_toman))}"
            f" · ادامهٔ سفارش با اعتبارِ صفر: {'روشن' if admin_settings.orders_allowed_when_wallet_empty else 'خاموش'}",
        ),
        ("global_ai_system_prompt", f"🌍 دستور سراسری هوش مصنوعی: {global_prompt_label}"),
        ("global_ai_prompt_sales", f"🛍 دستورِ سراسری — فروشگاهی: {'تنظیم‌شده ✅' if admin_settings.global_ai_prompt_sales else 'پیش‌فرضِ حرفه‌ای'}"),
        ("global_ai_prompt_consultation", f"💬 دستورِ سراسری — مشاوره‌ای: {'تنظیم‌شده ✅' if admin_settings.global_ai_prompt_consultation else 'پیش‌فرضِ حرفه‌ای'}"),
        ("reference_channel_link", f"🔗 کانال مرجع: {reference_channel_label}"),
        ("platform_support_username", f"📞 پشتیبانیِ پلتفرم — یوزرنیم: {'@' + admin_settings.platform_support_username if admin_settings.platform_support_username else 'تنظیم‌نشده'}"),
        ("platform_support_phone", f"📞 پشتیبانیِ پلتفرم — تلفن: {format_phone_display(admin_settings.platform_support_phone) or 'تنظیم‌نشده'}"),
        ("platform_support_text", f"📞 پشتیبانیِ پلتفرم — متن: {'تنظیم‌شده ✅' if admin_settings.platform_support_text else 'خالی'}"),
    ]
    if group is not None:
        labels = [(key, label) for key, label in labels if ADMIN_SETTING_GROUP.get(key) == group]
    return labels



# پ۵۹ · موردِ ۳۴: نامِ فایل‌هایِ ارسالی به کاربر فارسی است، ولی پسوندِ لاتین می‌ماند (تلگرام و
# ویندوز فایل را با پسوندِ فارسی نمی‌شناسند) و شمارهٔ فاکتور هم دست‌نخورده (کدِ پیگیری).
EXCEL_CUSTOMERS_FILENAME = "مشتریان.xlsx"
EXCEL_ORDERS_FILENAME = "سفارش‌ها.xlsx"
EXCEL_ACCOUNTING_FILENAME = "حسابداری.xlsx"
EXCEL_WALLET_LEDGER_FILENAME = "دفتر-کیف‌پول.xlsx"
AUDIT_CSV_FILENAME = "دفتر-ممیزی.csv"
RECEIPT_FALLBACK_FILENAME = "رسید"


# --- مدیریت فروشگاه‌دارها ---
ADMIN_SHOP_OWNERS_EMPTY = "هیچ فروشگاه‌داری ثبت‌نام نکرده."
# پ۵۶ · موردِ ۲۷: جست‌وجو در فهرستِ فروشگاه‌دارها
ADMIN_OWNER_SEARCH_BUTTON = "🔍 جست‌وجویِ فروشگاه‌دار"
ADMIN_OWNER_SEARCH_ASK = (
    "چه چیزی را بگردم؟ نام، نامِ خانوادگی، نامِ کاربری، شمارهٔ موبایل یا شناسهٔ تلگرام.\n"
    "· برایِ لغو «انصراف» بنویس."
)
ADMIN_OWNER_SEARCH_INVALID = "این عبارت را نفهمیدم یا خیلی بلند است؛ نام، نامِ کاربری، تلفن یا شناسهٔ تلگرام بنویس."
ADMIN_OWNER_SEARCH_CANCELLED = "↩️ جست‌وجو لغو شد؛ فهرستِ فروشگاه‌دارها عوض نشد."


def admin_owner_search_intro(term: str, total: int, page: int, total_pages: int) -> str:
    return (
        f"🔍 نتیجهٔ جست‌وجویِ «{term}» — {fa_number(total)} نفر (صفحه‌یِ {fa_number(page + 1)} از {fa_number(total_pages)})\n"
        "فقط دامنهٔ دسترسیِ تو جست‌وجو می‌شود.\nروی هر مورد بزن تا جزئیاتش باز بشه:"
    )


ADMIN_OWNER_SEARCH_EMPTY_TMPL = "🔍 چیزی برایِ «{term}» پیدا نشد (در دامنهٔ دسترسیِ تو)."


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
        f"👥 فهرستِ فروشگاه‌دارها — {fa_number(total)} نفر (صفحه‌یِ {fa_number(page + 1)} از {fa_number(total_pages)})\n"
        "✅ ربات فعال · ⛔️ ربات معلق · «بدونِ ربات» = هنوز رباتی وصل نکرده\n"
        "روی هر مورد بزن تا جزئیات و مدیریتش باز بشه:"
    )


ADMIN_OWNER_NO_SHOP_BOT = "این فروشگاه‌دار هنوز ربات فروشگاهی‌ای وصل نکرده."
# P21-E (F8): دامنهٔ دسترسیِ ادمینِ عملیاتی
ADMIN_OWNER_OUT_OF_SCOPE = "🚫 این فروشگاه‌دار در فهرستِ دسترسیِ تو نیست. برایِ افزودنش از سوپرادمین بخواه."
ADMIN_OWNER_OUT_OF_SCOPE_TOAST = "خارج از دامنهٔ دسترسیِ تو"
ADMIN_ROLE_SCOPE_BUTTON = "🏪 دامنهٔ فروشگاه‌ها"
ASK_ROLE_SCOPE = (
    "شناسه‌یِ کاربریِ تلگرامِ فروشگاه‌دارهایی که این ادمینِ عملیاتی باید ببیند را با کاما بفرست\n"
    "(مثال: 123456789,987654321). برایِ بازگشت به «همه» کلمه‌ی «همه» را بنویس و برایِ بستنِ "
    "کاملِ دسترسی کلمه‌ی «هیچ» را."
)
ROLE_SCOPE_SAVED = "✅ دامنه ذخیره شد: {detail}"
ROLE_SCOPE_UNLIMITED_LABEL = "همهٔ فروشگاه‌ها"
ROLE_SCOPE_EMPTY_LABEL = "هیچ فروشگاه (دسترسی بسته)"
ROLE_SCOPE_COUNT_LABEL = "{count} فروشگاه"
ROLE_SCOPE_UNKNOWN_IDS = " ⚠️ این شناسه‌ها فروشگاه‌دارِ ثبت‌نام‌کرده ندارند و نادیده گرفته شدند: {ids}"
# P21-F: دامنهٔ تهی عمدي است، پس هیچ‌وقت «ذخیره» نمی‌شود — وگرنه فهرستِ اشتباه یعنی دسترسیِ کامل.
ROLE_SCOPE_NO_MATCH = "⚠️ هیچ‌کدام ازِ این شناسه‌ها فروشگاه‌دارِ ثبت‌نام‌کرده نیست؛ دامنه تغییر نکرد. دوباره بنویس."


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


def admin_gift_preview(owner_name: str, amount_toman: int, minimum: int, maximum: int) -> str:
    return (
        f"🎁 تاییدِ اعطای هدیه\n\n"
        f"فروشگاه‌دار: {owner_name}\n"
        f"مبلغ: {format_toman(amount_toman)}\n\n"
        f"این مبلغ به کیف‌پولش اضافه می‌شود و در دفترِ کیف‌پول با نامِ شما ثبت می‌شود. "
        f"سقفِ هر هدیه {format_toman(maximum)} و کمترین {format_toman(minimum)} است."
    )


ADMIN_GIFT_OUT_OF_RANGE = "مبلغِ هدیه باید بینِ {min} تا {max} باشد."
ADMIN_GIFT_CANCELLED = "هدیه داده نشد."
ADMIN_GIFT_STALE = "این تایید قبلاً استفاده شده یا منقضی شده. اگر هدیه هنوز داده نشده، از اول شروع کن."


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


ACCOUNT_DELETED_NOTICE = "🔒 حسابِ این فروشگاه غیرفعال شده است. اگر باید برگردد، با پشتیبانیِ پلتفرم صحبت کن."


AUDIT_LOG_EMPTY = "هنوز هیچ رویدادی در گزارشِ ممیزی ثبت نشده."
# P21-E (F9): فیلترِ دسته/بازه + خروجیِ CSV (تا پیش‌ازاین فقط ۲۰ ردیفِ آخر دیده می‌شد)
AUDIT_FILTER_GROUPS: tuple[tuple[str, str], ...] = (
    ("all", "همه"),
    ("money", "💰 پول"),
    ("shops", "🏪 فروشگاه‌ها"),
    ("settings", "⚙️ تنظیمات"),
    ("roles", "👑 نقش‌ها"),
    ("brand", "🧴 برند/نگهبان"),
)
AUDIT_FILTER_WINDOWS: tuple[tuple[str, str], ...] = (("all", "همیشه"), ("24", "۲۴ ساعت"), ("7d", "۷ روز"), ("30d", "۳۰ روز"))
AUDIT_CSV_BUTTON = "📥 خروجیِ CSV"
AUDIT_FILTER_EMPTY = "📜 با این فیلتر هیچ رویدادی نبود. دسته یا بازهٔ زمانی را عوض کن."
AUDIT_CSV_EMPTY = "📥 برایِ این فیلتر ردیفی نبود که خروجی گرفته شود."
AUDIT_CSV_READY = "📥 خروجیِ CSVِ دفترِ ممیزی (با خنثی‌سازیِ فرمول) — {count} ردیف"


def audit_report_intro(group: str | None, window: str | None, count: int, *, scoped: bool = False) -> str:
    group_label = dict(AUDIT_FILTER_GROUPS).get(group or "all", "همه")
    window_label = dict(AUDIT_FILTER_WINDOWS).get(window or "all", "همیشه")
    tail = " · فقطِ فروشگاه‌هایِ دامنهٔ تو" if scoped else ""
    return f"📜 گزارشِ ممیزی · دسته: {group_label} · بازه: {window_label} · {fa_number(count)} ردیفِ آخر:{tail}"


# P48 · موردِ ۳۹/۴۸: بازهٔ تاریخِ دلخواه در همان صفحهٔ ممیزی (قبلاً فقط ۲۴ ساعت/۷/۳۰ روز بود).
AUDIT_RANGE_BUTTON = "🗓 بازهٔ دلخواه"
AUDIT_RANGE_CLEAR_BUTTON = "✖️ حذفِ بازه"
AUDIT_RANGE_FROM_ASK = (
    "🗓 تاریخِ شروعِ بازه را بنویس — الگو: ۲۰۲۶-۰۱-۱۵ یا ۲۰۲۶-۰۱-۱۵ ۰۹:۳۰ (میلادی، به وقتِ جهانی `UTC`).\n"
    "برایِ بی‌حدِ نوشتنِ «همه» یا «خالی» کافی است."
)
AUDIT_RANGE_TO_ASK = (
    "🗓 تاریخِ پایانِ بازه را بنویس — همان الگو؛ ردیف‌هایِ خودِِ این لحظه شامل نمی‌شوند.\n"
    "برایِ بی‌حدِ نوشتنِ «همه» یا «خالی» کافی است."
)
AUDIT_RANGE_INVALID = "🗓 این تاریخ را نفهمیدم. الگو: ۲۰۲۶-۰۱-۱۵ یا ۲۰۲۶-۰۱-۱۵ ۰۹:۳۰ (میلادی، به وقتِ جهانی `UTC`)."
AUDIT_RANGE_OPEN_END = "بی‌حد"
AUDIT_RANGE_CLEARED = "✖️ بازهٔ دلخواه حذف شد؛ دفترِ ممیزی دوباره با بازه‌هایِ آماده نشان داده می‌شود."
AUDIT_RANGE_HEADLINE = "🗓 بازهٔ دلخواه (جایِ بازهٔ آماده): از {start} تا {end}"
AUDIT_COUNTS_LINE = "📊 در این بازه: {total} ردیف{buckets}"
AUDIT_COUNTS_BUCKET = "{label}: {count}"


def audit_range_line(since: datetime.datetime | None, until: datetime.datetime | None) -> str:
    """دو سرِ بازهٔ دلخواه با تاریخِ شمسی (همان چیزی که کاربر در دفتر می‌بیند)."""
    from app.utils.jalali import format_jalali_datetime

    start = format_jalali_datetime(since) if since else AUDIT_RANGE_OPEN_END
    end = format_jalali_datetime(until) if until else AUDIT_RANGE_OPEN_END
    return fa_text(AUDIT_RANGE_HEADLINE, start=start, end=end)


def audit_counts_summary_line(total: int, buckets: tuple[tuple[str, int], ...]) -> str:
    """خلاصهٔ یک‌خطیِ حرفه‌ایِ همان فیلتر: «۴۲ ردیف · 💰 پول: ۵ · ⚙️ تنظیمات: ۳»."""
    parts = "".join(" · " + AUDIT_COUNTS_BUCKET.format(label=label, count=fa_number(count)) for label, count in buckets if count)
    return AUDIT_COUNTS_LINE.format(total=fa_number(total), buckets=parts)


def audit_csv_range_note(since: datetime.datetime | None, until: datetime.datetime | None) -> str:
    """ذیلِ همان ردیفِ ممیزیِ «خروجیِ گرفتم» — تا در خودِ دفتر هم معلوم باشد فایلی که رفت کدام بازه است."""
    from app.utils.jalali import format_jalali_datetime

    if not (since or until):
        return ""
    start = format_jalali_datetime(since) if since else AUDIT_RANGE_OPEN_END
    end = format_jalali_datetime(until) if until else AUDIT_RANGE_OPEN_END
    return f" · بازهٔ دلخواه: از {start} تا {end}"


# =============================================================================
# P48 · موردِ ۱۳: لاگِ زندهٔ سرور در پنل (بدونِ SSH و بدونِ دیتابیس)
# =============================================================================
SERVER_LOG_BUTTON = "🧾 لاگِ سرور"
SERVER_LOG_ROWS = 15  # سقفِ ردیف‌هایِ رویِ صفحه (بافرِ حافظه ۳۰۰ ردیف نگه می‌دارد)
SERVER_LOG_MESSAGE_LIMIT = 160
SERVER_LOG_EXC_LIMIT = 200
SERVER_LOG_TEXT_LIMIT = 3800  # جایِ امن زیرِ سقفِ ۴۰۹۶ نویسهٔ تلگرام
SERVER_LOG_INTRO = (
    "🧾 لاگِ سرور\n\n"
    "فقطِ همین پروسهٔ سرور، آخرین ۳۰۰ هشدار/خطا در حافظه؛ لاگِ کامل در `stdout` و فایلِ لاگِ داکر است."
)
SERVER_LOG_EMPTY = "✅ در حافظهٔ همین پروسه هیچ هشدار یا خطایی ثبت نشده است."
SERVER_LOG_COUNTS_LINE = "📊 در حافظه: {warnings} هشدار · {errors} خطا · {stored} ردیفِ کل"
SERVER_LOG_TRUNCATED = "\n\n… بقیهٔ خطوط برایِ ماندن زیرِ سقفِ پیام کوتاه شد."
LOGS_VIEW_WARNINGS_BUTTON = "🟡 هشدارها و خطاها"
LOGS_VIEW_ERRORS_BUTTON = "🔴 فقط خطاها"
LOGS_REFRESH_BUTTON = "🔄 تازه‌کردن"
LOGS_BACK_BUTTON = "⬅️ بازگشت"
_LOG_LEVEL_LABELS = {"WARNING": "⚠️ هشدار", "ERROR": "🔴 خطا", "CRITICAL": "🔥 بحرانی"}


def server_log_counts_line(counts: dict[str, int]) -> str:
    """خطِ شمارشِ بافر؛ سطح‌ها با ارقامِ فارسی."""
    return fa_text(SERVER_LOG_COUNTS_LINE, **counts)


def server_log_row_line(row: dict[str, str]) -> str:
    """یکِ ردیفِ لاگ در دو خط: «زمان · سطح · ماژول» و زیرش پیامِ برش‌خورده (+ دنبالهٔ استثنا)."""
    level = row.get("level", "")
    head = f"· {fa_number(row.get('t', ''))} {_LOG_LEVEL_LABELS.get(level, level)} · {row.get('where', '')}"
    body = clip(row.get("msg"), SERVER_LOG_MESSAGE_LIMIT)
    line = f"{head}\n{body}" if body else head
    exc = (row.get("exc") or "").strip()
    if exc:
        # دنبالهٔ متنِ استثنا مهم‌ترین بخش است (نوعِ خطا در آخرین خط است)، پس از انتها بریده می‌شود.
        line += f"\n   …{exc[-SERVER_LOG_EXC_LIMIT:]}"
    return line


def server_log_screen_text(counts: dict[str, int], rows: list[dict[str, str]]) -> str:
    """متنِ کاملِ صفحهٔ لاگ؛ برشِ نهایی تا سقفِ پیامِ تلگرام (۱۵ ردیفِ بلند از ۴۰۹۶ می‌گذرند)."""
    body = "\n".join(server_log_row_line(row) for row in rows) if rows else SERVER_LOG_EMPTY
    text = "\n\n".join([SERVER_LOG_INTRO, server_log_counts_line(counts), body])
    if len(text) > SERVER_LOG_TEXT_LIMIT:
        text = text[:SERVER_LOG_TEXT_LIMIT].rstrip() + SERVER_LOG_TRUNCATED
    return text


def audit_csv_headers() -> list[str]:
    """سرستون‌هایِ فایلِ CSVِ ممیزی — فارسی، چون فایل را آدم می‌خواند نه ماشین."""
    return [
        "شناسه",
        "تاریخ (به وقتِ تهران)",
        "رویداد",
        "آیدیِ تلگرامِ اقدام‌کننده",
        "فروشگاه",
        "شناسهٔ فروشگاه",
        "جزئیات",
        "هشِ ردیفِ زنجیره",
    ]

AI_POOL_MENU_INTRO = (
    "🔑 کلیدهایِ AI (کلید ۱ تا کلید ۱۰)\n\n"
    "تا ۱۰ کلیدِ API ثبت کن؛ هر کلید مدل، آدرس و *سقفِ همزمانیِ خودش* را دارد. هر درخواست "
    "سراغِ کلیدی می‌رود که الان کم‌ترین بار را دارد (تقسیمِ بار به نسبتِ سقفِ هرِ کلید)، پس "
    "درخواست‌ها تقریباً مساوی و هم‌زمان بینِ کلیدها پخش می‌شود. اگر یک کلید خطا بدهد یا "
    "موقتاً کنار گذاشته شده باشد، کلیدِ بعدی امتحان می‌شود.\n\n"
    "سقفِ کلِ پلتفرم از تنظیماتِ محیطی (AI_MAX_CONCURRENT_CALLS) خوانده می‌شود؛ کلیدهایی که "
    "سقفِ خودشان را ننویسی، سهمِ مساوی از همان سقفِ کلی می‌گیرند."
)
AI_POOL_EMPTY = "هنوز هیچ کلیدی اضافه نشده. با «➕ افزودنِ کلیدِ جدید» کلیدِ اول را ثبت کن."
AI_POOL_MAX_KEYS_REACHED = "به سقفِ ۱۰ کلید رسیدی؛ برایِ کلیدِ جدید اول یکی را حذف یا غیرفعال کن."
AI_POOL_LEGACY_AVAILABLE = (
    "ℹ️ در تنظیماتِ قدیمی یکِ «کلیدِ AIِ سراسری» داری که هنوز به این فهرست نیامده. با دکمهِٔ "
    "زیر همان کلید را بیاور داخلِ «کلیدِ ۱» تا مدل، آدرس و سقفِ همزمانی‌اش را همین‌جا مدیریت کنی."
)
AI_POOL_IMPORTED = "✅ کلیدِ قدیمی به «کلیدِ ۱» تبدیل شد؛ از این به بعد همین‌جا مدیریت می‌شود."


def ai_pool_capacity_line(report: dict[str, int]) -> str:
    """عددهایِ ظرفیت: چه‌قدر جا در پلتفرم و چه‌قدر جا در خودِ کلیدها هست (فقط شمارش، بدونِ کلید)."""
    if not report.get("keys"):
        return ""
    ceiling = fa_number(report["ceiling"])
    total = fa_number(report["sum_caps"])
    line = f"\n\n📊 ظرفیتِ فعلی: {fa_number(report['keys'])} کلیدِ فعال · جمعِ سقفِ کلیدها: {total} · سقفِ پلتفرم: {ceiling}"
    if report.get("bottleneck") == "keys":
        line += (
            "\n⚠️ گلوگاه: جمعِ سقفِ کلیدها از سقفِ پلتفرم کمتر است. یا سقفِ هرِ کلید را در همین "
            "پنل بالا ببر، یا با سرویس‌دهنده قراردادِ همزمانیِ بیشتر ببند."
        )
    else:
        line += "\n✅ گلوگاه: سقفِ کلِ پلتفرم. با بالا بردنِ AI_MAX_CONCURRENT_CALLS در تنظیماتِ محیطی ظرفیتِ بیشتر می‌شود."
    return line


def ai_pool_health_line(health: dict[str, int]) -> str:
    """P21-E (F10): failover از قبل کار می‌کرد؛ این خط «چرا کند شده» را برایِ ادمین می‌گوید."""
    if not health.get("open_keys") and not health.get("failures"):
        return ""
    return (
        f"\n\n⚠️ سلامتِ استخر: {fa_number(health['open_keys'])} کلید فعلاً کنار گذاشته شده · "
        f"{health['failures']} شکستِ پیاپی در {health['tracked']} مسیرِ پایش‌شده.\n"
        "هر کلیدِ بازشده ۶۰ ثانیه بعد دوباره امتحان می‌شود."
    )
ASK_AI_POOL_ENTRY = (
    "اطلاعاتِ کلیدِ جدید را در ۵ تا ۷ خط بفرست (دقیقاً به همین ترتیب):\n\n"
    "برچسب (فقط برایِ خودت، تا کلیدها را از هم تشخیص بدی)\n"
    "کلیدِ API\n"
    "نامِ مدل\n"
    "آدرسِ base_url کاملِ chat/completions\n"
    "نوع: chat یا vision یا both یا stt\n"
    "خطِ ششم (اختیاری): مدل‌هایِ پشتیبانِ همین کلید، با ویرگول و به همان ترتیبِ امتحان شدن (برایِ نداشتنِ پشتیبان بنویس «-»)\n"
    "خطِ هفتم (اختیاری): سقفِ همزمانیِ همین کلید (عدد؛ مثلاً ۲۰۰). خالی بگذار تا سهمِ مساوی از سقفِ پلتفرم بگیرد"
)
AI_POOL_ENTRY_INVALID_FORMAT = (
    "۵ خط لازم است (برچسب، کلید، مدل، base_url، نوع) — خطِ ششم مدل‌هایِ پشتیبان و خطِ هفتم سقفِ همزمانیِ "
    "همانِ کلید است، هر دو اختیاری. دوباره امتحان کن یا با «لغو» برگرد."
)
AI_POOL_ENTRY_INVALID_CAPABILITY = "خطِ پنجم باید دقیقاً یکی از این‌ها باشه: chat یا vision یا both یا stt."
AI_POOL_ENTRY_DELETED = "🗑 کلید حذف شد."
ASK_AI_POOL_FALLBACK_MODELS = (
    "مدل‌هایِ پشتیبانِ همین کلید را بنویس، با ویرگول و به همان ترتیبی که باید امتحان شوند "
    "(حداکثر ۵).\n\n"
    "برایِ پاک‌کردن بنویس «خالی». برایِ لغو «انصراف».\n\n"
    "⚠️ این مدل‌ها فقط وقتی امتحان می‌شوند که مدلِ قبلیِ همان کلید خطا بدهد؛ پس باید همان capability را داشته باشند."
)
AI_POOL_FALLBACK_SAVED = "✅ مدل‌هایِ پشتیبان ذخیره شد."

ASK_AI_POOL_CAP = (
    "سقفِ همزمانیِ همینِ کلید را بنویس: چند درخواستِ اینِ کلید می‌تواند *هم‌زمان* در حالِ اجرا باشد؟\n\n"
    "· عددِ مجاز: ۱ تا ۵۰۰\n"
    "· اگر نمی‌دانی از سرویس‌دهنده بپرس؛ هرچه بالاتر، همان‌قدر درخواستِ بیشتر در لحظه (به شرطِ این‌که "
    "سقفِ کلِ پلتفرم هم بالاتر باشد)\n"
    "· برایِ بازگشت به سهمِ مساوی بنویس «خالی»\n\n"
    "این عدد در پنل ذخیره می‌شود و *به تنظیماتِ محیطی نیازی ندارد*."
)
AI_POOL_CAP_SAVED = "✅ سقفِ همزمانیِ اینِ کلید ذخیره شد و از درخواستِ بعدی اعمال می‌شود."


def ai_pool_cap_screen_text(cap_label: str, report: dict[str, int]) -> str:
    """خلاصهٔ عددیِ بالایِ فرمِ سقفِ همزمانی: همینِ کلید + سقفِ پلتفرم + جمعِ همه."""
    return (
        f"سقفِ فعلیِ اینِ کلید: {cap_label}\n"
        f"سقفِ کلِ پلتفرم (تنظیماتِ محیطی): {fa_number(report['ceiling'])} درخواستِ هم‌زمان\n"
        f"جمعِ سقفِ {fa_number(report['keys'])} کلیدِ فعال: {fa_number(report['sum_caps'])} درخواستِ هم‌زمان"
    )


def ai_pool_entry_added_confirmation(label: str) -> str:
    return f"✅ کلیدِ «{label}» اضافه شد."


def _mask_api_key(api_key: str) -> str:
    if len(api_key) <= 8:
        return "•" * len(api_key)
    return f"{api_key[:4]}…{api_key[-4:]}"


def ai_pool_entry_detail_text(entry) -> str:
    from app.services import ai_pool_service

    cap = entry.capability.value if hasattr(entry.capability, "value") else entry.capability
    status = "فعال 🟢" if entry.is_active else "غیرفعال ⚪️"
    # P18 · A4: زنجیره‌یِ مدل‌ها باید دیده شود تا ادمین بداند واقعاً چه چیزی امتحان می‌شود.
    fallbacks = (getattr(entry, "fallback_models", "") or "").strip()
    return (
        f"برچسب: {entry.label}\n"
        f"کلید: {_mask_api_key(entry.api_key)}\n"
        f"مدل: {entry.model}\n"
        f"پشتیبان‌هایِ همین کلید: {fallbacks or '—'}\n"
        f"base_url: {entry.base_url}\n"
        f"نوع: {cap}\n"
        # P47: سقفِ همزمانیِ همینِ کلید — همان عددی که ادمین از سرویس‌دهنده می‌پرسد و همین‌جا می‌نویسد.
        f"سقفِ همزمانی: {ai_pool_service.key_cap_label(entry)}\n"
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
    from app.utils.jalali import format_jalali_datetime

    when = format_jalali_datetime(role.created_at) if role.created_at else "—"
    scope = admin_role_scope_label(role)
    return (
        f"👤 {label}\n"
        f"نقش: ادمینِ عملیاتی\n"
        f"دامنهٔ دسترسی: {scope}\n"
        f"اضافه‌شده توسطِ: {granter_label}\n"
        f"تاریخ: {when}\n"
        f"🔧 شناسه‌یِ فنی: {role.telegram_id}"
    )


def admin_role_scope_label(role) -> str:
    ids = getattr(role, "allowed_owner_ids", None)
    if ids is None:
        return ROLE_SCOPE_UNLIMITED_LABEL
    if not str(ids).strip():
        return ROLE_SCOPE_EMPTY_LABEL
    return ROLE_SCOPE_COUNT_LABEL.format(count=len([part for part in ids.split(",") if part.strip()]))


_AUDIT_EVENT_LABELS = {
    "moderation_match": "🛡 تطبیقِ نگهبانِ محتوا",
    "moderation_reviewed": "🛡 بسته‌شدنِ گزارشِ نگهبانِ محتوا",
    "moderation_chat_viewed": "👁 دیدنِ گفتگو از رویِ گزارشِ نگهبانِ محتوا",
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
    "owner_wallet_corrected": "🧮 اصلاحِ دستیِ کیف‌پول",
    "wallet_ledger_exported": "📤 خروجیِ دفترِ کیف‌پول (اکسل)",
    "wallet_reconciled": "🔍 نگاهِ همسنجیِ دفترِ کیف‌پول",
    "owner_profile_updated": "🪪 تغییرِ پروفایلِ فروشگاه‌دار",
    "owner_business_mode_changed": "🏬 تغییرِ نوعِ کسب‌وکار",
    "customer_block_changed": "🚫 مسدود/بازکردنِ مشتری",
    "bot_bio_tampered": "📝 تغییرِ بیوگرافیِ ربات",
    "branding_text_changed": "🧴 تغییرِ متنِ برند",
    "audit_exported": "📥 خروجیِ CSVِ دفترِ ممیزی",
    "owner_deactivated": "🧊 غیرفعال‌کردنِ حسابِ فروشگاه‌دار",
    "owner_restored": "♻️ بازگرداندنِ حسابِ فروشگاه‌دار",
    "owner_purged": "🔥 حذفِ قطعیِ دادهٔ فروشگاه‌دار",
    # پ۶۵ · موردِ ۲۷/۴۱-ب: حذفِ حساب *از پنلِ خودِ فروشگاه‌دار* (بی‌نام‌سازیِ هویت، اسنادِ مالی می‌ماند).
    "owner_self_deleted": "🧊 حذفِ حسابِ خودِ فروشگاه‌دار",
    "subscription_extended": "➕ تمدیدِ روزِ اشتراک توسطِ ادمین",
    "ai_usage_control_changed": "📊 سقف/توقفِ مصرفِ AIِ مشتری توسطِ فروشگاه‌دار",
    # P49-الف: کانالِ اینستاگرام (سوییچِ سراسری + اتصال/قطعِ اتصالِ فروشگاه).
    "instagram_toggled": "🟣 تغییرِ سوییچِ اینستاگرام",
    "instagram_connected": "🟣 اتصالِ اکانت اینستاگرام",
    "instagram_unbound": "🟣 حذفِ اتصالِ اینستاگرام",
    "retention_applied": "🗓 اجرایِ سیاستِ نگهداریِ داده (پاک‌سازیِ ردیف‌هایِ کهنه)",
    "instagram_data_erased": "🧹 حذفِ دادهٔ دایرکتِ اینستاگرام (حقِ فراموشی)",
    "web_panel_action": "🌐 نوشتن از پنلِ وبِ فروشگاه‌دار",
}


def audit_event_label(event_type) -> str:
    """برچسبِ فارسیِ هر رویدادِ ممیزی (در پنل و در فایلِ خروجی یکی)."""
    value = event_type.value if hasattr(event_type, "value") else str(event_type or "")
    return _AUDIT_EVENT_LABELS.get(value, value)


def audit_log_entry_line(entry) -> str:
    from app.utils.jalali import format_jalali_datetime

    label = audit_event_label(entry.event_type)
    when = format_jalali_datetime(entry.created_at) if entry.created_at else ""
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
CAMPAIGNS_LIST_TRUNCATED = "⚠️ فقط {limit} کمپینِ آخر نشان داده می‌شود؛ قدیمی‌ترها در این فهرست نیستند."
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
    return "نامحدود" if value is None else f"{fa_number(value)} {unit}"


def campaign_discount_description(discount_type, value: int, max_discount_toman: int | None) -> str:
    type_value = discount_type.value if hasattr(discount_type, "value") else discount_type
    if type_value == "percent":
        text = f"{fa_number(value)} درصد"
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
    lines.append(f"مدت: {fa_number(data['duration_days'])} روز — از همین الان تا {format_jalali_datetime(ends_at)} (به وقتِ تهران)")
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
    lines.append(f"\nاستفاده‌شده: {fa_number(uses)} بار — جمعِ تخفیفِ داده‌شده: {format_toman(discount_total_toman)}")
    if campaign.total_usage_limit is not None:
        lines.append(f"ظرفیتِ باقی‌مانده: {fa_number(max(0, campaign.total_usage_limit - uses))} بار")
    lines.append("(سفارش‌هایی که ردشدن یا رزروشون منقضی شده، حساب نمی‌شن.)")
    return "\n".join(lines)


def campaign_announcement_text(campaign) -> str:
    """متنِ پیش‌فرضِ اعلامِ کمپین به مشتری‌ها — فروشگاه‌دار قبل از ارسال می‌بینه."""
    from app.utils.jalali import format_jalali_datetime

    type_value = campaign.discount_type.value if hasattr(campaign.discount_type, "value") else campaign.discount_type
    if type_value == "percent":
        offer_line = f"{fa_number(campaign.discount_value)} درصد تخفیف روی کلِ سبدِ خرید"
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
        lines.append(f"هر نفر حداکثر {fa_number(campaign.per_customer_limit)} بار می‌تونه استفاده کنه.")
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


# پ۷۵ · خواستهٔ مالک (موردِ ۹): «سوال‌هایِ بی‌جوابِ مشابه را گروه کن و از آن‌ها دانش بساز».
GAP_CLUSTERS_BUTTON = "🧠 سوال‌هایِ مشابه"
GAP_CLUSTERS_TITLE = "🧠 سوال‌هایِ مشابه — {clusters} گروه از {gaps} سوالِ باز"
GAP_CLUSTERS_INTRO = (
    "هر گروه چند سوالِ *متفاوت* است که واژه‌هایِ اصلی‌شان یکی است (ترتیبِ کلمات، علامت‌ها و "
    "پیشوند/پسوند فرق نمی‌کند). با «✍️ یکِ جواب برایِ همه» یکِ پرسش‌وپاسخ می‌سازی و همهٔ سوال‌هایِ آن "
    "گروه بسته می‌شوند — جواب را خودت می‌نویسی و تا تایید نکنی چیزی به ربات اضافه نمی‌شود."
)
GAP_CLUSTERS_EMPTY = (
    "🧠 فعلاً دو سوالِ شبیه هم نداری. هر وقت چند مشتری چیزی را به شکل‌هایِ مختلف پرسیدند، اینجا "
    "گروه می‌شوند."
)
ASK_CLUSTER_ANSWER = (
    "جوابِ این گروه را بنویس (همان جواب برایِ همهٔ {count} سوال ذخیره می‌شود). برایِ انصراف «انصراف» "
    "را بزن."
)
CLUSTER_PREVIEW_QUESTION = "🧩 سوال‌هایِ این گروه:"
CLUSTER_SAVED = "✅ دانش ساخته شد و {count} سوالِ این گروه بسته شد."
GAP_CLUSTER_STALE = "این گروه دیگر باز نیست؛ فهرستِ سوال‌هایِ بی‌جواب را دوباره باز کن."


def gap_cluster_line(index: int, cluster: dict) -> str:
    """یکِ خطِ فهرست: «۱. «سوالِ نماینده» — ۳ سوال · ۷ تکرار»."""
    return (
        f"{fa_number(index)}. «{clip(cluster['representative'].question_text, 52)}» — "
        f"{fa_number(cluster['size'])} سوال · {fa_number(cluster['occurrences'])} تکرار"
    )


def gap_clusters_text(clusters: list[dict], open_total: int) -> str:
    if not clusters:
        return GAP_CLUSTERS_EMPTY
    grouped = sum(cluster["size"] for cluster in clusters)
    lines = [GAP_CLUSTERS_TITLE.format(clusters=fa_number(len(clusters)), gaps=fa_number(open_total)), ""]
    lines.extend(gap_cluster_line(index, cluster) for index, cluster in enumerate(clusters, start=1))
    lines += ["", GAP_CLUSTERS_INTRO]
    if grouped < open_total:
        lines.append("")
        lines.append(f"• {fa_number(open_total - grouped)} سوالِ باز در هیچ گروهی نیستند (تنها خودش‌اند).")
    return "\n".join(lines)


def gap_cluster_detail_text(cluster: dict) -> str:
    lines = [
        f"🧠 گروه با {fa_number(cluster['size'])} سوالِ متفاوت · {fa_number(cluster['occurrences'])} بار پرسیده شده",
        "",
        CLUSTER_PREVIEW_QUESTION,
    ]
    lines += [f"• {clip(question, 70)}" for question in cluster["questions"]]
    return "\n".join(lines)


def gaps_page_text(gaps, total: int, page: int, page_size: int) -> str:
    """سوالِ مشتری غیرِ قابلِ اعتماده؛ همیشه متنِ ساده (بدونِ parse_mode) نمایش داده می‌شه."""
    lines = [f"🧩 سوال‌هایِ بی‌جواب ({fa_number(total)} مورد) — بیشترین تکرار اول:\n"]
    for index, gap in enumerate(gaps, start=page * page_size + 1):
        lines.append(f"{fa_number(index)}. «{gap.question_text}»\n   🔁 {fa_number(gap.occurrences)} بار پرسیده شده")
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
        f"📚 پرسش‌وپاسخ‌هایِ تاییدشده ({fa_number(total)} مورد)\n"
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
ADMIN_WALLET_RECONCILE_LABEL = "🔎 همسنجیِ دفترِ کیف‌پول"
ADMIN_RECONCILE_CLEAN = "✅ همسنجیِ دفترِ کیف‌پول: هیچ اختلافی نیست. (موجودیِ هر فروشگاه‌دار = مجموعِ ردیف‌هایِ دفتر = مجموعِ بسته‌هایِ فعال)"
ADMIN_RECONCILE_NOTE = "هیچ داده‌ای خودکار اصلاح نمی‌شود؛ اصلاح با ردیفِ معکوسِ جدید و دلیلِ ادمین است."


def admin_reconcile_gaps(gaps: list[dict], limit: int) -> str:
    """گزارشِ فارسیِ اختلاف‌ها؛ شناسه‌یِ داخلی نمایش داده نمی‌شود و فهرست سقف دارد."""
    lines = [f"⚠️ {fa_number(len(gaps))} فروشگاه‌دار اختلافِ حسابداری دارد:"]
    for gap in gaps[:8]:
        lines.append(
            f"• @{gap['telegram_id']} | کشیده: {format_toman(gap['cached_toman'])} | "
            f"دفتر: {format_toman(gap['ledger_toman'])} (اختلاف {format_toman(gap['ledger_delta_toman'])}) | "
            f"بسته‌ها: {format_toman(gap['lots_toman'])}"
        )
    if len(gaps) > 8:
        lines.append(f"نمونه‌یِ ۸ مورد نمایش داده شد (سقفِ کوئری {fa_number(limit)}).")
    lines.append(ADMIN_RECONCILE_NOTE)
    return "\n".join(lines)
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
        f"💳 پرداختِ آنلاین: {fa_number(summary.online_paid_count)} مورد — {format_toman(summary.online_paid_toman)}",
    ]
    if summary.status_counts:
        lines.append("\n📋 وضعیتِ سفارش‌هایِ ثبت‌شده در این بازه:")
        lines.extend(f"  {accounting_status_label(status)}: {fa_number(count)}" for status, count in summary.status_counts.items())
    if report.pending_total > 0:
        lines.append(f"\n⏳ در حالِ حاضر کلاً {fa_number(report.pending_total)} سفارش منتظرِ بررسیِ شماست.")
    if summary.top_products:
        lines.append("\n🏆 پرفروش‌ترین‌ها:")
        for index, product in enumerate(summary.top_products, start=1):
            lines.append(f"  {fa_number(index)}. {product.name} — {fa_number(product.units)} عدد — {format_toman(product.net_toman)}")
    if summary.campaigns:
        lines.append("\n🎯 عملکردِ کمپین‌ها (سفارش‌هایِ تاییدشده):")
        for campaign in summary.campaigns:
            lines.append(
                f"  • {campaign.name}: {fa_number(campaign.uses)} بار مصرف — تخفیف {format_toman(campaign.discount_toman)}"
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
# پ۵۶ · موردِ ۴۱: جست‌وجویِ مشتری در پنلِ فروشگاه‌دار
CRM_SEARCH_BUTTON = "🔍 جست‌وجویِ مشتری"
CRM_SEARCH_ASK = (
    "چه چیزی را بگردم؟ نام، نامِ خانوادگی، نامِ کاربری، شمارهٔ موبایل یا شناسهٔ تلگرام.\n"
    "· فقط مشتری‌هایِ همین فروشگاه جست‌وجو می‌شوند.\n"
    "· برایِ لغو «انصراف» بنویس."
)
CRM_SEARCH_INVALID = "این عبارت را نفهمیدم یا خیلی بلند است؛ نام، نامِ کاربری، تلفن یا شناسهٔ تلگرام بنویس."
CRM_SEARCH_CANCELLED = "↩️ جست‌وجو لغو شد."


def crm_search_intro(term: str, total: int, page: int, total_pages: int) -> str:
    return (
        f"🔍 نتیجهٔ جست‌وجویِ «{term}» — {fa_number(total)} مشتری (صفحه‌یِ {fa_number(page + 1)} از {fa_number(total_pages)})\n"
        "روی هر مورد بزن تا کارتِ مشتری باز بشه:"
    )


CRM_SEARCH_EMPTY_TMPL = "🔍 مشتری‌ای با «{term}» در فروشگاهت پیدا نشد."
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
    lines = [f"💬 گفتگو با {customer_name}", f"صفحه‌یِ {fa_number(page + 1)} از {fa_number(total_pages)} — در مجموع {fa_number(total)} پیام", ""]
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
    lines = [f"👥 مشتری‌هایِ فروشگاهت — کل: {fa_number(total)} نفر\n"]
    for key, label in CRM_SEGMENT_LABELS.items():
        lines.append(f"{label}: {fa_number(counts.get(key, 0))} نفر\n   ↳ {CRM_SEGMENT_HINTS[key]}")
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
    lines = [f"{label} — {fa_number(total)} نفر (صفحه‌ی {fa_number(page + 1)} از {fa_number(total_pages)})\n"]
    for index, stat in enumerate(members, start=page * page_size + 1):
        lines.append(
            f"{fa_number(index)}. {crm_customer_name(stat)}\n"
            f"   🧾 {fa_number(stat.success_count)} سفارش — 💰 {format_toman(stat.net_toman)} — 📅 {_crm_date(stat.last_activity)}"
        )
    return "\n".join(lines)


def crm_card_text(stat, customer, orders) -> str:
    tags = [tag for tag in (customer.crm_tags or "").split(",") if tag]
    lines = [
        f"👤 {crm_customer_name(stat)}",
        f"بخش: {CRM_SEGMENT_LABELS.get(stat.segment, stat.segment)}",
        f"🧾 سفارشِ موفق: {fa_number(stat.success_count)} — 💰 خریدِ خالص: {format_toman(stat.net_toman)}",
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
            lines.append(f"{fa_number(index)}. {order_status_label(order.status)} — {what}{fa_number(quantity)}{value} — {_crm_date(order.created_at)}")
    else:
        lines.append("\nهنوز سفارشی ثبت نکرده.")
    return "\n".join(lines)


def crm_broadcast_ask(label: str, count: int) -> str:
    return f"متنِ پیامی که می‌خوای برایِ {fa_number(count)} مشتریِ بخشِ «{label}» بفرستی رو بنویس:"


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
SHOP_PREF_BACK_BUTTON = "⬅️ برگشت"

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
    # P46 · موردِ ۳۷: «حافظهٔ این گفتگو» تصمیمِ خودِ فروشگاه است.
    "history_limit_messages": (
        "💭 حافظه‌ی مکالمه",
        "پیام",
        "هر بار که ربات جواب می‌دهد، چند پیامِ آخرِ همان گفتگو به هوش مصنوعی نشان داده می‌شود. "
        "عددِ بیشتر یعنی جوابِ باحافظه‌تر و توکنِ بیشتر (هزینه با خودت است).",
    ),
    # P46 · نیمهٔ کاربرمحورِ موردِ ۱۴: سقفِ پیام هم per-shop.
    "rate_limit_messages": (
        "🚦 سقفِ پیامِ هر مشتری",
        "پیام",
        "هر مشتری در یکِ پنجره‌یِ زمانی چند پیام بفرستد، پیامِ بعدی‌اش موقتاً رد می‌شود. "
        "بالا بردنِ این عدد هزینه‌یِ خودت و فشارِ بیشتر رویِ سرویسِ هوش مصنوعی است.",
    ),
    "rate_limit_seconds": (
        "🚦 طولِ پنجره‌یِ سقفِ پیام",
        "ثانیه",
        "همان سقفِ پیام در این چند ثانیه شمرده می‌شود.",
    ),
}


def shop_prefs_text(shop_bot, admin_settings, prefs) -> str:
    from app.services import shop_prefs_service

    lines = [f"{SHOP_PREFS_BUTTON} — فقط برایِ همین فروشگاه", ""]
    for pref in prefs:
        label, unit, _help = SHOP_PREF_LABELS[pref.key]
        effective = shop_prefs_service.resolve(pref, shop_bot, admin_settings)
        origin = "خودت" if getattr(shop_bot, pref.key, None) is not None else "پیش‌فرضِ سراسری"
        lines.append(f"• {label}: {fa_number(effective)} {unit} ({origin})")
    lines.append("")
    lines.append("روی هر کدام بزن تا عوضش کنی. این‌ها سراسری نیستند و رویِ بقیه‌یِ فروشگاه‌ها اثر ندارند.")
    return "\n".join(lines)


def shop_pref_text(shop_bot, admin_settings, pref) -> str:
    from app.services import shop_prefs_service

    label, unit, help_text = SHOP_PREF_LABELS[pref.key]
    stored = getattr(shop_bot, pref.key, None)
    effective = shop_prefs_service.resolve(pref, shop_bot, admin_settings)
    origin = f"مقدارِ خودت: {fa_number(stored)} {unit}" if stored is not None else "هنوز تنظیم نکرده‌ای ⇒ پیش‌فرضِ سراسری"
    return (
        f"{label}\n\n"
        f"اثرِ فعلی: {fa_number(effective)} {unit}\n"
        f"{origin}\n"
        f"بازه‌یِ مجاز: {fa_number(pref.low)} تا {fa_number(pref.high)} {unit}\n\n"
        f"{help_text}"
    )


def shop_pref_ask(pref) -> str:
    _label, unit, _help = SHOP_PREF_LABELS[pref.key]
    return f"عددِ دلخواه را به {unit} بنویس ({fa_number(pref.low)} تا {fa_number(pref.high)}). برایِ انصراف /cancel رو بزن."


def shop_pref_invalid(pref) -> str:
    _label, unit, _help = SHOP_PREF_LABELS[pref.key]
    return f"عدد نامعتبره. یه عددِ صحیح بینِ {fa_number(pref.low)} تا {fa_number(pref.high)} {unit} بنویس."


# ------------------------------------------------------------------ P18 · C2: «💬 گفتگوها و کاربران» (مشاوره)
CONSULT_CONTACTS_BUTTON = "💬 گفتگوها و کاربران"
CONSULT_NO_CATALOG = "🗂 در مودِ مشاوره‌ای کاتالوگِ محصول/خدمت نداریم؛ مخاطب همین‌جا در چت سوالش را می‌پرسد."
# پ۵۸ · موردِ ۲۴: دروازهٔ مشترکِ صفحه‌هایی که فقط در مودِ فروشگاهی معنا دارند
MODE_SALES_ONLY = (
    "🏪 این بخش فقط در مودِ «فروشگاهی» کار می‌کند (محصول، سبد، سفارش، کمپین و حسابداری).\n"
    "در مودِ مشاوره‌ای همین اطلاعات را در «💬 گفتگوها و کاربران» داری.\n"
    "اگر می‌خوای مودِ فروشگاهت عوض بشه، به «👤 پروفایل من» برو."
)
CONSULT_CONTACTS_EMPTY = "💬 هنوز کسی با رباتِ مشاوره‌ای تو چت نکرده."
CONSULT_CONTACTS_STALE = "این مخاطب پیدا نشد. دوباره «💬 گفتگوها و کاربران» رو بزن."
CONSULT_BLOCK_DONE = "🚫 بلاک شد؛ ربات از این پس فقط یک پیامِ ادبی به او می‌دهد."
CONSULT_UNBLOCK_DONE = "✅ رفعِ بلاک شد."
CONSULT_CONTACT_BACK = "⬅️ برگشت به فهرست"
CONSULT_CONTACTS_SALES_HINT = "👥 در مودِ فروشگاهی همین اطلاعات را با بخش‌بندی و یادداشت در «👥 مشتری‌ها» داری."


def consult_contacts_text(members, total: int, page: int, total_pages: int) -> str:
    lines = [f"💬 گفتگوها و کاربران — {fa_number(total)} مخاطب (صفحه‌ی {fa_number(page + 1)} از {fa_number(total_pages)})\n"]
    for index, customer in enumerate(members, start=1):
        lines.append(f"{fa_number(index)}. {crm_customer_label(customer)}")
    lines.append("\nروی هر کدام بزنی گفتگو و بلاک/رفعِ بلاک را می‌بینی.")
    return "\n".join(lines)


CONSULT_CONTACTS_PAGE_SIZE = 10


# ------------------------------------------------------------------ P18 · B9: گام‌هایِ پیش‌فرضِ چک‌اوت
CHECKOUT_STEPS_BUTTON = "🧾 گام‌هایِ پیش‌فرضِ چک‌اوت"
CHECKOUT_STEP_LABELS = {
    # پ۶۸: «استان» و «شهر» زیرگامِ «آدرسِ تحویل» هستند و پیش‌فرض خاموش‌اند (از مشتری پرسیده نمی‌شود).
    "province": "🗺 استان",
    "city": "🏙 شهر",
    "name": "👤 نامِ تحویل‌گیرنده",
    "phone": "📱 شماره‌یِ موبایل",
    "address": "🏠 آدرسِ تحویل",
    "shipping": "🚚 روشِ ارسال",
    "note": "📝 توضیحِ سفارش",
}
CHECKOUT_STEP_ON = "⛔️ خاموش‌کردن"
CHECKOUT_STEP_OFF = "✅ روشن‌کردن"
# نشانِ وضعیت در فهرستِ گام‌ها (ردیفِ دونفره ⇒ برچسب باید کوتاه بماند؛ فعلِ «خاموش‌کردن» آن‌جا جا نمی‌شود)
CHECKOUT_STEP_MARK_ON = "✅"
CHECKOUT_STEP_MARK_OFF = "⏸"
CHECKOUT_STEP_QUESTION_BUTTON = "✏️ متنِ پرسش"
CHECKOUT_STEPS_BACK_BUTTON = "⬅️ برگشت"
CHECKOUT_STEPS_SAVED = "✅ ذخیره شد."
CHECKOUT_STEPS_STALE = "این دکمه دیگه معتبر نیست. دوباره از «📝 سوال‌هایِ چک‌اوتِ سبد» شروع کن."
CHECKOUT_STEPS_GUARD = "🚫 آدرس و موبایل را نمی‌توانی هم‌زمان خاموش کنی؛ سفارش باید راهی برایِ تحویل داشته باشد."
CHECKOUT_STEP_QUESTION_ASK = (
    "متنِ پرسش را بنویس (حداکثر ۱۵۰ نویسه). برایِ برگشت به متنِ پیش‌فرض بنویس «خالی». برایِ انصراف /cancel رو بزن."
)
CHECKOUT_STEP_QUESTION_TOO_LONG = (
    "متنِ پرسش نباید بیشتر از ۱۵۰ نویسه باشه. کوتاه‌ترش کن یا «خالی» بنویس تا متنِ پیش‌فرض برگردد."
)
CHECKOUT_STEP_PHYSICAL_HINT = "🧾 این گام فقط وقتی در چک‌اوت می‌آید که سبد کالایِ فیزیکی داشته باشد."
CHECKOUT_STEP_REGION_HINT = (
    "🗺 «استان» و «شهر» دو زیرگامِ جدا از «آدرس» هستند و پیش‌فرض خاموش‌اند تا مشتری آدرس را در یک پیام بنویسد. "
    "اگر می‌خواهی هر کدام را جدا از مشتری بپرسی، روشنشان کن."
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
        if key in ("province", "city"):
            marks.append("زیرِ گامِ «آدرسِ تحویل»")
        if step.question != checkout_config_service.DEFAULT_QUESTIONS[key]:
            marks.append("متنِ خودت")
        tail = f" ({' · '.join(marks)})" if marks else ""
        lines.append(f"• {label}: {state}{tail}")
    lines.append("")
    lines.append("گامی که خاموش باشد از مشتری پرسیده نمی‌شود و در سفارش هم ثبت نمی‌شود.")
    lines.append(CHECKOUT_STEP_REGION_HINT)
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
    current_line = f"{fa_number(current)} ثانیه" if current else f"{fa_number(default_seconds)} ثانیه (پیش‌فرضِ سیستم)"
    names = REPORT_WEEKDAY_NAMES
    report_line = (
        f"{names[int(shop_bot.weekly_report_weekday) % len(names)]} ساعتِ {fa_number(f'{int(shop_bot.weekly_report_hour):02d}:00')}"
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
        f"ساعت: {fa_number(f'{int(shop_bot.weekly_report_hour):02d}:00')} (به وقتِ تهران)\n\n"
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
DG_ARCHIVE_BUTTON = "🗄 بایگانیِ محصول‌هایِ دیجیتال"
DG_ARCHIVE_ASK = (
    "این فروشگاه {count} محصولِ دیجیتال دارد. با بایگانی، آن‌ها از فهرستِ محصولاتِ پنل، کاتالوگِ مشتری و "
    "پرامپتِ ربات بیرون می‌روند. هیچ ردیف، کد یا سفارشی پاک نمی‌شود و برگشتنی است."
)
DG_ARCHIVE_UNDO_NOTE = "• اگر پشیمان شدی، همان‌جا دکمهٔ «بازگرداندنِ بایگانی» هست."
DG_ARCHIVE_DONE = "بایگانی شد: {count} محصولِ دیجیتال از فهرست‌ها بیرون رفت (هیچ داده‌ای پاک نشد)."
DG_ARCHIVE_NONE = "محصولِ بایگانی‌نشده‌ای برایِ بایگانی کردن نیست."
DG_ARCHIVE_ALL = "همهٔ {count} محصولِ دیجیتالِ این فروشگاه بایگانی شده‌اند (هیچ داده‌ای پاک نشده). برایِ برگرداندن: دکمهٔ پایین."
DG_UNARCHIVE_BUTTON = "↩️ بازگرداندنِ بایگانی"
DG_UNARCHIVE_DONE = "بازگشت: {count} محصولِ دیجیتال دوباره در فهرست‌ها دیدنی شد."
DG_UNARCHIVE_NONE = "چیزی بایگانی نشده بود که برگردد."
DG_ARCHIVE_CONFIRM_YES = "✅ بله، بایگانی کن"
DG_ARCHIVE_CONFIRM_NO = "⬅️ بی‌خیال، چیزی عوض نشود"
DG_RETIRED = (
    "ساختنِ محصولِ دیجیتال از این نسخه متوقف شده است. محصول‌ها، کدها و سفارش‌هایِ "
    "موجود دست‌نخورده‌اند و برایِ همان محصولاتِ دیجیتال می‌توانی کدِ تازه اضافه کنی."
)
DG_STALE = "این دکمه دیگه معتبر نیست. از فهرستِ محصولات ادامه بده."
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
    lines = [f"✅ {fa_number(added)} کدِ جدید اضافه شد. موجودیِ فعلی: {available} کد."]
    if duplicates:
        lines.append(f"♻️ {duplicates} کدِ تکراری نادیده گرفته شد.")
    if ignored:
        lines.append(f"⚠️ {fa_number(ignored)} خط (تکراری/بیش‌ازحد بلند/خارج از سقفِ ۵۰۰۰تایی) نادیده گرفته شد.")
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
        lines.append(f"📬 {fa_number(delivered)} سفارشِ منتظر هم الان تحویل داده شد.")
    if still_waiting:
        lines.append(f"⏳ {fa_number(still_waiting)} سفارش هنوز منتظرِ کدِ بیشتره.")
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
            lines.append(f"📥 سقفِ دریافت: {fa_number(product.digital_max_downloads)} بار")
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
def switch_toast(subject: str, enabled: bool) -> str:
    """بازخوردِ هر سوییچِ پنل: چه چیزی و به کدام طرف عوض شد (P22 · لایهٔ بازخورد)."""
    return f"{subject}: {'روشن ✅' if enabled else 'خاموش ⏸'}"


PAYS_STALE = "این پرداخت پیدا نشد یا دیگه به این عملیات نیاز نداره."
PAYS_ILLEGAL = "در وضعیتِ فعلیِ پرداخت این کار مجاز نیست (شاید قبلاً تصمیم گرفته شده)."
PAYS_ASK_REJECT_REASON = "دلیلِ ردِ رسید رو انتخاب کن (مشتری همین رو می‌بینه):"
PAYS_ASK_REJECT_TEXT = "دلیل رو بنویس (حداکثر ۳۰۰ حرف). /cancel = انصراف"
PAYS_APPROVED_SUFFIX = "✅ پرداخت تایید شد و سفارش «پرداخت‌شده» است."
PAYS_REJECTED_SUFFIX = "❌ رسید رد شد؛ مشتری خبردار شد."
PAYS_CUSTOMER_NOTIFY_FAILED = "⚠️ تصمیم ثبت شد ولی پیام به مشتری نرسید (احتمالاً رباتِ فروشگاه رو مسدود کرده)."
PAYS_SAVED = "✅ ذخیره شد."
# P22 (لایهٔ بازخورد): هر سوییچ باید بگوید چه شد، و هر پیامِ راهنما باید در همین فایل باشد.
PAYS_METHOD_LABELS = {
    "card": "💳 کارت‌به‌کارت",
    "bale": "🟢 بله‌پی",
    "zarinpal": "🟡 زرین‌پال",
    "manual": "🤝 پرداختِ دستی/هماهنگی",
    "auto": "⚡ تاییدِ خودکارِ آنلاین",
}
PAYS_TOGGLED = "{label}: {state}"
PAYS_NEEDS_CARD_FIRST = "اول «💳 تنظیمِ کارت (شماره/نام/بانک)» رو کامل کن (شماره و نامِ صاحبِ کارت)."
PAYS_NEEDS_BALE_FIRST = "اول «🔵 بله‌پی: توکنِ ربات + درگاه» را همین صفحه ثبت کن."
PAYS_NEEDS_ZARINPAL_FIRST = "اول «🔑 مرچنتِ زرین‌پال» رو ثبت کن."
PAYS_LAST_METHOD_GUARD = "حداقل یک روش باید فعال بمونه؛ پرداختِ دستی تنها روشِ فعاله."


PAYS_INVALID_CARD = "شماره‌کارتِ معتبرِ ۱۶رقمی بفرست (فاصله/ارقامِ فارسی مشکلی نداره)."
PAYS_ASK_CARD_NUMBER = "شماره‌کارتِ ۱۶رقمیِ فروشگاه رو بفرست (برایِ مشتری نمایش داده می‌شه):"
PAYS_ASK_CARD_HOLDER = "نامِ صاحبِ کارت رو بنویس (برایِ رد کردن «-»):"
PAYS_ASK_CARD_BANK = "نامِ بانک رو بنویس (برایِ رد کردن «-»):"
PAYS_INVALID_NUMBER = "عددِ معتبر در بازه‌یِ مجاز بفرست."
PAYS_ASK_ZARINPAL = "مرچنت‌کدِ ۳۶نویسه‌ایِ زرین‌پالِ خودت رو بفرست (برایِ حذف «حذف»):"
PAYS_INVALID_MERCHANT = "مرچنت‌کد باید ۳۶ نویسه باشه (حروفِ انگلیسی/عدد/خط‌تیره)."
PAYS_NEEDS_SALES_MODE = "این بخش فقط برایِ فروشگاهِ فروشگاهی است."


def payments_menu_text(row, shop_bot, bale_missing=()) -> str:
    """`bale_missing` نتیجه‌یِ `bale_credentials_service.shop_status` است تا وضعیتِ نشان‌داده‌شده به فروشگاه‌دار
    دقیقاً همان چیزی باشد که مشتری تجربه می‌کند (B11: هرگز «✅ روشن» در حالی که مسیرِ مشتری بسته است)."""
    from app.services import payment_settings_service as pss

    def flag(value) -> str:
        return "✅ روشن" if value else "⛔️ خاموش"

    card_number = pss.get_card_number(row)
    own_token = bool(shop_bot.bale_provider_token)
    # P41: درگاهِ سراسریِ ادمین هرگز برایِ پرداختِ *سفارش* مصرف نمی‌شود (پولِ مشتری نباید در
    # کیف‌پولِ پلتفرم بنشیند)؛ پس نوشتنِ «توکنِ سراسریِ مدیر استفاده می‌شود» گمراه‌کننده بود.
    global_note = "" if own_token else " (درگاهِ سراسری برایِ پرداختِ سفارش استفاده نمی‌شود)"
    bale_line = (
        f"بله‌پی: {flag(not bale_missing)} — توکنِ درگاهِ فروشگاه: {'تنظیم شده' if own_token else 'تنظیم نشده'}"
        f"{global_note}"
        f" — مهلت: {fa_number(row.bale_deadline_minutes)} دقیقه"
    )
    lines = [
        "💳 روش‌هایِ پرداختِ مشتری",
        "",
        f"کارت‌به‌کارت: {flag(row.card_enabled and bool(card_number))} — کارت: {pss.mask_card(card_number)} — مهلت: {fa_number(row.card_deadline_minutes)} دقیقه — نگهداریِ بررسیِ رسید: {fa_number(row.receipt_review_hold_minutes)} دقیقه",
        bale_line,
        f"زرین‌پال: {flag(row.zarinpal_enabled and bool(row.zarinpal_merchant_id_enc))} — مرچنت: {'تنظیم شده' if row.zarinpal_merchant_id_enc else 'تنظیم نشده'} — مهلت: {fa_number(row.zarinpal_deadline_minutes)} دقیقه",
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
    return f"مهلتِ پرداخت (دقیقه) رو بفرست — بینِ {fa_number(low)} و {fa_number(high)}. موجودی دقیقاً همین‌قدر رزرو می‌مونه:"


def pays_ask_hold(low: int, high: int) -> str:
    return f"مهلتِ بررسیِ رسید (دقیقه) — بینِ {fa_number(low)} و {fa_number(high)}. بعد از ارسالِ رسید موجودی تا این مدت رزرو می‌مونه:"


def pays_range_hint(low: int, high: int, unit: str) -> str:
    return f"بازه‌یِ مجاز: {fa_number(low)} تا {fa_number(high)} {unit}"


PAYS_LATE_APPROVED_SUFFIX = "⏰ مهلتِ این سفارش تموم شده بود؛ با تاییدِ تو دوباره رزرو و «پرداخت‌شده» شد."
PAYS_LATE_OVERSOLD_SUFFIX = "⚠️ موجودیِ بعضی اقلام دیگه کافی نیست (فروشِ بیشتر از موجودی). با مشتری هماهنگ کن یا استرداد بده."


def receipt_review_warning(code: str, hours_left: float) -> str:
    return (
        f"⏰ رسیدِ سفارشِ {code} هنوز بررسی نشده و حدودِ {fa_number(max(1, round(hours_left)))} ساعتِ دیگه مهلتش تموم می‌شه "
        "(بعدش سفارش منقضی و موجودی آزاد می‌شه؛ البته بعدش هم می‌تونی با تایید دوباره فعالش کنی). لطفاً تایید یا رد کن."
    )


# =============================================================================
# P21-D — خلاصهٔ روزانهٔ پولی، پخشِ زمان‌بندی‌شده، اخطارِ موجودی
# =============================================================================
def digest_wallet_line(
    balance_toman: int,
    usable_toman: int,
    expiring_toman: int,
    expiring_days: int | None,
    debt_toman: int,
    window_days: int | None = None,
) -> str:
    """چند خطِ پولی به انتهایِ گزارشِ شبانه (پیش‌تر فقط تعدادِ سفارش/مشتری داشت).

    `format_toman` خودش «تومان» دارد؛ افزودنِ دوبارهٔ آن واحدِ تکراری می‌ساخت
    («۱٬۰۰۰٬۰۰۰ تومان تومان») — P22 اصلاح شد.
    P44 · موردِ ۵۱: عددِ پنجرهِ انقضا («ظرفِ N روزِ آینده») دیگر در متنِ ثابت ننوشته می‌شود؛
    فراخوانِ واقعی (`report_service`) آن را از `wallet_service.EXPIRING_SOON_DAYS` می‌گیرد، پس
    اگر آن آستانه روزی عوض شود، گزارشِ شبانه دروغ نمی‌گوید. با پیش‌فرضِ همین‌جا همان ۳۰ روز است."""
    lines = ["", "💼 کیف‌پول:"]
    lines.append(f"• موجودی: {format_toman(balance_toman)}")
    if usable_toman != balance_toman:
        lines.append(f"• قابل‌استفاده الان: {format_toman(usable_toman)} (بقیه رزروِ کمیسیونِ سفارش‌هایِ درجریان است)")
    if expiring_toman > 0 and expiring_days is not None:
        window = int(window_days) if window_days else 30
        lines.append(
            f"• نزدیک‌ترین انقضا: {fa_number(expiring_days)} روزِ دیگر — "
            f"{format_toman(expiring_toman)} ظرفِ {fa_number(window)} روزِ آینده منقضی می‌شود "
            "(هر شارژ انقضایِ خودش دارد)"
        )
    if debt_toman > 0:
        lines.append(f"• طلبِ کمیسیونِ وصول‌نشده: {format_toman(debt_toman)} (با شارژِ بعدی خودکار کسر می‌شود)")
    return "\n".join(lines)


SCHEDULE_BROADCAST_BUTTON = "⏰ برایِ بعد از"
SCHEDULED_LIST_BUTTON = "⏰ ارسال‌هایِ زمان‌بندی‌شده"
ASK_SCHEDULE_WHEN = (
    "⏰ کی ارسال بشه؟\n\nیکِ گزینه را بزن، یا اگر وقتِ دیگری مدِ نظرته «✍️ ساعتِ دلخواه» را بزن "
    "و خودت بنویس (مثلاً «۲۱:۳۰» یا «فردا ۹:۳۰»). همه‌یِ ساعت‌ها به وقتِ تهران است."
)
ASK_SCHEDULE_WHEN_CUSTOM = (
    "✍️ زمان را بنویس. نمونه‌ها: «۲۱:۳۰» (امشب یا فردا اگر گذشته باشد، فردا) · «فردا ۹:۳۰» · "
    "«+۲h» · «+۴۵m» · «+۳d». برایِ لغو «لغو» بنویس."
)
SCHEDULE_INVALID_WHEN = "این را نفهمیدم. نمونه‌ها: ۲۱:۳۰ · فردا ۹:۳۰ · +۲h"
# اعدادِ ۵/۶۰/۵ در سه متنِ بالا باثباتِ `scheduled_broadcast_service` (MIN_LEAD_MINUTES،
# MAX_LEAD_DAYS، MAX_ACTIVE_PER_SHOP) یکی‌اند؛ importِ سرویس در این فایل دورِ import می‌سازد،
# پس test_p24_automation_surfaces.py همان‌ها را با متن مقایسه می‌کند (اگر عددی عوض شد، تست می‌گوید).
SCHEDULE_TOO_SOON = "حداقلِ ۵ دقیقه وقت لازم است — برایِ «همین الان» همون دکمهٔ «بله، بفرست» را بزن."
SCHEDULE_TOO_FAR = "حداکثر ۶۰ روز جلوتر می‌شود زمان‌بندی کرد."
SCHEDULE_CANCELLED = "⏱ زمان‌بندی لغو شد؛ پیامی ارسال نمی‌شود."
SCHEDULE_MAX_REACHED = "همزمان فقط ۵ ارسالِ زمان‌بندی‌نشده می‌توانی داشته باشی؛ اول یکی را لغو کن."
SCHEDULE_EMPTY = (
    "⏰ هیچ ارسالِ زمان‌بندی‌شده‌ای در انتظار نیست.\n"
    "با دکمهٔ پایین، متنِ پیام را بنویس و بعد ساعتِ ارسالش را تعیین کن."
)
# پ۷۶ · خواستهٔ مالک (موردِ ۱۷): ویزاردِ «روز → ساعت → تکرار → پایان» + ارسالِ چندروزه/هفتگی.
SCHEDULE_WIZARD_BUTTON = "🗓 روز و تکرار"
SCHEDULE_WIZARD_DAY = "🗓 کدامِ روز؟ (همه به وقتِ تهران)"
SCHEDULE_WIZARD_TIME = "⏰ چه ساعتی؟ برایِ ساعتِ دقیق‌تر «✍️ ساعتِ دلخواه» را بزن."
SCHEDULE_WIZARD_REPEAT = "🔁 یک‌بار فرستاده شود یا تکرار شود؟"
SCHEDULE_WIZARD_UNTIL = "🏁 تکرار تا کِی ادامه داشته باشد؟"
SCHEDULE_WIZARD_CUSTOM_TIME = "ساعت را بنویس (مثلاً ۲۱:۳۰ یا فردا ۹:۳۰):"
SCHEDULE_WIZARD_STALE = "🗓 این زمان دیگر معتبر نیست؛ از «⏰ برایِ بعد از» دوباره شروع کن."
SCHEDULE_WIZARD_BAD_TIME = "آن ساعت را نفهمیدم. نمونه: ۲۱:۳۰"
SCHEDULE_DAY_OPTIONS: tuple[tuple[int, str], ...] = ((0, "امروز"), (1, "فردا"), (2, "پس‌فردا"), (3, "۳ روز بعد"), (7, "یک هفته بعد"))
SCHEDULE_TIME_OPTIONS: tuple[tuple[int, str], ...] = ((9, "۹:۰۰"), (12, "۱۲:۰۰"), (15, "۱۵:۰۰"), (18, "۱۸:۰۰"), (21, "۲۱:۰۰"))
SCHEDULE_UNTIL_OPTIONS: tuple[tuple[int, str], ...] = ((3, "۳ روز"), (7, "یک هفته"), (14, "دو هفته"), (30, "یک ماه"))
SCHEDULE_REPEAT_OPTIONS: tuple[tuple[str, str], ...] = (("once", "یک‌بار"), ("daily", "هر روز"), ("weekly", "هر هفته"))
SCHEDULE_REPEAT_LABELS = {"once": "یک‌بار", "daily": "هر روز", "weekly": "هر هفته"}


def schedule_wizard_preview(when_text: str, repeat_kind: str, until_text: str | None, recipients: int) -> str:
    label = SCHEDULE_REPEAT_LABELS.get(repeat_kind, repeat_kind)
    lines = [f"🗓 زمانِ ارسال: {when_text}", f"🔁 تکرار: {label}"]
    if repeat_kind != "once":
        lines.append(f"🏁 پایانِ تکرار: {until_text}" if until_text else "🏁 پایانِ تکرار: بدونِ تاریخِ پایان (سقفِ ۶۰ نوبت)")
    lines.append(f"👥 گیرنده‌ها: {fa_number(recipients)} نفر")
    lines.append("")
    lines.append("با «✅ زمان‌بندی کن» این در صف می‌نشیند و هر نوبت سرِ وقتش ارسال می‌شود.")
    return "\n".join(lines)


def schedule_recurring_saved_text(first_text: str, repeat_kind: str, recipients: int) -> str:
    label = SCHEDULE_REPEAT_LABELS.get(repeat_kind, repeat_kind)
    return f"✅ زمان‌بندی شد: اولین ارسال {first_text} · {label} · {fa_number(recipients)} گیرنده."


SCHEDULE_NEW_BUTTON = "🕓 زمان‌بندیِ تازه"
SCHEDULE_STALE = "⏳ این ارسال دیگر در فهرست نیست (فرستاده شده یا لغو شده)."
SCHEDULE_NO_CUSTOMERS = "هنوز هیچ مشتری‌ای در فهرستِ تو نیست؛ وقتی مشتری اضافه شد می‌توانی برایِ بعد زمان‌بندی کنی."


def schedule_cancel_button_label(position: int) -> str:
    """شمارهٔ *صفحه‌ای* (۱..N)، نه شناسهٔ داخلیِ دیتابیس — قراردادِ پروژه: عددِ داخلی در متنِ کاربر نیاید."""
    return f"🗑 لغوِ ارسالِ {fa_number(position)}"


def schedule_saved_text(when_label: str, recipients: int) -> str:
    return (
        f"✅ ثبت شد: این پیام {when_label} برایِ {fa_number(recipients)} مشتری در صفِ ارسال می‌نشیند.\n"
        "اگر تلگرام لحظه‌ای پاسخ ندهد، خودش دوباره تلاش می‌کند و گم نمی‌شود.\n"
        "برایِ دیدن یا لغو: «⏰ ارسال‌هایِ زمان‌بندی‌شده»"
    )


def scheduled_list_text(rows) -> str:
    from app.utils.jalali import format_jalali_datetime

    lines = ["⏰ ارسال‌هایِ زمان‌بندی‌شده", ""]
    for position, row in enumerate(rows, start=1):
        preview = (row.text or "").replace("\n", " ")[:60]
        kind = getattr(row, "repeat_kind", "once") or "once"
        repeat = "" if kind == "once" else f" · {SCHEDULE_REPEAT_LABELS.get(kind, kind)}"
        lines.append(f"{fa_number(position)}) {format_jalali_datetime(row.scheduled_at)}{repeat} — «{preview}»")
    lines.append("")
    lines.append("برایِ لغو، دکمهٔ همان شماره را بزن.")
    return "\n".join(lines)


def stock_alert_button_label(shop_bot) -> str:
    value = getattr(shop_bot, "low_stock_alert_threshold", None)
    return "📦 اخطارِ موجودی: خاموش" if not value else f"📦 اخطارِ موجودی: زیرِ {fa_number(value)} عدد"


ASK_STOCK_THRESHOLD = (
    "چند عدد؟ هر کالایی که موجودیِ واقعی‌اش (کمِ رزروِ سفارش‌هایِ باز) به این عدد یا کمتر برسد، "
    "در اولین پاسِ بعدی به تو خبر داده می‌شود (حداکثر یک خبر در شبانه‌روز).\n"
    "برایِ خاموش‌کردن «خالی» بنویس."
)
STOCK_THRESHOLD_SAVED = "✅ ذخیره شد: از این به بعد کالاهایِ زیرِ {value} عدد بهت خبر می‌دهد."
STOCK_THRESHOLD_OFF = "🔕 اخطارِ موجودی خاموش شد."
STOCK_THRESHOLD_INVALID = "یک عددِ صحيح بينِ ۱ و ۱۰۰۰ بفرست (یا «خالی» برایِ خاموش‌کردن)."


def stock_alert_text(rows, threshold: int, limit: int) -> str:
    lines = [f"📦 موجودیِ چند کالا به {threshold} رسیده یا کمتر است:", ""]
    for product in rows[:limit]:
        remaining = (product.stock_quantity or 0) - (product.reserved_quantity or 0)
        lines.append(f"• {product.name}: {fa_number(remaining)} عدد")
    if len(rows) > limit:
        lines.append(f"… و {fa_number(len(rows) - limit)} کالایِ دیگر")
    lines.append("")
    lines.append("برایِ توقفِ این اخطار، آستانه را در «⚙️ تنظیماتِ ربات فروشگاه» خالی کن.")
    return "\n".join(lines)


ORDER_RESTOCKED = "📦 موجودیِ اقلامِ این سفارش به انبار برگشت."
ORDER_RESTOCK_NOTHING = "چیزی برایِ برگشت به انبار نبود (محصولِ بدونِ موجودی یا قبلاً برگشته)."
ADMIN_ASK_WALLET_COST_RECEIPT_ANALYSIS = "هزینه‌یِ هر بار تحلیلِ هوشمندِ رسید (مشورتی)، به تومان چقدر باشه؟"


# =============================================================================
# P20 · صندوقِ خروجیِ اعلان‌ها (دیدِ ادمین از صفِ خبر‌هایِ نرسیده)
# =============================================================================
NOTIFICATION_QUEUE_ALL_CLEAR = (
    "📮 صفِ اعلان‌ها خالی است.\n\n"
    "✅ ارسال‌شده: {sent}\n"
    "هیچ خبری معطّل یا شکست‌خورده نیست."
)
NOTIFICATION_QUEUE_REPORT = (
    "📮 صفِ اعلان‌ها\n\n"
    "⏳ در انتظارِ ارسال: {pending}\n"
    "🛑 شکست‌خورده (بعد از {max_attempts} تلاش): {failed}\n"
    "✅ ارسال‌شده: {sent}\n\n"
    "{detail}"
)
NOTIFICATION_QUEUE_DETAIL = "🕓 نزدیک‌ترین تلاشِ دوباره: {when}\n\n🛑 آخرین شکست‌ها:\n{items}"
NOTIFICATION_QUEUE_ITEM = "• {label}: {error} ({attempts} تلاش)"
NOTIFICATION_QUEUE_NO_ITEM = "• (نمونه‌ای برایِ نمایش نبود)"
NOTIFICATION_QUEUE_RETRY_NONE = "🛑 شکست‌خورده‌ای نبود؛ همه در انتظارِ تلاشِ خودشان‌اند."
NOTIFICATION_QUEUE_RETRY_DONE = "🔁 {count} اعلانِ شکست‌خورده دوباره در صف قرار گرفت."
NOTIFICATION_QUEUE_RETRY_BUTTON = "🔁 تلاشِ دوباره برایِ شکست‌خورده‌ها"

# =============================================================================
# P22 · مشکلِ ۸ — دستهٔ «کاربرانِ غیرفعال» و حذفِ حسابِ فروشگاه‌دار
# =============================================================================
INACTIVE_BUTTON = "🧹 کاربرانِ غیرفعال"
INACTIVE_LIST_INTRO = "🧹 {days} روز است خبری نشده — {count} حساب{scoped}"
INACTIVE_SCOPED_NOTE = " · فقطِ دامنهٔ تو"
INACTIVE_EMPTY = "🎉 با این بازه هیچ حسابِ غیرفعالی نیست."
INACTIVE_DELETED_INTRO = "🧊 حساب‌هایِ غیرفعال‌شده — {count} مورد (برایِ بازگرداندن یا حذفِ قطعی رویشان بزن)"
INACTIVE_DELETED_NONE = "🧊 هیچ حسابِ غیرفعال‌شده‌ای نداریم."
INACTIVE_DELETED_LIST_BUTTON = "🧊 غیرفعال‌شده‌ها"
INACTIVE_NO_HISTORY = "بدونِ سابقه"
INACTIVE_DAYS_AGO = "{days} روزِ پیش"
INACTIVE_LIST_HIDDEN = "⚠️ فقط {limit} مورد اول نشان داده می‌شود؛ {hidden} حسابِ دیگر هم در همین دسته‌اند."
INACTIVE_PURGE_WORD = "حذفِ قطعی"
INACTIVE_DELETED_BADGE = "🧊 این حساب غیرفعال شده است."
INACTIVE_LAST_SEEN_LINE = "🕓 آخرین دیدار: {when}"
INACTIVE_SUPER_ONLY = "این کار فقط برایِ سوپرادمین است."
INACTIVE_STALE = "این حساب در دامنهٔ تو نیست یا پیدا نشد؛ فهرست را تازه کن."
INACTIVE_NOT_DELETED_FIRST = "🧊 حذفِ قطعی فقط رویِ حسابی ممکن است که اول غیرفعال شده باشد."
INACTIVE_DELETE_CONFIRM = "حسابِ «{name}» غیرفعال شود؟ سفارش‌ها، کیف‌پول و ممیزی می‌مانند و هر وقت بخواهی برمی‌گردد."
INACTIVE_RESTORE_CONFIRM = "حسابِ «{name}» به فهرست برگردد؟"
INACTIVE_DEACTIVATED_DONE = "🧊 حسابِ «{name}» غیرفعال شد؛ از پنل، آمار و ورودِ کاربر بیرون ماند."
INACTIVE_RESTORED_DONE = "♻️ حسابِ «{name}» برگشت."
INACTIVE_PURGE_ASK = (
    "⚠️ حذفِ قطعیِ دادهٔ «{name}» برگشت‌ناپذیر است. اگر مطمئنی، همین عبارت را بنویس: {word}"
    + "\n"
    + "برایِ بی‌عمل ماندن /cancel را بزن."
)
INACTIVE_PURGE_BAD_WORD = "عبارت را دقیقِ «{word}» بنویس (یا /cancel را بزن)."
INACTIVE_PURGE_SUMMARY = "🔥 قرار است پاک شود: {items}. برایِ ادامه این عبارت را بنویس: «{tail}»"
INACTIVE_PURGE_SHELL_KEPT = "پوستهٔ حساب و ردیف‌هایِ ممیزی می‌مانند (زنجیرهٔ هشِ ممیزی پاک‌شدنی نیست)."
INACTIVE_PURGE_SHELL_REMOVED = "پوستهٔ حساب هم حذف شد (هیچ ردیفِ ممیزی به آن بند نبود)."
INACTIVE_PURGE_DONE = "🔥 دادهٔ «{name}» پاک شد — {count} ردیف. {tail}"
INACTIVE_PURGE_FAILED = "❌ حذفِ قطعی انجام نشد: {error}"


def inactive_detail_text(
    *, name: str, bot_username: str | None, last_seen: str, since_label: str, wallet: str, is_deleted: bool
) -> str:
    """کارتِ یکِ حسابِ غیرفعال: کیست، کِی آخرین بار آمده، و الان چه وضعی دارد."""
    lines = [f"👤 {name}"]
    if bot_username:
        lines.append(f"🤖 رباتِ فروشگاه: @{bot_username.lstrip('@')}")
    lines.append(f"{INACTIVE_LAST_SEEN_LINE.format(when=last_seen)} ({since_label})")
    lines.append(f"💰 کیف‌پول: {wallet}")
    if is_deleted:
        lines.append(INACTIVE_DELETED_BADGE.strip())
    return "\n".join(lines)


def inactive_purge_summary(removed_rows: int, touched_tables: int) -> str:
    """چکیدهٔ آنچه حذفِ قطعی می‌بُرد + یادآوریِ عبارتِ تایید (ارقامِ فارسی، مثلِ بقیهٔ پنل)."""
    return INACTIVE_PURGE_SUMMARY.format(
        items=f"{fa_number(removed_rows)} ردیف در {fa_number(touched_tables)} جدول", tail=INACTIVE_PURGE_WORD
    )


# =============================================================================
# پ۶۵ · موردِ ۲۷/۴۱-ب — «حذفِ حسابِ من» در پنلِ خودِ فروشگاه‌دار
# =============================================================================
# واژهٔ تایید عمداً در `_KNOWN_MENU_BUTTONS` ثبت نشده (دیدنی‌بودنش حالتِ تایید را می‌شکند):
# توضیحش در `AccountDeletionStates` است.
ACCOUNT_DELETE_BUTTON = "🗑 حذفِ حسابِ من"
ACCOUNT_DELETE_GO_BUTTON = "✅ بله، حسابم را ببند"
ACCOUNT_DELETE_WORD = "حذفِ حساب"
ACCOUNT_DELETE_NOT_REGISTERED = "برایِ حذفِ حساب اول باید ثبت‌نامت را تمام کنی."
ACCOUNT_DELETE_ALREADY = "🧊 این حساب ازپیش بسته شده است."
ACCOUNT_DELETE_BAD_WORD = "عبارت را دقیقاً «{word}» بنویس. برایِ بیرون‌آمدن از این مرحله دکمه‌هایِ منو را بزن."
ACCOUNT_DELETE_STALE = "چیزی برایِ حذفِ حساب باز نمانده؛ از «👤 پروفایل من» دوباره شروع کن."
ACCOUNT_DELETE_ASK = (
    "⚠️ بستنِ حساب برگشت‌ناپذیر است: ربات خاموش و هویت‌ها بی‌نام می‌شوند. اگر مطمئنی، همین عبارت را بنویس: {word}\n"
    "برایِ بی‌عمل ماندن /cancel را بزن."
)
ACCOUNT_DELETE_BLOCKED_WALLET = "⚠️ کیف‌پولت هنوز {wallet} اعتبار دارد. با موجودیِ غیرصفر حساب بسته نمی‌شود: اول مصرفش کن یا با پشتیبانیِ پلتفرم هماهنگ شو."
ACCOUNT_DELETE_BLOCKED_RESERVED = "⚠️ {reserved} کمیسیونِ سفارش‌هایِ درجریانِ پرداخت قفل شده است؛ وقتی همان سفارش‌ها بسته شدند دوباره تلاش کن."
ACCOUNT_DELETE_DONE = "🧊 حساب بسته شد. {summary}\nهر وقت خواستی برایِ بازگشت با پشتیبانیِ پلتفرم صحبت کن."
ACCOUNT_DELETE_DONE_SUMMARY = "{erased} ردیف پاک و {customers} مشتری بی‌نام شد؛ {documents} سندِ مالی و ردیفِ ممیزی نگه داشته شد."
ACCOUNT_DELETE_FAILED = "❌ حذفِ حساب انجام نشد: {error}"


def account_delete_preview_text(
    *,
    customers: int,
    messages: int,
    addresses: int,
    documents: int,
    open_orders: int,
    bot_count: int,
    instagram_accounts: int,
    bale_bots: int,
    pending_messages: int,
) -> str:
    """صفحهٔ پیشِ تایید: چه چیزی می‌رود، چه چیزی می‌ماند و چه خطری هست (ارقامِ جلالی)."""
    lines = [
        "🗑 حذفِ حسابِ من",
        "",
        "این‌ها پاک یا بی‌نام می‌شوند:",
        f"• {fa_number(bot_count)} رباتِ فروشگاه خاموش می‌شود و هر کلیدِ اتصال (تلگرام، بله، اینستاگرام، درگاهِ پرداخت) پاک می‌شود",
        f"• {fa_number(messages)} پیامِ گفتگو با مشتری‌ها حذف می‌شود",
        f"• هویتِ {fa_number(customers)} مشتری بی‌نام می‌ماند (نام، یوزرنیم، شماره، یادداشت و برچسب)",
        f"• {fa_number(addresses)} آدرسِ دفترچهٔ آدرس حذف می‌شود",
        f"• {fa_number(pending_messages)} پیامِ ارسال‌نشده از صف می‌رود",
        "• نام، موبایل و ایمیلِ خودِ تو پاک می‌شود",
        "",
        "این‌ها می‌مانند (بدونِ نامِ کسی):",
        f"• {fa_number(documents)} سفارش، فاکتور و ردیفِ کیف‌پول — سندِ حسابداریِ تو و پلتفرم",
        "• ردیف‌هایِ ممیزی، که پاک‌کردنشان دفترِ شاهدِ تصمیمها را بی‌ارزش می‌کند",
    ]
    if instagram_accounts:
        lines.append(f"• اتصالِ اینستاگرام ({fa_number(instagram_accounts)} پیج) هم قطع می‌شود")
    if bale_bots:
        lines.append(f"• رباتِ بله‌یِ خودِ فروشگاه ({fa_number(bale_bots)} مورد) هم خاموش می‌شود")
    if open_orders:
        lines += ["", f"⚠️ {fa_number(open_orders)} سفارشِ باز داری؛ با حذفِ حساب هیچ‌کس آنها را پردازش نمی‌کند."]
    lines += ["", "اگر مطمئنی «بله، حسابم را ببند» را بزن؛ بعدش همان عبارتِ «حذفِ حساب» را باید بنویسی."]
    return "\n".join(lines)

# =============================================================================
# پ۶۶ · موردِ ۲۴-ب — دو صفحهٔ اختصاصیِ مودِ مشاوره‌ای + دروازهٔ معکوس
# =============================================================================
MODE_CONSULTATION_ONLY = (
    "🧮 این بخش فقط در مودِ «مشاوره‌ای» کار می‌کند (گزارشِ جلسات و بازگشتِ مخاطب).\n"
    "در مودِ فروشگاهی همان اطلاعات در «🧮 حسابداری» و «👥 مشتری‌ها» هست.\n"
    "اگر می‌خوای مودِ فروشگاهت عوض بشه، به «👤 پروفایل من» برو."
)
CONSULT_REPORTS_BUTTON = "🧮 گزارشِ جلسات"
CONSULT_RETURN_BUTTON = "🎯 بازگشتِ مخاطب"
CONSULT_REPORTS_BACK = "⬅️ برگشت به گفتگوها"
CONSULT_REPORTS_TRUNCATED = "⚠️ جلسه‌هایِ این بازه از سقفِ گزارش بیشتر است؛ عددها ناقص‌ان."
CONSULT_REPORTS_NOTE = (
    "ℹ️ فقط «جلسه»هایِ همین فروشگاه و فقط بازهٔ انتخابی شمرده می‌شوند؛ «تاییدشده» یعنی خودِ مخاطب "
    "جلسه را تایید کرده است. این گزارش فقط‌خواندنیه و چیزی را تغییر نمی‌دهد."
)
CONSULT_RETURN_EMPTY = "🎯 فعلاً مخاطبی برایِ بازگشت نداریم؛ وقتی گفتگوها بیشتر شد، بخش‌بندی پر می‌شود."
CONSULT_RETURN_STALE = "این بخش عوض شده است؛ «🎯 بازگشتِ مخاطب» را دوباره بزن."
CONSULT_RETURN_TRUNCATED = "⚠️ برایِ بخش‌بندی فقط ۵۰٬۰۰۰ مخاطبِ آخر بررسی شد؛ عددها ممکن است ناقص باشد."
CONSULT_RETURN_NOTE = "ℹ️ ارسالِ پیام هزینه‌ای برایِ تو ندارد، ولی برایِ آن مخاطبان واقعاً می‌رود؛ متن را دقیق بنویس."
# واژه‌هایِ این فهرست عمداً «خرید/سفارش» ندارند (قانونِ واژگانِ مودِ مشاورهٔ پ۱۸).
CONSULT_SEGMENT_LABELS = {
    "new": "🌱 تازه‌آمده",
    "active": "💬 فعال",
    "loyal": "⭐ پیگیرِ جلسه",
    "churning": "⚠️ در حالِ ریزش",
    "no_purchase": "👀 بدونِ جلسهٔ تاییدشده",
}
CONSULT_SEGMENT_ORDER = ("churning", "new", "active", "loyal", "no_purchase")
# «منتظرِ تاییدِ مخاطب» در مشاوره معنیِ «سفارش» نمی‌دهد؛ سه وضعیتِ فروشِ صریح جایِ خودشان را عوض می‌کنند.
CONSULT_STATUS_OVERRIDES = {
    "awaiting_customer_confirmation": "⏳ منتظرِ تاییدِ تو",
    "pending": "🕓 در انتظارِ بررسی",
    "awaiting_payment": "🕓 در انتظارِ بررسی",
    "receipt_submitted": "🧾 رسیدِ تو ثبت شد",
    "paid": "✅ تاییدشده",
}


def consult_status_label(status) -> str:
    key = status.value if hasattr(status, "value") else str(status or "")
    return CONSULT_STATUS_OVERRIDES.get(key) or order_status_label(key)


def consult_reports_text(report) -> str:
    """نسخهٔ مشاوره‌ایِ گزارشِ حسابداری: همان شمارش‌هایِ `accounting_service` با واژگانِ «جلسه».

    سه تفاوتِ عمدی با نسخهٔ فروشگاهی: واژهٔ «سفارش» هیچ‌جا نمی‌آید، «پرفروش‌ترین‌ها» و
    «عملکردِ کمپین‌ها» حذف‌اند (کاتالوگ و تخفیف در این مود معنا ندارد) و به‌جایشان شمارشِ
    روزبه‌روزِ جلسه‌ها می‌آید.
    """
    import datetime as _dt

    from app.utils.jalali import format_jalali_date

    summary = report.summary
    period = summary.period
    first_day = format_jalali_date(period.start)
    last_day = format_jalali_date(period.end - _dt.timedelta(days=1))
    date_line = first_day if first_day == last_day else f"{first_day} تا {last_day}"

    lines = [
        f"🧮 گزارشِ جلسات — {period.label}",
        f"📅 {date_line}",
        "",
        f"✅ جلسهٔ تاییدشده: {fa_number(summary.successful_count)} — میانگینِ ارزشِ هر جلسه: {format_toman(summary.average_order_toman)}",
        f"💰 ارزشِ جلسه‌هایِ تاییدشده: {format_toman(summary.net_toman)}",
    ]
    if summary.status_counts:
        lines.append("\n📋 وضعیتِ جلسه‌هایِ ثبت‌شده در این بازه:")
        lines.extend(f"  {consult_status_label(status)}: {fa_number(count)}" for status, count in summary.status_counts.items())
    if report.pending_total > 0:
        lines.append(f"\n⏳ همین حالا {fa_number(report.pending_total)} جلسه منتظرِ بررسیِ توست.")
    if summary.daily:
        lines.append("\n🗓 روزبه‌روز:")
        for day in summary.daily[-7:]:
            lines.append(f"  {day.day_label}: {fa_number(day.orders)} جلسه — {format_toman(day.net_toman)}")
    if report.truncated:
        lines.append(f"\n{CONSULT_REPORTS_TRUNCATED}")
    lines.append(f"\n{CONSULT_REPORTS_NOTE}")
    return "\n".join(lines)


def consult_return_text(counts: dict[str, int], total: int, truncated: bool) -> str:
    """صفحهٔ «بازگشتِ مخاطب»: هر بخش چند نفر است — جایِ «🎯 کمپین‌ها» در مودِ مشاوره."""
    lines = ["🎯 بازگشتِ مخاطب", "", "هر بخش را انتخاب کنی، پیامِ تو فقط به همان نفرها می‌رود:", ""]
    for key in CONSULT_SEGMENT_ORDER:
        lines.append(f"• {CONSULT_SEGMENT_LABELS.get(key, key)}: {fa_number(int(counts.get(key, 0)))} نفر")
    lines += ["", f"👤 مجموعِ مخاطبانِ این فروشگاه: {fa_number(total)}"]
    if truncated:
        lines.append(f"⚠️ {CONSULT_RETURN_TRUNCATED}")
    lines += ["", CONSULT_RETURN_NOTE]
    return "\n".join(lines)


def consult_return_ask(segment: str, count: int) -> str:
    return (
        f"🎯 بخشِ «{CONSULT_SEGMENT_LABELS.get(segment, segment)}» — {fa_number(count)} نفر\n\n"
        "متنِ پیام را بنویس. با «❌ لغو» بیرون می‌آیی و هیچ پیامی نمی‌رود."
    )


# =============================================================================
# پ۶۷ · موردِ ۲۷/۴۱-پ — «🧾 پروندهٔ کاملِ کاربر» در پنلِ ادمین
# =============================================================================
OWNER_DOSSIER_BUTTON = "🧾 پروندهٔ کاملِ کاربر"
OWNER_DOSSIER_STALE = "این حساب در دامنهٔ تو نیست یا پیدا نشد؛ فهرست را تازه کن."
OWNER_DOSSIER_NOT_FOUND = "🧾 این حساب دیگر وجود ندارد."
OWNER_DOSSIER_NOTE = (
    "ℹ️ این نما فقط‌خواندنی است؛ هر دکمه همان کاری را می‌کند که در صفحهٔ اختصاصیِ خودش می‌کرد "
    "(با همان ممیزی و همان چکِ دسترسی). اعدادِ مصرف، ۳۰ روزِ آخر است."
)
OWNER_DOSSIER_DELETED_BADGE = "🧊 حساب بسته شده"
OWNER_DOSSIER_ACTIVE_BADGE = "✅ حساب فعال"
OWNER_DOSSIER_NO_SUBSCRIPTION = "بدونِ اشتراکِ ثبت‌شده"
OWNER_DOSSIER_SUBSCRIPTION_LABELS = {
    "trial": "آزمایشی",
    "active": "فعال",
    "grace": "در مهلت",
    "expired": "منقضی",
}
OWNER_DOSSIER_NO_BOT = "رباتِ فروشگاهی تنظیم نشده"
OWNER_DOSSIER_NO_SEEN = "بدونِ سابقهٔ دیدار"
OWNER_DOSSIER_DAYS_AGO = "{days} روزِ پیش"
OWNER_DOSSIER_DAYS_LEFT = "{days} روز مانده"
OWNER_DOSSIER_DAYS_PAST = "{days} روز گذشته"
OWNER_DOSSIER_EXTEND_DONE = "✅ اشتراک {days} روز تمدید شد و در ممیزی ثبت شد."
OWNER_DOSSIER_EXTEND_BAD_DAYS = "عددِ روز را درست بنویس (مثلاً ۷). برایِ بیرون‌آمدن /cancel را بزن."
OWNER_DOSSIER_EXTEND_ASK = (
    "➕ چند روز به اشتراکِ «{name}» اضافه شود؟ عددِ روز را بنویس (مثلاً ۷). برایِ بیرون‌آمدن /cancel را بزن."
)
OWNER_DOSSIER_EXTEND_DELETED = "🧊 حسابِ بسته‌شده تمدید نمی‌شود؛ اول آن را بازگرداندن لازم است."
OWNER_DOSSIER_AUDIT_NONE = "بدونِ ردیفِ ممیزی"


def _dossier_yes_no(value) -> str:
    """«بله/خیر»ِ فارسی برایِ خطِ وضعیتِ فروشگاه (پ۶۷)."""
    return "بله" if value else "خیر"


def owner_dossier_text(data: dict, audit_rows: list[tuple[str, int]]) -> str:
    """کارتِ تجمیعیِ یکِ فروشگاه‌دار: هویت، اتصال‌ها، اشتراک/کیف‌پول، مصرف و فعالیت."""
    from app.utils.jalali import format_jalali_date, format_jalali_datetime
    from app.utils.validators import fa_number, format_toman

    name = data.get("name") or (f"@{data['username']}" if data.get("username") else "کاربرِ بی‌نام")
    lines = [f"🧾 پروندهٔ کاملِ کاربر — {name}", ""]

    lines.append("👤 هویت و ورود")
    lines.append(f"• شناسهٔ داخلیِ حساب: {fa_number(data['owner_id'])} (برایِ پیوندِ ممیزی و بلیطِ پشتیبانی)")
    lines.append(f"• یوزرنیم: {'@' + data['username'].lstrip('@') if data.get('username') else '—'}")
    lines.append(f"• موبایل: {data.get('phone_masked') or '—'} · ایمیل: {data.get('email') or '—'}")
    mode = "فروشگاهی" if data.get("business_mode") == "sales" else "مشاوره‌ای"
    lines.append(f"• نوعِ کسب‌وکار: {mode} · ثبت‌نام: {'کامل' if data['registration_completed'] else 'ناتمام'}")
    if data["last_seen_at"] is None:
        lines.append(f"• آخرین دیدار: {OWNER_DOSSIER_NO_SEEN}")
    else:
        when = format_jalali_datetime(data["last_seen_at"])
        ago = OWNER_DOSSIER_DAYS_AGO.format(days=fa_number(data["last_seen_days"])) if data["last_seen_days"] is not None else "—"
        lines.append(f"• آخرین دیدار: {when} ({ago})")
    badge = OWNER_DOSSIER_DELETED_BADGE if data["is_deleted"] else OWNER_DOSSIER_ACTIVE_BADGE
    if data["is_deleted"] and data["deleted_at"] is not None:
        badge += f" · {format_jalali_datetime(data['deleted_at'])}"
    lines.append(f"• وضعیتِ حساب: {badge}")

    lines += ["", "🤖 اتصال‌ها"]
    bot = data.get("shop_bot")
    if bot is None:
        lines.append(f"• {OWNER_DOSSIER_NO_BOT}")
    else:
        status = "فعال ✅" if bot["is_active"] else f"غیرفعال ❌ ({bot['disabled_reason'] or '—'})"
        lines.append(f"• رباتِ تلگرام: @{str(bot['bot_username']).lstrip('@')} — {status}")
        lines.append(f"• توکنِ ربات: {'ثبت شده' if bot['has_token'] else 'پاک شده'}")
        conn = data["connections"]
        if conn["bale"]:
            bale_state = "روشن" if conn["bale_enabled"] else "خاموش"
            handle = f" (@{str(conn['bale_username']).lstrip('@')})" if conn["bale_username"] else ""
            lines.append(f"• رباتِ بله: متصل{handle} — {bale_state}")
        else:
            lines.append("• رباتِ بله: تنظیم نشده")
        ig = conn["instagram"]
        if ig is None:
            lines.append("• اینستاگرام: متصل نیست")
        elif ig["muted"]:
            until = format_jalali_datetime(ig["muted_until"]) if ig["muted_until"] else "—"
            lines.append(f"• اینستاگرام: @{str(ig['ig_username'] or '—').lstrip('@')} — ⏸ خاموش تا {until}")
        else:
            lines.append(f"• اینستاگرام: @{str(ig['ig_username'] or '—').lstrip('@')} — {'روشن ✅' if ig['is_active'] else 'غیرفعال ❌'}")
        doors = [
            ("درگاهِ بله", bot["bale_provider"]),
            ("زرین‌پال", bot["zarinpal"]),
            ("کانالِ دانش", bot["knowledge_channel"]),
            ("پشتیبانیِ انسانی", bot["support_enabled"]),
        ]
        lines.append("• " + " · ".join(f"{label}: {'✅' if on else '—'}" for label, on in doors))

    lines += ["", "💳 اشتراک، کیف‌پول و مصرف"]
    sub = data.get("subscription")
    if sub is None:
        lines.append(f"• اشتراک: {OWNER_DOSSIER_NO_SUBSCRIPTION}")
        lines.append(f"• قابلِ استفاده بودنِ فروشگاه (با مهلت): {_dossier_yes_no(data.get('shop_usable'))}")
    else:
        left = sub["days_left"]
        tail = OWNER_DOSSIER_DAYS_LEFT.format(days=fa_number(left)) if left >= 0 else OWNER_DOSSIER_DAYS_PAST.format(days=fa_number(-left))
        trial = " (آزمایشی)" if sub["is_trial"] else ""
        status_label = OWNER_DOSSIER_SUBSCRIPTION_LABELS.get(sub["status"], sub["status"])
        lines.append(f"• اشتراک: {status_label}{trial} تا {format_jalali_date(sub['end_date'])} — {tail}")
        lines.append(f"• قابلِ استفاده بودنِ فروشگاه (با مهلت): {_dossier_yes_no(sub.get('usable'))}")
    lines.append(f"• موجودیِ کیف‌پول: {format_toman(data['wallet_toman'])} · قابلِ مصرف: {format_toman(data['usable_toman'])}")
    lines.append(f"• کمیسیونِ قفل‌شده: {format_toman(data['reserved_toman'])} · بدهیِ بازِ مصرف: {format_toman(data['debt_toman'])}")
    usage = data["usage"]
    lines.append(
        f"• مصرفِ هوشِ مصنوعیِ {fa_number(usage['days'])} روز: {format_toman(usage['toman'])} در {fa_number(usage['calls'])} فراخوان"
    )
    payments = data["payments"]
    lines.append(
        f"• پرداخت‌هایِ تاییدشده: {fa_number(payments['count'])} مورد — {format_toman(payments['total_toman'])}"
    )

    activity = data.get("activity") or {}
    lines += ["", "📊 فعالیتِ فروشگاه"]
    lines.append(
        f"• مشتری‌ها: {fa_number(activity.get('customers', 0))} · سفارش‌ها: {fa_number(activity.get('orders', 0))} "
        f"(باز: {fa_number(activity.get('open_orders', 0))}) · کمپینِ فعال: {fa_number(activity.get('campaigns', 0))}"
    )
    lines.append(
        f"• گزارشِ بازِ نگهبانِ محتوا: {fa_number(activity.get('moderation_open', 0))} · ردیفِ ممیزی: {fa_number(activity.get('audit_rows', 0))}"
    )
    if audit_rows:
        lines.append("• آخرینِ رویدادهایِ ممیزی:")
        for label, when in audit_rows:
            lines.append(f"  ◂ {label}: {format_jalali_datetime(when)}")
    else:
        lines.append(f"• {OWNER_DOSSIER_AUDIT_NONE}")
    lines += ["", OWNER_DOSSIER_NOTE]
    return "\n".join(lines)


# ------------------------------------------------------------------ پ۶۹ · موردِ ۳۶: برآوردِ هزینهٔ واقعیِ AI
AI_COST_BUTTON = "💸 برآوردِ هزینهٔ واقعیِ AI"
AI_COST_RANGES = ((7, "۷ روز"), (30, "۳۰ روز"), (90, "۹۰ روز"))
AI_COST_FEATURE_LABELS = {
    "chat_message": "💬 پاسخِ چتِ مشتری",
    "photo_analysis": "🖼 تحلیلِ عکس",
    "receipt_analysis": "🧾 رسیدِ پرداخت",
    "voice_transcription": "🎙 تبدیلِ صوت",
    "order_detection": "📦 سفارش‌یابی",
    "cart_edit": "🛒 ویرایشِ سبد",
    "crm_summary": "🗂 خلاصهٔ CRM",
    "owner_assistant": "🤖 دستیارِ مدیر",
}
AI_COST_NO_DATA = "🧾 در این بازه هیچ مصرفِ AI‌ای ثبت نشده است."
AI_COST_NO_MEASURE = (
    "⚠️ هیچ فراخوانیِ AI در این بازه با توکنِ ثبت‌شده نیست؛ جمعِ پول پایین نمایش داده می‌شود ولی "
    "میانگینِ توکن حساب نمی‌شود (برآورد از گذشته ساخته نمی‌شود)."
)
AI_COST_COVERAGE_NOTE = "📏 پوششِ اندازه‌گیری: فقط فراخوانی‌هایِ پ۶۹ به بعد توکن دارند."
AI_COST_ESTIMATED_NOTE = "اعدادِ برچسب‌دار: MEASURED = از ردیف‌هایِ دیتابیس · EXTRAPOLATED = همان ردیف‌ها × نرخِ پنل · ESTIMATED = تقریبِ اندازهٔ پرامپت"


def _ai_cost_ratio_word(ratio) -> str:
    return "بالاتر ازِ هزینهٔ خام (سودِ ناخالص)" if ratio >= 1 else "پایین‌تر ازِ هزینهٔ خام (زیان)"


def ai_cost_text(view, days: int) -> str:
    """صفحهٔ برآورد: جمعِ پنجره، تفکیکِ هر قابلیت، و سه عددِ قیمت."""
    lines = [f"💸 برآوردِ هزینهٔ واقعیِ AI — {fa_number(days)} روز گذشته", ""]
    if not view.rows:
        lines.append(AI_COST_NO_DATA)
    else:
        lines.append(f"• فراخوانی‌هایِ AI: {fa_number(view.calls)}")
        lines.append(f"• گرفته‌شده از فروشگاه‌دارها: {format_toman(view.charged_toman)}")
        if view.measured_calls:
            lines.append(f"• توکنِ واقعیِ مصرفی: {fa_grouped(view.tokens)}")
            lines.append(f"• میانگینِ هر فراخوانی: {fa_grouped(view.mean_tokens)} توکن (MEASURED)")
            lines.append(f"• چیزی که واقعاً به‌ازایِ هر ۱۰۰۰ توکن گرفته شده: {format_toman(view.charged_per_1k)}")
            lines.append(f"• هزینهٔ خامِ همین توکن‌ها: {format_toman(int(view.measured_raw_cost_toman))} (EXTRAPOLATED)")
            ratio = view.margin_ratio()
            if ratio is not None:
                lines.append(f"• نسبتِ گرفته/هزینه: {fa_number(f'{float(ratio):g}')}× — {_ai_cost_ratio_word(ratio)}")
        else:
            lines.append(AI_COST_NO_MEASURE)
        lines += ["", "📊 تفکیکِ هر قابلیت:"]
        for row in view.rows:
            label = AI_COST_FEATURE_LABELS.get(row.reason, row.reason)
            if row.measured_calls:
                lines.append(
                    f"  ◂ {label}: {fa_number(row.calls)} فراخوانی · {fa_grouped(row.tokens)} توکن · "
                    f"میانگینِ هر فراخوانی {fa_grouped(row.mean_tokens)} توکن · هر ۱۰۰۰ توکن = "
                    f"{format_toman(row.charged_per_1k)}"
                )
            else:
                lines.append(f"  ◂ {label}: {fa_number(row.calls)} فراخوانی · {format_toman(row.charged_toman)} · بی‌توکنِ ثبت‌شده")
        lines.append(AI_COST_COVERAGE_NOTE)
    lines += [
        "",
        "💰 سه عددِ قیمت:",
        f"• قیمتِ فعلیِ هر ۱۰۰۰ توکن: {format_toman(view.price_per_1k_toman)}",
        f"• هزینهٔ خامِ هر ۱۰۰۰ توکن با نرخِ پنل: {format_toman(int(view.raw_cost_per_1k_toman))}",
        f"• پیشنهادِ فرمولِ خودکار (با ضریبِ سود): {format_toman(view.suggested_price_per_1k)}",
        "",
        f"🧠 کفِ پرامپتِ سیستمی (ESTIMATED): فروشگاهی {fa_number(view.prompt_floor_sales)} توکن، "
        f"مشاوره‌ای {fa_number(view.prompt_floor_consultation)} توکن — این سهم را *هر* فراخوانی "
        "پخش می‌کند، حتی اگر مشتری یک کلمه بنویسد.",
        AI_COST_ESTIMATED_NOTE,
    ]
    return "\n".join(lines)


# ------------------------------------------------------------------ پ۷۰ · مصرفِ AI به تفکیکِ فروشگاه + پنلِ فروشگاه‌دار
AI_USAGE_SHOP_FILTER_LINE = "🏪 فیلتر: فقطِ مشتریانِ فروشگاهِ @{shop}"
AI_USAGE_SHOP_ALL_BUTTON = "🌐 همهٔ فروشگاه‌ها"
AI_USAGE_SHOP_FILTERED_BUTTON = "🏪 فقطِ این فروشگاه"
AI_USAGE_SHOP_INVALID = "این فروشگاه در دسترس نیست. از کارتِ فروشگاه‌دار دوباره امتحان کن."
OWNER_AI_USAGE_BUTTON = "📈 پرمصرف‌هایِ AI"
OWNER_AI_USAGE_INTRO = (
    "📈 پرمصرف‌ترینِ مشتریانِ هوش مصنوعیِ فروشگاهِ خودت — {window} · صفحهٔ {page} از {total_pages}"
)
OWNER_AI_USAGE_TITLE = "📈 پرمصرف‌هایِ AI — مشتریانِ همین فروشگاه"
OWNER_AI_USAGE_EMPTY = "در این بازه هیچ مشتری‌ای از هوش مصنوعیِ فروشگاهِ تو هزینه نداشته است."
OWNER_AI_USAGE_NOTE = (
    "🧾 این فهرست فقطِ مشتریانِ همین فروشگاه است و ازِ پ۷۰ به بعد شمرده می‌شود؛ مصرفِ کامنتِ "
    "اینستاگرام، خلاصهٔ CRM و دستیارِ مدیریتی به کاربری وصل نمی‌شود و در این فهرست نیست."
)
OWNER_AI_USAGE_INVALID = "این کاربر مشتریِ فروشگاهِ تو نیست یا دیگر وجود ندارد."


def owner_ai_usage_intro(window_label: str, page: int, total_pages: int) -> str:
    return OWNER_AI_USAGE_INTRO.format(window=window_label, page=fa_number(page + 1), total_pages=fa_number(total_pages))


# ============================================================================= پ۱۰۹ · پنجرهٔ نوشتنیِ وب
WEB_PANEL_BUTTON = "🌐 پنلِ وب"
WEB_PANEL_REVOKE_BUTTON = "🔐 ابطالِ لینک‌هایِ وب"
WEB_PANEL_MINUTES = 15
WEB_PANEL_DISABLED = (
    "⚙️ پنلِ وب رویِ این سرویس روشن نیست (یا کلیدِ امضایِ نشست در تنظیماتِ سرور نوشته نشده، یا "
    "صاحبِ پلتفرم دکمه‌اش را موقتاً پنهان کرده). همهٔ کارهایی که در پنلِ وب هست، همین‌جا در ربات هم هست."
)
WEB_PANEL_NO_ADDRESS = (
    "🌐 آدرسِ عمومیِ این سرویس در تنظیماتِ سرور نوشته نشده، پس لینکی ساخته نمی‌شود. "
    "تا پیش ازِ آن، همین ربات تنها راهِ مدیریت است."
)
WEB_PANEL_INTRO = (
    "🌐 لینکِ پنلِ وب فقط برایِ تو کار می‌کند، یک‌بار باز می‌شود و تا {} دقیقه اعتبار دارد. "
    "پس ازِ باز کردن، نشستِ همین مرورگر ۶ ساعت می‌چرخد.\n\n"
    "در این پنل فقط چهار کار مجاز است: روشن/خاموش‌کردنِ نمایشِ یک محصول، ثبتِ موجودی، ثبتِ قیمت، "
    "و بردنِ یک سفارش به قدمِ بعدی. هیچ پرداخت، استرداد، شارژِ کیف‌پول یا پیامی به مشتری از این پنل "
    "انجام نمی‌شود و هر تغییر در دفترِ ممیزی ثبت می‌شود.\n\n"
    "اگر لینک گم شد یا از کامپیوترِ دیگری استفاده کردی، «" + WEB_PANEL_REVOKE_BUTTON + "» را بزن تا "
    "همهٔ لینک‌ها و نشست‌هایِ فعال بسته شوند و تازه بگیر."
)
WEB_PANEL_LINK_TITLE = "🔗 لینکِ پنلِ وب (یک‌بارمصرف):"
WEB_PANEL_REVOKED = "✅ {} لینک/نشست ابطال شد. اگر مرورگری باز مانده باشد، از این لحظه بسته است."
WEB_PANEL_NONE_ACTIVE = "🔎 لینکِ فعالی برایِ ابطال پیدا نشد (همه سوخته یا منقضی شده‌اند)."
