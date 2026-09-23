from __future__ import annotations

import re

_IRAN_MOBILE_RE = re.compile(r"^09\d{9}$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def format_toman(amount: int) -> str:
    return f"{amount:,} تومان"


def is_valid_email(email: str) -> bool:
    return bool(_EMAIL_RE.match(email.strip()))


def normalize_iran_phone(raw_phone: str) -> str | None:
    """
    شماره‌ی موبایل ایرانی رو به فرمتِ استانداردِ 09XXXXXXXXX نرمالایز می‌کنه.
    فرمت‌های ورودیِ قابل‌قبول: 09123456789، +989123456789، 00989123456789،
    9123456789 (بدونِ صفر ابتدایی). اگه شماره معتبر نبود، None برمی‌گردونه.
    """
    digits = re.sub(r"\D", "", raw_phone.strip())

    if digits.startswith("0098"):
        digits = digits[4:]
    elif digits.startswith("98"):
        digits = digits[2:]

    if digits.startswith("9") and len(digits) == 10:
        digits = "0" + digits

    if _IRAN_MOBILE_RE.match(digits):
        return digits
    return None


_PRICE_CLEAN_RE = re.compile(r"[,\u060C\s]")


def parse_price_toman(raw_text: str) -> int | None:
    """
    متنِ واردشده توسط فروشگاه‌دار برای قیمت رو به عددِ صحیح تبدیل می‌کنه.
    جداکننده‌های هزارگان (کاما یا ممیزِ فارسی) و فاصله‌ها رو نادیده می‌گیره.
    اگه عدد نبود یا صفر/منفی بود، None برمی‌گردونه.
    """
    cleaned = _PRICE_CLEAN_RE.sub("", raw_text.strip())
    if not cleaned.isdigit():
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

    if not cleaned.isdigit():
        return None

    value = int(cleaned) * sign
    if value == 0:
        return None
    return value
