from __future__ import annotations

import re

_IRAN_MOBILE_RE = re.compile(r"^09[0-9]{9}$")
# ارقامِ فارسی (۰-۹) و عربی‌-هندی (٠-٩) → ASCII؛ کاربرِ ایرانی بیشتر با کیبوردِ فارسی تایپ می‌کنه
_DIGIT_TABLE = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
_USERNAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{4,31}$")
_NAME_FORBIDDEN_RE = re.compile(r"[0-9۰-۹٠-٩@]|https?:|t\.me|www\.", re.IGNORECASE)
NAME_MIN_LENGTH = 2
NAME_MAX_LENGTH = 30
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# P22 (لایهٔ «ارقام فارسی»): نمایشِ یکتا با ارقامِ فارسی و جداکنندهٔ هزارگانِ فارسی.
# ورودیِ کاربر همیشه با `_DIGIT_TABLE` به لاتین برمی‌گردد، پس پارسرها هرگز ارقامِ فارسی نمی‌بینند
# و این تغییرِ نمایش هیچ جایی را نمی‌شکند. فایل‌هایِ اکسل عمداً عددِ خام می‌گیرند (نه این رشته)
# تا فیلتر و جمعِ ستون در اکسل کار کند.
_TO_PERSIAN_DIGITS = str.maketrans("0123456789,", "۰۱۲۳۴۵۶۷۸۹٬")


def fa_number(value: object) -> str:
    """عدد (یا رشته‌یِ عددی) را با ارقامِ فارسی می‌نویسد: 1200000 ⇒ ۱٬۲۰۰٬۰۰۰."""
    return str(value).translate(_TO_PERSIAN_DIGITS)


def fa_percent(value: object, decimals: int = 0) -> str:
    """درصدِ فارسی: 92.34 ⇒ «۹۲٫۳٪» ( ممیزِ فارسی، نه نقطهٔ لاتین)."""
    text = f"{float(value):.{decimals}f}".replace(".", "٫") if decimals else str(int(float(value)))
    return f"{fa_number(text)}٪"


def fa_text(template: str, **values) -> str:
    """الگو را پر می‌کند و هر مقدارِ عددی را با ارقامِ فارسی می‌نویسد (متن‌ها و شناسه‌هایِ
    رشته‌ای دست‌نخورده می‌مانند، پس «۱۲۳۴۵۶۷۸۹۰» در متنِ کپی‌شدنی خراب نمی‌شود)."""
    return template.format(**{key: (fa_number(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else value) for key, value in values.items()})


def fa_grouped(amount: int) -> str:
    """یکِ عدد را با جداکنندهٔ هزارگانِ فارسی می‌نویسد (برایِ شمارش‌ها، بدونِ واحد)."""
    return fa_number(f"{int(amount):,}")


def format_toman(amount: int) -> str:
    return f"{fa_grouped(amount)} تومان"


def is_valid_email(email: str) -> bool:
    return bool(_EMAIL_RE.match(email.strip()))


def normalize_iran_phone(raw_phone: str) -> str | None:
    """
    شماره‌ی موبایل ایرانی رو به فرمتِ استانداردِ 09XXXXXXXXX نرمالایز می‌کنه.
    فرمت‌های ورودیِ قابل‌قبول: 09123456789، +989123456789، 00989123456789،
    9123456789 (بدونِ صفر ابتدایی). اگه شماره معتبر نبود، None برمی‌گردونه.
    """
    digits = re.sub(r"[^0-9]", "", raw_phone.strip().translate(_DIGIT_TABLE))

    if digits.startswith("0098"):
        digits = digits[4:]
    elif digits.startswith("98"):
        digits = digits[2:]

    if digits.startswith("9") and len(digits) == 10:
        digits = "0" + digits

    if _IRAN_MOBILE_RE.match(digits):
        return digits
    return None


def to_e164_iran(raw_phone: str) -> str | None:
    """شماره‌یِ موبایلِ ایرانی → «+98912…» (فرمتِ ذخیره‌یِ ستون‌هایِ تازه). نامعتبر → None."""
    local = normalize_iran_phone(raw_phone)
    return None if local is None else "+98" + local[1:]


def format_phone_display(phone: str | None) -> str | None:
    """هر شماره‌یِ ذخیره‌شده (09… یا +98… یا 98…) → «+98912…» برایِ نمایش. خالی/نامعتبر → None."""
    if not phone:
        return None
    return to_e164_iran(phone)


def mask_phone(phone: str | None) -> str:
    """نسخه‌یِ ماسک‌شده برایِ لاگ/ممیزی (بدونِ شماره‌یِ کامل): «+98912***67»."""
    shown = format_phone_display(phone)
    if not shown:
        return "—"
    return shown[:6] + "***" + shown[-2:]


def normalize_telegram_username(raw: str | None) -> str | None:
    """«@Ali_shop» / «ali_shop» / «https://t.me/ali_shop» → «ali_shop» (بدونِ @). نامعتبر → None.
    قاعده‌یِ تلگرام: با حرف شروع می‌شه، فقط حرفِ لاتین/رقم/_ ، ۵ تا ۳۲ نویسه."""
    if raw is None:
        return None
    text = raw.strip()
    for prefix in ("https://t.me/", "http://t.me/", "https://telegram.me/", "t.me/", "telegram.me/"):
        if text.lower().startswith(prefix):
            text = text[len(prefix):]
            break
    text = text.lstrip("@").split("?")[0].strip("/")
    return text if _USERNAME_RE.match(text) else None


def validate_person_name(raw: str | None) -> tuple[str | None, str | None]:
    """اعتبارسنجیِ نرمِ نامِ کوچک/نامِ خانوادگی → (نامِ تمیز, None) یا (None, کدِ خطا).
    کدِ خطا: «length» (۲..۳۰ نویسه نیست) یا «chars» (رقم/لینک/@ داره). فاصله‌هایِ اضافه یکی می‌شن."""
    cleaned = " ".join((raw or "").split())
    if _NAME_FORBIDDEN_RE.search(cleaned):
        return None, "chars"
    if not (NAME_MIN_LENGTH <= len(cleaned) <= NAME_MAX_LENGTH):
        return None, "length"
    return cleaned, None


def split_last_word(full_name: str) -> tuple[str, str]:
    """«علی رضایی» → («علی», «رضایی»)؛ «محمد رضا نوری» → («محمد رضا», «نوری»). فقط وقتی کاربر خودش «جدا کن» بزنه."""
    parts = full_name.split()
    if len(parts) < 2:
        return full_name, ""
    return " ".join(parts[:-1]), parts[-1]


# P22: پنل حالا «۷۵۰٬۰۰۰ تومان» نشان می‌دهد؛ اگر کاربر همان را کپی و پیست کند، جداکنندهٔ
# هزارگانِ فارسی (٬) و ممیزِ فارسی (٫) هم مثلِ ویرگولِ لاتین نادیده گرفته می‌شوند.
_PRICE_CLEAN_RE = re.compile(r"[,\u060C\u066B\u066C\s]")


def parse_price_toman(raw_text: str) -> int | None:
    """
    متنِ واردشده توسط فروشگاه‌دار برای قیمت رو به عددِ صحیح تبدیل می‌کنه.
    جداکننده‌های هزارگان (کاما یا ممیزِ فارسی) و فاصله‌ها رو نادیده می‌گیره.
    اگه عدد نبود یا صفر/منفی بود، None برمی‌گردونه.
    """
    cleaned = _PRICE_CLEAN_RE.sub("", raw_text.strip())
    if not cleaned.isdecimal():  # نه isdigit(): «²/①» int() رو می‌ترکونه
        return None

    value = int(cleaned)
    if value <= 0:
        return None
    return value


def parse_signed_toman_amount(raw_text: str) -> int | None:
    """
    مثلِ parse_price_toman، ولی علامت‌دار — برایِ جاهایی مثلِ استرداد/اصلاحِ
    کیف‌پول که هم مقدارِ مثبت (افزایش) هم منفی (کاهش) معنی داره. علامتِ +
    اختیاریه، - باید بیاد. صفر همیشه نامعتبره (یعنی هیچ تغییری بی‌معنیه).
    """
    cleaned = _PRICE_CLEAN_RE.sub("", raw_text.strip())
    if not cleaned:
        return None

    sign = 1
    if cleaned[0] in "+-":
        sign = -1 if cleaned[0] == "-" else 1
        cleaned = cleaned[1:]

    if not cleaned.isdecimal():  # نه isdigit(): «²/①» int() رو می‌ترکونه
        return None

    value = int(cleaned) * sign
    if value == 0:
        return None
    return value


def parse_nonneg_int(raw_text: str | None, allow_zero: bool = True, max_value: int = 1_000_000_000) -> int | None:
    """عددِ صحیحِ غیرمنفی از ورودیِ تایپی (ارقامِ فارسی/عربی/ASCII؛ جداکننده‌یِ هزارگان و فاصله نادیده).
    نه isdigit() — «²/①» int() رو می‌ترکونه. نامعتبر/منفی/بیش‌ازحد بزرگ = None؛ allow_zero=False ⇒ صفر هم None."""
    if raw_text is None:
        return None
    cleaned = _PRICE_CLEAN_RE.sub("", raw_text.strip())
    if not cleaned or not cleaned.isdecimal():
        return None
    value = int(cleaned)
    if value > max_value or (value == 0 and not allow_zero):
        return None
    return value


RECIPIENT_NAME_MAX_LENGTH = 60
POSTAL_CODE_LENGTH = 10
ADDRESS_MIN_LENGTH = 8
ADDRESS_MAX_LENGTH = 400
PLACE_MIN_LENGTH = 2
PLACE_MAX_LENGTH = 40


def clean_person_name(raw: str | None) -> str | None:
    """نامِ تحویل‌گیرنده (۲..۶۰ نویسه؛ بدونِ رقم/لینک/@). نامعتبر → None. (W5/C3)"""
    cleaned = " ".join((raw or "").split())
    if _NAME_FORBIDDEN_RE.search(cleaned):
        return None
    if not (NAME_MIN_LENGTH <= len(cleaned) <= RECIPIENT_NAME_MAX_LENGTH):
        return None
    return cleaned


def is_valid_postal_code(raw: str | None) -> str | None:
    """کدپستیِ ۱۰رقمی (ارقامِ فارسی/عربی هم می‌پذیره، فاصله/خط‌تیره نادیده). معتبر → رشته‌یِ ASCII؛ وگرنه None.
    کدپستیِ ایران با صفر شروع نمی‌شه و رقمِ پنجمش هم صفر نیست."""
    digits = re.sub(r"[\s\-\u200c]", "", (raw or "").translate(_DIGIT_TABLE))
    if len(digits) != POSTAL_CODE_LENGTH or not (digits.isascii() and digits.isdecimal()):
        return None
    if digits[0] == "0" or digits[4] == "0":
        return None
    return digits


def clean_place_name(raw: str | None) -> str | None:
    """نامِ استان/شهر: ۲..۴۰ نویسه، بدونِ رقم/لینک/@. نامعتبر → None."""
    cleaned = " ".join((raw or "").split())
    if _NAME_FORBIDDEN_RE.search(cleaned):
        return None
    if not (PLACE_MIN_LENGTH <= len(cleaned) <= PLACE_MAX_LENGTH):
        return None
    return cleaned


def clean_address_text(raw: str | None) -> str | None:
    """متنِ آدرس: ۸..۴۰۰ نویسه، فاصله‌هایِ اضافه یکی می‌شه (خط‌شکستن حفظ). نامعتبر → None."""
    lines = [" ".join(line.split()) for line in (raw or "").splitlines()]
    cleaned = "\n".join(line for line in lines if line)
    if not (ADDRESS_MIN_LENGTH <= len(cleaned) <= ADDRESS_MAX_LENGTH):
        return None
    return cleaned


def parse_positive_int_text(raw: str | None, low: int, high: int) -> int | None:
    """عددِ صحیحِ مثبت با ارقامِ فارسی/عربی و جداکننده‌یِ هزارگان، در بازه‌یِ [low, high]؛ وگرنه None. (W5 · ادمین)"""
    cleaned = re.sub(r"[,\s٬،]", "", (raw or "").translate(_DIGIT_TABLE))
    if not cleaned or len(cleaned) > 14 or not (cleaned.isascii() and cleaned.isdecimal()):
        return None
    value = int(cleaned)
    return value if low <= value <= high else None
