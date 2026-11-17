"""
نمایشِ هویتِ کاربر (H2): «نام (@یوزرنیم) · شماره» — هرگز آیدیِ عددیِ تلگرام.

تنها تابعی که متنِ هویت می‌سازه؛ همه‌یِ اعلان‌ها/فهرست‌ها/گزارش‌ها باید از همین بگیرن (قاعده‌یِ طلاییِ ۴ و ۱۱).
عددِ خام فقط در صفحه‌هایِ سوپرادمین که صریح اجازه دارند («📜 گزارشِ ممیزی» و خطِ فنیِ پرونده) مجاز است و از این‌جا رد نمی‌شه.

ورودی: ShopOwner / Customer (هر آبجکتی با first_name/last_name/username/phone_number)، dict، یا تاپلِ
(first_name, last_name, username, phone_number). شماره‌یِ ذخیره‌شده با 09… یا +98… هر دو پذیرفته می‌شه و
همیشه به‌شکلِ +98… نمایش داده می‌شه.
"""
from __future__ import annotations

from typing import Any

from app.utils.validators import format_phone_display, mask_phone

NO_USERNAME_SUFFIX = "(بدونِ یوزرنیم)"
UNKNOWN_USER_LABEL = "کاربرِ بی‌نام"

STYLE_SHORT = "short"
STYLE_FULL = "full"
STYLE_MENTION = "mention"


def _clean(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _coerce(obj: Any) -> tuple[str, str, str, str]:
    """→ (first_name, last_name, username بدونِ @، شماره‌یِ خام) با رشته‌هایِ تمیز (خالی = ندارد)."""
    if isinstance(obj, dict):
        first, last, username, phone = (obj.get(k) for k in ("first_name", "last_name", "username", "phone_number"))
    elif isinstance(obj, (tuple, list)):
        padded = list(obj) + [None] * (4 - len(obj))
        first, last, username, phone = padded[:4]
    else:
        first, last, username, phone = (getattr(obj, k, None) for k in ("first_name", "last_name", "username", "phone_number"))
    return _clean(first), _clean(last), _clean(username).lstrip("@"), _clean(phone)


def display_name(obj: Any) -> str:
    """فقط «نام نام‌خانوادگی»؛ اگه نامی نبود @یوزرنیم، وگرنه «کاربرِ بی‌نام»."""
    first, last, username, _phone = _coerce(obj)
    name = f"{first} {last}".strip()
    if name:
        return name
    return f"@{username}" if username else UNKNOWN_USER_LABEL


def display_user(obj: Any, style: str = STYLE_SHORT):
    """
    - short:  «نام (@u)»؛ بدونِ یوزرنیم ولی با شماره «نام · +98…»؛ بدونِ هر دو «نام (بدونِ یوزرنیم)»
    - full:   «نام (@u) · +98…» (شماره اگه باشه)
    - mention: تاپلِ (متن, entities) با لینکِ text_mention به‌سمتِ کاربر (نیازمندِ telegram_id؛ بهترین‌تلاش)
    """
    if style == STYLE_MENTION:
        return mention_user(obj)

    first, last, username, phone_raw = _coerce(obj)
    name = f"{first} {last}".strip()
    phone = format_phone_display(phone_raw)

    if not name:
        # نامی نداریم: یوزرنیم (یا شماره) خودش هویته؛ «@u (@u)» نمی‌سازیم
        if username:
            return f"@{username}" + (f" · {phone}" if phone and style == STYLE_FULL else "")
        if phone:
            return phone
        return UNKNOWN_USER_LABEL

    if username:
        base = f"{name} (@{username})"
        if style == STYLE_FULL and phone:
            return f"{base} · {phone}"
        return base

    if phone:
        return f"{name} · {phone}"
    return f"{name} {NO_USERNAME_SUFFIX}"


def _utf16_len(text: str) -> int:
    """تلگرام offset/length ِ entityها رو بر حسبِ واحدهایِ UTF-16 می‌خونه (ایموجی = ۲ واحد)."""
    return len(text.encode("utf-16-le")) // 2


def mention_user(obj: Any):
    """(متنِ full, [MessageEntity text_mention]) — اگه telegram_id نبود entity خالیه. aiogram فقط همین‌جا ایمپورت می‌شه."""
    text = display_user(obj, STYLE_FULL)
    if isinstance(obj, dict):
        telegram_id = obj.get("telegram_id")
    elif isinstance(obj, (tuple, list)):
        telegram_id = None
    else:
        telegram_id = getattr(obj, "telegram_id", None)
    if not telegram_id:
        return text, []
    from aiogram.types import MessageEntity, User  # noqa: PLC0415

    name_part = display_name(obj)
    entity = MessageEntity(
        type="text_mention",
        offset=0,
        length=_utf16_len(name_part),
        user=User(id=int(telegram_id), is_bot=False, first_name=name_part),
    )
    return text, [entity]


def sync_from_telegram_user(target: Any, tg_user: Any, *, with_last_name: bool = False) -> bool:
    """
    یوزرنیم (و برایِ مشتری نامِ‌خانوادگی) رو از آبجکتِ کاربرِ تلگرام تازه می‌کنه، **فقط وقتی عوض شده**.
    True = چیزی عوض شد (فراخوان می‌تونه flush کنه). اگه کاربر یوزرنیمش رو برداشته، None ثبت می‌شه.
    """
    if tg_user is None:
        return False
    changed = False
    new_username = getattr(tg_user, "username", None) or None
    if getattr(target, "username", None) != new_username:
        target.username = new_username
        changed = True
    if with_last_name:
        new_last = getattr(tg_user, "last_name", None) or None
        if new_last is not None and getattr(target, "last_name", None) != new_last:
            target.last_name = new_last
            changed = True
    return changed


__all__ = [
    "NO_USERNAME_SUFFIX",
    "UNKNOWN_USER_LABEL",
    "STYLE_SHORT",
    "STYLE_FULL",
    "STYLE_MENTION",
    "display_name",
    "display_user",
    "mention_user",
    "sync_from_telegram_user",
    "mask_phone",
]
